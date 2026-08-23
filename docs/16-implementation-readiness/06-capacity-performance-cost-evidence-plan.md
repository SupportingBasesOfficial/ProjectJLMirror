# Implementation Readiness — Capacity, Performance & Cost Evidence Plan

**Status:** proposed gate baseline

## Principle

Implementation Readiness defines what must be measured and bounded. It does not fabricate production numbers.

## Mandatory dimensions

Every applicable implementation slice declares measurement/admission plans for:

```text
tenant count and skew
request concurrency and operation mix
worker-specialization concurrency
provider/destination concurrency
realtime connections/fanout
broker backlog age/volume
retry/redrive/replay amplification
machine-auth assertion replay-state cardinality/retention/validation work
message-equivalence comparison/KMS work
transactional DB connections/CPU/IO/storage
customer telemetry ingest/projection/backlog
artifact throughput/storage/processing
observability ingest/query/export/cardinality
control-plane placement/lifecycle pressure
migration/backfill/recovery load
temporary relocation/rollout dual footprint
secret/key/config authority calls
network/egress throughput and destination skew
build/test/release compute and artifact retention
operational incident/recovery surge
```

One scalar such as CPU or requests/second is insufficient.

## Evidence lifecycle

### Before canonical implementation selection

C2 spikes/benchmarks MAY compare replaceable mechanisms using synthetic/minimized data and bounded credentials. The spike cannot acquire production authority or become canonical until a reviewed decision selects it.

### Before merge of an implementation slice

The slice SHALL contain:

- bounded defaults rather than unlimited queues/body sizes/concurrency;
- instrumentation points for all relevant dimensions;
- explicit overload/backpressure/shedding behavior from Phase 11;
- tenant/workload/provider/destination bulkhead hooks;
- bounded replay-state retention/cardinality and cross-replica admission work for replay-sensitive authentication/capability paths;
- cost attribution dimensions that avoid unsafe cardinality;
- tests proving no unbounded amplification path.

### Before production eligibility

C3 OPENs close with representative runtime/business/recovery evidence, including applicable numeric SLO/RPO/RTO, limits, retention, rollout thresholds, staffing/cadence and capacity headroom.

## Skew and abuse

Capacity tests SHALL include worst-case skew rather than uniform averages:

- one heavy tenant;
- one failing provider/destination;
- duplicate/replay storm;
- concurrent duplicate `private_key_jwt` assertions across token-boundary replicas and replay-state recovery/reconnect surge;
- poison/quarantine accumulation;
- retry storm after dependency recovery;
- high-cardinality diagnostic input;
- parser/archive expansion;
- relocation/recovery plus live traffic;
- migration/backfill plus serving load;
- release/incident surge.

## Cost safety

A mechanism may be technically correct but readiness-ineligible if attacker/user-controlled input can create unbounded cost without attribution/admission. Cost controls remain subordinate to correctness; cost pressure cannot justify skipping audit, idempotency, replay protection, recovery or security checks.

## OPEN interaction

C2 choices may be benchmarked during authorized bounded spikes. C3 values remain OPEN until evidence exists. An implementation MAY expose configuration slots for C3 values only when safe bounded temporary defaults are explicitly non-production and cannot be mistaken for accepted production targets.
