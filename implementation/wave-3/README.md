# Wave 3 — Platform observability and release chain

**Authorized slices:** `impl.observability@1`, `impl.release-supply-chain@1`

This implementation establishes vendor-neutral executable conformance primitives for Phase 12 observability semantics and Phase 14 release/deployment semantics. It does not activate Product capabilities, establish production objectives, or select the remaining C2 backend/tool products.

## Authority boundary

The Python modules are portable reference/conformance code in the same implementation substrate established by Waves 1 and 2. They do not become normative authority over the accepted documents pinned in `source-registry.json`.

The Wave 3 authority bundle pins not only the Phase 12 semantic manifest but also the owning Phase 12 health/readiness contract and telemetry security/cardinality contract used by the executable health/cardinality guards. A local implementation mapping cannot silently replace those accepted owners.

Observability records may describe system state, but:

```text
TELEMETRY != BUSINESS/SECURITY/RECOVERY AUTHORITY
HEALTH != AUTHORIZATION
MISSING TELEMETRY != SUCCESS
CORRELATION != TRUST
SEMANTIC CLASS != UNBOUNDED TENANT/RESOURCE IDENTIFIER
HEALTH REASON CLASS != UNBOUNDED RUNTIME TOKEN
OUTCOME TOKEN != ACCEPTED OUTCOME TAXONOMY
NO_APPLICABLE_CASE != FREE-TEXT ASSERTION
PRODUCT SELECTOR VALUE != PRODUCT AUTHORITY EVIDENCE
```

Release records may control release-specific progression, but:

```text
UNTRUSTED SOURCE != TRUSTED RELEASE INPUT
BUILD SUCCESS != ARTIFACT TRUST
ARTIFACT EXISTS != PROMOTION AUTHORITY
PROMOTION EVIDENCE != INTERCHANGEABLE DEPLOYMENT EVIDENCE
BOOLEAN CURRENT != EVIDENCE LINEAGE
CURRENT POLICY PROFILE != SOURCE-TRUST TRANSITION LINEAGE
EVIDENCE REFERENCE != MUTABLE ALIAS/URL
ADMISSION BOOLEAN != SCOPED CURRENT-AUTHORITY PROOF
RECONCILIATION BOOLEAN != RECONCILIATION AUTHORITY
RECOVERY CLASSIFICATION BOOLEAN SET != SCOPED DURABLE EVIDENCE
REQUIRED HEALTH SET != RUNTIME EVIDENCE DISCRETION
PHASE 11 RELIABILITY JOIN != OPTIONAL HEALTH EVIDENCE
PHASE 13 RUNTIME PROFILE != RELEASE-POLICY-DISCRETIONARY RELIABILITY MINIMUM
RUNTIME.WORKER@1 != UNSPECIALIZED RELEASE TARGET
RUNTIME VERIFICATION POLICY CURRENTNESS != DIFFERENT PRE-EFFECT GATE POLICY LINEAGE
RUNTIME VERIFICATION EVIDENCE != REPLAYABLE ACROSS DEPLOYMENT SCOPE OR TARGET VERSION
HEALTH GATE EVIDENCE != REPLAYABLE ACROSS RELEASE TARGET STATE VERSION
RELEASE OUTCOME WITHOUT RETAINED EVIDENCE != DURABLE RELEASE RECORD
DEPLOYMENT SUCCESS != RUNTIME ADMISSION
RELEASE TARGET STATE != PLACEMENT/RUNTIME AUTHORITY
TIMEOUT/LOST RESPONSE != RELEASE EFFECT ABSENCE
```

## Implemented observability substrate

- exact Phase 12 core signal/health/SLI/alert profile IDs;
- bounded metric-dimension guardrails that keep request/message/operation IDs and raw URL/query material out of metric labels;
- Wave 3 classification and tenant-scope classes are finite reviewed implementation mappings rather than arbitrary runtime strings;
- operation classes require a bounded namespaced semantic shape, and metric `operation_class` cannot disagree with the enclosing signal record;
- `outcome_class` and duplicate/equivalence comparison outcomes are checked against accepted Phase 12 taxonomies;
- health readiness reason classes are finite/reviewed against the accepted Phase 12 health contract; arbitrary caller/tenant/provider strings cannot become reason classes merely because they look token-safe;
- `telemetry_missing` is the bounded Wave 3 mapping for Phase 12's missing-data=`unknown` condition and is not caller-defined taxonomy or a Product-specific reason class;
- ordinary-telemetry secret-bearing field rejection;
- missing/incomplete health evidence represented as `unknown`, never false-green;
- generic direct-SLI `NO_APPLICABLE_CASE` requires reason + owning authority profile + immutable `evidence:*` identity + exact scope binding + currentness;
- Product applicability is resolved only from current exact-scope selector evidence; missing Product evidence remains upstream OPEN, while stale/wrong-scope/wrong-selector evidence fails closed;
- Product disabled/enabled cannot be inferred from deployment, telemetry, catalog presence, a free-form string or a local boolean detached from current Product authority evidence;
- health objects expose no authority-grant path.

