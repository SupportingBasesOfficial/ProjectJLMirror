# JLMirror Glossary

Status: canonical project-memory source

- **tenant**: isolated customer/organization boundary inside the SaaS. Answers “whose data/authority is this?”.
- **provider**: external system supplying evidence, currently Zabbix 7.4.
- **adapter**: provider-specific translation boundary that prevents provider semantics from leaking into canonical domain identity.
- **canonical**: platform-owned official representation/meaning inside JLMirror.
- **Monitoring Source**: tenant-owned configured external monitoring source.
- **source generation**: source-instance epoch used to distinguish current provider identity/evidence from stale historical instances.
- **resource**: platform-owned monitored entity identity. Provider host/device IDs are evidence only.
- **Metric Definition**: what is measured.
- **Metric Current State**: current accepted value/state for a metric definition.
- **Metric History**: accepted historical observations over time.
- **Problem State**: Monitoring-owned canonical problem occurrence, currently `active | resolved`.
- **Health Projection**: Monitoring-owned derived resource health: `unknown | healthy | degraded | unhealthy`.
- **Alert**: Alerting-owned actionable occurrence produced only under accepted Alerting policy authority; not the same as Problem/Health/event.
- **Alert Policy**: versioned business authority that decides when current Monitoring truth should create/resolve an Alert.
- **outbox**: durable database-backed obligation to publish an accepted asynchronous message after/with business-state commit semantics.
- **inbox**: durable consumer-side receipt/dedup/equivalence mechanism for at-least-once delivery.
- **at-least-once**: delivery model where a message may arrive more than once; business effects therefore must be idempotent.
- **idempotency**: reprocessing the same logical action/message produces no duplicate logical effect.
- **equivalence**: proof that a repeated stable identity carries the same immutable meaning; same ID with different meaning is integrity failure.
- **BFF**: Backend-for-Frontend boundary through which browser-facing composition/session/realtime admission is controlled.
- **current authority**: evidence/authorization that is valid now for the exact tenant/source/generation/scope/action, not merely historically valid.
- **reconciliation**: process for resolving ambiguity/drift by comparing authoritative current truth under bounded rules.
- **recovery**: rebuilding/restoring durable operational obligations/state after failure without inventing new business truth or duplicating effects.
- **responsible person**: principal associated with ongoing responsibility for a resource/operation; may be one of several.
- **action owner**: principal who currently owns the next required action; not necessarily the same as every responsible person.
- **ACK / acknowledgement**: explicit actor-attributed JLMirror business action indicating awareness/acceptance of responsibility for the scoped operational item. ACK != resolution.
- **notification intent**: canonical obligation/desire to contact a specific destination/recipient for a defined reason.
- **delivery attempt**: one transport attempt toward a notification destination.
- **delivery state**: evidence such as queued/sent/provider-accepted/delivered/failed/unknown according to channel capability.
- **view/read evidence**: authoritative evidence that a human/principal viewed/opened the relevant item. Lack of evidence is not automatically proof of non-view.
- **response/waiting state**: business state describing what response is pending, e.g. awaiting customer position or technical position.
- **approval**: first-class business decision workflow such as budget/quote approval; not a delivery flag.
- **next-action projection**: derived current view of what must happen next, who owns it and what deadline/SLA applies.
- **Incident**: ITSM-owned formal operational case; Alert != Incident.
- **realtime**: delivery/projection mechanism for fresh UI updates; realtime stream is never canonical business truth.
