# Business Rules

**Status:** accepted

Business rules define product semantics independent from controllers, tables, queues, caches, or frameworks.

## Tenancy

**BR-TEN-001** — One tenant represents one customer organization boundary for administration and protected operational data.

**BR-TEN-002** — Human-readable tenant name/slug may change; the platform tenant identity does not.

**BR-TEN-003** — Tenant lifecycle state governs whether new operational work may be admitted. Suspended or migrating tenants may have intentionally reduced capabilities according to the lifecycle policy.

**BR-TEN-004** — Tenant onboarding/provisioning and creation/activation of tenant users are distinct lifecycle concerns and need not share one transaction.

## Identity and access

**BR-AUTH-001** — Authentication establishes principal identity; it does not by itself grant access to tenant resources.

**BR-AUTH-002** — Tenant access requires an active membership or an explicitly privileged platform operation.

**BR-AUTH-003** — Default roles are convenience policy. Custom roles and permissions are first-class authorization concepts.

**BR-AUTH-004** — Feature enablement and authorization are independent. A feature can be enabled while access remains denied.

**BR-AUTH-005** — Machine/API principals are independently attributable and do not borrow a human user's implicit authority.

## Monitoring

**BR-MON-001** — Monitoring Source is an external data origin; Monitoring is the platform-owned domain.

**BR-MON-002** — Resource/device internal identity is stable across provider synchronization and is not defined solely by a provider-native identifier.

**BR-MON-003** — Temporary provider absence does not imply resource deletion. Synchronization may move resources through states such as active, missing, stale, and removed according to policy.

**BR-MON-004** — Current operational state and historical telemetry are distinct concerns and may use different physical storage/projection strategies.

## Alerting and ITSM

**BR-ALT-001** — Observation/Problem, Alert, Incident, and Ticket are distinct concepts.

**BR-ALT-002** — Not every alert creates an incident or ticket. Policy determines notification, correlation, suppression, escalation, automation, or ITSM creation.

**BR-ALT-003** — Notification delivery is not the source of truth for alert state.

**BR-ITSM-001** — Human-readable ticket/RFC numbers are business identifiers and are not database primary keys.

**BR-ITSM-002** — Maintenance windows may alter alert/SLA interpretation but do not erase historical observations.

## Automation

**BR-AUTO-001** — Automation definition, execution, workflow and scheduled task are distinct concepts with independent lifecycle/state.

**BR-AUTO-002** — An automation may require approval even if the principal has permission to request it.

**BR-AUTO-003** — Execution authorization is evaluated against the target scope and applicable policy, not only the script/workflow definition.

**BR-AUTO-004** — Retry must not cause an automation to execute the same logical irreversible side effect more than permitted by its idempotency contract.

## AIOps

**BR-AIOPS-001** — A derived AIOps finding never modifies historical source evidence to make the prediction appear correct.

**BR-AIOPS-002** — Confidence, algorithm/model/version and source window are part of the meaning of a derived finding when applicable.

## FinOps and Commercial

**BR-FIN-001** — Infrastructure/service cost analysis and the commercial relationship between JLMIRROR's operator and a customer are distinct business concerns even when they exchange information.

**BR-FIN-002** — Monetary values use explicit currency and non-floating-point monetary representation.

**BR-COM-001** — Provider payment identifiers are external references and do not replace platform-owned invoice/payment identity.

## Reporting and public output

**BR-REP-001** — Reports and dashboards consume owned data/projections; they do not become owners of the underlying operational entities.

**BR-REP-002** — Public status information is explicitly selected for publication. Internal severity, identifiers, topology, tenant metadata, or sensitive details are not public by default.

## Integration

**BR-INT-001** — External payloads are untrusted until validated and normalized.

**BR-INT-002** — Webhook acknowledgement/delivery failure does not roll back an already committed originating business transaction.

**BR-INT-003** — Integration retry state is explicit and bounded; permanent failures are surfaced rather than retried forever.

## Audit and compliance

**BR-AUD-001** — Audit represents accountability and may record that an action occurred even when application logs are expired.

**BR-AUD-002** — Audit records exclude secrets and minimize regulated/personal data to what accountability requires.

**BR-GOV-001** — Legal/compliance retention may override ordinary deletion for specific data, but the reason and scope must be explicit.

## Configuration

**BR-CONF-001** — Tenant configuration, platform configuration, feature enablement and secrets are separate concepts.

**BR-CONF-002** — A secret value is not returned after creation/rotation unless the corresponding secret lifecycle explicitly requires one-time presentation.
