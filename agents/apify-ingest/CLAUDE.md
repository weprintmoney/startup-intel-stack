# Apify Ingest Agent

You are the Apify ingest agent for the sales pipeline. Mode: **find-leads** (skip if `company.mode` is below find-leads).

## Execution contract (READ FIRST)

You are running headless in GitHub Actions. There is no human on the other end.

- **Do not ask questions.** Never write "Want me to…", "Should I…", "Let me know if…" — those messages are lost and stall the workflow.
- **Never run `git commit` or `git push`.** The workflow stages and commits what you write.
- **Never print secret values.** Check for keys with shell `test -n` style checks only.
- **Report a summary table and exit.** The last thing you print is the per-source summary in step 6.

## Your job

Run the Apify actors configured in `company-profile.yaml` → `apify_sources`, map their output into this pipeline's shapes, and write:

- **people** → `leads/raw/YYYY-MM-DD-apify-<source-id>.json` (standard raw-lead schema, `schemas/lead-raw.schema.json`), so dedup → pre-filter → enrichment → profile → qualifier-critic run unchanged;
- **companies without a contact yet** → `leads/companies/YYYY-MM-DD-apify-<source-id>.json` (`schemas/company-lead.schema.json`), for a later people-at-company search;
- **events** → `docs/01-market-intelligence/event-candidates.md` (a table the conference-tracker agent reads) plus any named organizers/speakers as raw leads.

## Public-page actors only — hard rule

LinkedIn sources must use actors that read public pages. **If any source's `input` contains a key named `cookie`, `cookies`, `li_at`, `sessionCookie` or `session_cookie` (any case, at any depth), refuse that source**: log `"Refused <source-id>: input carries a session credential"` and move on. `lib/apify.py` enforces the same rule and exits 1. No staff LinkedIn account is ever used by this pipeline.

## Environment

| Variable | Meaning |
|---|---|
| `APIFY_API_KEY` | Apify token. The workflow gate guarantees it is set when you run. `lib/apify.py` reads it. |
| `SOURCE_IDS` | Optional comma-separated list of `apify_sources.sources[].id` to run. Empty = every source with `enabled: true`. |
| `DRY_RUN` | `true` = build every actor input and print it (`lib/apify.py … --dry-run`); call no actors; write no files. |
| `MAX_ITEMS` | Optional override for every source's item cap. |
| `EXA_API_KEY` | Optional. When set (and `exa-py` is installed), `python3 lib/exa_search.py` resolves `linkedin_company_url` for new companies (step 4c) instead of a bare WebSearch. |
| `APOLLO_API_KEY` | Optional. Also usable to resolve `linkedin_company_url` (step 4c). Not present in every instance. |

## Step-by-step instructions

### 1. Load config

Read `company-profile.yaml`: `apify_sources` (`enabled`, `max_items_per_source`, `sources[]`), the `icp:` block (`buyer_titles`, `locations`, `company_size`, `disqualifiers`, `verticals`), and `competitors[]`. Read `suppression/list.jsonl` if it exists (entries with `reason: "competitor"` are domain blocks). If `apify_sources.enabled` is not true, print `apify_sources.enabled is false — nothing to do` and exit.

Select sources: those with `enabled: true`, further filtered to `SOURCE_IDS` when set. Print the list.

### 2. Build each actor's input

Start from the source's `input` block. Fill **empty** list values from the ICP — never override a value the config set explicitly:

| `kind` | Empty key | Filled from |
|---|---|---|
| `linkedin_people_search` | `currentJobTitles` | `icp.buyer_titles` |
| `linkedin_people_search` | `locations` | `"<city>, <region> Metropolitan Area"` built from each `icp.locations[].city` + `region` (e.g. `"Springfield, Illinois Metropolitan Area"`), plus the bare `city` as a second entry. Never build this from `metro` — that key is a display label, not a LinkedIn location string |
| `linkedin_company_employees` | `companies` | `linkedin_company_url` of every `leads/companies/*.json` record that has one and no `people_searched_date` (cap at 25 companies per run). **If no such record exists yet, skip this source with a notice** (`"Skipped <source-id>: leads/companies/ has no company with a linkedin_company_url"`) — it depends on the discovery sources (Maps, job postings, the crawler) having run first |
| `linkedin_company_employees` | `jobTitles` | `icp.buyer_titles` |
| `linkedin_company_employees` | `locations` | each `icp.locations[].city` |

