# Phase 15 — Async, Replay, Quarantine, Realtime and Webhook Operations

**Status:** proposed baseline

## Core rule

Operational intervention does not weaken Phase 09/10/11 delivery, idempotency, deduplication, generation or ambiguity semantics.

## Redrive operation

`ops.redrive-operation@1` records:

```text
redrive_operation_id
source quarantine/backlog identity
consumer/delivery/replay contract
message/delivery identity scope
tenant/current placement
source/destination/replay generations
content-equivalence/dedup evidence where required
external-effect ambiguity state
compatibility profile
capacity admission
authorizing principal/reason
result/reconciliation state
```

## Redrive eligibility

Redrive requires current privileged authority and owning-contract eligibility. Time in quarantine, operator desire, queue age or a vendor DLQ button is not eligibility.

A same-ID content conflict, ambiguous effect or unavailable historical equivalence proof remains blocked according to Phase 10/11 contracts.

## Replay

Replay does not create a new semantic past. It preserves replay/source generation, message identity, current authorization/placement and historical comparison semantics where required.

Replaying under a new canonical comparison profile cannot silently redefine old equality.

## Quarantine

Quarantine is durable responsibility, not deletion or successful processing. Operational disposition preserves owner, classification, safe identity, evidence and retention while minimizing confidential payload exposure.

## Realtime recovery

After auth/permission/placement/runtime generation changes or recovery, clients resubscribe/resync under current authority. An old socket/session does not remain authorized merely because transport is open.

Operational recovery cannot reuse burned/single-use realtime tickets or infer state continuity from connection survival.

## Webhook recovery

Webhook redelivery/recovery preserves immutable obligation/delivery identity, destination generation/fence and exact representation evidence. Retargeting an old delivery to a newly configured destination is prohibited unless the owning contract explicitly defines a new obligation.

Ambiguous external delivery remains reconciliation-aware; timeout is not proof of no disclosure/effect.

## Artifacts

Artifact reissue/recovery follows artifact lifecycle, authorization and delivery evidence. A restored artifact object does not restore disclosure authority.

## Capacity/abuse

Redrive/replay/quarantine operations are tenant/workload/destination bounded. Operators cannot unleash unbounded replay or KMS/comparison work that bypasses Phase 11 capacity controls.

## Evidence

Permanent evidence records operation identity, scope, authority, current generations, compatibility/dedup/equivalence basis, capacity gate, actions, outcomes and unresolved ambiguity without exposing unrestricted payloads/fingerprints/secret material.