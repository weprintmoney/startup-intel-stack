---
title: "Pluggable job store — memory, local disk, S3-compatible object stores — FIXTURE"
graph_id: claim/job-store-memory-disk-s3
graph_type: positioning-claim
confidence: verified
---

# Claim: pluggable job store (fixture)

example-app keeps job state in memory, on local disk, or in any
S3-compatible object store. One binary, no separate database server to
run. The disk store is the default; S3 is for cloud-native and multi-region
deployments. Since v0.33.0 there is no relational backing store.
