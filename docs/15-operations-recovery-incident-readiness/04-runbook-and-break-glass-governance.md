# Phase 15 — Runbook and Break-Glass Governance

**Status:** proposed baseline

## Core law

```text
RUNBOOK != AUTHORITY
RUNBOOK PROFILE ID != LOCALLY INVENTED PROCEDURE AUTHORITY
BREAK-GLASS != AUTHORITY ESCAPE HATCH
UNKNOWN DUAL-CONTROL APPLICABILITY != NO_APPLICABLE_CASE
```

A runbook encodes an accepted procedure and its preconditions. It cannot create authority missing from Product, Security, domain, data, API/event, runtime or release contracts.

## Mandatory runbook classes

```text
runbook.diagnose@1
runbook.degraded-operation@1
runbook.recovery@1
runbook.crypto-secret-recovery@1
runbook.redrive-replay-quarantine@1
runbook.relocation@1
runbook.release-forward-recovery@1
runbook.break-glass@1
runbook.maintenance-decommission@1
runbook.incident-closure@1
```

Each runbook profile below materializes owner, required roles, authoritative preconditions, allowed procedure/effect boundary, prohibited substitutions and falsification vectors. A future serialized runbook may add implementation steps only inside that profile; it cannot broaden authority, remove a precondition, substitute a local tool state for an accepted authority, or silently reuse the profile ID for materially different semantics.

## Canonical role authority matrix

| Role | May coordinate/authorize within Phase 15 | SHALL NOT substitute for |
|---|---|---|
| `role.service-owner@1` | capability operating mode, escalation, accepted runbook applicability and service-level containment within inherited semantics | Product enablement, Security authorization, tenant placement, domain outcome, release/recovery eligibility |
| `role.incident-commander@1` | incident coordination, owner mobilization, change freeze, selection among already-accepted procedures, communication coordination | Product/Security/domain/placement/release/recovery authority or break-glass self-admission |
| `role.operations-executor@1` | execution of an admitted runbook step under current scoped authorization and preconditions | self-authorization, scope broadening, effect-outcome declaration, recovery/incident closure authority |
| `role.recovery-authority@1` | recovery quarantine/resumption decision using exact recovery profile, `R`, `F`, reconciliation and current owning-authority evidence | missing Security/Product/domain/release truth, effect absence, stale authority restoration |
| `role.break-glass-approver@1` | admission of the exact break-glass action/scope when current policy and dual-control selector permit | execution authority when separation forbids it, policy waiver, unknown-applicability override |
| `role.break-glass-executor@1` | exact admitted break-glass actions within scope/expiry/currentness | admission, scope expansion, audit/recovery/tenant/crypto bypass |
| `role.security-authority@1` | current Security-owned authorization, trust, tenant-isolation and crypto/currentness decisions | business/domain outcome, Product applicability, release effect outcome |
| `role.domain-outcome-authority@1` | owning business/process outcome and ambiguous external-effect reconciliation | Security/placement/release-policy authority or evidence fabrication |
| `role.communications-owner@1` | evidence-bounded internal/customer/public/regulatory communication within accepted classification | incident declaration/closure, recovery admission, Product commitment creation |
| `role.evidence-reviewer@1` | review of completeness, provenance and conformity of evidence | protected eligibility or authority unless the same principal separately holds an accepted owning role |

A person may hold multiple roles only where current accepted policy permits and every applicable separation-of-duty requirement remains satisfied. Physical staffing remains OPEN; logical role boundaries do not.

## Canonical runbook profile catalog