Extending the finite implementation mappings is a reviewed compatibility change. Untrusted tenant/resource/provider input cannot manufacture a new semantic class merely by matching a token regex.

No backend, collector, trace transport, dashboard, pager, sampling numeric, SLO numeric, retention numeric, or cardinality numeric is selected here.

## Implemented release substrate

- cryptographic immutable artifact identity distinct from mutable tags/locations;
- accepted source evidence binds exact Git source state, accepted source/change provenance, review/assurance provenance, and the source-trust policy profile/evidence that established the transition;
- the current build release-policy profile must match the policy profile bound to the accepted source-trust transition; a later `current=True` boolean cannot launder an older/different source-trust policy;
- build release policy, builder authority, declared-input integrity, provenance verifier currentness and artifact lifecycle each require immutable durable evidence lineage in addition to status/currentness fields;
- build, provenance and SBOM/dependency-inventory record identities are immutable `evidence:*` references rather than mutable aliases/URLs;
- promotion principal authority and promotion release-policy currentness require their own immutable evidence lineage;
- exact target configuration identity/generation/semantic profile;
- promotion records bind durable promotion/approval evidence plus exact target, validation scope, rollout scope, runtime profile set, schema/API/event compatibility state and validation/compatibility evidence identities;
- runtime profile IDs are restricted to the exact canonical Phase 13 set and duplicates/unknown profiles fail closed;
- any deployment containing `runtime.worker@1` carries one or more exact canonical Phase 13 worker specialization IDs; unspecialized workers, duplicate/unknown specializations and specialization without `runtime.worker@1` fail closed;
- runtime verification independently observes the same worker specialization set as the approved deployment intent, so a controller/runtime cannot substitute a different worker privilege/reliability class after admission;
- deployment admission rejects recombination of a promotion with different configuration-validation, rollout-compatibility or cell-compatibility evidence;
- deployment admission requires the exact five current-authority gate classes (`deployment_principal`, `release_policy`, `release_target_authority`, `reliability`, `security_recovery`), each carrying an owning authority profile/version, immutable evidence identity, exact deployment scope, expected target-state version and currentness;
- missing, duplicate, stale, wrong-scope, wrong-version or mutable-reference admission evidence fails closed;
- the durable deployment record retains all admission-gate evidence references so a later terminal record cannot lose the authority lineage that allowed the operation to start;
- configuration validation and rollout compatibility require current durable evidence references even when the target configuration happens to equal the validation configuration;
- stable `deployment_operation_id` create-or-observe semantics;
- `expected_release_target_state_version` stale-executor fencing;
- unresolved prior effectful operation blocks a fresh operation identity;
- missing/ambiguous effect observation moves to `reconciliation_required`;
- resolving `reconciliation_required` requires a separate current reconciliation-authority evidence record bound to the same deployment scope and current target-state version; a boolean is insufficient;
- effect confirmation/absence resolution requires durable target evidence and the deployment record retains both target evidence and reconciliation-authority lineage where applicable;
- runtime verification independently requires durable evidence for runtime admission, configuration currentness, release-policy currentness, verifier authority and owning health-admission policy; vendor/controller green is ignored as authority;
- the exact reliability/health gate requirements come from a dedicated current `release.runtime-verification-requirements@1` evidence record bound to the same deployment scope, post-effect release-target state version and the release-policy evidence lineage that authorized the pre-effect gate set; runtime verification must present that same release-policy lineage and cannot launder the gate set through a later unrelated `current=True` policy record;
- a legitimate release-policy change after effectful admission therefore blocks completion under the old requirements until governed re-authorization/reconciliation establishes a new eligible operation path; it is never inferred as equivalent from matching profile text alone;
- Phase 12 health-admission policy evidence remains independently current and may rotate without repinning the pre-effect gate set, because it adjudicates the already-required health profiles rather than selecting the requirement set itself;
- each Phase 13 runtime profile contributes its fixed non-conditional minimum Phase 11 reliability bindings before the release-policy authority may add deployment-specific conditional gates; `runtime.api@1`, for example, cannot omit transactional/session/cache/configuration reliability;
- each concrete worker specialization contributes its fixed Phase 13 minimum reliability bindings; contextual `worker.reconciliation@1` affected-profile bindings remain explicit pre-effect requirements rather than being guessed globally;
- every declared Phase 11 reliability profile contributes its accepted Phase 12 health bindings, and the requirements record cannot omit those implied health profiles;
- runtime health evidence must match the exact required gate set: missing, duplicate or unexpected gates fail closed;
- runtime verification evidence, requirements evidence and every individual health gate are bound to the exact `{target_id, deployment_operation_id}` scope and post-effect `release_target_state_version`, preventing cross-operation/target/version replay;
- completed deployment records retain runtime-verification evidence identity;
- rollback/forward-recovery/reconciliation classification requires an immutable evidence record, owning authority profile, exact release-scope binding and currentness before its compatibility/security/reliability booleans are interpreted;
- validation evidence for a different target configuration requires explicit semantic equivalence or target-specific validation;
- production secret-value copying cannot be used as configuration equivalence proof.