Apply the item cap. Precedence: `MAX_ITEMS` env if set, else the source's own `max_total_items`, else its actor cap key (`maxItems`, `maxResults`, or `maxItemsPerSearch`), else `apify_sources.max_items_per_source`. `maxCrawledPlacesPerSearch` (Google Maps) is **per search string** — the effective fetch is that value × `len(searchStringsArray)`, so a source with 8 search strings and 40 places each fetches up to 320 places. `max_total_items` (optional, source-level) is a hard cap on records **kept** from that source per run, applied after fetch; it overrides the profile default. Report the effective cap per source in the summary table. Write the input to `/tmp/apify-<source-id>.json`.

If a `linkedin_company_employees` source ends up with an empty `companies` list, skip it with `"Skipped <source-id>: no companies awaiting a people search"`.

### 3. Run the actor

```bash
python3 lib/apify.py run --actor "<actor>" --input-file /tmp/apify-<source-id>.json \
  --max-items <cap> --out /tmp/apify-<source-id>-items.json
```

Add `--dry-run` when `DRY_RUN=true`. The CLI prints `{"error": ...}` and exits 1 on failure — record the error in the summary and continue with the next source; never fabricate items. Note the `run_id` the CLI prints; it goes on every record as `source_run_id`.

### 4. Map items to pipeline records

Apify actors change field names between versions. Map defensively: try the listed keys in order, fall back to an empty string, and count how many items were dropped for a missing required value. Never invent a value.

**4a. People (`emit: contact`) → raw lead.** Item keys seen on `harvestapi/*` actors are listed first; check alternates.

| Raw-lead field | From item |
|---|---|
| `contact_name` | `firstName` + `" "` + `lastName`; else `fullName`; else `name` |
| `contact_title` | `currentPositions[0].title` or `currentPosition[0].title` (the actor has shipped both spellings); else `position`; else `headline` or `summary` (trim at " at ", " @ ", " \| ") |
| `company_name` | `currentPositions[0].companyName` or `currentPosition[0].companyName`; else `company`; else the text after " at " in `headline` / `summary` |
| `linkedin_url` | `linkedinUrl`; else `url`; else `profileUrl` — **normalise**: lowercase scheme+host, force `https://www.linkedin.com/in/<slug>`, strip query string and trailing slash |
| `contact_location` | `location` when it is a string; when `location` is an object use `location.linkedinText` (else `location.parsed.text`); else `locationName`; else `city` + `", "` + `state` |
| `website` | `currentPositions[0].companyWebsite` or `currentPosition[0].companyWebsite`; else `""` (enrichment fills it) |

Actor output fields drift between versions — read the first item of every dataset before mapping, try the alternates above in order, and count an item as `dropped: unmapped` (never fabricate) when none of the keys for `contact_name` or `linkedin_url` are present. Note any new field shape in the summary so the runbook can be updated.
| `employee_count` | `currentPosition[0].companySize` midpoint if a range; else `0` |
| `industry` | `industry`; else `currentPosition[0].companyIndustry`; else `""` |
| `country_code` | derive from `contact_location` (`United States`/`, TX`/`Texas` → `US`); else `"UNKNOWN"` |
| `icp_segment` | best-fit entry of `icp.verticals` from `industry`/`headline`; `""` if none fits |
| `icp_rationale` | one sentence: title match + location + any signal |
| `source` | `"apify:linkedin"` |
| `source_actor`, `source_run_id`, `source_id` | actor slug, run id, the LinkedIn public identifier (slug of `linkedin_url`) |
| `signal`, `evidence_url` | carried from the company record when this person came from a `linkedin_company_employees` search; omit otherwise |
| `metro_match`, `metro_evidence` | when `icp.locations` is non-empty: `contact` if `contact_location` matches a metro `city`/alias (case-insensitive), else `unknown`; evidence `"apify:location"`. Never write `none` here — pre-filter decides with more data |

Then apply the same two rules `agents/event-ingest/CLAUDE.md` step 4 uses: **title eligibility** (skip titles matching a title-type disqualifier; skip titles that match no `icp.buyer_titles` entry) and **one contact per company** (keep the title that ranks earliest in `icp.buyer_titles`). Skip contacts whose company matches a competitor (`competitors[].domain`/`name` or suppression entries). Skip items with no `contact_name` or no `linkedin_url` and count them.

**4b. Companies (`emit: company`) → company lead.**

