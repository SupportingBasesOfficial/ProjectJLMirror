# JLMirror Canonical Invariants

Status: canonical project-memory source

This file indexes cross-project laws. When a more specific accepted ADR/contract exists, that source remains the detailed authority; this index exists so a fresh contributor can discover the laws quickly.

## Identity and tenancy
- `TENANT A != TENANT B`
- `PROVIDER ID != PLATFORM ID`
- `PROVIDER IDENTITY != PLATFORM IDENTITY`
- provider IDs are scoped evidence, never global canonical identity.
- shared provider infrastructure must not collapse tenant isolation.

## Authorization and trust
- `JWT VALID != CURRENT AUTHORIZATION`
- `NETWORK PRESENCE != TRUST`
- browser/session/network reachability never grants domain authority.
- every privileged read/write must re-establish current authority at the accepted boundary.

## Time, ordering and generations
- `PROVIDER EVENT TIME != PLATFORM ORDERING`
- `EVENT ARRIVAL != CURRENT TRUTH`
- `BROKER ORDER != BUSINESS ORDER`
- `HISTORICAL GENERATION != CURRENT AUTHORITY`
- stale restored provider events/generations cannot regain current decision authority.

## Monitoring
- `PROVIDER EVENT ID != CANONICAL PROBLEM ID`
- `PROVIDER ACKNOWLEDGED != JLMIRROR ACKNOWLEDGEMENT`
- `PROVIDER SEVERITY != HEALTH CLASS`
- `TRIGGER METADATA != PROBLEM LIFECYCLE AUTHORITY`
- `ABSENCE FROM INCOMPLETE problem.get != RESOLVED`
- `PROBLEM STATE != HEALTH PROJECTION`
- `STALE/INCOMPLETE EVIDENCE != PROVEN HEALTHY`
- `PROBLEM ABSENCE WITHOUT AUTHORITATIVE COMPLETENESS != HEALTHY`
- `SCOPE EXCLUSION != HEALTHY`
- `REMOVED RESOURCE != CURRENT HEALTH AUTHORITY`

## Cross-domain semantics
- `PROBLEM != HEALTH`
- `PROBLEM != ALERT`
- `HEALTH != ALERT`
- `MONITORING EVENT != ALERT`
- `ALERT != ITSM INCIDENT`
- `ALERT != NOTIFICATION DELIVERY`
- `ALERT != AIOPS FINDING`
- `EVENT ARRIVAL != ALERT CREATION AUTHORITY`
- `POLICY VERSION != MUTABLE LOOKUP AT EXECUTION TIME`

## Alert lifecycle
- Alert v1 lifecycle is `active | resolved`.
- resolved `alert_id` is terminal in v1.
- re-observation of the same accepted transition is idempotent.
- Monitoring resolution/healthy/event absence/timeout/retry cannot independently mutate Alert lifecycle.
- provider ACK has zero Alert lifecycle authority.

## Human responsibility and communication
- `NOTIFICATION RECIPIENT != RESPONSIBLE PERSON`
- `RESPONSIBLE PERSON != CURRENT ACTION OWNER`
- `VIEWER != ACKNOWLEDGER`
- `ACKNOWLEDGEMENT != RESOLUTION`
- `DEVICE RESPONSIBILITY != ALERT OWNERSHIP`
- `SENT != DELIVERED`
- `DELIVERED != VIEWED`
- `VIEWED != RESPONDED`
- `PROVIDER ACCEPTED != HUMAN NOTIFIED`
- `BUDGET APPROVAL STATE != NOTIFICATION DELIVERY STATE`
- lack of a read receipt is not proof of non-view unless the admitted channel/workflow provides authoritative read evidence.
- critical workflows that require proof of awareness must admit only mechanisms capable of producing authoritative visibility evidence, directly or through a JLMirror-controlled confirmation surface.

## Async/recovery
- delivery is at-least-once;
- retry/redelivery must not duplicate logical business effects;
- stable message/transition identities are required for equivalence;
- same identity with non-equivalent immutable meaning is an integrity failure;
- PostgreSQL durable business state outranks transient worker/broker memory;
- outbox/inbox/recovery bookkeeping must not become a second source of domain truth.

## Presentation
- UI/realtime projections are not business truth.
- cursor tokens, caches and client state never confer authorization or authority.
