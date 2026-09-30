# doc-drift-miner — 2026-W34 fixture

Mined 2 findings. Both are graph nodes where merged code contradicts the node's claim. Zero staleness confirmations, zero not-confirmed downgrades this week.

- **f-01-storage-adr-drift** — doc-drift on node `adr-storage-backends`: the ADR names Postgres and Redis as first-class stores but PR #291 removed both, leaving memory / disk / s3. 3 occurrences (ADR body + removal PR + release notes).
- **f-02-enc-index-drift** — doc-drift on node `component-enc-index`: the node's `depends_on` still lists `mock-vector-encoder` after PR #305 replaced it with the production encoder. 3 occurrences.
