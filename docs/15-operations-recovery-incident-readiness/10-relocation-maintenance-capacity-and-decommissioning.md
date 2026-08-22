# Phase 15 — Relocation, Maintenance, Capacity and Decommissioning Operations

**Status:** proposed baseline

## Relocation operations

Operational relocation consumes accepted Control Plane placement authority and Phase 13 source-fence/target-admission semantics. `ops.relocation-operation@1` is evidence/coordination around that authority; it does not own tenant placement.

Relocation records tenant/scope, source/target placement generations, cell/runtime compatibility, continuity transfer/reconciliation, source fencing, target admission and unresolved work.

After target accepts writes/effects, rollback is not a pointer flip.

## Maintenance

Maintenance has explicit scope, owner, affected capability profiles, expected degradation/draining state, change/release relationship, rollback/forward-recovery class, capacity headroom and communication responsibility.

Maintenance does not waive current authorization, generation fencing, durable work ownership or incident declaration when actual state exceeds the accepted maintenance envelope.

## Capacity management

Operational capacity dimensions include:

- incident/recovery concurrency;
- backup/restore read/write/egress;
- reconciliation `(R,F]` work volume;
- redrive/replay/quarantine backlog;
- migration/backfill overlap;
- cell/control-plane load and tenant skew;
- crypto/verifier recovery work;
- observability surge;
- temporary dual/surge runtime during recovery;
- evidence retention/storage growth.

Exact thresholds remain OPEN, but bounded admission, measurement points and overload behavior are mandatory.

## Recovery prioritization

Priority may follow accepted business/risk authority, but operator intuition, tenant identity or AI score cannot silently become cross-tenant priority authority. Priority policy must be explicit, fair/bounded and auditable.

## Decommissioning

`ops.decommission-operation@1` proves before completion:

- no current tenant/workload/placement authority depends on target;
- no unresolved deployment/recovery/redrive/relocation operation can still act there;
- credentials/principals/routes are retired;
- data/artifacts/evidence are migrated, retained or erased under owning governance;
- recovery/legal-hold/audit obligations are dispositioned;
- cell compatibility/lifecycle and release state agree;
- stale executors/writers cannot regain authority.

Zero desired replicas or empty dashboards are not sufficient decommission proof.

## Vendor/dependency exit

Operational exit/replacement preserves logical identity, authority, evidence, recovery continuity and historical interpretability. Vendor export success alone is not conformance proof.

## Evidence

Record maintenance/relocation/decommission operation IDs, authorities, generation/fence state, capacity evidence, communication, result and residual obligations.