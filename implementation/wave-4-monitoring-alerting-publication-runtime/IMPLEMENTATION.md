# Wave 4 Monitoring → Alerting Publication Runtime

**Status:** implementation candidate  
**Authorization:** `wave4.monitoring-alerting-publication@1`  
**Canonical base:** `main@fb7d2e6309df432b133105aa081dc1ef37784820`

## What this slice implements

This slice materializes the already-authorized internal Monitoring publication bridge for exactly two contracts:

- `monitoring.problem-state.changed`
- `monitoring.health-projection.changed`

It does not create Alert state. It only creates immutable Phase 10 outbox obligations when the already-authoritative Monitoring transition records are inserted.

## Composition boundary

The runtime migration lives under `sql/integration/` because it composes two already-accepted substrates:

1. Wave 2 `system.async_outbox_message` / `system.async_outbox_dispatch`;
2. Wave 4 `monitoring_problem_transition` / `health_projection_transition`.

It intentionally does **not** duplicate the outbox schema inside Wave 4.

## Atomic publication law

`AFTER INSERT` triggers on the immutable Monitoring transition tables call a dedicated NOLOGIN publication executor. The outbox insert occurs in the same PostgreSQL transaction as the owning transition.

Therefore:

```text
TRANSITION ROLLBACK => OUTBOX ROLLBACK
TRANSITION COMMIT   => OUTBOX OBLIGATION COMMIT
OUTBOX DELIVERY     != BUSINESS TRANSITION COMMIT
```

Pure Problem/Health refreshes that create no transition record create no publication.

## Logical identity

Each logical message uses a deterministic compact `message_id` derived from:

- exact contract;
- trusted tenant identity;
- exact immutable transition identity.

The compaction digest is not used as security evidence. If the same scoped `message_id` is ever observed with different immutable meaning, the bridge compares the full expected envelope/payload equivalence evidence and fails closed with `monitoring.publication_identity_conflict`.

Redelivery or recovery therefore reuses one logical message identity.

## Payloads

Problem invalidation payload:

```text
problem_id
monitoring_source_id
source_instance_generation
monitoring_resource_id
projection_revision
problem_transition_id
```

Health invalidation payload:

```text
monitoring_source_id
source_instance_generation
monitoring_resource_id
projection_revision
health_transition_id
```

No Problem lifecycle/severity or Health class/evidence-state value is copied into the message.

## Recovery

Two recovery entry points are granted only to the existing Wave 4 recovery authority:

- `monitoring.recover_problem_state_publication(...)`
- `monitoring.recover_health_projection_publication(...)`

They re-read the exact immutable transition and ensure the same logical outbox record exists. They never synthesize a new transition identity. If mutable dispatch bookkeeping was lost while the immutable outbox message survived, the bridge recreates only the missing dispatch row.

## Still not authorized

This slice does not implement:

- broker selection or deployment;
- Alert creation/resolution;
- Alert policy evaluation;
- acknowledgement or suppression;
- routing, notification or escalation;
- ITSM, Automation or AIOps mutation;
- browser realtime;
- public webhooks;
- provider write-back;
- frontend or production rollout.

A consumer receiving these events must still re-establish current authority and re-read Monitoring before any future protected Alerting decision.
