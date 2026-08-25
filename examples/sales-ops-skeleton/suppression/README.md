# Suppression list

`list.jsonl` is the live send blocklist. One JSON object per line:

```
{
  "email":        "string  — exact-match block (case-insensitive)",
  "domain":       "string  — block every address at this domain",
  "company_name": "string  — human label (audit only, not matched)",
  "reason":       "one of: bounced_hard | unsubscribed | complaint | competitor | internal | gdpr_request | prior_outreach",
  "added_date":   "ISO-8601 date the row was added",
  "added_by":     "string  — GitHub actor, workflow name, or human handle"
}
```

Either `email` or `domain` must be non-empty. If both are set, the domain block is authoritative.

## Who writes here

- `reply-monitor.yml` — appends `unsubscribed` rows on any reply matching an unsubscribe keyword.
- `smtp-send.yml` — appends `bounced_hard` rows on any hard bounce from the send provider.
- `deliverability-monitor.yml` — appends `complaint` rows above the complaint-rate threshold.
- Humans — append `competitor`, `internal`, `gdpr_request`, and `prior_outreach` rows by hand as they come up.

## Do not

- Do not sort or reformat the file — it's a live blocklist and merge conflicts break sends. If you must dedup, do it in a scripted job with a checksum step, not by hand.
- Do not use it as an activity log — it's a blocklist. Deleted rows silently re-open the address to sending.
