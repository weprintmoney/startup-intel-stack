# Claims vetted — FIXTURE

Synthetic excerpt carrying only the retired-claims table.

## Retired claims — never publish

Positioning retirements from a repositioning (proxy → standalone database), plus one factual error.

| Retired phrase | Why | Say instead |
|---|---|---|
| "proxy mode" / "proxy layer" / "sits in front of" | Pre-repositioning product framing | "standalone encrypted database" |
| "point it at Postgres" / "Postgres, Redis" (as backing stores) | Proxy story | "tiered storage — RAM, local disk, S3-compatible object stores" |
| "your data plane stays put" | Proxy-era value prop | "runs entirely in your environment" |
| "no new database to staff/operate/manage" / "isn't another database" | example-app IS a new self-hosted database | Omit |
| "your existing database" / "transforms your database" (PostgreSQL/Redis) | Proxy story | "standalone encrypted database in your environment" |
| "separates compute from storage" | Proxy-heritage architecture framing | "tiered by design" / "disk-native" |
| "MySQL" (as a supported backend) | Never supported — factual error | — |
| "end-to-end encrypted collaboration" | Legacy product scope | Current mission language |

## Legacy product — what you may say

(omitted in fixture)
