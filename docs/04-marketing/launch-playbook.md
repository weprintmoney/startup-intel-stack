---
title: "Launch Playbook"
description: "Reusable step-by-step playbook for any public launch — product, feature, benchmark, case study, or SDK release. Anyone on the team can run it."
owner: ""
status: "draft"
last_reviewed: ""
---

# Launch Playbook

How to run a public launch. This doc is generic and reusable — every launch (product debut, feature, benchmark, case study, SDK release) gets its own short **launch plan** file next to this one that fills in the parameters (date, hook, owners, metrics) and links back to the steps here.

**Operating principles:**

1. A launch is won or lost in preparation. Launch day should be ~10% of the total work.
2. All launches are organic — no paid placements, no agencies. Your currency is early access and a genuinely novel story.
3. Define the conversion target before anything else: visitor → signup → **activated** (first successful use). Optimize every asset for activation, not views.
4. Every public number passes claims vetting ([`content-ops/reference/claims-vetted.md`](content-ops/reference/claims-vetted.md)) before it appears in any asset. One debunked claim poisons the whole launch.
5. You don't get one launch. Every feature, benchmark, and integration is a launch, and each one compounds the audience the last one built.

## Roles — assign these by name in the launch plan, week 1

At an early-stage company, one person often holds several roles — but every role needs a named owner. Draw names from `people:` in `company-profile.yaml`.

| Role | Responsibility |
|---|---|
| **Launch owner** | Runs this playbook end to end; owns the timeline, the tracking sheet, the go/no-go call |
| **Technical owner** | Quickstart/product readiness, technical claims review, benchmark reproducibility |
| **Poster** | Posts the Show HN and is the named voice in comments — must be a technical founder or senior engineer |
| **Comment rotation** | 2–3 engineers scheduled (in sprint planning, not ad hoc) to answer HN/X technical questions on launch day |
| **Infra owner** | Load test, CDN, rate limits, on-call for the traffic spike |
| **Approver** | Signs off on the PR/FAQ, public claims, date, and anything on the public site (usually the CEO/founder) |

## Timeline at a glance

| Week | Work |
|---|---|
| T-5 | Launch plan written + approved. Date locked. Roles assigned. Step 1 (product gate) scoped into sprint. PR/FAQ drafted. |
| T-4 | PR/FAQ signed off. Video scripted. Supporter list built. First runway content published. |
| T-3 | Video recorded + cut. Amplifier outreach begins. Product gate test round 1. |
| T-2 | Supporter asks sent + calendar invites out. Hooks written and culled. Thread + Show HN drafted. |
| T-1 | Amplifier early access + packets. Product gate round 2 → **go/no-go**. Load test. Newsletter drafted. Full dry run Friday. |
| T-0 | Launch (Step 7 run of show). |
| T+1 | 48-hour follow-up. Funnel review. Retro. Schedule the next launch. |

---

## Step 1 — Product gate: the first 30 and 60 seconds

A launch sends thousands of skeptical strangers to the product at once. They decide in 30 seconds whether to care and 60 seconds whether to try. Nothing else in this playbook matters if this step fails.

Three surfaces, in the order strangers hit them:

1. **Landing page (first 10 seconds).** Must answer "what is this and why should I care" above the fold: one-liner, copy-pasteable install command, 30-second visual. Pricing visible, free tier obvious. Any public-site change goes to the Approver early — not launch week.
2. **Quickstart (60 seconds → 15 minutes).** One install command → first successful use, copy-paste only, zero configuration decisions required. Advanced options are a separate "advanced" path, never the default.
3. **The "aha" (the moment they screenshot).** Identify the single demonstrable thing only you can show, and make it the quickstart's final step and the video's centerpiece.

**The gate — run this exactly:**

