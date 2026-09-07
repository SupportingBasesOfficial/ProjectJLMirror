# D4-D OPEN-EVT-017 — Secret/Credential Payload Exclusion Source Evidence

## Status

Source evidence only. This package does **not** grant ledger credit, select a D4-D candidate, grant selection authority, accept D4, or grant product/Wave4/production authority.

Corrected canonical source base: `e899b4a422a72e998dc6d0b612ac93c5cb71eb6a`.

Source-time D4 state:

- D4-A: 7/7 selected candidate
- D4-B: 5/5 selected profile
- D4-C: 9/9, candidate unselected
- D4-D: 3/5, candidate unselected
- D4-wide: 24/26
- D4 gate: `scoped`
- D4 transport authority: `selected_not_granted`
- Product/Wave4 implementation authority: `not_granted`
- Production authority: `none`
- C3 numeric/topology authority: `not_selected`

## Correction lineage

PR #114 merged the first source-evidence package at reviewed HEAD `c8d49ccf05113f0274287578bbc6965d220a677d`. A Codex review published after the merge identified three material gaps:

1. `verification_profile_ref` could alias or embed the resolvable secret handle and then survive sanitization/erasure as if it were a non-secret historical reference;
2. `audit_reference` could alias or embed the secret handle and be written to the audit sink while the record merely asserted that no handle was logged;
3. secret resolution did not enforce the authority's current generation, so stale or fabricated generations could resolve.

That source is therefore superseded for promotion purposes. The source manifest binds this correction lineage explicitly to PR #114, source HEAD `c8d49ccf05113f0274287578bbc6965d220a677d`, and Codex review `5134974949`. Any future ledger promotion must bind this corrected lineage or a later reviewed source; the superseded #114 provenance is not promotion-eligible.

Subsequent adversarial review of the corrected lineage identified further proof gaps before promotion eligibility: typed `SecretMaterial` nested inside otherwise allowed containers could bypass a shallow payload check; a secret handle could still occupy the reserved `verification-profile://` namespace and collide with historical verification authority; a validated payload could be mutated after construction; boolean/fractional generations could pass positivity-only checks; and the reserved `secret-audit-ref://` namespace lacked an independent negative probe. The current package closes those gaps with recursive JSON-like payload validation, rejection of opaque payload value types, deep defensive freezing, strict positive-integer generation validation, reserved namespace separation for both verification and audit handles, and real-path collision probes.

## Evidence axis

Evidence ID: `secret_credential_payload_exclusion_and_erasure_boundary`

Decision source: `OPEN-EVT-017`

The exact candidate-plan obligations are:

1. ordinary message payloads never contain secret or credential material;
2. inbox, logs, trace, and quarantine records never copy secret or key material;
3. erasure/minimization does not remove the last required non-secret historical verification reference;
4. secret reference resolution is narrowly authorized and audited;
5. secret-store/KMS outage never degrades to plaintext or unverified acceptance;
6. historical verification references are not bearer authority;
7. payload redaction/erasure preserves required correctness evidence without retaining secret material.

## Executable proof model

The source harness treats ordinary messages as reference-only consumers of external secret/KMS authority. Every ordinary payload field carries an explicit material classification. Only `public`, `internal`, and `business_data` classifications are admitted; `secret`, `credential`, `key_material`, unknown classifications, and typed `SecretMaterial` values are rejected. A successfully resolved secret is returned as `SecretMaterial`, not as an ordinary string, so it cannot be relabeled as `business_data` and serialized into an ordinary message.

Payload values are restricted to validated JSON-like scalars, lists/tuples, and string-keyed objects. Secret-material detection walks those containers recursively, so wrapping a resolved secret in a list or nested object does not bypass the boundary. Unsupported opaque Python objects are rejected rather than being assumed safe. After validation, payloads are defensively deep-frozen: the top-level mapping and nested mappings are immutable proxies, list-like values become tuples, and each `PayloadField` is reconstructed over the frozen value so later mutations of the caller's source object cannot alter an accepted ordinary message.

A shared message-boundary validator is applied at creation, sanitization, and erasure. This prevents a reconstructed/deserialized `OrdinaryMessage` from bypassing the same payload, secret-reference, verification-reference, and verification-generation invariants that apply at creation time.

