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

Subsequent adversarial review of the corrected lineage identified further proof gaps before promotion eligibility: typed `SecretMaterial` nested inside otherwise allowed containers could bypass a shallow payload check; a secret handle could still occupy the reserved `verification-profile://` namespace and collide with historical verification authority; a validated payload could be mutated after construction; boolean/fractional generations could pass positivity-only checks; the reserved `secret-audit-ref://` namespace lacked an independent negative probe; serializing a resolved `SecretMaterial` to mapping, positional, JSON-text, URL/form text, fully percent-escaped text, or recursively percent-escaped text could strip or obscure the runtime type marker and re-enter ordinary `business_data`; reconstructed message/tenant identifiers could retain typed secret material or the resolvable handle as ordinary strings; truthy non-boolean configuration values could bypass explicit authorization or authority-availability fail-closed checks; object keys could retain resolvable handles; detached or cross-reference payloads could retain a configured handle as a plain string; textual JSON probes initially failed before the structural parser was required; process-local resolved-handle memory could disappear after restart or worker handoff; a durable deny catalog could drift from the set of authorities accepted by the resolver; an audit reference could embed a different cataloged authority handle through an otherwise canonical scope; `allowed_scopes` reconstructed as a string could degrade exact membership to substring membership; malformed non-string `SecretReference.handle` values could raise implementation exceptions; and reconstructed/deserialized messages could carry an unhydrated mapping or other non-`SecretReference` object in `secret_ref` and crash during field access. The current package closes those gaps with recursive JSON-like payload validation across values **and keys**, structural rejection of mapping and positional serialized secret-handle/generation forms, textual JSON revalidation with parser-only fixtures, URL/form normalization plus bounded iterative standalone percent-decoding and reinspection, a restart-safe immutable catalog of secret-authority handles independent of call history, resolver enforcement that every accepted authority handle is present in that same catalog, explicit collection validation for authority scope allowlists before membership checks, catalog-wide audit-reference exclusion, rejection of opaque payload value types, deep defensive freezing, strict positive-integer generation validation, literal non-empty string enforcement for secret handles and identifiers, hydrated `SecretReference` type enforcement before dereference, literal-boolean authorization/availability checks, reserved namespace separation for both verification and audit handles, and real-path collision probes.

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

The source harness treats ordinary messages as reference-only consumers of external secret/KMS authority. Every ordinary payload field carries an explicit material classification. Only `public`, `internal`, and `business_data` classifications are admitted; `secret`, `credential`, `key_material`, unknown classifications, and typed `SecretMaterial` values are rejected. A successfully resolved secret is returned as `SecretMaterial`; independently, the admission boundary is provisioned with a restart-safe immutable catalog representing durable secret/KMS authority knowledge, so a configured resolvable handle is never considered ordinary safe text merely because the current worker has not resolved it before.

Payload values are restricted to validated JSON-like scalars, lists/tuples, and string-keyed objects. Secret-material detection walks containers recursively across both values and object keys, so wrapping a resolved secret in a list, nested object, top-level key, or nested key does not bypass the boundary. A mapping containing both a non-empty `handle` and a strictly positive integer `generation` is treated as a structurally serialized secret/reference representation and is rejected even if its Python dataclass type marker has been stripped by serialization such as `dataclasses.asdict`. A two-item list/tuple shaped as `(non-empty handle string, strictly positive integer generation)` is likewise reserved and rejected, covering positional serialization such as `dataclasses.astuple`.

Text values are evaluated against the durable authority-handle catalog plus the message-selected handle when present. JSON-looking text beginning with `{` or `[` is deserialized and recursively evaluated under the same mapping/positional rules. URL/form-looking text is normalized with form decoding before the same secret-handle/serialized-material rules are applied. Standalone percent-escaped text is normalized iteratively for at most four decode rounds, with a decoded-size bound; every decoded layer is reinspected for known handles, structural JSON secret/reference shapes, or form serialization. If input remains meaningfully percent-decodable after the depth bound, the boundary fails closed instead of accepting over-encoded text. This prevents both `quote(json.dumps(asdict(resolve_secret(...))), safe="")` and `quote(quote(json.dumps(asdict(resolve_secret(...))), safe=""), safe="")` from bypassing the boundary simply because intermediate layers contain no raw handle or form pair. Dedicated parser-only JSON fixtures use an unrelated opaque handle and no attached secret reference, so removing JSON decoding itself makes those probes fail; the structural JSON revalidation is therefore independently required rather than shadowed by the raw-handle substring guard. A dedicated URL/form probe uses `urlencode(asdict(resolve_secret(...)))` with `secret_ref=None`; separate single- and double-percent-escaped probes require the bounded iterative URL-normalization path rather than raw substring matching. Unsupported opaque Python objects are rejected rather than assumed safe.