1. Recruit 5 developers who have never used the product (not employees, not existing customers).
2. Send them only the landing page URL. No coaching, no docs links.
3. Watch each one (screen share) and time two checkpoints: (a) can they say why the product exists within 60 seconds of landing, (b) first successful use in under 15 minutes.
4. Log every stumble in the friction log. Fix. Re-test with fresh people at T-1.
5. **Pass = 5/5 on both checkpoints.** Anything less blocks the launch (see go/no-go, Step 7).

## Step 2 — PR/FAQ: the source of truth

Write a one-page press release + FAQ **before any other asset**. Everything downstream — video script, thread, HN post, supporter packet, newsletter — is derived from it. If this page can't be written crisply, the launch isn't ready; the confusion is about the product, not the marketing.

**The one page must contain:**
- What you're launching, in one sentence.
- The problem, **in the customer's words** (pull real quotes from account calls — not your positioning language).
- Who it's for (the ICP segments it serves).
- What it costs, including the free tier.
- How it works (3–5 plain-language bullets).
- Proof: vetted benchmark numbers, named customers (per-piece approval required — see Step 4), partner validations.

**The FAQ:** write the hostile questions first — the ones HN will ask within 20 minutes. For every launch, include: "how is this different from [obvious incumbent]," "what are the limitations," "what's the license," "why should I trust the claims." Answer honestly; an explicit "what this does NOT do" section earns more trust than any claim. Vagueness on a technical question is fatal.

**Process:** Launch owner drafts (the raw material is in [`../01-market-intelligence/`](../01-market-intelligence/CLAUDE.md)). Technical owner reviews every claim against claims-vetted. Approver signs. This page is also exactly what goes to any journalist.

## Step 3 — The video

**Decide the outcome first:** it's always signups/activation, not brand awareness. A video without a decided outcome optimizes for nothing.

**Format rules:**
- Plain screen recording, terminal-first, under 2 minutes. No high production — if viewers discuss the video instead of the product, you lost.
- First 3 seconds: show the product or state the problem. No logo animation, no intro, no "hey everyone."
- Do not lead with "AI" or a category label. Lead with the problem and the outcome that sounds impossible.

**Script skeleton (adapt per launch):**
- 0:00–0:03 — cold open on the pain, visually.
- 0:03–0:20 — the problem, concretely.
- 0:20–1:10 — the demo, ending on the "aha" from Step 1.
- 1:10–1:40 — the counterintuitive proof point (benchmark chart or number).
- 1:40–2:00 — who it's for (one line), free tier, clean URL.

**Deliverables:** 2-min master, 45-second cut for the launch tweet (uploaded natively to X — never a YouTube link in tweet 1), 30-second vertical cut for LinkedIn.

## Step 4 — Pick the day and recruit the fifty

**The day:** Tuesday, 9:00 AM ET. US developer audience is awake and idle. Before locking: check the industry-news calendar for that week (major conferences, expected big releases) and pre-agree a backup Tuesday. Never launch into a known collision.

**The fifty:** the first hour decides whether reach expands or decays — algorithms reward early velocity, and early velocity comes from people recruited in advance. Recruit **≥50 committed people** to engage within 30 minutes of the post.

Do this exactly:

1. Create a tracking sheet with columns: name, bucket, channel (X/LinkedIn), who asks, asked date, committed Y/N, calendar invite sent Y/N, engaged on day Y/N.
2. Fill buckets: team + their personal networks (everyone at the company), investors (Approver asks), customer/design-partner engineers (the individuals who use the product, not the logos), partner-company contacts, friendly founders/VCs, personal networks.
3. Send the ask at **T-2 weeks**, personally, one at a time:

   > Subject: Imp! [Product] launch — [date]
   >
   > Hi [name],
   >
   > We've been building [product] quietly for [period] — it's in production at [N] companies, and we're doing a real public launch.
   >
   > On **[day, date] at 9am ET** we're posting the launch on X and Hacker News. If you'd be willing to repost / quote-tweet / comment with your honest take in the first half hour, it genuinely makes the difference — early engagement decides whether the algorithm shows it to anyone.
   >
   > If you're in, I'll send a 15-min calendar invite as a reminder, plus the link the moment we're live. Want early access before then? I'll set you up this week.
   >
   > Thanks,
   > [name]

