# System Design Validation Matrix

**Status:** proposed baseline

This matrix converts the design into evidence gates. Passing happy-path tests is not enough.

| Area | Required evidence before production |
|---|---|
| Tenant routing | Caller-supplied cell/schema/DB routing is ignored/rejected; authoritative placement controls routing |
| Tenant isolation | Known cross-tenant IDs leak zero protected rows through API, repository, reporting, realtime, export and workers |
| Placement cache | Stable active traffic can use bounded cache; migration/suspension invalidates or is rejected by destination admission/version |
| Relocation | Concurrent stale source writer is fenced; no source writes accepted after cutover; target becomes sole authority |
| Authorization | UI omission cannot bypass server policy; cross-tenant privileged operations are distinct and audited |
| Transactions | Mutation + required audit + outbox commit atomically; injected dispatcher failure loses no committed event intent |
| Event delivery | Duplicate event causes no duplicate irreversible effect; poison message quarantines after bounded policy |
| Job delivery | Worker crash after external timeout does not duplicate accepted logical side effect beyond contract |
| Provider outage | One tenant/provider failure does not create global outage/retry storm |
| Cache outage | Behavior matches cache class; no cache loss becomes durable data loss |
| Realtime outage | Authoritative write/read continues; reconnect/resync restores client state |
| Control Plane outage | Stable admitted traffic behavior matches policy; topology-changing operations fail closed |
| Cell DB outage | Affected cell is removed/degraded; unrelated cells continue |
| Telemetry outage | Buffer/backpressure remains bounded; transactional core protected from telemetry backlog |
| Secret authority outage | No plaintext fallback; only accepted lease/cache behavior continues |
| SQL administration | Normal app/migration owner credentials are unavailable to interactive query path |
| Migration | Mixed-version rollout validated; destructive change follows expand/migrate/contract |
| Recovery | Cell restore and tenant-level recovery rehearsal completed with tenant isolation intact |
| Observability | Request -> transaction -> outbox/job -> worker -> provider can be correlated without secret leakage |

## Release-blocking invariant tests

The following failures block release regardless of other test success:

- cross-tenant protected data disclosure or write;
- application runtime can bypass tenant RLS/data policy unexpectedly;
- stale placement can write after relocation fence/cutover;
- required privileged audit record can be omitted on successful mutation;
- duplicate delivery can repeat an irreversible payment/destructive execution without contract protection;
- secrets appear in logs/traces/events/queue payload/audit/client error;
- migration makes active supported runtime versions access incompatible schema;
- restore cannot re-establish verified tenant isolation.

## Evidence traceability

Automated tests SHOULD reference `INV-*`, `QA-*`, `SEC-*` and `TM-*` identifiers. Architecture-specific tests additionally reference the ADR/design section they validate.