The durable authority-handle catalog is independent of process-local resolution history and is now the same admissibility source used by `resolve_secret`. The resolver fails closed if `authority.current_handle` is not in that catalog before exact handle/generation/scope authorization is considered. Dedicated evidence proves three directions of this coupling: a second cataloged handle `kms://other/current` resolves normally under its matching authority; that same cataloged handle is rejected when detached into ordinary `business_data`; and an otherwise matching uncataloged authority handle is rejected by the resolver. Fresh-worker evidence also attempts to place the configured `kms://orders-signing/current` handle into `business_data` with `secret_ref=None` without relying on prior local resolution history and requires fail-closed admission. The same authority knowledge is consulted by payload values, object keys, identifiers, verification references, and generated audit references. A dedicated `verification-profile://collision-profile` fixture has no attached `secret_ref`, so the verification-reference authority collision can only be rejected by the durable authority-handle guard.

After validation, payloads are defensively deep-frozen: the top-level mapping and nested mappings are immutable proxies, list-like values become tuples, and each `PayloadField` is reconstructed over the frozen value so later mutations of the caller's source object cannot alter an accepted ordinary message.

A shared message-boundary validator is applied at creation, sanitization, and erasure. Message and tenant identifiers must be literal non-empty strings and must not equal or embed a selected or durably known secret-authority handle before they can be copied into ordinary or secondary records. Any non-`None` `secret_ref` must first be an actual hydrated `SecretReference` object before any field is dereferenced; unhydrated mappings or other reconstructed/deserialized objects therefore fail with `SecretBoundaryDenied` rather than leaking `AttributeError`. Secret-reference handles are then required to be literal non-empty strings **before** namespace operations. This blocks both malformed reference objects and malformed handles at the shared downstream boundaries. The same shared boundary prevents reconstructed/deserialized `OrdinaryMessage` instances from bypassing payload, secret-reference, verification-reference, and verification-generation invariants that apply at creation time.

Verification references must use the dedicated `verification-profile://` namespace and a canonical profile identifier. Secret handles are prohibited from using the reserved verification or audit-reference namespaces. Verification references are also rejected if they alias/embed a selected or durably known secret-authority handle. The namespace, canonical-ID, namespace-separation, selected-reference alias/embedding, and durable-authority alias guards each have independent negative probes. Alias/embedding probes use collision-shaped values that satisfy earlier syntax guards, so the overlap guards themselves are required.

Secret references require a hydrated `SecretReference` object, a literal non-empty string handle, a strictly positive integer generation, canonical slash-delimited scope, reserved-namespace separation, and non-bearer semantics. Audit references are **not caller-supplied**: they are derived from the validated scope and exact generation as `secret-audit-ref://<scope>/generation-<n>`. Before persistence, the derived audit reference is checked against the selected reference handle **and the entire durable authority-handle catalog**; any selected or other configured bearer handle embedded through the scope causes fail-closed rejection. The proof includes one collision where the selected cataloged handle itself appears in the generated audit path and a separate collision where the selected handle is safe but another cataloged handle (`collision-profile`) appears in the scope. A dedicated probe also configures a secret handle directly inside the reserved audit namespace and requires fail-closed resolution.

Secret resolution is independently guarded by authority availability, authority source, **durable catalog membership**, exact authorized handle, exact current generation, explicit authorization, reference/request scope equality, and authority allowlisting. Authority `allowed_scopes` must be an explicit tuple/list collection; a string/bytes-like scalar is never treated as a membership container, and every member is independently validated as a canonical scope before exact membership is evaluated. Availability and authorization must each be the literal boolean `True`; truthy non-boolean values such as the string `"false"` fail closed. Reference, retained historical, and authority generations must all be strictly positive integers; booleans and fractional values are rejected. Unknown/revoked handles, uncataloged authority handles, stale generations, unknown generations, and malformed scope collections fail closed. A historical verification reference is actively rewrapped as a secret reference in a negative probe and is rejected through the real resolver path; a second probe deliberately configures authority collision with the retained verification reference and still requires fail-closed because reserved namespaces cannot become secret-handle authority.

