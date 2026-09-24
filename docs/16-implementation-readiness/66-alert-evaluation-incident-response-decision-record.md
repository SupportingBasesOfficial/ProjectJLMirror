# 66 — Alert Evaluation and Incident Response Decision Record

**Status:** proposed — model selected; closure conditions below are binding before Alert Policy/Evaluation and the ApplicationErrorEvent inbound path are treated as implementation-authorized
**Decision class:** C1/C2 (Alert Policy/Evaluation semantics are C1 fixed; IncidentResponsePolicy per-tenant configuration is C2 product selection)
**Drivers:** `ADR-019` (event-driven), `ADR-005` (tenant isolation), G5 (Problem/Health), G6 (Alerting transport), G7 (Alert Policy Lifecycle), G9 (Notification), G10 (ITSM), Product requirement: per-tenant auto-ticket and automation configuration

This document proposes a candidate resolution for the "Alert Policy/Evaluation" open question and proposes `ApplicationErrorEvent` plus `IncidentResponsePolicy`. The open question remains open, and neither concept gains implementation or mutation authority, until this record is accepted through governance.

## Context and problem

`OPEN-QUESTIONS-AND-DEFERRED.md` lists: "exact Alert Policy/Evaluation DSL/model remains unaccepted; exact grouping/correlation/dedupe semantics remain unaccepted; automatic Alert create/resolve remains blocked." This record proposes a policy model for a future gate while keeping G10-and-below accepted semantics unchanged. Any conflict with existing G5-G10 authority must be resolved in favor of the already-accepted contracts unless separately authorized.

Additionally, the product vision requires: when a monitored application or infrastructure system encounters an error or incident, the platform must:
1. ingest the event automatically (push API from the monitored system);
2. evaluate it against the tenant's configured policy;
3. trigger the configured downstream actions (open ITSM ticket, notify channels, run automation) without manual human intervention — unless the tenant has configured manual-only mode.

This is distinct from the current G6/G7 flow where alerts are derived from ProblemState/HealthProjection changes within JLMirror's own monitoring stack.

## Requirements and invariants this selection must satisfy

- ADR-019: alert evaluation is event-driven; no polling loop owns Alert creation authority.
- ADR-005: IncidentResponsePolicy is per-tenant; one tenant's configuration cannot affect another's alert lifecycle.
- G5/G6: existing ProblemState ACTIVE→RESOLVED and HealthProjection DEGRADED/UNHEALTHY transition events remain the primary alert creation sources; this record extends, not replaces, that path.
- G7: Alert lifecycle (OPEN → ACKNOWLEDGED → RESOLVED → CLOSED) is unchanged; new inbound events must feed into the same lifecycle.
- No Alert is created or resolved without a traceable, authorized event source (audit requirement).
- AIOps findings must not silently gain authority over Alert lifecycle (OPEN-QUESTIONS-AND-DEFERRED.md constraint preserved).

## Decision

### Proposed alert evaluation model — three candidate inbound event types

If accepted, the proposed evaluator would consume exactly these candidate event types. This section does not expand current G5-G7 authority:

#### Type 1 — ProblemState transition events (existing, G5/G6)
- `ProblemState` transitions to `ACTIVE` → evaluate Alert creation policy for the affected resource/tenant.
- `ProblemState` transitions to `RESOLVED` → evaluate Alert auto-resolve policy; if no open policy exception, resolve the linked Alert.
- Grouping/correlation: within a single evaluation window (configurable, default 60 s), multiple ProblemState events for the same resource group are correlated into a single Alert. The grouping key is `(tenant_id, resource_id, problem_category)`. Dedupe is idempotent: a second event for an already-open Alert for the same key updates the Alert's evidence set, not a new Alert.

#### Type 2 — HealthProjection change events (existing, G5/G6)
- `HealthProjection` transitions to `DEGRADED` or `UNHEALTHY` → treated as an alert signal for the aggregate resource group.
- `HealthProjection` returns to `HEALTHY` → evaluate Alert auto-resolve if no overriding open ProblemState.
- Grouping key: `(tenant_id, resource_group_id, health_dimension)`.

