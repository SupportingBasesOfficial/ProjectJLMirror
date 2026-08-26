# Wave 3 — Platform observability and release chain

**Authorized slices:** `impl.observability@1`, `impl.release-supply-chain@1`

This implementation establishes vendor-neutral executable conformance primitives for Phase 12 observability semantics and Phase 14 release/deployment semantics. It does not activate Product capabilities, establish production objectives, or select the remaining C2 backend/tool products.

## Authority boundary

The Python modules are portable reference/conformance code in the same implementation substrate established by Waves 1 and 2. They do not become normative authority over the accepted documents pinned in `source-registry.json`.

Observability records may describe system state, but:

```text
TELEMETRY != BUSINESS/SECURITY/RECOVERY AUTHORITY
HEALTH != AUTHORIZATION
MISSING TELEMETRY != SUCCESS
CORRELATION != TRUST
SEMANTIC CLASS != UNBOUNDED TENANT/RESOURCE IDENTIFIER
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
- completed deployment records retain runtime-verification evidence identity;
- validation evidence for a different target configuration requires explicit semantic equivalence or target-specific validation;
- production secret-value copying cannot be used as configuration equivalence proof.

No CI vendor, registry, signing service, SBOM product, IaC/deploy product, release coordination backend, or physical environment mapping is selected here.

## Scope guard

This wave is platform substrate only. It does not create customer/domain endpoints, enable outbound webhook/realtime/artifact Product branches, claim production SLOs, or authorize Wave 4.

`READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.
