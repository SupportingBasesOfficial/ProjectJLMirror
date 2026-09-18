# G5 Problem + Health — Implementation Authorization

**Status:** proposed exact-scope authorization  
**Canonical base:** `main@96de4f58831e9c773d9bc00595e771fce9094f1e`  
**Authorization ID:** `g5.problem-health@1`

## Purpose

Authorize only the fifth AI-E2E product increment: expose already-canonical Monitoring Problem State and Health Projection through protected BFF/API/browser UI for an already-authorized tenant user.

G5 MUST reuse the accepted Wave 4 Problem State and Health Projection substrate. It MUST NOT create another problem/health store, recalculate canonical lifecycle/health in the UI/BFF, query Zabbix directly, create Alerts, acknowledge anything, mutate ITSM, or broaden into G6+.

## Authorization on acceptance

```text
implementation_authority_before_merge = blocked
implementation_authority_after_merge = granted_for_exact_g5_problem_health_only
```

Authorized slice:

```text
g5.problem-health@1
```

Observable outcome: an authorized tenant user can inspect canonical Problems and Health for current resources, including active/resolved transitions, severity, health class, evidence/currentness and historical-generation truthfulness.

`merge_authorization = not_granted` remains separate.

## Dependency boundary

G5 depends on canonical G1–G4 implementations plus accepted Wave 4 Problem State and Health Projection.

Existing Monitoring/domain/SQL/runtime substrate is read-only under this authorization.

## Implementation path authority

Allowed prefixes:

- `apps/g5-problem-health/`;
- `contracts/g5-problem-health/`;
- `implementation/g5-problem-health/`;
- `tests/g5/`;
- `tools/g5/`.

Allowed exact path:

- `.github/workflows/g5-problem-health-runtime.yml`.

Required future implementation PR identity:

- branch prefix `impl/g5-problem-health`;
- label `jlmirror-slice:g5-problem-health`;
- claim file `implementation/g5-problem-health/IMPLEMENTATION_CLAIM.json`;
- authorization ID `g5.problem-health@1`;
- same repository;
- base equal to current default branch tip when trusted evidence is produced.

## Product behavior authorized

The later implementation may expose only:

1. current tenant admission through canonical G1;
2. current `monitoring.resource.read`, `monitoring.problem.read` and `monitoring.health.read` authorization;
3. canonical Problem list/detail;
4. canonical Health list/detail;
5. resource association through canonical IDs;
6. active/resolved Problem state and canonical severity;
7. current/stale/incomplete/reconciliation-required/unavailable evidence states;
8. active-generation default current meaning;
9. visibly historical/non-current retained evidence;
10. bounded problem/reason/provider metadata exactly where accepted;
11. browser E2E for activation/recovery, health transition, revoked and cross-tenant denial;
12. bounded runtime/container proof.

## Binding semantics

```text
PROVIDER_EVENT_ID != PROBLEM_ID
PROVIDER_ACKNOWLEDGED != JLMIRROR_ACK
PROVIDER_SEVERITY != HEALTH_CLASS
PROBLEM_STATE != HEALTH_PROJECTION
PROBLEM_STATE != ALERT_STATE
HEALTH_PROJECTION != ALERT_STATE
ABSENCE_FROM_INCOMPLETE_PROBLEM_EVIDENCE != RESOLVED
PROBLEM_ABSENCE_WITHOUT_AUTHORITATIVE_COMPLETENESS != HEALTHY
STALE_OR_INCOMPLETE_EVIDENCE != HEALTHY
OUT_OF_SCOPE != HEALTHY
REMOVED_RESOURCE != CURRENT_HEALTH_AUTHORITY
HISTORICAL_GENERATION != CURRENT_PROBLEM_AUTHORITY
HISTORICAL_GENERATION != CURRENT_HEALTH_AUTHORITY
```

The UI/BFF projects accepted canonical truth only; it does not derive lifecycle or health.

## API/BFF authority

Relevant accepted surfaces:

```text
GET /api/v1/tenants/{tenant_id}/problems
GET /api/v1/tenants/{tenant_id}/problems/{problem_id}
GET /api/v1/tenants/{tenant_id}/health-projections
GET /api/v1/tenants/{tenant_id}/health-projections/{monitoring_resource_id}
```

Stable actions:

```text
monitoring.problem.read
monitoring.health.read
```

Every page/read re-establishes current authorization, tenant, filter and generation eligibility. IDs/cursors never grant authority.

## Cache behavior

- Problems list/detail: `no_store`;
- Health list/detail: accepted `private_revalidate`;
- errors never become public/shared cache entries.

## Frontend authority

Authorized states include:

- Problem loading/empty/active/resolved/historical/incomplete/unavailable/forbidden;
- canonical severity;
- Problem opened/resolved/last-confirmed times;
- Health loading/unknown/healthy/degraded/unhealthy/stale/incomplete/reconciliation-required/unavailable/forbidden;
- bounded canonical problem/reason references;
- explicit historical/non-current presentation.

The UI MUST NOT:
- resolve a Problem from omission;
- compute Health from visible Problems;
- map provider severity directly to Health;
- treat no visible Problems as healthy;
- treat provider ACK as JLMirror ACK.

## Explicit non-authority

This gate does not authorize:

- new Problem or Health persistence;
- modification of accepted ingestion/derivation semantics;
- direct provider passthrough or provider calls;
- Alert creation/resolution/policy/evaluation;
- G6 Monitoring→Alerting transport changes;
- ACK/responsibility/visibility state;
- notifications/escalation/routing;
- ITSM incidents/tickets/tasks;
- Automation/AIOps behavior;
- provider write-back;
- source replacement/cutover;
- canonical device taxonomy/classification;
- production deployment/C3 numerics;
- raw unrestricted provider payloads;
- shared Monitoring/G1–G4 substrate modification without successor authorization.

## Required proof before later implementation merge

- exact allowlist diff;
- semantic scope guard rejects Alerting/ACK/ITSM/provider passthrough/new persistence;
- current auth and cross-tenant tests;
- accepted Wave 4 Problem State and Health Projection reuse proof;
- response-contract tests;
- active/historical-generation truthfulness;
- omission/incomplete-evidence falsification;
- healthy requires authoritative completeness proof;
- Problem activation/recovery browser E2E;
- Health transition browser E2E;
- cache-profile tests;
- cursor/anchor current-authority tests;
- runtime/container proof;
- exact-head CI green;
- trusted scope/readiness evidence;
- panoramic/adversarial review;
- separate explicit owner merge authorization.

```text
G4_AUTHORIZED != G5_AUTHORIZED
G5_AUTHORIZED != G6_AUTHORIZED
PROBLEM != ALERT
HEALTH != ALERT
PROVIDER_ACK != JLMIRROR_ACK
IMPLEMENTED != PRODUCTION_READY
GREEN_STATUS != MERGE_AUTHORIZATION
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
