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
```

Release records may control release-specific progression, but:

```text
UNTRUSTED SOURCE != TRUSTED RELEASE INPUT
BUILD SUCCESS != ARTIFACT TRUST
ARTIFACT EXISTS != PROMOTION AUTHORITY
PROMOTION EVIDENCE != INTERCHANGEABLE DEPLOYMENT EVIDENCE
BOOLEAN CURRENT != EVIDENCE LINEAGE
EVIDENCE REFERENCE != MUTABLE ALIAS/URL
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
- explicit `NO_APPLICABLE_CASE` reason requirement;
- Product applicability unknown fails closed rather than becoming disabled/enabled;
- health objects expose no authority-grant path.

Extending the finite implementation mappings is a reviewed compatibility change. Untrusted tenant/resource/provider input cannot manufacture a new semantic class merely by matching a token regex.

No backend, collector, trace transport, dashboard, pager, sampling numeric, SLO numeric, retention numeric, or cardinality numeric is selected here.

## Implemented release substrate

- cryptographic immutable artifact identity distinct from mutable tags/locations;
- accepted vs untrusted source trust classes;
- exact target configuration identity/generation/semantic profile;
- promotion records bind durable promotion/approval evidence plus exact target, validation scope, rollout scope, runtime profile set, schema/API/event compatibility state and validation/compatibility evidence identities;
- durable release evidence references use explicit immutable `evidence:*` record identities; mutable aliases/URLs are rejected by the reference model;
- deployment admission rejects recombination of a promotion with different configuration-validation, rollout-compatibility or cell-compatibility evidence;
- configuration validation and rollout compatibility require current durable evidence references even when the target configuration happens to equal the validation configuration;
- stable `deployment_operation_id` create-or-observe semantics;
- `expected_release_target_state_version` stale-executor fencing;
- unresolved prior effectful operation blocks a fresh operation identity;
- missing/ambiguous effect observation moves to `reconciliation_required`;
- effect confirmation/absence resolution requires durable target evidence and the deployment record retains that evidence lineage;
- runtime verification independently requires current durable verification evidence, current runtime admission and Phase 12 health evidence; vendor/controller green is ignored as authority;
- completed deployment records retain runtime-verification evidence identity;
- validation evidence for a different target configuration requires explicit semantic equivalence or target-specific validation;
- production secret-value copying cannot be used as configuration equivalence proof.

No CI vendor, registry, signing service, SBOM product, IaC/deploy product, release coordination backend, or physical environment mapping is selected here.

## Scope guard

This wave is platform substrate only. It does not create customer/domain endpoints, enable outbound webhook/realtime/artifact Product branches, claim production SLOs, or authorize Wave 4.

`READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.
