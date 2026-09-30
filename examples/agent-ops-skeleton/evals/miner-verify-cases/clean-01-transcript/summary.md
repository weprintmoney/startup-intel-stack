# transcript-failure-miner — 2026-W34 fixture

Mined 3 findings across 2 transcripts in the 9-day window. All three are recurring dead-ends where the implementer re-derived pipeline conventions that already live in `.claude/team-memory/`.

- **f-01-agent-branch-naming** — dead-end in `sessions/2026-W34/implement-core-pr312.stream.jsonl`: agent tried `agents/<ticket>-<slug>` branch names 3 times before finding the `agent/<ticket>-<slug>` convention. 3 occurrences, 1 distinct transcript.
- **f-02-schema-path-drift** — wrong-assumption in the same transcript: agent guessed `schemas/miner_findings.schema.json` before landing on the hyphenated form. 2 occurrences, 1 distinct transcript.
- **f-03-git-worktree-convention** — missing-context in `sessions/2026-W34/implement-example_app-pr47.stream.jsonl`: agent attempted `git checkout` on the shared checkout and had to be rescued. 4 occurrences, 1 distinct transcript.
