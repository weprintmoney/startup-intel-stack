# Brief: {title}

**Decision:** {one sentence — what is being decided}
**Horizon:** {default 18 months}
**Out of scope:** {…}

## Constraints

| Area | Constraint | Hard or preference? | Source |
|---|---|---|---|
| Team & skills | size, what they already run well, who's on call | | |
| On-call appetite | pages/week tolerated, 24/7 or business hours | | |
| Budget | build + monthly run, USD | | |
| Scale | now → 18 months (req/s, data volume, tenants) | | |
| Latency / SLOs | p50/p99, availability target | | |
| Compliance & residency | regimes, data location, audit needs | | |
| Security model | trust boundaries, key custody, threat actors | | |
| Deploy cadence | how often, how (CI, manual, customer-hosted) | | |
| Existing stack & sunk cost | what must be reused or integrated | | |
| Last production failure | what broke, why — the scar tissue | | |
| Deadlines | hard dates and what depends on them | | |
| Must not change | APIs, contracts, customer commitments | | |

## Cross-check

- **Contradictions:** {…resolved how}
- **Probably preferences, not constraints:** {…}
- **Implied constraints added:** {…}

## Assumptions ledger

| # | Assumption | If wrong → failure mode | Evidence | Risk | Verify by |
|---|---|---|---|---|---|
| A1 | | | Measured / Observed / Assumed / Hoped | H/M/L | |
