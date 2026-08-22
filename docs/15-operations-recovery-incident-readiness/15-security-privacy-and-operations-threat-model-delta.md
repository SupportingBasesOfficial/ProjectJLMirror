# Phase 15 — Security, Privacy and Operations Threat-Model Delta

**Status:** proposed baseline

## Trust boundaries

Phase 15 adds/refines:

- alert/telemetry -> incident declaration;
- incident commander -> operational owners;
- operator -> runbook execution;
- break-glass requester -> approver -> executor -> protected target;
- backup/restore mechanism -> recovery quarantine;
- restored state -> current authority/reconciliation;
- recovery operator -> Control Plane/cell/tenant scopes;
- telemetry restore -> operational-observability vs customer-monitoring continuity;
- artifact restore -> artifact bytes/integrity vs lifecycle/delivery/disclosure/release authority;
- recovery process -> crypto/verifier/secret authority;
- operator -> quarantine/redrive/replay;
- operator -> relocation/maintenance/decommission workflows;
- incident/recovery evidence -> closure/admission review.

## Threats

### OPS-TM-001 — Incident authority laundering
Alert/vendor/AI signal becomes autonomous declaration/closure/privilege authority. Controls: accountable incident lifecycle and protected authority separation. `OPRV-001`, `OPRV-043`, `OPRV-050`.

### OPS-TM-002 — Runbook authority laundering
Procedure text or automation grants actions not authorized by current upstream state. Controls: runbook preconditions/currentness and stable effect IDs. `OPRV-002`, `OPRV-003`.

### OPS-TM-003 — Break-glass privilege escalation
Emergency context broadens actions/targets or bypasses separation. Controls: exact scope, approver, expiry/revocation, dual control where required. `OPRV-004..008`, `OPRV-045`.

### OPS-TM-004 — Recovery authority resurrection
Restore makes old authorization/placement/release/crypto state current. Controls: quarantine, R/F, forward reconciliation. `OPRV-009..015`, `OPRV-019`.

### OPS-TM-005 — Secret/evidence leakage
Sensitive material enters tickets/logs/transcripts or broad operator UIs. Controls: references, minimization, classification. `OPRV-016`, `OPRV-052`.

### OPS-TM-006 — Historical crypto misuse
Historical verifier/key needed for evidence becomes current authority for new work. `OPRV-017`, `OPRV-018`.

### OPS-TM-007 — Split writer after failover
Two cells/control authorities become effectful. Controls: generation/fencing/admission. `OPRV-020`, `OPRV-022`.

### OPS-TM-008 — Tenant isolation failure during restore
Physical backup location or cross-tenant tooling changes identity/scope. Controls: canonical tenant identity/current placement. `OPRV-021`.

### OPS-TM-009 — Relocation rollback laundering
Operator pointer-flips after target accepted writes. `OPRV-023`, `OPRV-024`.

### OPS-TM-010 — Redrive/replay as duplicate bypass
Operator/tool uses DLQ/replay convenience to skip effect/equivalence/currentness/capacity. `OPRV-025..028`.

### OPS-TM-011 — Realtime/webhook stale authority
Old sessions/tickets/destinations regain authority after recovery. `OPRV-029..031`.

### OPS-TM-012 — Artifact disclosure resurrection
Restored artifact existence becomes download/disclosure authority. `OPRV-032`.

### OPS-TM-013 — External status authority laundering
Vendor green or missing telemetry becomes local recovery/health truth. `OPRV-033..035`.

### OPS-TM-014 — Release ambiguity/rollback bypass
Incident tooling repeats timed-out deployment or uses rollback contrary to Phase 14. `OPRV-036..038`, `OPRV-051`.

### OPS-TM-015 — Unsafe decommission/maintenance
Operational cleanup/maintenance leaves stale authority or exceeds degraded envelope. `OPRV-039..041`.

### OPS-TM-016 — Cross-tenant priority abuse
Operator/AI ranking becomes hidden recovery priority authority. `OPRV-042`.

### OPS-TM-017 — Handoff/closure evidence loss
Command handoff or closure drops active blocker/operation context. `OPRV-043`, `OPRV-044`, `OPRV-052`.

### OPS-TM-018 — Game-day authority bleed
Rehearsal executes real production effects or invents business commitments. `OPRV-046..048`.

### OPS-TM-019 — Chat/transcript as truth
Unstructured operational text becomes authoritative state. `OPRV-049`.

### OPS-TM-020 — Customer telemetry continuity laundering
Operational-observability restore, process liveness or a lower restored customer-monitoring watermark is treated as proof that later durably accepted customer observations never existed. Controls: `recovery.telemetry@1` subscope separation, accepted observation identity and acceptance/projection/watermark reconciliation, no healthy-silence inference. `OPRV-034`, `OPRV-053`.

### OPS-TM-021 — Artifact lifecycle/disclosure authority resurrection
A backup restores artifact bytes/tag/access object older than retirement, revocation, erasure, delivery-generation or release-policy state and tooling re-enables download/deployment. Controls: immutable integrity separated from current lifecycle/delivery/disclosure/release authority, newer deny/retirement/erasure state precedence. `OPRV-032`, `OPRV-054`.

## Privacy

Operational evidence and incident communications minimize tenant identifiers, customer data, topology, credentials, secret references and confidential payloads. Production-derived test/recovery data requires governed purpose, minimization, residency and isolation.

Broad incident visibility does not grant broad data access. Diagnostic access remains purpose/scope bound and audited.

Telemetry recovery evidence does not expose raw customer-monitoring payloads merely to prove acceptance/projection continuity. Artifact recovery evidence does not expose artifact bytes, access capabilities or internal locations beyond the minimum needed for reconciliation.

## AI boundary

AI may summarize evidence, suggest hypotheses, draft communications or identify missing steps. It cannot be direct, indirect, intermediate or joint authority for authentication/authorization, tenant/placement authority, retry/redrive/replay/recovery eligibility, incident closure, break-glass admission, Product/architecture or protected release decisions.

## Recovery/security continuity

Restore/PITR cannot move revocation, erasure, legal hold, audit, reliability, cryptographic, release-policy/verifier, target-config/target-state, customer-monitoring acceptance/projection, artifact lifecycle/delivery/disclosure or placement authority backwards. Unknown continuity fails closed for protected operations.

## Portability

Replacing incident, paging, backup, KMS, telemetry, artifact-storage, runbook, access or evidence products must preserve logical authority, identity, currentness, evidence, failure and recovery semantics.