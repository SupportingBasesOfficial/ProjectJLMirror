# JLMirror Open Questions and Deferred Work

Status: canonical project-memory source
Last updated: 2026-09-23

This file records intentional non-decisions and deferred scopes so future contributors do not mistake absence for acceptance. Items that have been decided are marked **CLOSED** with a pointer to the closing record; they remain here for traceability.

## Alerting

- **CLOSED** — Alert Policy/Evaluation model: `docs/16-implementation-readiness/66-alert-evaluation-incident-response-decision-record.md` (proposed; awaiting acceptance).
- **CLOSED** — grouping/correlation/dedupe semantics: same record (§ "grouping key" and "debounce"); `(tenant_id, resource_id, problem_category)` is the canonical grouping key.
- **CLOSED** — timing/debounce/confirmation semantics: same record (configurable 30 s debounce for Type 1/2; 5-minute bucket dedupe for Type 3).
- policy conflict/precedence behavior: per-tenant policy is always unique (one record per tenant); no cross-tenant inheritance; **CLOSED** — see same record (§ "Policy conflict and precedence").
- policy edit behavior for existing active Alerts: policy changes take effect for new alerts only; open alerts retain the policy snapshot captured at open time. **CLOSED** — same record.
- **CLOSED** — automatic Alert create/resolve: authorized by `66-alert-evaluation-incident-response-decision-record.md` for G6+G7 event-driven paths. AIOps-driven create/resolve remains BLOCKED until G12 authority contract is accepted.

### Remaining open

- exact Alert evaluation DSL / CEL / OPA-based policy language: deferred until G12 AIOps co-evaluation requirement is clearer;
- AIOps findings authority contract: AIOps (G12) may provide evidence to the evaluator but cannot directly create/resolve alerts until a separate authority record is accepted.

## Human responsibility / ACK

- **CLOSED** — canonical persistence/API/event models: IMPLEMENTED in G8 (PR #169).
- **CLOSED** — exact responsibility roles/types: IMPLEMENTED in G8.
- ACK reversal existence: not yet accepted; G8 does not implement reversal.
- ACK comments/reasons vocabulary and permissions: not yet accepted.
- resource-level responsibility inheritance/delegation rules: not yet accepted.

## Notification / authoritative visibility

- **CLOSED** — channel capability model: `docs/16-implementation-readiness/67-notification-channels-decision-record.md` (proposed; awaiting acceptance).
- **CLOSED** — Email and Webhook integrations: authorized and IMPLEMENTED in G9 (PR #171); formalized in IR-D-067.
- **CLOSED** — SMS (Twilio) integration: authorized in IR-D-067; implementation deferred to G11 cycle.
- **CLOSED** — WhatsApp integration: authorized in IR-D-067 pending template governance; implementation deferred.
- which workflows require authoritative read evidence: not yet authorized; AuthoritativeViewRecord design remains open.
- exact authenticated JLMirror confirmation surface: not yet designed.
- privacy/retention rules for read/view receipts: not yet authorized.
- customer identity binding and delegation for approvals: not yet authorized.

## Response / approval

- quote/budget object ownership: may belong to Commercial/ITSM/another bounded context; not yet decided.
- approval lifecycle, expiration, cancellation, revision/requote semantics: not yet authorized.
- waiting-state vocabulary and SLA pause/continue rules: not yet authorized.

## Monitoring

- full Metric History product (retention/downsampling/query/export/scale policy): FOUNDATION substrate exists; complete history product is future work.
- advanced device taxonomy/vendor/model/role/topology: future work; partial foundations in G3.
- future additional monitoring source providers: undefined until separately authorized.

## ITSM / Automation / AIOps

- detailed Automation state machines and cross-domain contracts: G11 future; runbook execution authority not yet accepted.
- no assumption should be made that an Alert automatically creates an Incident without an explicit IncidentResponsePolicy authorizing it — see IR-D-066.
- no assumption should be made that an Alert automatically executes an automation — requires `automation_triggers` in IncidentResponsePolicy and G11 Automation authority.
- AIOps findings (G12) must not silently gain authority over Monitoring/Alerting lifecycle.

## Frontend / production

- **CLOSED** — frontend stack: `docs/16-implementation-readiness/65-frontend-stack-decision-record.md` (React 18 + Vite + TypeScript + shadcn/ui + Tailwind CSS + Recharts + TanStack Query; proposed, awaiting acceptance).
- **CLOSED** — initial authorized screens: same record (6 screens: shell/login gate, source list, resource inventory, active alerts, alert detail, NOC dashboard).
- final UX/navigation/NOC screen contracts beyond the 6 initial screens: incomplete; future screens (AIOps, FinOps, multi-region NOC) require separate authorization.
- production deployment/HA/DR/performance/capacity/security operations: require separate C3 evidence; IMPLEMENTED does not imply PRODUCTION-READY.

## Identity / session / fencing

- **CLOSED** — BFF session fence store: `docs/16-implementation-readiness/IR-D-003-fence-storage-decision-record.md` (PostgreSQL + 30 s TTL in-process cache; proposed, awaiting acceptance).
- **CLOSED** — workload identity (monolith phase): `docs/16-implementation-readiness/IR-D-002-workload-identity-decision-record.md` (PostgreSQL role-per-worker; proposed, awaiting acceptance).
- **CLOSED** — Keycloak IdP selection: `docs/16-implementation-readiness/IR-D-001-keycloak-idp-decision-record.md` (proposed, per IR-D-001 closure conditions).
- BFF multi-instance session fencing: BLOCKED until IR-D-003 Phase B is authorized (requires distributed invalidation mechanism; Redis pub/sub or PostgreSQL LISTEN/NOTIFY).

## Memory system

- this foundation establishes the corpus and validator contract;
- future accepted work should progressively backfill earlier phases/PRs with richer links and exact authority references;
- automation may later validate canonical main SHA and accepted PR chain against GitHub metadata, but must not silently rewrite repository truth.
