# D4-D — Bounded C2 Security Profile Selection

## Status

This record governs the transition from **D4-D evidence complete (5/5), selection pending** to a **bounded C2 security-profile selection**.

Canonical selection base:

- `main@4b76249e351a1fe18e425541af6d10ae540b0af1`

Source decisions:

- `OPEN-EVT-016` — service-to-broker authentication/authorization;
- `OPEN-EVT-017` — message protection/KMS and historical verifier profile;
- `OPEN-EVT-018` — trace-context propagation.

This transition does not rewrite the historical candidate-evaluation plan or any source-evidence manifest. Those artifacts remain true for the time at which they were produced: candidate unselected, no selection authority, no auto-credit.

## Selected bounded C2 profile

### Axis A — workload identity to broker credential

Selected mechanism class:

- **`derived_short_lived_broker_native_credential_adapter`**

The canonical workload identity remains owned by `IR-D-002`. The broker credential is a replaceable, short-lived, least-privilege derivation used only to obtain broker transport authority within the selected role/contract scope.

The broker credential is not platform identity authority. Rotation or replacement of the broker credential must not change the canonical workload identity, and stale/revoked workload authority cannot mint or retain current broker authority.

No concrete workload-identity provider, mTLS PKI product, OIDC vendor or broker credential product is selected here.

### Axis B — tenant and contract scoped broker authorization

Selected mechanism class:

- **`broker_acl_projection_adapter`**

Broker authorization is a projection of current platform authorization, scoped by tenant, service/domain, broker role and contract. Broker-native policy or ACL state is never independent business authority.

Cross-tenant access, wildcard grants, broad administrative roles and stale authorization generations remain fail-closed. The projection must be reconcilable from current platform authority.

The class name does not require one specific broker ACL implementation. A policy engine or broker-native authorization implementation may replace the physical adapter only if it preserves the same projection semantics and passes equivalent review.

### Axis C — message protection, KMS and historical verifier continuity

Selected mechanism class:

- **`kms_backed_envelope_or_transport_protection_profile`**

Selected invariant profile:

- protection is controlled by data classification;
- key material remains behind accepted secret/KMS authority;
- retained evidence stores only non-secret profile/key-generation references;
- historical verifier continuity survives rotation for the supported horizon or is replaced through equality-preserving governed migration;
- missing/unknown verifier authority fails closed for duplicate-sensitive effects;
- encryption never substitutes for minimization or authorization.

No KMS vendor, crypto algorithm, key type, rotation interval or production key topology is selected here.

### Axis D — secret and credential exclusion / erasure boundary

Selected mechanism class:

- **`reference_only_secret_authority_profile`**

Ordinary message payloads, inbox payloads, logs, traces and quarantine records cannot carry secret, credential or key material. Where correctness requires durable historical verification, only non-secret references may survive.

A secret reference is not bearer authority. Resolution remains narrowly authorized and audited, and secret-store outage cannot degrade to plaintext or unverified acceptance.

No secret-store vendor or secret-handle product is selected here.

### Axis E — trace context

Selected mechanism class:

- **`w3c_trace_context_bounded_profile`**

The selected profile uses bounded, validated W3C Trace Context semantics for `traceparent`, with governed bounded/canonical handling of `tracestate` and deny-by-default bounded/redacted attributes.

Trace context remains observability only. It is never tenant authority, authorization authority, idempotency identity, ordering identity, message identity or business-effect authority. Missing or malformed tracing cannot alter delivery/business semantics.

No tracing/APM vendor is selected here.

## Cross-axis security rules

The selected profile is one replaceable C2 adapter/profile boundary. It does not permit one axis to become authority for another.

The following remain mandatory:

- broker/vendor identity never becomes canonical platform workload or tenant identity;
- broker authorization remains a projection of current platform authority;
- internal network or broker presence never establishes trust;
- secret/key/credential material never enters ordinary event/recovery/observability records;
- historical verifier continuity survives rotation or requires equality-preserving governed migration;
- trace context never becomes business/security authority;
- physical products are replaceable adapters beneath the selected semantic/security profile.

## Selection is not implementation or D4 acceptance authority

After this transition:

- D4-D evidence remains `5/5`;
- D4-wide evidence remains `26/26`;
- D4-D becomes `selected_candidate` at bounded C2 security-profile scope;
- D4 global gate remains `scoped`;
- `d4_transport_authority=selected_not_granted`;
- canonical Product implementation authority remains `not_granted`;
- Wave 4 implementation authority remains `not_granted`;
- production authority remains `none`;
- C3 numeric/topology authority remains `not_selected`;
- full D4 acceptance remains a separate governed transition.

Therefore this selection does **not**:

- accept D4;
- authorize Product or Wave 4 implementation;
- authorize production deployment;
- select an identity provider, KMS, secret manager or tracing vendor;
- select a cryptographic algorithm, key type or rotation interval;
- grant broker-native ACL/policy state independent business authority;
- choose production partition/retry/retention/replay/topology numerics.

## Historical truth remains immutable

The D4-D candidate-evaluation plan intentionally retains:

- `selection_state=not_selected`;
- `selection_authority=not_granted`;
- `separate_selection_required=true`.

All five source-evidence manifests intentionally retain:

- `candidate=null`;
- `candidate_status=not_selected`;
- `selection_authority=not_granted`;
- `current_run_auto_credit=false`;
- their original source-time D4-wide state.

Current D4-D selection authority is represented only by:

- `implementation/d4-eventing-async/d4-d-selection-record.json`;
- `implementation/d4-eventing-async/d4-d-evidence-plan.json`;
- `implementation/d4-eventing-async/state-manifest.json`.

## Replacement governance

A material change to a selected D4-D mechanism class requires a separate governed transition with equivalent-or-stronger evidence for the affected axis.

Physical vendor/product replacement inside a selected mechanism class does not redefine canonical identity, tenant authority, contract meaning, message identity or security semantics. A replacement implementation must prove conformance before receiving implementation authority.

## Merge and acceptance governance

This selection may merge only after:

1. exact-HEAD CI is clean;
2. D4-D plus related D4 panoramic/adversarial review is clean;
3. all material review threads are resolved;
4. the PR is mergeable;
5. separate explicit user authorization for squash merge is given.

Merging this selection record still does not constitute full D4 acceptance. D4 acceptance remains a separate transition after the required terminal disposition of every D4 track is confirmed.
