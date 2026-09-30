# transcript-failure-miner — 2026-W35 fixture

Mined 2 findings this week. Both come from sessions in the implement pipeline.

- **f-01-repo-a-dead-end** — dead-end in `sessions/2026-W34/implement-repo-A.stream.jsonl`: agent looped on a missing schema import 3 times. 3 occurrences, 1 distinct transcript.
- **f-02-repo-c-wrong-assumption** — wrong-assumption in `sessions/2026-W34/implement-repo-C.stream.jsonl`: agent asserted the `run-meta.json` file was at `/tmp/meta.json` when the pipeline writes it to `/tmp/review-input/run-meta.json`. 2 occurrences, 1 distinct transcript.
