# Threat Model

**Status:** accepted baseline

This document establishes threats that architecture and testing must explicitly address. It is not a substitute for feature-specific threat modeling.

## Assets

Primary protected assets include tenant operational data, identity/session state, authorization policy, integration credentials, infrastructure topology/configuration, automation capability, audit evidence, commercial/financial records, generated exports/reports, and platform control-plane metadata.

## Trust boundaries

1. user/browser -> Web/BFF;
2. Web/BFF -> API;
3. API -> owning domain/application layer;
4. application -> transactional data/cache/queue;
5. queue/event transport -> worker/consumer;
6. worker -> script/automation execution environment;
7. platform -> monitoring/ITSM/payment/notification/identity provider;
8. inbound provider/webhook -> platform;
9. tenant admin -> tenant privileged capability;
10. platform admin -> control plane/cross-tenant capability;
11. SQL/data administration -> protected data plane;
12. reporting/export/status -> external information release.

## TM-001 — Cross-tenant object reference

**Attack:** Tenant A submits Tenant B resource ID through API, report filter, export, WebSocket subscription, worker target or integration path.  
**Required controls:** tenant context, authorization, owner query constraints/data-layer isolation, tenant-scoped cache/topics/read models, isolation tests.

## TM-002 — Confused deputy in asynchronous processing

**Attack:** forged/stale job payload includes another tenant's schema/connection/target and worker executes with trusted privileges.  
**Required controls:** logical tenant ID only, trusted placement resolution, contract validation/versioning, worker authorization policy, deduplication, audit.

## TM-003 — Privilege escalation

**Attack:** viewer/operator/tenant admin reaches stronger tenant/global action through undocumented endpoint, API key, feature flag or direct-query capability.  
**Required controls:** declared server-side permissions/scopes, deny-by-default privileged paths, separate cross-tenant operations, security tests.

## TM-004 — Cache/pub-sub tenant collision

**Attack:** insufficiently namespaced key/topic returns or publishes Tenant B data to Tenant A.  
**Required controls:** canonical tenant-aware key/topic construction, subscriber authorization, test fixtures across multiple tenants.

## TM-005 — SSRF through connectors/webhooks

**Attack:** tenant config causes platform to call metadata service, localhost, private control endpoint, unsafe protocol or redirect chain.  
**Required controls:** outbound policy, destination validation, DNS/IP handling policy, redirect limits, protocol allowlist, egress restrictions where appropriate.

## TM-006 — Malicious provider payload

**Attack:** monitoring/ITSM/provider sends oversized, malformed, script-like or semantically hostile content.  
**Required controls:** adapter validation, size limits, normalization, safe rendering/escaping, no implicit provider authority.

## TM-007 — Script/command breakout

**Attack:** authorized automation escapes target/runtime boundary, accesses platform secrets, network or neighboring workloads.  
**Required controls:** isolated execution runtime, least-privilege credentials, filesystem/network/resource limits, approval/policy, timeouts, output limits, audit.

## TM-008 — SQL console escalation

**Attack:** direct-query tool changes protected schema, bypasses tenant controls, reads control-plane/other tenant data, or creates resource exhaustion.  
**Required controls:** read-only default, dedicated role, tenant-scoped connection/session, statement/row/time limits, restricted commands, audit and stronger privileged mode if ever allowed.

## TM-009 — Data exfiltration through export/report

**Attack:** attacker requests broad export, downloads stale artifact after authorization revocation, or exploits public/report projection to obtain internal fields.  
**Required controls:** field contracts, asynchronous authorization re-check, short-lived artifact access, tenant-scoped storage keys, audit, public projection separation.

## TM-010 — Secret leakage

**Attack:** credentials appear in exception, trace, log, event, queue, audit before/after or generated support bundle.  
**Required controls:** structured redaction at source/sink, safe error contracts, secret references, automated leakage tests.

## TM-011 — Replay/duplicate side effect

**Attack:** retry/replay duplicates ticket, workflow, payment, notification or destructive automation.  
**Required controls:** idempotency keys/inbox/outbox or equivalent, stable operation identity, consumer deduplication, reconciliation.

## TM-012 — Placement/migration race

**Attack/failure:** tenant moves cluster while stale API/worker continues writing old placement, causing split state or leakage.  
**Required controls:** placement version/state, migration admission control, logical resolution per unit of work, cutover verification and stale-writer rejection.

## TM-013 — Global-admin abuse/compromise

**Attack:** compromised global principal accesses all tenant data through implicit wildcard authority.  
**Required controls:** cross-tenant operations explicitly modeled, MFA/step-up, least privilege, scoped support access, strong audit and optional dual control for highest-risk actions.

## TM-014 — Supply-chain compromise

**Attack:** malicious dependency/build artifact or leaked CI credential changes production behavior.  
**Required controls:** dependency review/scanning, pinned/reproducible build inputs where practical, least-privilege CI credentials, protected release path, artifact provenance/signing policy to be defined.

## Residual/open work

Feature-specific threat models are required for authentication/session design, automation execution, direct SQL, marketplace extensions, tenant migration, public status, data export/import, payment integration and any agent/AI execution capability.