| Runbook profile | Primary owner profile | Required roles | Mandatory preconditions / authority inputs | Allowed procedure boundary | Forbidden substitutions | Required vectors |
|---|---|---|---|---|---|---|
| `runbook.diagnose@1` | owning `owner.*@1` capability profile | `role.operations-executor@1`; service/security/domain owner as data classification requires | current diagnostic authorization, exact capability/scope, accepted signal/evidence classification | read/inspect/correlate bounded evidence and identify missing proof; may recommend another accepted runbook | diagnostic access as mutation authority; logs/dashboard/AI/transcript as business, Security, recovery or Product truth | `OPRV-002`, `OPRV-033`, `OPRV-034`, `OPRV-049`, `OPRV-050`, `OPRV-059` |
| `runbook.degraded-operation@1` | exact Phase 15 service owner for the affected reliability profile | `role.service-owner@1`, `role.operations-executor@1`; incident commander when declared | exact Phase 11 failure/degradation profile, current scope/authority, capacity/admission state, applicable Phase 12 evidence | execute only accepted containment, draining, throttling, isolation, pause or bounded degraded-mode actions already allowed upstream | inventing a fallback, bypassing dedup/auth/fencing, exceeding accepted degradation envelope, treating vendor green as recovery | `OPRV-002`, `OPRV-003`, `OPRV-033..035`, `OPRV-041`, `OPRV-059` |
| `runbook.recovery@1` | applicable recovery-profile owner | `role.recovery-authority@1`, `role.operations-executor@1`; Security/domain/release owners where their authority is in scope | exact recovery profile/subscope, current authorization, quarantine, `R`, `F_or_unproven`, `(R,F]` inventory, reconciliation IDs, current Security/governance/runtime/release evidence | restore/failover/reconcile/fence and perform evidence-driven `blocked -> partially_admitted -> fully_admitted` transitions | restore/health as admission, missing state as absence, unknown shared authority as partial admission, stale writer/generation resurrection | `OPRV-009..015`, `OPRV-019..024`, `OPRV-048`, `OPRV-052..056`, `OPRV-059` |
| `runbook.crypto-secret-recovery@1` | `owner.security-identity@1` | `role.security-authority@1`, `role.recovery-authority@1`, `role.operations-executor@1` under scoped privilege | current crypto/secret policy, exact key/verifier/secret-reference generation/scope, revocation/erasure state, recovery boundary/evidence | recover/re-establish narrowly authorized current crypto/secret capability or historical proof authority | secret/key material in ordinary evidence, retired verifier as unrelated current authority, revocation/erasure reversal | `OPRV-015..018`, `OPRV-045`, `OPRV-051`, `OPRV-052`, `OPRV-059` |
| `runbook.redrive-replay-quarantine@1` | `owner.async-messaging@1` or applicable integration owner | `role.operations-executor@1`, current privileged authorizer, `role.domain-outcome-authority@1` when effect ambiguity exists | current tenant/placement/contract/generations, stable operation/message/delivery identity, dedup/content-equivalence/effect reconciliation, compatibility and capacity admission | disposition quarantine and perform only contract-eligible redrive/replay using preserved identities/fences | queue age/DLQ button/AI as eligibility; new identity to bypass ambiguity; dedup/equivalence/current-auth bypass; unbounded replay | `OPRV-025..028`, `OPRV-050`, `OPRV-059` |
| `runbook.relocation@1` | `owner.control-plane@1` | `role.recovery-authority@1`, `role.operations-executor@1`; Security/data/domain owners as affected | current Control Plane placement operation, source/target generations, target compatibility/admission, continuity transfer/reconciliation and source-fence evidence | execute the accepted source-fence/target-admission relocation workflow and controlled reverse relocation where admitted | manual pointer/routing edit as placement authority, rollback pointer flip after target write authority, stale source workers/sockets | `OPRV-019`, `OPRV-021`, `OPRV-023`, `OPRV-024`, `OPRV-042`, `OPRV-059` |
| `runbook.release-forward-recovery@1` | release/platform owner for the exact target | `role.operations-executor@1`, applicable release owner, `role.recovery-authority@1`; Security where trust/crypto is affected | exact Phase 14 `deployment_operation_id`, target-state/config/artifact/verifier evidence, rollback/forward/reconciliation class, current cell/runtime compatibility | continue/reconcile the same release operation or execute the already-classified forward/rollback path | new deployment identity to bypass ambiguity, rollback button as eligibility, stale config/policy/verifier/target state, emergency urgency as waiver | `OPRV-036..038`, `OPRV-051`, `OPRV-052`, `OPRV-059` |
| `runbook.break-glass@1` | `owner.privileged-operations@1` with Security policy authority | `role.break-glass-approver@1`, `role.break-glass-executor@1`; `role.security-authority@1` as policy owner | exact current break-glass policy/version, action/scope/reason, current authorization, dual-control applicability/evidence, expiry/revocation/audit sink | only the explicitly admitted exceptional actions for the approved scope and lifetime | self-admission, unknown dual-control -> N/A, scope broadening, permanent privilege, audit/tenant/erasure/crypto/recovery/release-fence bypass | `OPRV-004..008`, `OPRV-045`, `OPRV-055`, `OPRV-059` |
| `runbook.maintenance-decommission@1` | applicable platform/service owner | `role.service-owner@1`, `role.operations-executor@1`; recovery/security/governance owners as obligations require | exact maintenance/decommission scope, current placement/work/release/recovery state, degradation envelope, capacity, durable obligations, credential/route/data/evidence disposition | drain/maintain/retire only after accepted prerequisites and stale-authority fences are proven | zero replicas/empty dashboard as proof, silent degradation beyond envelope, deleting evidence/data/credentials before owning obligations resolve | `OPRV-039..041`, `OPRV-046`, `OPRV-059` |
| `runbook.incident-closure@1` | incident command with evidence governance | `role.incident-commander@1`, `role.evidence-reviewer@1`; affected service/recovery/security/domain owners for their dispositions | accepted closure criteria, affected capability safe/restored state, communication disposition, break-glass termination/review, `residual_obligation_disposition`, retained evidence | transition incident governance state only; create/retain follow-up ownership and post-incident review obligation | symptom/alert/vendor green/AI as closure authority; hiding residual ambiguity; changing underlying reconciliation-blocked operation identity or eligibility | `OPRV-001`, `OPRV-043`, `OPRV-044`, `OPRV-057`, `OPRV-059` |

