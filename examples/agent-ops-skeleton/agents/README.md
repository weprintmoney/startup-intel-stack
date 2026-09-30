# Pipeline agents

One directory per pipeline node, each containing a `CLAUDE.md` prompt. Workflows invoke nodes as:

```bash
bash scripts/run-claude.sh /tmp/<node>.stream.jsonl "$(cat agents/<name>/CLAUDE.md)

Task: <the one task block for this run>" \
  --allowedTools "<explicit whitelist>" \
  --max-turns <cap>
```

`scripts/run-claude.sh` appends the persona to the system prompt (cache-prefix-stable across runs of the same node), passes only the task block as the user message, and prints the parsed result entry, the CLI's stderr, and the stream tail on any failure. Every node ends with exactly one `RESULT: <TOKEN> [detail]` line, parsed by `scripts/result-line.sh` — the only parser.

Every node is a separate `claude -p` process with a scoped context load — reviewers and judges never see an implementer transcript.

Current nodes (13), each documented in its own `README.md` sibling to its `CLAUDE.md`:

| Node | Phase | Model | Workflow(s) |
|---|---|---|---|
| [`spec-drafter`](spec-drafter/README.md) | 2 | sonnet | `spec-draft.yml` |
| [`plan-drafter`](plan-drafter/README.md) | 2 | sonnet | `implement.yml` (plan job) |
| [`implementer`](implementer/README.md) | 2 | sonnet | `implement.yml` (implement job) |
| [`pr-reviewer`](pr-reviewer/README.md) (fresh-context, generic review) | 2 | sonnet | `implement.yml` |
| [`founder-voice-pr-reviewer`](founder-voice-pr-reviewer/README.md) (fresh-context, founder-voice review) | 2 | opus | `implement.yml` |
| [`reviser`](reviser/README.md) (fixes judge findings; may decline, never rebuts) | 2/3 | sonnet | `revise.yml` |
| [`code-judge`](code-judge/README.md) | 3 | opus | `code-judge.yml` |
| [`dream-orchestrator`](dream-orchestrator/README.md) (+ 3 miner subagents) | 4 | sonnet | `dream.yml` |
| [`miner-verifier`](miner-verifier/README.md) (fresh-context, gates dream memory PRs) | 4 | sonnet | `dream.yml`, `verifier-evals.yml` |
| [`claim-verifier`](claim-verifier/README.md) (fresh-context, gates spec PRs + release-intelligence findings; deterministic pre-pass in `scripts/verify-claims.py`) | 2 / R1 | sonnet | `spec-draft.yml`, `claim-verify.yml`, `claim-verify-evals.yml`, `release-intelligence.yml` |
| [`release-intelligence-miner`](release-intelligence-miner/README.md) | R1 | sonnet | `release-intelligence.yml` |
| [`ticket-drafter`](ticket-drafter/README.md) | R1 | sonnet | `release-intelligence.yml` |
| [`dependabot-diagnoser`](dependabot-diagnoser/README.md) (fresh-context, read-only; explains a verification-check regression on a Dependabot PR *after* `scripts/dependabot-triage.py` has already decided `blocked:regression` — never gates a merge) | ops | sonnet | `dependabot-triage.yml` |

Satellites with no standalone `agents/` directory: the three dream miners (`transcript-failure-miner`, `review-delta-miner`, `doc-drift-miner`) live as prompt files under `agents/dream-orchestrator/miners/`, invoked by the orchestrator rather than a workflow directly.