#### Type 3 — ApplicationErrorEvent (NEW, PROPOSED; not authorized by this record while status is proposed)
- A monitored application or infrastructure system pushes an error/incident event to the platform via an authenticated inbound REST API endpoint.
- This event type represents a push from the monitored side, as opposed to the pull/observation model of G2-G5.
- The event carries:
  - `tenant_id` (mandatory; authenticated at the BFF boundary — the push credential is tenant-scoped)
  - `application_id` (the monitored application, registered in G3 resource inventory)
  - `error_code` / `error_message` (the raw error from the monitored system)
  - `occurred_at` (ISO 8601; the time the error occurred in the source system, not the ingestion time)
  - `principal_id` (optional; the user or service account that was active when the error occurred)
  - `operation` (optional; the operation/process/function where the error was raised)
  - `session_context` (optional; opaque context string from the source system, e.g. request ID, session ID)
  - `severity_hint` (optional; `LOW | MEDIUM | HIGH | CRITICAL`; advisory only — tenant policy governs actual severity)
  - `raw_payload` (optional; structured or unstructured additional context; stored but not parsed for business logic)
- The inbound API endpoint authenticates the push source via the external machine principal profile (OAuth 2.0 Client Credentials + `private_key_jwt`), not a shared API key.
- `ApplicationErrorEvent` feeds into the same Alert evaluation pipeline as Type 1/2 events; the evaluator treats it as a problem signal, not a pre-formed Alert.

### IncidentResponsePolicy — per-tenant configuration

Each tenant has exactly one `IncidentResponsePolicy` record (created with defaults at onboarding; updatable by tenant admins). The policy governs what happens when an alert evaluation triggers a response.

Schema:

```
IncidentResponsePolicy {
    tenant_id:               UUID (PK, FK tenants)
    severity_threshold:      ENUM(LOW, MEDIUM, HIGH, CRITICAL)  -- minimum severity to trigger any automated response
    auto_open_ticket:        BOOLEAN DEFAULT false               -- automatically open ITSM ticket on alert open
    itsm_integration:        ENUM(NONE, JIRA, SERVICENOW, GLPI) -- which ITSM adapter to use
    notify_channels:         JSONB   -- [{channel_type, channel_config, on_severities: [...]}]
    automation_triggers:     JSONB   -- [{trigger: ALERT_OPEN|ACK|RESOLVE, runbook_id, condition: ...}]
    manual_override_only:    BOOLEAN DEFAULT false               -- when true: no automated actions; all manual
    created_at, updated_at
}
```

Evaluation rules:
1. If `manual_override_only = true`: no automated action is taken; the alert is opened and the operator sees it in the NOC dashboard only.
2. If alert severity < `severity_threshold`: no automated response beyond the alert record itself.
3. If `auto_open_ticket = true` and severity ≥ threshold: the ITSM adapter opens a ticket with the alert's evidence set as the description. The ticket includes: `occurred_at` (for ApplicationErrorEvent: the source-reported time), `error_message`, `operation`, `principal_id`, `application_id`, `session_context` — the fields the product vision described as essential for direct-to-root-cause investigation.
4. `notify_channels` entries are evaluated in order; each matching severity entry dispatches a notification via the NotificationPort/channel model proposed in record 67, only after that record is separately accepted.
5. `automation_triggers` entries are evaluated against the alert lifecycle event; matching entries enqueue a runbook execution in the Automation subsystem (G11, future).

### Policy conflict and precedence

- A single alert can match at most one `IncidentResponsePolicy` (tenant-scoped, always unique).
- There is no cross-tenant policy inheritance.
- If the policy evaluation itself fails (policy record missing, ITSM adapter error, notification adapter error): the alert is still created and opened; the failed downstream action is logged as a `ResponseActionFailure` audit event and retried with bounded exponential backoff (max 3 retries, 5 min cap).
- Policy changes take effect for new alerts only; already-open alerts retain the policy evaluation that was active at open time (captured as a JSON snapshot in the alert record).

