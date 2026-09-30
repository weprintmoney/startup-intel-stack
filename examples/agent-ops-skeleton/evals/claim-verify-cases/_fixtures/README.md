# _fixtures — shared synthetic sources for the claim-verify golden set

Hermetic stand-ins for the three checkouts the production gate reads:

| Dir | Stands in for | Contents |
|---|---|---|
| `internal-docs/` | `example-org/internal-docs` | `graph.json` (9 nodes), condensed `terminus/invariants.md`, `backing-stores/behavior-matrix.yaml`, the retired-claims table in `claims-vetted.md`, two ADR stubs, two positioning-claim docs, an ICP stub |
| `docs-public/` | `example-org/example-app-docs` | `versions/changelog.mdx` excerpt (v0.15.0 – v0.17.0) |
| `product/` | `example-org/example-app-core` default branch | a 4-file Python tree with stable line numbers the spec fixtures cite |

Everything here is **synthetic** — condensed paraphrases of the real docs
carrying only the facts the cases need (storage surface is memory/disk/s3
since v0.17.0; postgres/redis removed in v0.17.0; MySQL never supported;
no plaintext mode). No prospect names, no customer details, no secrets.

The runner (`scripts/run-claim-verify-evals.py setup`) points
`verify-claims.py sources/extract` at these directories, so the eval
exercises the same code path production does. **Line numbers in
`product/` are load-bearing** — `clean-01`, `clean-03` and `planted-01` cite
them. If you edit a product file, re-check every `path:line` in the
artifacts (`grep -rn 'src/example_app' ../*/artifact.md`).