4. **Everyone who says yes gets a calendar invite** for launch time (this is half the trick — people are willing, just busy).
5. On launch day, DM each one the direct link individually (Step 7). Not a broadcast.

**Customer naming:** any customer or partner named in any asset needs per-piece written approval. Start these asks at T-4 — they are always the longest external dependency.

## Step 5 — Recruit external amplifiers (organic)

No payments, no agency. The offer is early access + a story worth writing about.

1. Build a list of ~40 target accounts in the tracking sheet: X accounts in your niche (10K+ followers, consistent posting, real per-post reach), category commentators, newsletter authors, YouTubers, active-posting founders/VCs. Expect ~10–15 yeses.
2. DM/email each with one line on **why this is their kind of story**, plus the early-access offer. Personal, not templated-sounding.
3. Give committed amplifiers product access **one week before launch**. Specific posts beat generic ones, and specificity only comes from actually using it.
4. Send the amplifier packet: the one-page PR, the 45s video, the key chart, 3–4 suggested angles, and — most effective — **screenshots of quote-posts that performed well in comparable launches**, with "something like this, in your voice." People write badly from instructions and well from examples.
5. Say explicitly: "we want your honest take, including criticisms." Readers smell coordinated copy instantly; one honest "the setup was rough but X blew my mind" outperforms ten pasted taglines.
6. Launch morning: individual DMs with the live link.

**Compliance:** everything within platform rules. Anything sponsored gets a sponsored tag (you have nothing sponsored). You coordinate genuine supporters; you never buy engagement.

## Step 6 — The thread and the Show HN

Both go live at the same minute. X drives reach; HN drives your actual buyers.

### The hook (do not skip this process)

