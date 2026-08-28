# Failure and Degradation Matrix

**Status:** accepted  
**Primary ADR:** ADR-017

The system must fail predictably. `retry` is not a universal failure policy.

| Dependency / failure | Tenant-facing behavior | Mutation behavior | Recovery / isolation |
|---|---|---|---|
| Control Plane unavailable | Stable admitted traffic may continue from bounded trusted placement cache; topology/admin operations unavailable | Tenant lifecycle/relocation/suspension changes fail closed | Preserve cell autonomy; alert; recover authority before topology changes |
| Cell transactional DB unavailable | Affected cell/tenants unavailable or degraded; unrelated cells continue | Fail closed | Cell health removes traffic; database recovery/failover per platform design |
| External monitoring provider unavailable | Stored monitoring/ITSM data may remain readable with explicit staleness | Provider-dependent sync/action fails fast after bounded policy | Per-tenant/provider circuit + bulkhead; no global outage |
| Queue/job transport unavailable | Synchronous state may commit when durable outbox/job intent is stored; async progress pauses | Do not claim completed external side effect | Dispatcher resumes from durable state; bounded backlog |
| Performance cache unavailable | Bypass where safe with concurrency protection | Authoritative writes continue if other dependencies healthy | Avoid cache stampede; alert degraded performance |
| Security/session authority durable store (system of record) unavailable | Locally verifiable already-issued credentials MAY continue only within accepted policy; otherwise deny | Security-sensitive operation fails closed when authority cannot be established | Recover authority; no permissive fallback |
| Security/session acceleration cache unavailable, durable authority reachable | Bypass to the durable session/permission authority under an explicit per-cell bulkhead/concurrency budget sized for full-cache-miss load; do not fail closed platform-wide on this condition alone | Security-sensitive mutations continue via the durable authority only after the unavailable/old cache generation is excluded from positive security admission across every serving BFF that could otherwise trust it. A local Redis failure/partition at the writer is not sufficient proof; if a shared degraded/admission fence cannot be established, the mutation fails closed. | Restore cache under budget, but do **not** re-admit recovered Redis for positive session/permission authority merely because it is reachable. Re-entry requires the `OPEN-REL-015` cache recovery-admission/epoch mechanism, joined to current durable session authority and `OPEN-REL-031.A` topology: advance/re-establish trusted cache admission or equivalently invalidate pre-outage positives, reconcile durable security-cache obligations through the recovery boundary, then mark the tier current. Redis failover/restore without proven fence continuity also invalidates the old admission generation. Pre-outage/pre-failover stale positives never regain authority after recovery. |
| Realtime fanout/gateway unavailable | API/read state remains available; live updates pause | Authoritative writes continue | Clients reconnect/resync; no business truth lost |
| Telemetry store unavailable | Historical queries/ingest degrade; current transactional state MAY continue | Telemetry ingestion buffers only within bounded durable policy; then backpressure/drop by explicit data policy | Protect core transactional system from unbounded buffering |
| Object storage unavailable | New report/export artifacts and downloads degrade | Core domain mutations continue | Jobs retry within bounded policy; artifact state remains explicit |
| Secret manager unavailable | Operations needing uncached/unleased secret fail; unrelated operations continue | No plaintext fallback | Existing short-lived secret lease only if accepted; recover secret authority |
| Webhook destination slow/down | Only that destination delivery lags/fails | Originating committed business state is not rolled back | Destination-specific concurrency, retry/backoff, quarantine |
| Reporting/AIOps worker pool saturated | Reports/derived findings delayed | Core transactional operations continue | Separate queue/pool/concurrency budget |
| One tenant workload noisy | Tenant may be throttled/degraded | Preserve other tenants | Tenant quotas/bulkheads; candidate for dedicated cell |
| Cell unavailable | Tenants in cell affected; other cells continue | No writes to unavailable cell | Cell recovery; future relocation/failover only through controlled placement process |

## Queue/backlog protection

Backlogs have per-workload observability, age/lag limits and admission/concurrency policy. The system must not accept infinite work it cannot drain.

## Staleness

Any degraded path serving previously stored state exposes freshness/staleness where material. It must not present stale provider data as newly confirmed state.

## Health reporting

Liveness, readiness and degraded dependency status are distinct. A process can be alive but not safe to receive tenant traffic.

## Chaos/fault validation

Pre-production validation must inject at least: provider timeout, provider throttling, cache loss, queue outage, cell DB loss, Control Plane loss, realtime loss, object-store loss, worker crash/restart and stale placement during relocation, and — distinctly — session/security-acceleration-cache-only loss (durable session authority reachable) versus session/security-authority durable-store loss, to prove the two rows above are never conflated into one fail-closed-platform-wide response.

For the session/security acceleration cache specifically, validation also injects: cache write failure before a revocation commit; process death after the durable revocation commit but before cache finalization; cache restart/restore with intentionally stale positive entries; concurrent stale cache-fill during a revocation fence; and a partial Redis partition where one BFF loses cache reachability while another can still read an older positive generation. A recovered cache remains non-authoritative for positive admission until its `OPEN-REL-015` recovery-admission barrier proves currentness against durable authority, and partial reachability never counts as proof that the old cache generation has been globally fenced.
