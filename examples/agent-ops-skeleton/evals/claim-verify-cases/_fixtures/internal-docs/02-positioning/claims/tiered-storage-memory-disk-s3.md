---
title: "Tiered storage — RAM, local disk, S3-compatible object stores — FIXTURE"
graph_id: claim/tiered-storage-memory-disk-s3
graph_type: positioning-claim
confidence: verified
---

# Claim: tiered storage (fixture)

example-app tiers encrypted index data across RAM, local disk and any
S3-compatible object store. One container, no separate database server to
run. The disk store is the default; S3 is for cloud-native and multi-region
deployments. Since v0.17.0 there is no relational backing store.