1. Pull up the 20 biggest launches in your category from the past year. Read only their first lines. Note the patterns: an impossible-sounding claim, a number, a villain, a before/after.
2. Write 20 hooks. Kill 19. Grounded in vetted claims only.
3. The survivor must be at least one of: **emotional** (reader feels the pain), **divisive** (takes a side), or a **hot take** (says what people believe but won't post). If nobody could disagree with it, nobody will reply to it — and replies are fuel.

### The X thread

- **T1:** hook + 45s native video + clean short URL (it will be retyped from memory off someone's phone — no UTM soup visible).
- **T2:** the problem, concretely — the moment the ICP recognizes from their own life.
- **T3:** how it works, 4 lines max, one image.
- **T4:** the proof chart. Let the image carry it.
- **T5:** named customers/partners (approved per-piece only).
- **T6:** pricing — free tier front and center, time-to-first-use claim.
- **T7:** CTA + explicit ask to RT.

### The Show HN

- **Title:** plain and factual — "Show HN: [Product] – [what it literally does]". HN punishes hype. Draft 5 variants; Poster and Approver pick.
- **Poster:** technical founder or senior engineer. Never a marketing-adjacent account.
- **First comment, pre-written, posted immediately:** why you built it, how it actually works, the threat/limitation model **including what it doesn't do**, methodology links, what feedback you want. The FAQ's hostile questions are the prep. Humility + depth wins HN; evasiveness dies.
- **Comment rotation:** scheduled engineers answer every substantive technical question within the hour, all day. Tone: "great question — here's exactly the tradeoff and why we accept it."
- **Hard rules:** never send anyone a direct link to the HN post. Never ask for upvotes. HN detects voting rings and buries the post. Supporters get told "we're on HN today" and find it from the front page. Authentic comments from real users describing real usage are legitimate and gold.

### LinkedIn (secondary)

Approver/CEO posts a founder-voice version; the team reshares. Same minute as the others.

## Step 7 — Launch day

**Infra readiness — complete by T-1, not launch week:**
- [ ] Named infra owner confirmed
- [ ] Signup path load-tested (assume a front-page HN post = 10–50K visitors in hours)
- [ ] Rate limits on free-tier provisioning
- [ ] Docs behind CDN
- [ ] At least 2 people hold operational access to DNS/CDN/prod accounts (no single-person bus factor on launch day)
- [ ] On-call rotation named for launch week; zero feature work scheduled

**Run of show (launch = 9:00 ET; convert to your `hq_timezone`):**

| Time (ET) | Action | Who |
|---|---|---|
| 8:00 | Final checks: site, signup flow end-to-end, quickstart green on a fresh machine | Infra owner |
| 8:55 | Thread, video, Show HN, first HN comment all staged | Launch owner + Poster |
| 9:00 | Everything live: thread, Show HN + first comment, LinkedIn | Poster + Launch owner |
| 9:00–9:15 | Individual DMs to all fifty + amplifiers with the X link (never the HN link) | Split across team |
| 9:05 | Newsletter sends (Step 8) | Launch owner |
| 9:00–13:00 | Comment rotation on HN; reply to every substantive X reply; repost every quote-tweet | Rotation + Launch owner |
| 13:00 | Midday read: which angle is landing? Quote-tweet it, screenshot it into the thread, double down | Launch owner |
| 13:00–18:00 | Continue; sales-inbox triage — every "how do I get this for my company" answered same day | Launch owner + Sales |
| 18:00 | Hand evening monitoring (HN threads run 12+ hours) to a named engineer | Rotation |

**Go/no-go gate (decided at T-1 week, by the Launch owner):** slip to the backup date if ANY of:
- Product gate (Step 1) not passing 5/5
- Any public claim not fully vetted
- PR/FAQ not signed by the Approver
- Infra owner not confident in spike readiness

A one-week slip costs nothing. A botched debut costs the story.

## Step 8 — The newsletter

Email is the only channel with no algorithm between you and the audience.

- **Pre-launch:** every runway content piece ends with a newsletter CTA. Grow the list before you need it.
- **Launch morning:** short email = the one-page PR + the launch-thread link + one explicit ask: "if this is useful to you, engaging with the launch post in the next hour genuinely helps." One link, one ask, nothing else. Subscribers are the warmest audience; tell them exactly what helps.

**Content runway (T-4 → T-1):** publish 2–4 pieces that soften the ground — benchmark/methodology pages, anchor comparisons, and a pre-emptive technical post answering the hardest expected question. The launch should never be the first time the audience hears the name. Route through the content-ops pipeline ([`content-ops/CLAUDE.md`](content-ops/CLAUDE.md)).

## Step 9 — Afterward

Virality decays in 48 hours. In that window:

1. Follow up with **everyone** who engaged meaningfully: DM quote-tweeters, reply to commenters, personal thank-yous to the fifty.
2. Every signup gets an activation nudge (quickstart link + "stuck? reply to this email").
3. Sales triage: inbound sorted against ICP within 24 hours; strong-fit conversations scheduled same day.
4. New-user stumbles → friction log → engineering weekly.

**Funnel (definitions set in the launch plan, before launch):** visitor → signup → activated → week-2 retained → sales conversation. Review at T+3d and T+14d against the launch plan's targets.

**Retro at T+1 week:** what worked, what died, update this playbook. Then **schedule the next launch** — the supporter sheet, hook archive, and amplifier packet are permanent infrastructure that compound with every run.

## Mini-launch variant

For smaller moments (SDK release, single feature, one benchmark): keep Steps 2 (half-page PR), 4 (the fifty — the sheet already exists, just re-ask), 6 (single post or short thread; Show HN only if genuinely substantive), and 9. Skip the video (a GIF or screenshot suffices) and the amplifier outreach. Total prep: ~1 week, not 5.