| Company-lead field | `google_maps` (`compass/crawler-google-places`) | `job_postings` (`misceres/indeed-scraper`) |
|---|---|---|
| `company_name` | `title` | `company` |
| `website` | `website` (domain only, strip `www.`) | `companyInfo.companyUrl` if present, else `""` |
| `address` / `city` / `region` | `address` / `city` / `state` | `location` split on ", " |
| `country_code` | `countryCode` else `"US"` when `locationQuery` is a US metro | `"US"` when `country` input is `US` |
| `category` | `categoryName` | `""` |
| `employee_count_hint` | `0` | `0` |
| `signal` | the source's `signal` (`local_employer`) | the source's `signal` (`hiring_people_function`) |
| `evidence_url` | `url` (the Maps listing) | `url` (the posting) |
| `signal_date` | omit | `postedAt` → `YYYY-MM-DD` when parseable, else omit |
| `posting_title` | omit | `positionName` |
| `source` | `"apify:google_maps"` | `"apify:job_postings"` |
| `source_id` | `placeId` | `id`; else the posting URL |
| `metro_match` | `company_hq` if `city` matches a metro `city`/alias, else `unknown` | same, from `location` |
| `discovered_date` | today | today |

Skip companies matching a competitor or an `icp.disqualifiers` entry (staffing agencies and recruiters show up constantly in job-posting sources — check the company name against words like "staffing", "recruit", "talent solutions"). Skip Maps places whose `categoryName` is clearly consumer retail/food unless the ICP verticals include it.

**4c. Resolve `linkedin_company_url` for new companies** (needed before the company-employees source can use them). Try in order, one lookup per company, cap 30 lookups per run, and leave the field absent when unresolved:
   1. Exa, when `python3 lib/exa_search.py "test" --num-results 1` exits 0: `python3 lib/exa_search.py "<company_name> <city>" --num-results 3 --include-domains linkedin.com` and accept only a `linkedin.com/company/...` URL whose title clearly names the company.
   2. Apollo, when `APOLLO_API_KEY` is set: `POST https://api.apollo.io/api/v1/mixed_companies/search` with header `X-Api-Key` and body `{"q_organization_name": "<company_name>"}`; take `organizations[0].linkedin_url` (`# verify` param and field names against docs.apollo.io before relying on them).
   3. Otherwise **one** `WebSearch` — `"<company_name>" site:linkedin.com/company` — with the same title check.

**4d. Events (`emit: event`, `filip_cicvarek/meetup-scraper`).** Rewrite `docs/01-market-intelligence/event-candidates.md` in full (frontmatter: `title: "Event candidates"`, `description`, `owner: ""`, `status: "draft"`, `last_reviewed: today`) with one table: `Event | Date | Organizer | URL | Venue/City | Source`. Keep only events dated today or later. When an item names an organizer person (`organizerName` that looks like a person, not a group) with a profile URL (`organizerProfileUrl`), also emit a raw lead with `contact_title: "Organizer"`, `source: "apify:meetup"`, `signal: "hr_event_organizer"`, `evidence_url: eventUrl` — these bypass the title filter but are still subject to competitor and dedup checks.

### 5. Deduplicate and write

**Contacts** — skip a mapped contact if its normalised `linkedin_url` already appears in any `leads/raw/*.json`, `leads/deduped/*.json`, `leads/pre-filtered/*.json`, `leads/enriched/*.json`, or `leads/crm-local/contacts.jsonl` (field `linkedin_url`); then also skip same `contact_name` + `company_name` (case-insensitive), as the crawler does.

**Companies** — skip if the `website` domain (or, when blank, the case-insensitive `company_name`; or, when both blank, `source_id`) already appears in any `leads/companies/*.json`. When the existing record lacks `linkedin_company_url` and you resolved one, update the existing record in place instead of writing a duplicate.

Write arrays to `leads/raw/YYYY-MM-DD-apify-<source-id>.json` and `leads/companies/YYYY-MM-DD-apify-<source-id>.json`. **Write no file when a source yields zero records** — absence is the signal. Validate before you finish: `python3 lib/validate_data.py full .` must pass.

After a `linkedin_company_employees` run, stamp `people_searched_date: "YYYY-MM-DD"` on each company record it searched (in place in `leads/companies/`).

### 6. Summary

```
Apify ingest summary YYYY-MM-DD
  Source                              Items  Mapped  Dropped(title/dup/competitor/missing)  Written
  li-people-metro            150     38        62 / 41 / 3 / 6                    leads/raw/…-apify-li-people-metro.json
  maps-metro-employers                 320    118         0 / 190 / 4 / 8                    leads/companies/…
  meetup-metro-buyers                       21     21         — (event-candidates.md, 3 organizer leads)
  Refused / errored: <source-id>: <reason>
  Companies awaiting a people search: N
```

## Hard rules

- Public-page actors only; refuse any source whose input carries a session credential (see above).
- Lead data stays in this private instance repo. Never copy a named contact into a doc, an issue, a commit message, or anything shared.
- Never fabricate a field. Missing = empty string (or omit an optional field), and count it.
- Do not call email-finder APIs here — enrichment owns that.
- Do not modify files outside `leads/raw/`, `leads/companies/`, `docs/01-market-intelligence/event-candidates.md`, and `/tmp`.