### Alert evaluation timing/debounce

- For Type 1/2 events: a configurable debounce window (per-tenant, default 30 s) suppresses duplicate signals for the same grouping key within the window.
- For Type 3 (ApplicationErrorEvent): no debounce by default; each event produces at most one evaluation cycle, but deduplication uses `(tenant_id, application_id, error_code, occurred_at rounded to 1-minute bucket)` as the dedupe key for a 5-minute window to prevent event-replay storms.
- The debounce and dedupe windows are stored configuration, not hard-coded constants.

### Proposed automatic Alert create/resolve authority (not yet granted)

If this record is later accepted, a subsequent implementation authorization may permit automatic Alert create/resolve under the following candidate conditions. While status is proposed, this text grants no Alert mutation authority:
- CREATE: any evaluation cycle produces an OPEN alert only when no open alert for the same grouping key already exists.
- RESOLVE: automatic resolution is triggered by a matching RESOLVED/HEALTHY event only if `IncidentResponsePolicy.manual_override_only = false`; if `manual_override_only = true`, resolution requires an operator ACK action.
- AIOps findings (future G12) may provide evidence to the evaluator but cannot directly create or resolve alerts without a separately authorized AIOps authority contract.

### Closure conditions

**Closure 1 — ApplicationErrorEvent inbound API (binding)**
Before any future accepted push API could be considered production-eligible:
- inbound credential authenticates to the correct tenant scope; a credential for tenant A cannot push events that create alerts for tenant B;
- `occurred_at` from the source is preserved exactly in the alert evidence and in the ITSM ticket body;
- a replay of the same event within the 5-minute dedupe window produces exactly one alert, not N;
- missing/invalid mandatory fields reject at the API boundary with a 422 and a structured error body.

**Closure 2 — IncidentResponsePolicy enforcement (binding)**
Before any future accepted auto-ticket path could be considered production-eligible:
- `manual_override_only = true` produces zero downstream automated actions;
- severity below threshold produces zero downstream automated actions;
- ITSM ticket body contains all required fields (`occurred_at`, `error_message`, `operation`, `principal_id`, `application_id`, `session_context`);
- a failed ITSM adapter call logs a `ResponseActionFailure` and retries; it does not prevent the alert from opening.

## Consequences

### Positive
- operators receive automatic tickets enriched with the context they need to go directly to root cause;
- tenant administrators can configure fully automated or fully manual response per their operational maturity;
- the ApplicationErrorEvent push model enables monitoring of application-side errors that are invisible to infrastructure metric collectors.

### Negative / cost
- per-tenant policy snapshot at alert-open time increases alert record size;
- the 5-minute dedupe window for ApplicationErrorEvent requires a durable dedupe state (PostgreSQL dedupe table or Redis set with TTL);
- IncidentResponsePolicy JSONB columns for channels and triggers must be validated at write time, not only at evaluation time.

## Validation

- alert created from ProblemState ACTIVE event; policy with `auto_open_ticket = true` produces ITSM ticket within 30 s;
- alert created from ApplicationErrorEvent with all optional fields; ticket body contains `occurred_at`, `principal_id`, `operation`;
- policy with `severity_threshold = HIGH`; LOW severity alert produces no ticket and no notification;
- `manual_override_only = true`; CRITICAL severity alert produces no automated action;
- replay of ApplicationErrorEvent within 5-minute dedupe window; exactly one alert exists.

## Exit / revisit conditions

Revisit if the grouping/correlation semantics need DSL-level expressibility (e.g., CEL or OPA-based evaluation), if AIOps (G12) requires a richer co-evaluation model, or if ApplicationErrorEvent volume requires a streaming ingest path (Kafka consumer) rather than a synchronous REST endpoint.
