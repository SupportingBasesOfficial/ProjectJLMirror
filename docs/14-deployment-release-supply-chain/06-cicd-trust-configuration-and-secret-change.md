# Phase 14 — CI/CD Trust, Configuration and Secret Change Lifecycle

**Status:** proposed baseline

## CI/CD principal classes

Phase 14 defines logical release principals:

```text
principal.release-build@1
principal.release-publish@1
principal.release-promote@1
principal.release-deploy@1
principal.release-migrate@1
principal.release-verify@1
principal.release-emergency@1
principal.release-untrusted-validation@1
```

One implementation may map several classes to one platform only when effective permissions remain independently bounded and auditable.

## Least privilege

- `principal.release-untrusted-validation@1` can execute bounded tests/scans of not-yet-accepted source but cannot publish trusted release artifacts, sign trusted provenance, promote/deploy production, obtain migration authority or read production secrets;
- build principal cannot deploy production by default;
- publish principal can publish only artifact identities produced by accepted build authority;
- promotion principal cannot modify artifact bytes;
- deploy principal cannot forge promotion/provenance;
- migration principal is distinct from serving runtime and ordinary deploy authority where destructive privilege is needed;
- verification principal is read/observe oriented and cannot self-fix release state silently;
- emergency principal is bounded, exceptional and auditable.

## Trigger/context is not authority

A pull request, branch name, workflow trigger, repository membership, successful prior job or physical runner/environment selection SHALL NOT by itself select a more privileged principal class.

Not-yet-accepted source is evaluated under the untrusted-validation profile until an accepted source state and release policy authorize a trusted build. Candidate workflow/config changes are themselves untrusted inputs and cannot choose their own privileged execution context.

## Configuration lifecycle

Configuration is released as a separately identified semantic/operational input, not baked into per-environment rebuilds.

A configuration change has:

- exact configuration identity/generation;
- semantic configuration profile/version sufficient to compare release-relevant meaning;
- owning authority;
- compatibility/security classification;
- target environment/runtime scope;
- environment-scoped non-secret values and secret references;
- validation evidence;
- validation-to-target compatibility/equivalence evidence where evidence from another environment/scope is reused;
- promotion/deployment relationship;
- rollback/forward-recovery classification.

## Same artifact does not mean same environment configuration

The one-artifact rule applies to executable/deployable artifact identity. It does not require validation and production to use byte-identical environment configuration or the same secret references/values.

Required shape:

```text
immutable artifact A
 + validation configuration V
 -> validation evidence E

immutable artifact A
 + production configuration P
 + evidence that P preserves the validated release-relevant semantics,
   or target-specific validation for material differences
 -> production eligibility
```

Rules:

- production configuration has its own exact identity/generation;
- production secret references/credentials are not copied into validation merely to make configuration identical;
- environment-specific endpoints, resource tuning and secret references MAY differ only within accepted compatibility/security/runtime profiles;
- any difference affecting trust, authorization, tenant isolation, network/egress, Product behavior, failure/retry semantics, schema/API/event compatibility, runtime authority, SLI meaning, recovery or release gates is material and requires explicit review plus applicable validation;
- evidence from `validation.general@1` or `validation.reference-cell@1` cannot be reused for production configuration P unless the relevant difference is explicitly shown compatible/equivalent or separately validated;
- “same artifact” is never evidence that a materially different production configuration is safe.

The exact configuration-diff/equivalence mechanism remains under `OPEN-RLS-017`; the requirement to account for semantic differences is fixed.

## Secret lifecycle

Artifacts and ordinary configuration contain secret references, not production secret values. Secret rotation/revocation is independently governed and does not require artifact rebuild unless artifact semantics truly change.

Release automation receives only scoped secret references/credentials needed by its stage. Logs/provenance/SBOM must not contain secret values. Untrusted validation has a distinct secret policy and receives no production/release credential merely because candidate source references a secret name.

Configuration compatibility compares secret purpose/reference policy and consuming semantics, not secret values. Production secret material is not exported into validation to prove equivalence.

## Configuration vs Product authority

Feature/config/environment state cannot resolve Product applicability or authorization merely because a release toggles a component. Product authority remains upstream.

## Pipeline resumption

A pipeline retry/resume revalidates current approval/principal/artifact/config/target authority. A stale paused job cannot continue because it once held permission. Revalidation includes the current trust classification of the source/workflow definition, selected principal profile and exact target configuration identity/generation.

## CI/CD self-modification

Pipeline/workflow definitions are source/build inputs subject to review and provenance. A release workflow cannot silently modify its own authority/policy and use the modified state in the same trust decision without independent acceptance.

A candidate workflow SHALL NOT gain privileged release authority by selecting a privileged runner/environment, requesting a broader token, changing secret inheritance, altering approval conditions or rewriting the policy that evaluates the candidate. The trusted policy version used for admission is recorded outside the candidate's unilateral control.

## Evidence

Every privileged stage emits tamper-resistant/accountable evidence sufficient to reconstruct who/what acted on which exact source trust state, immutable artifact, configuration identity/generation/profile, validation-to-target configuration evidence, target and result without recording credentials.

`RLV-049` is the canonical falsification path for configuration evidence laundering between validation and production.