The reconstructed/deserialized-input probes cover aliased verification references, unhydrated `secret_ref` mappings, secret-bearing message/tenant identifiers, identifiers that equal the resolvable secret handle, secret-classified payload material, malformed non-string secret handles, and invalid historical verification generations at both sanitization and erasure boundaries. Secondary persistence/observability records retain only validated message identity, tenant identity, and non-secret verification profile/generation references. Secret references and secret/key/credential material are excluded from inbox, log, trace, and quarantine records.

The corrected harness executes an exact validator-pinned set of **108** positive and negative probes covering:

- safe ordinary-payload admission;
- immutable top-level and nested payload structure plus defensive-copy isolation from later source-object mutation;
- rejection of password, secret, credential, token, API key, private key, key material, unknown payload classifications, and typed resolved secret material even when mislabeled as business data;
- direct and recursively nested rejection of mapping and positional serialized resolved-secret representations after type information has been stripped;
- direct, positional, and nested textual JSON serialization rejection, URL/form serialization rejection after percent-decoding, single- and double-percent-escaped serialization rejection under bounded iterative normalization, plus rejection of opaque text fragments containing known secret-authority handles;
- parser-only mapping, positional, and nested JSON fixtures that require the structural JSON decoder/revalidation path itself;
- top-level and nested object-key rejection when a key contains a selected or durably known secret-authority handle;
- fresh-worker rejection of configured secret-authority handles without prior local resolution history, plus detached and cross-reference payload rejection;
- resolver/catalog coupling: successful resolution of a second cataloged handle, detached rejection of that handle, and fail-closed rejection of an uncataloged authority handle;
- recursive rejection of typed secret material nested in lists or objects, plus rejection of opaque unsupported payload value types;
- non-empty string-only message/tenant identifiers, rejection of identifiers that equal or embed a selected or durably known secret-authority handle, and reconstructed sanitize/erasure coverage for handle-bearing identifiers;
- independent secret-reference hydrated-object, literal-string handle, strict integer generation, scope, reserved verification namespace, reserved audit namespace, and bearer guards, including creation/resolution probes for malformed handles and sanitize/erasure probes for unhydrated mappings;
- strict integer verification-generation requirements at creation and independently at reconstructed sanitize/erasure boundaries;
- independent verification namespace and canonical-ID guards;
- verification-reference selected-reference alias/embedding guards plus a detached durable-authority collision probe;
- internally derived audit references with selected-handle and catalog-wide bearer-handle overlap rejection;
- unsupported secondary-record kinds;
- reconstructed/deserialized alias rejection at sanitization and erasure;
- reconstructed/deserialized secret-payload rejection at sanitization and erasure;
- reconstructed/deserialized non-positive, boolean, and fractional verification-generation rejection at sanitization and erasure;
- exclusion of secret/key/credential material from inbox, logs, trace, and quarantine;
- erasure/minimization preserving only required non-secret historical verification continuity;
- duplicate-sensitive correctness after erasure;
- successful narrowly authorized and audited resolution without logging the resolvable handle;
- literal-boolean authorization and authority-availability enforcement, including truthy non-boolean negative probes;
- independent unauthorized, reference/request scope-mismatch, exact allowlist, string-container allowlist, outage, authority-source, uncataloged-authority, unknown/revoked-handle, stale-generation, unknown-generation, boolean-generation, and fractional-generation fail-closed paths;
- real-path proof that a historical verification reference cannot be used as a secret bearer, including an authority deliberately configured to collide with the retained verification namespace;
- bearer secret-reference rejection at both message creation and secret resolution.

## Governance boundary

The source manifest is intentionally non-promoting:

- `current_run_auto_credit=false`
- `ledger_credit=[]`
- candidate remains `null/not_selected`
- selection authority remains `not_granted`

The validator additionally requires the current canonical state to remain exactly D4-D 3/5 and D4-wide 24/26 while this corrected source package is reviewed, and falsifies attempts to remove the correction lineage or reuse the superseded source base. Any future ledger credit for this evidence must be performed by a separate promotion PR bound to the exact corrected reviewed source HEAD, workflow run, job, artifact, and source-manifest digest.