### Runbook completeness and versioning rule

The exact profile IDs above are the canonical Phase 15 runbook set. Every operations-catalog or recovery-manifest runbook reference must resolve to one of these materialized definitions or a future explicitly accepted successor/version.

A conforming implementation SHALL reject:

- an unknown/local runbook alias used as if it were a canonical profile;
- a canonical profile whose required roles, preconditions or prohibited substitutions are omitted by the execution system;
- a local customization that broadens effect scope or weakens authority while retaining the same profile/version;
- resumption of a paused execution under a materially changed profile without explicit compatibility review/migration of the execution state;
- tool-generated steps that introduce a protected decision not present in the selected profile.

`OPRV-059` falsifies runbook-profile authority laundering.

## Runbook execution

`ops.runbook-execution@1` has stable execution identity and records the exact `runbook_profile@version` from the catalog above. Resume after pause/restart revalidates current authority, selected profile version, preconditions and underlying operation state rather than assuming old eligibility.

A runbook step that performs an effectful ambiguous operation preserves the owning stable operation ID/fence. Retrying the human step does not create a new effect identity by convenience.

## Break-glass session

Canonical record:

```text
break_glass_session_id
break_glass_policy_profile_and_version
requester
approver_authority
executor_principal
reason/incident_id
exact allowed actions
resource/tenant/cell/environment scope
start/expiry
revocation/currentness
dual_control_applicability_state
dual_control_policy_evidence
dual_control_execution_profile_or_NO_APPLICABLE_CASE
credential/reference profile
audit/evidence sink
post_use_review_owner/status
```

## Dual-control applicability

The canonical selector is closed:

```text
dual_control_applicability_state:
  required_by_current_policy
  not_required_by_current_policy_with_evidence
  applicability_unproven
```

Rules:

- `required_by_current_policy` requires the accepted current Security/Risk policy evidence and the required independent approval/execution constraints before admission;
- `not_required_by_current_policy_with_evidence` may use `dual_control_execution_profile_or_NO_APPLICABLE_CASE=NO_APPLICABLE_CASE`, but only with exact accepted policy evidence proving non-applicability for the same action/scope;
- `applicability_unproven` is fail-closed for break-glass admission. It is not `NO_APPLICABLE_CASE` and cannot inherit the less restrictive branch;
- `OPEN-OPS-010` owns the concrete dual-control implementation/applicability-mapping mechanism; it does not authorize an implementation to resolve unknown policy applicability locally.

`OPRV-055` falsifies applicability laundering.

## Admission

Break-glass requires explicit current policy and incident/operational justification. Where accepted Security/risk authority requires dual control, requester/approver/executor constraints are enforced; exact staffing/count/product remains OPEN.

No emergency condition turns a denied, stale or unknown authorization/dual-control state into allowed state automatically.

## Least privilege

Break-glass authority is narrower than ordinary administrator omnipotence. It is action-scoped, resource-scoped, time-bounded/revocable and cannot silently inherit broad credentials from a workstation or dashboard session.

## Forbidden break-glass bypasses

Break-glass cannot waive:

- tenant isolation and current placement;
- immutable audit/accountability;
- erasure/legal hold/crypto-erasure intent;
- cryptographic/verifier currentness;
- `(R,F]` reconciliation;
- ambiguous external-effect reconciliation;
- idempotency/dedup/content-equivalence requirements;
- release artifact/configuration integrity and operation fencing;
- stale-writer/source/destination generation fencing;
- Product applicability/architecture authority.

## Session end

Expiry/revocation removes further eligibility but does not erase effects already performed. Ambiguous effects remain reconciliation-required. Temporary credentials/tokens are revoked/retired; ordinary authority is re-established explicitly.

## Post-use review

Every material break-glass use is attributable and reviewable. Review compares requested scope, actual effects, authority/currentness, evidence completeness, unexpected access/effects and required follow-up.

Break-glass cannot self-certify its own safe completion.

## Tool/AI boundary

Automation may prefill evidence, detect policy mismatch or recommend a runbook. AI/tool output cannot select a runbook profile in a way that grants otherwise-missing authority, invent protected steps, admit break-glass, select the dual-control applicability state, broaden scope, waive dual control, decide recovery eligibility or close the incident.