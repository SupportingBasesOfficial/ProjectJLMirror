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

The source harness treats ordinary messages as reference-only consumers of external secret/KMS authority. Every ordinary payload field carries an explicit material classification. Only `public`, `internal`, and `business_data` classifications are accepted; `secret`, `credential`, and `key_material` are rejected independently of the field name.

Verification references must use the dedicated `verification-profile://` namespace, and the profile identifier is constrained to a canonical identifier alphabet. Negative probes independently require both the namespace guard and the canonical-ID guard, rather than relying only on collision fixtures. The reference therefore cannot be an arbitrary secret handle, path, URI, or malformed identifier.

Audit references are **not caller-supplied**. They are derived internally from the validated scope and the exact secret generation as `secret-audit-ref://<scope>/generation-<n>`. Because neither scope nor generation can carry the resolvable secret handle, the audit reference cannot alias or embed it by construction. Sanitization and erasure revalidate the secret reference and verification reference before retaining any historical reference.

The revalidation boundary is tested independently of message creation: adversarial probes directly reconstruct `OrdinaryMessage` instances with a syntactically valid verification-reference/secret-handle collision and prove that both `sanitize_record` and `erase_and_minimize` reject them before persistence or historical retention. This models deserialized/reconstructed input that never passed through `create_message`.

Secret resolution requires the exact current authority generation. Stale and unknown generations fail closed. Secondary persistence/observability records retain only message identity, tenant identity, and validated non-secret verification profile/generation references. Secret references and secret/key/credential material are excluded from inbox, log, trace, and quarantine records. Secret-resolution audit records retain only the derived non-secret audit reference and never the resolvable handle or secret material.

The corrected harness executes 27 positive and negative probes covering:

- explicit payload-material classification and rejection of secret, credential, and key material regardless of field name;
- representative negative vectors for password, secret, credential, token, API key, private key, and key material;
- independent rejection of a wrong verification namespace and a non-canonical verification profile identifier;
- rejection of verification-reference aliasing or embedding of the secret handle with collision-shaped fixtures that reach the overlap guards;
- proof that the audit reference is internally derived and non-secret, plus rejection of a secret-handle-shaped scope;
- direct reconstructed/deserialized-message rejection at both sanitization and erasure boundaries;
- exclusion of secret handles/material from inbox, log, trace, and quarantine records;
- erasure/minimization that preserves only validated non-secret verification profile/generation continuity;
- duplicate-sensitive correctness after erasure using only non-secret historical verification references;
- narrowly scoped and audited secret resolution without logging the resolvable handle;
- fail-closed behavior for unauthorized, cross-scope, authority-outage, stale-generation, and unknown-generation resolution;
- rejection of bearer-capable secret references;
- proof that historical verification references cannot resolve secrets.

## Governance boundary

The source manifest is intentionally non-promoting:

- `current_run_auto_credit=false`
- `ledger_credit=[]`
- candidate remains `null/not_selected`
- selection authority remains `not_granted`

The validator additionally requires the current canonical state to remain exactly D4-D 3/5 and D4-wide 24/26 while this corrected source package is reviewed, and falsifies attempts to remove the correction lineage or reuse the superseded source base. Any future ledger credit for this evidence must be performed by a separate promotion PR bound to the exact corrected reviewed source HEAD, workflow run, job, artifact, and source-manifest digest.