Verification references must use the dedicated `verification-profile://` namespace and a canonical profile identifier. Secret handles are prohibited from using the reserved verification or audit-reference namespaces. The namespace, canonical-ID, namespace-separation, and alias/embedding guards each have independent negative probes. Alias/embedding probes use collision-shaped values that satisfy earlier syntax guards, so the overlap guards themselves are required.

Secret references require a non-empty handle, a strictly positive integer generation, canonical slash-delimited scope, reserved-namespace separation, and non-bearer semantics. Audit references are **not caller-supplied**: they are derived from the validated scope and exact generation as `secret-audit-ref://<scope>/generation-<n>`, with an explicit overlap guard preventing the resolvable handle from appearing in the derived audit reference. A dedicated probe also configures a secret handle directly inside the reserved audit namespace and requires fail-closed resolution.

Secret resolution is independently guarded by authority availability, authority source, **exact authorized handle**, exact current generation, explicit authorization, reference/request scope equality, and authority allowlisting. Reference, retained historical, and authority generations must all be strictly positive integers; booleans and fractional values are rejected. Unknown/revoked handles, stale generations, and unknown generations fail closed. A historical verification reference is actively rewrapped as a secret reference in a negative probe and is rejected through the real resolver path; a second probe deliberately configures authority collision with the retained verification reference and still requires fail-closed because reserved namespaces cannot become secret-handle authority.

The reconstructed/deserialized-input probes cover aliased verification references, secret-classified payload material, and invalid historical verification generations at both sanitization and erasure boundaries. Secondary persistence/observability records retain only validated message identity, tenant identity, and non-secret verification profile/generation references. Secret references and secret/key/credential material are excluded from inbox, log, trace, and quarantine records.

The corrected harness executes an exact validator-pinned set of **63** positive and negative probes covering:

- safe ordinary-payload admission;
- immutable top-level and nested payload structure plus defensive-copy isolation from later source-object mutation;
- rejection of password, secret, credential, token, API key, private key, key material, unknown payload classifications, and typed resolved secret material even when mislabeled as business data;
- recursive rejection of typed secret material nested in lists or objects, plus rejection of opaque unsupported payload value types;
- independent secret-reference handle, strict integer generation, scope, reserved verification namespace, reserved audit namespace, and bearer guards;
- strict integer verification-generation requirements at creation and independently at reconstructed sanitize/erasure boundaries;
- independent verification namespace and canonical-ID guards;
- verification-reference alias and embedding guards with collision-shaped fixtures;
- internally derived non-secret audit references and audit-handle overlap rejection;
- unsupported secondary-record kinds;
- reconstructed/deserialized alias rejection at sanitization and erasure;
- reconstructed/deserialized secret-payload rejection at sanitization and erasure;
- reconstructed/deserialized non-positive, boolean, and fractional verification-generation rejection at sanitization and erasure;
- exclusion of secret/key/credential material from inbox, logs, trace, and quarantine;
- erasure/minimization preserving only required non-secret historical verification continuity;
- duplicate-sensitive correctness after erasure;
- successful narrowly authorized and audited resolution without logging the resolvable handle;
- independent unauthorized, reference/request scope-mismatch, allowlist, outage, authority-source, unknown/revoked-handle, stale-generation, unknown-generation, boolean-generation, and fractional-generation fail-closed paths;
- real-path proof that a historical verification reference cannot be used as a secret bearer, including an authority deliberately configured to collide with the retained verification namespace;
- bearer secret-reference rejection at both message creation and secret resolution.

## Governance boundary

The source manifest is intentionally non-promoting:

- `current_run_auto_credit=false`
- `ledger_credit=[]`
- candidate remains `null/not_selected`
- selection authority remains `not_granted`

The validator additionally requires the current canonical state to remain exactly D4-D 3/5 and D4-wide 24/26 while this corrected source package is reviewed, and falsifies attempts to remove the correction lineage or reuse the superseded source base. Any future ledger credit for this evidence must be performed by a separate promotion PR bound to the exact corrected reviewed source HEAD, workflow run, job, artifact, and source-manifest digest.