No CI vendor, registry, signing service, SBOM product, IaC/deploy product, release coordination backend, or physical environment mapping is selected here.

## Known residual limitations (require explicit decision, not silent omission)

Recorded 2026-08-26 from an adversarial audit of this HEAD. These are not implementation bugs
in the mechanical sense (all falsification tests pass against the properties actually claimed
above); they are gaps between what is enforced and what a first reading of the surrounding law
might assume is enforced.

- **`required_health_profile_ids` authorship independence is not closed for four runtime/worker
  profiles.** `RuntimeVerificationRequirements` has no principal/authority-class field (unlike
  `PromotionEvidence`, `BuildProvenanceEvidence`, `DeploymentAdmissionEvidence`), and
  `runtime.worker@1`, `runtime.untrusted-parser@1`, `runtime.edge-optional@1` and
  `worker.reconciliation@1` carry an empty non-conditional reliability floor
  (`RUNTIME_PROFILE_MINIMUM_RELIABILITY_BINDINGS` / `WORKER_SPECIALIZATION_MINIMUM_RELIABILITY_BINDINGS`
  in `verification.py`). A deployment declared with one of those profiles can have its entire
  required reliability/health gate set chosen by the same submitter requesting the deployment.
  See the `OPEN` comment at `verification.py` immediately above
  `RUNTIME_PROFILE_MINIMUM_RELIABILITY_BINDINGS` for the full analysis. **Not resolved here** --
  needs either a genuinely independent release-policy-authority evidence chain, or an explicit
  reviewed decision that the empty floor is intentional risk acceptance for those four profiles.

- **Telemetry health veto vs. `TELEMETRY != ... AUTHORITY` (Phase 12).** `verify_runtime`
  (`verification.py`) treats `HealthState.UNAVAILABLE`/`QUARANTINED`/`DRAINING` as an
  unconditional release block even when `health_admitted=True` (policy admission granted) --
  see `test_release.py::test_quarantined_health_cannot_be_released_even_if_complete`. The
  *positive* direction is correctly excluded from authority (`vendor_controller_green` is
  ignored, never a grant); this is the *negative*/veto direction. Read narrowly, a pure veto
  never grants permission, so it does not violate "telemetry SHALL NOT grant authorization" --
  and it is the fail-closed, monotonically-safer reading consistent with this project's
  "less evidence never implies more authority" principle. This wave keeps that behavior
  deliberately. Confirming this reading against the accepted Phase 12 text is an explicit
  decision for whoever owns `docs/12-observability-sre`, not something this implementation wave
  should settle unilaterally by editing an accepted normative document.

- **Out of scope for this wave, found during the same audit, tracked here so they are not lost:**
  a documented-but-unimplemented "protected realtime" WebSocket capability-admission mechanism
  (Wave 1, `docs/07-system-design/request-auth-and-authorization-lifecycle.md`); `MachineReplayAuthority.claim_once`
  being a `Protocol` without a persisted atomic compare-and-swap equivalent to
  `platform.advance_authority_fence` (Wave 1, `src/jlmirror_authority/machine.py`); and both
  `system.async_consumer_inbox` atomicity against a real multi-connection Postgres (Wave 2,
  `src/jlmirror_async/inbox.py` proves atomicity only via an in-process `RLock`) and
  outbox+domain-mutation atomicity (Wave 2) having no domain/use-case call site yet to enforce
  against. These are Wave 1/Wave 2 files already accepted on `main`; correcting them belongs in a
  dedicated corrective PR against those waves, not a silent edit bundled into Wave 3.

## Scope guard

This wave is platform substrate only. It does not create customer/domain endpoints, enable outbound webhook/realtime/artifact Product branches, claim production SLOs, or authorize Wave 4.

`READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.
