# Content Format Rules

These rules apply to every piece. Format-specific additions are at the bottom. Voice specifics live in `docs/02-brand/` — read that first; the rules below are the enforced floor.

## Universal structure

### The Lead (first 80-120 words)

- **First sentence must be a standalone thesis or a surprising fact with a specific number.** It must work as the only sentence in a tweet. Never a question. Never scene-setting. Never a definition.
- One concrete number, stat, or specific claim that is quotable on its own with no surrounding context.
- This block is what AI answer engines lift verbatim. Write it like a Wikipedia opener.
- The `aeoQuotableBlock` frontmatter field must be a verbatim copy of 1-2 sentences from this section.

### Body

- H2s are questions or declarative statements, meaningful enough to stand as their own search results.
- H3s break down the H2's claim.
- **Paragraphs: 1–3 sentences.** Never 4. Most paragraphs are 2. Long paragraphs read as AI-generated and tank both SEO and AEO.
- **Single-sentence paragraphs for emphasis** — 1–2x per post maximum, after a multi-sentence buildup. Never as a default.
- **Your product is introduced no earlier than the second H2.** The problem must be established before the solution appears.
- Define every entity the first time it appears, using the one-liner and value pillars from your positioning doc. Save your defining differentiator for the closer, not the opener, unless the piece is explicitly about it.
- At least one of: comparison table, ordered list, or definition list. LLMs cite structured content disproportionately.
- Inline citations: hyperlink the source on the specific claim, not at the end of the paragraph.

### Examples & specificity

- One concrete example per major claim. "A team running 200 concurrent queries" beats "a large organization."
- **Use real numbers when sourced. Use ranges with citations when not. Never use "many," "several," "various," or adjectives that substitute for numbers ("significantly," "much faster").**

### FAQ block (mandatory, 3-5 questions)

- Real questions your personas would type into ChatGPT or Google.
- Answers 40-60 words each — the PAA sweet spot and ideal LLM extraction length.
- Question wording mirrors real search syntax, not marketing copy ("How does [product] handle [capability]?" not "What sets [product]'s [capability] apart?").

### The Close

- One soft CTA: link to docs, a related article, or contact. No "schedule a demo today!" energy.
- No "in conclusion" or "to wrap up." End on the strongest sentence you have.

## Banned patterns (will get the post rejected in PR)

- "In today's [adjective] landscape"
- "It's no secret that"
- "Leverage" (use "use")
- "Robust," "cutting-edge," "seamless," "best-in-class"
- "Empower," "unlock," "revolutionize"
- "Whether you're [X] or [Y]"
- "The world of [topic]"
- "Significantly," "much faster/better/more secure" without a number
- "Many," "several," "various" — use a specific count or drop the modifier
- "Root cause," "root failure" — name the specific assumption or failure mode instead
- "Operationalize," "operationalization" — say "implement," "execute," "deploy," or "use"
- Em-dashes used as a substitute for commas or periods — cap at 3 per post regardless of length; the pattern is a top AI-generated tell
- Bullet lists of 2 items (just use a sentence)
- Paragraphs that exist only to introduce the next section
- "We" or "our" before the first H2 (lead with the topic, not the company)
- Opening a post with a question ("Have you ever wondered...")
- Framing a vulnerability or incident as a competitor problem rather than an industry pattern

## Voice anchors

- **Confident, not boastful.** State facts. Don't editorialize about how impressive they are.
- **Technical, not jargony.** Use the right word, define it once.
- **Opinionated, not preachy.** Take positions on real tradeoffs. Don't moralize.
- **Specific, not exhaustive.** One sharp example beats five vague ones.

When in doubt: would your engineering lead be embarrassed to share this on their LinkedIn? If yes, rewrite.

## Format-specific rules

### Reactive blog (350-500 words)

- Lead with the news in the first sentence: "On [date], [thing happened]."
- The whole post is: news → why it matters → your relevant angle → what readers should do.
- Cite the original source in the first paragraph, not the third.
- One H2 max — these are short.

### Pillar blog (1,200-1,800 words)

- 3-5 H2s, each meaningful enough to stand as its own search result.
- At least one diagram-shaped section (table, structured comparison).
- The pillar's job is to be THE answer for its target query — exhaustive without being padded.
- Internal links to related KB articles strengthen the topic cluster.

### KB article (600-1,000 words)

- Title is a question or definition. The first sentence directly answers it.
- Structure: Definition → How it works → When to use it → How it relates to [adjacent concepts] → FAQ.
- These are AEO-first. Write for the LLM citing you, not the human reading.
- Heavy internal linking to other KB articles builds the entity graph.

### Comparison page (800-1,200 words)

- Structure: TL;DR verdict (1 paragraph) → Comparison table → Where [Competitor] wins → Where you win → Decision criteria → FAQ.
- **The "Where [Competitor] wins" section is mandatory.** A comparison page that only flatters your product reads as marketing and loses both human and LLM trust.
- Every competitor capability claim cites a competitor source (their docs, changelog, pricing page) with the access date.
- If you cannot find a citation for a claim about a competitor, the claim does not go in the post.
- **Version strings live in a single legend line** ("Versions: X 1.2 · Y 3.4") below the table — not repeated per-row in tables, chart labels, or prose.
