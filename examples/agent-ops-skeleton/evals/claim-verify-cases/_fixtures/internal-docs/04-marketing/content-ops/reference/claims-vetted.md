# Claims vetted — FIXTURE

Synthetic excerpt carrying only the retired-claims table.

## Retired claims — never publish

Positioning retirements from a repositioning (cron add-on → self-hosted job scheduler), plus one factual error.

| Retired phrase | Why | Say instead |
|---|---|---|
| "plugin mode" / "cron add-on" / "bolts on top of" | Pre-repositioning product framing | "self-hosted job scheduler" |
| "back it with Postgres" / "Postgres, Redis" (as backing stores) | Add-on story | "job store — memory, local disk, S3-compatible object stores" |
| "your cron stays where it is" | Add-on-era value prop | "runs entirely in your environment" |
| "no new service to run/operate/manage" / "isn't another scheduler" | example-app IS a new self-hosted service | Omit |
| "your existing queue" / "upgrades your queue" (PostgreSQL/Redis) | Add-on story | "self-hosted job scheduler in your environment" |
| "decouples scheduling from execution" | Add-on-heritage architecture framing | "one binary" / "durable by default" |
| "MySQL" (as a supported backend) | Never supported — factual error | — |
| "shared team calendar" | Legacy product scope | Current mission language |

## Legacy product — what you may say

(omitted in fixture)
