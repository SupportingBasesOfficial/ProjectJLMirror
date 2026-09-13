# JLMirror Decision Register

Status: canonical project-memory source

This register is a reconstruction index. Detailed authority remains in accepted ADRs/contracts/manifests/PRs. New material decisions must receive a stable ID and be appended or explicitly superseded.

| ID | Decision | Rationale / consequence | Accepted source / status |
|---|---|---|---|
| JLM-DEC-001 | JLMirror is provider-neutral, not a Zabbix UI | provider-specific identity/semantics must stay behind adapters | foundation / accepted |
| JLM-DEC-002 | Tenant isolation is foundational | every business identity/read/write must remain tenant-safe | foundation / accepted |
| JLM-DEC-003 | Provider identity is not platform identity | provider IDs can be reused/recreated and cannot become canonical IDs | accepted throughout Monitoring |
| JLM-DEC-004 | Source generation participates in provider-evidence scope | stale identities/events from prior source instances cannot regain current authority | accepted Monitoring architecture |
| JLM-DEC-005 | PostgreSQL is durable business truth | workers/brokers/caches are recoverable infrastructure, not domain authority | accepted async/recovery architecture |
| JLM-DEC-006 | Async delivery is at-least-once | logical effects require stable identity, idempotency and equivalence checks | Phase 10 / Wave 2 runtime |
| JLM-DEC-007 | Browser access crosses mandatory BFF boundary | session/composition/realtime admission stays controlled | API architecture accepted |
| JLM-DEC-008 | Problem State and Health Projection are distinct Monitoring concepts | observed problem lifecycle must not be conflated with derived resource health | PRs #142-#145 accepted |
| JLM-DEC-009 | Healthy requires authoritative completeness | missing/incomplete/stale evidence cannot be converted into healthy | Health authorization/implementation accepted |
| JLM-DEC-010 | Monitoring->Alerting events are invalidation/resync only | payload must not replicate semantic state; consumers re-read current owner truth | PR #146 accepted |
| JLM-DEC-011 | Alert is platform-owned actionable occurrence | Problem/Health/event/provider IDs are source evidence, not Alert identity | PR #147 accepted |
| JLM-DEC-012 | Alert v1 lifecycle is `active | resolved`; resolved is terminal | repeated future occurrence gets a new `alert_id` unless a future accepted version changes semantics | PR #147 accepted |
| JLM-DEC-013 | Effectful Alert lifecycle transitions require immutable policy ID/version | prevents policy-less mutation and retroactive reinterpretation | PR #147 hardening accepted |
| JLM-DEC-014 | Alert source family is explicit | `monitoring_problem` and `monitoring_health_projection` cannot be ambiguously mixed | PR #147 hardening accepted |
| JLM-DEC-015 | Human operations use orthogonal state dimensions, not one giant status | responsibility, ACK, delivery, view, response, approval and next action must remain independently truthful | Issue #149 canonical requirement; authorization pending |
| JLM-DEC-016 | Critical human workflows must provide authoritative visibility evidence | the platform must select/admit channels or JLMirror-controlled confirmation surfaces that can prove awareness on internal and customer sides | Issue #149 canonical requirement; authorization pending |
| JLM-DEC-017 | Repository truth outranks assistant/chat memory | project continuity must be reconstructable from Git without old conversations | Issue #150; this project-memory foundation |

## Supersession rule
A decision is never silently edited into a different meaning. Material replacement must append a new decision ID and mark the prior decision `superseded by <ID>` with source authority.

## Update rule
Every accepted change that alters project identity, domain ownership, lifecycle/state machine, cross-domain contract, implementation maturity, next dependency-safe step or a canonical invariant must update this register or explicitly prove that no new decision was made.
