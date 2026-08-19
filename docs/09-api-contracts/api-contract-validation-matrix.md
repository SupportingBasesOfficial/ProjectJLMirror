# API Contract Validation Matrix

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

This matrix turns the Phase 09 contract model into review and implementation evidence gates. Passing a schema validator or happy-path controller test is not sufficient.

| Area | Required evidence before an endpoint/contract is accepted for implementation/release |
|---|---|
| Contract ownership | One accepted owning domain/use case; route does not become a generic cross-domain mutation owner |
| Logical identity | Resource IDs remain stable/opaque across provider replacement, tenant relocation and service extraction |
| Physical routing isolation | Caller cannot select cell/database/schema/shard/cluster/secret reference through public path/query/header/body |
| HTTP message canonicalization | Every externally reachable HTTP surface inherits `http-message-framing-and-canonicalization.md`; one accepted wire request has one canonical interpretation across gateway/BFF/proxy/owning-service hops before protected decisions |
| HTTP framing ambiguity | Conflicting `Content-Length`/`Transfer-Encoding`, multiple differing lengths, malformed transfer coding/chunk framing and protocol-invalid framing metadata fail closed before auth/body processing/idempotency/effect |
| Security-header cardinality | Security-sensitive headers have explicit cardinality/combine semantics; duplicate/conflicting authentication/idempotency/trusted-routing values cannot be resolved by arbitrary first/last/framework behavior |
| Method/trailer safety | Generic method override is deny-by-default; request trailers cannot introduce/override authentication, idempotency, routing, CSRF/Origin, precondition, callback or realtime authority after initial admission |
| Authority/proxy normalization | Host/authority and trusted proxy metadata have one authoritative interpretation; untrusted `Forwarded`/`X-Forwarded-*` cannot spoof scheme/host/client identity/redirect or routing authority |
| Path canonicalization before placement | Tenant/resource path is decoded/canonicalized once before placement resolution; repeated slash, dot-segment, encoded slash/backslash, malformed percent, invalid/non-canonical UTF-8 and double-decoding ambiguity cannot route/authorize different resources |
| Query canonicalization/multiplicity | Query decoding is canonical before cache/auth/use case; singleton parameters reject duplicates/alternate-encoding collisions; genuinely repeated parameters define ordering/duplicate/count semantics |
| HTTP-version translation | HTTP/1.x↔HTTP/2↔HTTP/3 translation validates source framing and reconstructs target messages from canonical semantics rather than forwarding incompatible hop/framing metadata |
| Content coding | Raw and decoded limits are independent; malformed/unsupported/ambiguously ordered `Content-Encoding` cannot make edge/signature/size enforcement/application process different entity representations |
| Structured request entity | Every accepted structured request media type has one bounded canonical parse profile; duplicate/alias JSON members, multipart part-name/metadata/boundary ambiguity and equivalent structured-format parser ambiguity fail closed before protected body fields reach validation, authorization, idempotency or use-case mapping |
| Structured entity propagation | Request validation, owning authorization inputs, idempotency fingerprinting, body-dependent preconditions, callback replay identity/freshness where body-carried, and use-case/domain mapping consume the same canonical parsed entity; retained raw bytes are not independently reparsed as a second semantic authority |
| Tenant scope | Tenant-scoped operation carries explicit logical tenant scope and validates current credential + placement + authoritative membership/resource authorization |
| Tenant auth ordering | When membership/resource authority is cell-owned: canonical ingress -> authenticate -> logical tenant -> trusted placement -> route -> cell admission -> TenantContext -> request-contract validation -> owning membership/permission/resource authorization; ingress prechecks cannot substitute for the owning decision |
| Authorization input safety | Owning authorization consumes only request fields validated under the trusted TenantContext/route; earlier cheap size/syntax checks cannot convert caller input into trusted authorization/resource scope or leak protected existence |
| Cross-tenant admin | Cross-tenant behavior uses distinct privileged platform operation; no wildcard tenant bypass on ordinary routes |
| Browser boundary | First-party browser protected API flow remains behind BFF; browser JS does not receive long-lived platform access/refresh credentials |
| Browser origin/CORS | Credentialed BFF is deny-by-default for untrusted origins; any cross-origin profile uses explicit allowlist/credential policy and never wildcard credentialed origin; CORS is not authorization |
| Request schema | Unknown mutation fields rejected by default; types/nullability/bounds are explicit |
| Representation | Response is deliberate contract projection, not ORM/table/provider payload serialization |
| Provider identity | Provider-native IDs remain external references and cannot replace canonical platform resource identity |
| Error safety | Stable machine `code`; no stack/SQL/physical placement/secrets/cross-tenant existence leakage |
| Request correlation | Server request ID and effective correlation ID observable without becoming auth/idempotency authority |
| Response header profile | Every endpoint inherits or declares bounded grammar/cardinality/serialization rules for emitted headers and one serialization owner/composition model across application/BFF/proxy/CDN hops; dynamic `Location`, `Link`, `ETag`, `Retry-After`, `Content-Disposition`, redirect, cache/security/CORS/authentication and request/correlation headers cannot depend on raw string concatenation or conflicting singleton composition |
| Response header failure recovery | CR/LF/NUL/control injection, obsolete folding, invalid URI/header-value grammar and conflicting singleton output fail safely; a response-header serialization failure after a committed mutation cannot trigger blind mutation replay and must recover through authoritative idempotency/operation/read semantics |
| Response cache class | Every endpoint declares `no_store`, `private_revalidate`, `public_shared` or `artifact_delivery_guarded`; infrastructure defaults cannot choose a more permissive class |
| Protected cache isolation | Auth-dependent protected API/BFF response cannot be reused across principal/tenant boundary; `Vary`/caller metadata alone is not treated as authorization |
| Protected error caching | Authentication/authorization/step-up/existence-concealing protected errors cannot be shared across principals/tenants; safe cache policy applies to all response variants, not only success |
| Secret response caching | Initial secret-bearing response is `no_store`; secret cannot be served from browser/proxy/CDN/idempotency replay state |
| Public shared caching | Shared cache is allowed only for deliberately public projections with explicit safe variance/freshness/invalidation policy |
| Protected artifact caching | CDN/cache optimization preserves current auth/releasability/delivery-generation/active-stream fencing or is disabled/non-shared |
| Artifact media authority | Delivered media type/browser-execution classification is server-controlled and cannot be derived solely from uploader filename, extension or `Content-Type`; unknown/untrusted type fails toward non-executable download |
| Artifact safe filename | Download name is server-derived under a canonical policy; controls/bidi/path separators/reserved/special names/misleading extensions cannot create ambiguous or deceptive save behavior; `filename`/`filename*` are coherent and a neutral fallback always exists |
| Artifact browser delivery | Every browser-reachable artifact declares `opaque_download`, `safe_inline` or equivalent accepted isolated-active profile; authorization to download never implies permission for bytes to execute on the application/BFF origin |
| Active artifact isolation | Browser-active/script-capable content may execute inline only under a dedicated untrusted-content boundary that does not share application/BFF ambient credentials or DOM/service-worker origin trust, prevents persistent state/origin control from crossing tenant/artifact/principal boundaries, and preserves current artifact delivery fencing |
| Active delivery capability | Any browser-visible capability used to bridge active isolated content is artifact/delivery-generation bounded, not a general API credential, and is redeemed/burned or otherwise unusable for subsequent protected access before active content can exfiltrate/reuse it |
| Opaque artifact download | Unknown/untrusted/browser-active content defaults to attachment/non-sniffable download semantics; caller metadata cannot opt the object into inline execution or inject/ambiguate response headers/filename parameters |
| Untrusted artifact processing | Complex document/archive/media classification, preview, conversion, extraction or rendering uses an isolated least-privilege bounded processing profile with no ordinary application secrets/unrestricted egress, bounded expansion/resources and no implicit macro/script/embedded-URL execution; derived output receives independent artifact identity/classification |
| Archive extraction containment | Archive/member extraction remains inside the intended staging root; absolute/parent traversal, separator tricks, symlink/hardlink and special/device-file escape cannot materialize outside the accepted processing boundary |
| Archive member identity/collision | One canonical member-name model is established before scan/materialization; duplicates and Unicode/case/trailing-dot-space/platform/path normalization collisions are rejected; scanner and later consumer see the same canonical member bytes; materialization is no-follow atomic/no-replace or equivalent |
| XML/document active features | XML/XML-derived artifact processing **rejects every DTD declaration by default** and disables external entities/XInclude/external schemas/stylesheets/resource resolution; any exceptional DTD/resolver profile is separately reviewed, pinned/isolated and deny-by-default |
| Idempotency manifest completeness | Effectful idempotent operations govern `idempotency_class`, trusted effective scope, canonical fingerprint fields, completed replay behavior, in-progress duplicate behavior, fingerprint mismatch behavior, retention/recovery policy, external-ambiguity reconciliation and recovery-continuity policy as semantic manifest dimensions; changing one cannot hide behind an unchanged class |
| Idempotency admission | Required effectful POST/command atomically create-or-observes durable claim before protected effect and only after canonical HTTP acceptance |
| Idempotency fingerprint | Same key/scope with different semantic request conflicts before execution |
| Idempotency concurrency | Simultaneous same key/fingerprint yields one logical executor |
| Idempotency response loss | Retry after committed result but lost response replays/reconstructs logical result without re-execution |
| Idempotency retention/recovery | Claim/result/tombstone/operation authority covers the advertised safe retry/replay/recovery interval; expiry cannot make a previously completed irreversible effect newly executable |
| Idempotency recovery continuity | After restore/PITR/partial loss or mismatched recovery generations, missing/older claim/result/tombstone state is recovery uncertainty rather than proof of non-execution; effectful admission remains quarantined/fail-closed until accepted `(R,F]` reconciliation with surviving operation/outcome/audit/provider/external-effect authorities proves continuity |
| One-time-secret response loss | Same-key retry after lost secret-bearing response does not duplicate effect and does not re-present/retain secret; safe metadata identifies the completed resource and explicit recovery semantics are deterministic |
| Lockout-safe secret recovery | Before a secret rotation/reissue can invalidate the caller's only usable credential, the contract proves a still-valid alternate/current authority or a staged/overlap cutover that can authorize recovery without the lost new secret; revoke-plus-create is not treated as recovery when no authority remains to create |
| Idempotency external ambiguity | Timeout/lease expiry with possible external effect yields operation/reconciliation; does not authorize blind retry |
| Optimistic concurrency | Lost-update-sensitive mutation requires current revision/`If-Match`; missing/stale precondition has deterministic no-mutation response; multi-value/precondition semantics are canonical across hops |
| State transitions | Protected domain state-machine transitions use owning command semantics; generic PATCH cannot bypass transition policy |
| Pagination | Deterministic order + tie-breaker; opaque cursor; no unbounded list contract |
| Cursor scope | Cursor cannot be replayed to weaken tenant/filter/sort/endpoint scope and exposes no sensitive topology |
| Cursor confidentiality | URL-visible cursor reveals no confidential/restricted tenant/filter/search/resource-key payload; protected cursor state uses server-side opaque handle, confidentiality+integrity protection or equivalent; encoding/signing alone is insufficient for protected plaintext |
| Cursor browser transport | Browser-facing cursor token classified as protected/reusable is not placed in address/history-visible query transport; URL cursor is allowed only when exposed handle itself is explicitly non-sensitive for that browser surface or under a separately accepted non-browser machine profile |
| Cursor URL/logging policy | Raw protected cursor values are redacted/hashed/referenced in normal logs/analytics/traces and cannot leak through redirects/referrers/third-party URLs |
| Query URL confidentiality | Query/filter/search parameters are data-classified; confidential/restricted query state is not forced into URL-visible transport and uses a protected body/query-handle equivalent when necessary |
| Cursor authorization freshness | Every protected page/historical continuation re-establishes current principal/tenant/resource authorization; old cursor/snapshot/watermark cannot freeze authority after revoke/suspend/scope reduction/relocation |
| Concurrent pagination | Live/snapshot/historical traversal semantics are explicitly documented; snapshot data semantics do not freeze authorization |
| Filtering/sorting | Only allowlisted fields/operators; arbitrary client query grammar cannot become SQL injection/query-plan authority |
| Includes/expansion | Bounded include graph and independent authorization where referenced protected resources require it |
| Historical telemetry | Time/resource/metric query is bounded or converted to export; no unlimited history scan API |
| Bulk authorization | Every bulk item remains within current tenant/resource authority; mixed unauthorized outcomes preserve existence concealment and cannot widen batch authority |
| Bulk mutation | Maximum batch size + atomicity/per-item semantics + idempotency + partial failure are explicit |
| Large data | Oversized read/write workflow routes to governed export/import/operation rather than raising synchronous bounds indefinitely |
| `202` semantics | Durable operation exists before accepted response; `202` never falsely means business success |
| Operation durability | Operation status/progress/result survives worker restart and does not expose queue/node identity as canonical operation identity |
| Operation access authorization | `operation_id`/URL is not bearer authority; read/poll/cancel/retry/resume/result access re-establish current tenant/principal/resource authorization |
| Operation ambiguity | `reconciliation_required` cannot be turned into client retry eligibility without authoritative reconciliation |
| Operation cancel | Cancellation is modeled as request/state; worker interruption alone is not accepted business cancellation and current cancellation authority is checked |
| Artifact identity | API exposes stable artifact metadata identity; object-store path/vendor URL is not canonical identity |
| Artifact release | Current auth + releasable state + accepted browser-delivery/safe-filename profile + generation-bound active delivery admission commit before first protected byte |
| Artifact erasure | API cannot report confirmed deletion/erasure while old capability/late lease/active stream/stale publisher/destructive-governance uncertainty remains |
| Delayed export | Current authorization checked before execution and release, not only at request creation |
| Delayed import | Worker re-establishes current tenant context/authority before protected mutation and on stale resumed stages |
| Realtime manifest completeness | Every `realtime-admission` contract governs ticket scope/expiry, current-authority checks, current placement/admission-generation checks, atomic shared single-winner consume, burn-on-ambiguity, replay-store recovery/epoch continuity and subscription-authorization separation as semantic manifest dimensions |
| Realtime ticket mint | BFF authenticates current session and creates bounded tenant/principal/scope ticket; ticket is not general API credential and mint response is `no_store` |
| Realtime ticket transport | Ticket-bearing URL/transport is transient, redacted and excluded from normal logs/analytics/history/referrer-like propagation under the accepted profile |
| Realtime pre-101 | Canonical HTTP ingress + expected Origin + ticket + current underlying auth + placement + replay continuity + atomic single-winner consume all pass before `101` |
| Realtime concurrency | Same single-use ticket presented to replicas yields at most one `101`; every loser rejected pre-upgrade |
| Realtime crash after consume | Ticket remains burned; remint required |
| Realtime replay-state recovery | Replay-state loss/restore cannot make consumed ticket redeemable; missing state never means unused |
| Realtime subscription separation | Successful connection does not grant arbitrary subscriptions; Phase 10 must preserve current subscription authorization |
| Provider callback framing | Callback framing/header canonicalization passes before signature/freshness/replay; signature verification and adapter processing observe the same bounded raw body; duplicate/conflicting provider-auth headers follow one explicit profile |
| Provider callback raw bound | Chunked/streamed over-limit body rejected before complete buffering/signature work after canonical framing admission |
| Provider callback auth | Invalid authenticity rejected before protected domain mutation |
| Provider callback freshness policy | Each provider profile declares the accepted freshness evidence source plus clock/window/sequence acceptance policy as governed semantic metadata; an undeclared source is not trusted, and widening admissibility is security-sensitive even when authenticator binding is unchanged |
| Provider callback freshness binding | Every timestamp/nonce/sequence value used as security freshness evidence is bound to the authenticated callback body/identity by the accepted authenticator or comes from independently trusted protocol metadata associated with this request; window checks alone cannot make unbound metadata authoritative |
| Provider callback freshness/replay coherence | Freshness/sequence acceptance and provider retry admissibility cannot exceed effective replay/ambiguity-retention authority in a way that makes an old authenticated delivery newly executable after ordinary replay state expires; equivalent durable tombstone/operation/reconciliation authority preserves the no-repeat property |
| Provider callback tenant binding | Payload tenant/account fields cannot reroute callback away from trusted integration mapping |
| Provider callback replay | Exact replay cannot repeat protected effect; same raw event ID across trusted scopes does not collide; body-carried replay identity is derived from the same canonical structured entity later mapped to the owning use case |
| Provider callback replay atomicity | Replay admission is atomic create-or-observe under trusted scope and coupled to durable inbox/work/effect responsibility; concurrent deliveries produce one logical executor, and cross-authority ambiguity enters durable reconciliation instead of blind re-admission |
| Provider callback replay retention | Replay retention/expiry is an explicit profile contract; expiry cannot make unresolved or still-supported duplicate/recovery state executable again, and equivalent durable tombstone/operation authority persists where ordinary replay records may age out |
| Provider callback replay recovery continuity | Replay-state restore/PITR/partial loss/mismatched recovery generation cannot make a previously admitted callback appear unused; callback admission remains quarantined/fail-closed until surviving inbox/effect/provider-ack/audit/reconciliation authorities establish `(R,F]` continuity, and a still-fresh authenticated retry cannot bypass that gate |
| Provider callback acknowledgement durability | The profile declares the durable-responsibility boundary required before a provider-facing success acknowledgement; success cannot be emitted while required work exists only in memory or before the accepted durable admission/terminal boundary |
| Provider callback post-effect ambiguity | If a cross-authority irreversible effect may have succeeded before its outcome is durably recorded, stable operation/replay authority enters or retains reconciliation and no further effect attempt is admitted until authoritative reconciliation determines the prior outcome |
| Provider callback parse bound | Authenticated compressed/structured payload remains bounded after decompression/parsing |
| Provider callback XML safety | XML callback profile **rejects every DTD declaration by default** plus external entities/XInclude/external schema/stylesheet/resource resolution; exceptional DTD/resolver profiles require separate review and pinned/isolated deny-by-default resources |
| Provider callback durability | Success acknowledgement after async acceptance has durable replayable work authority; replay identity cannot be independently consumed while required work remains only in memory or otherwise unrecoverable |
| Provider callback SSRF | Callback-supplied URL cannot cause arbitrary outbound fetch; follow-up retrieval uses trusted provider destination/protocol/redirect/size/timeout policy |
| Version compatibility | Additive change obeys unknown-field/open-enum rules; breaking change requires governed version boundary |
| Semantic compatibility | Schema-compatible change does not silently alter consistency, idempotency, authorization, scope, cache or retry meaning |
| Cache compatibility | Cache class, shared-cache eligibility, variance, validator/revalidation/current-auth requirements and security-relevant freshness policy are reviewed as semantic contract; a more permissive cache policy cannot ship as an implementation-only change |
| Security-metadata compatibility | Weakening HTTP framing/method/trailer/content-coding/path/query/header/trusted-proxy semantics, structured-body parser/canonical-entity propagation, idempotency scope/fingerprint/duplicate/retention/external-ambiguity/recovery-continuity semantics, response-header grammar/cardinality/serialization ownership, callback freshness source/window/binding/replay atomicity/durable coupling/replay retention/replay recovery continuity/acknowledgement durability/post-effect reconciliation, realtime ticket scope/expiry/current-authority/placement/single-winner/burn/replay-recovery/subscription-separation, cursor confidentiality/transport/logging, archive member identity, safe-filename handling, artifact browser-delivery/parser isolation or XML DTD/external-resolution policy is reviewed as a security-sensitive semantic change even if schemas remain unchanged |
| Service extraction | Moving owner to new runtime/service does not change public IDs/routes/tenant semantics solely due to deployment topology |
| Provider replacement | New provider adapter does not force canonical resource IDs/schema to become provider-native |
| Contract source of truth | Machine-readable contract is reviewed canonical artifact; controller/ORM DTO does not define public schema by accident |
| Breaking-change CI | Contract diff detects structural risk; semantic review checks HTTP canonicalization/structured-entity/idempotency-recovery-continuity/response-header/security/ownership/retry/consistency/cache/callback-freshness-replay-recovery/realtime-replay-admission/browser-delivery/cursor/parser changes |
| Client resilience | Official client ignores compatible unknown response fields/open enum values and only auto-retries operations marked safe |
| Data classification | Request/response/URL/logging policy prevents secret/credential/regulated/confidential-data leakage |
| Abuse limits | Body/header/decoded-body/page/filter/include/bulk/export/expensive operation constraints are explicit or explicitly OPEN with implementation blocked |

## Release-blocking contract failures

The following failures block acceptance/release regardless of other success:

- two accepted HTTP hops can disagree on where one request ends and another begins;
- conflicting `Content-Length`/`Transfer-Encoding`, multiple body lengths or malformed transfer framing can reach authentication, body parsing, idempotency admission or protected effect logic;
- duplicate/conflicting `Authorization`, `Idempotency-Key` or another security-sensitive field can be resolved differently by edge and application code or by arbitrary first/last/framework behavior;
- security-sensitive request trailers can inject or override authority after initial header admission;
- implicit method override can make edge/cache/security logic and the owning use case apply different effective methods;
- gateway/BFF/proxy and owning service can derive different credentials, idempotency keys, preconditions or cache/security meaning from one wire request;
- untrusted `Forwarded`/`X-Forwarded-*` or conflicting Host/authority metadata can override trusted scheme/host/client identity/routing/security decisions;
- placement resolution can parse a tenant/resource path before canonical path decoding or downstream can reinterpret that path differently;
- repeated slash, dot-segment, encoded separator, malformed percent, invalid/non-canonical UTF-8 or double-decoding can make edge/placement/cache/auth/application resolve different resources;
- duplicate singleton query parameters or alternate encodings can be interpreted as first/last/list differently across hops;
- a repeated query parameter lacks an explicit multiplicity/order/duplicate rule yet influences cache/auth/validation/use case;
- HTTP-version translation can turn an invalid/ambiguous source request into a protected accepted request or propagate incompatible framing metadata downstream;
- content-coding/decompression interpretation can make security verification/size enforcement and semantic processing operate on different entity representations;
- a structured request body can be interpreted with different duplicate/alias/member/part/boundary semantics by validation, authorization, idempotency, callback replay admission or the owning use case;
- a structured request media type has no accepted canonical entity profile or protected components independently reparse retained raw bytes and derive different logical values;
- a body-carried callback replay/freshness/event identity can be derived from a different parse than the canonical entity used for domain mapping;
- cache/proxy can accept/cache one interpretation of an ambiguous request while the owning service rejects or interprets another;
- public/BFF caller can choose or override physical tenant placement;
- tenant-scoped implementation performs cell-owned membership/resource authorization before trusted placement routing/cell admission/TenantContext/request-contract validation, or treats ingress authorization as a substitute for owning authorization;
- owning authorization consumes unvalidated caller-controlled request fields as trusted scope/resource/policy input;
- known cross-tenant resource ID returns or mutates protected state under the wrong tenant context;
- implementation exposes long-lived platform access/refresh credentials to first-party browser JavaScript;
- credentialed BFF permits arbitrary/wildcard untrusted origins or treats CORS as authorization;
- route authorization exists only in UI/BFF and not in owning server-side boundary;
- response contract exposes raw secret/token or sensitive internal topology;
- an endpoint emits dynamic/security-relevant response headers without an accepted bounded grammar/cardinality profile or without one declared serialization/composition owner across application/BFF/proxy/CDN layers;
- caller/provider/resource-derived response-header data can inject CR/LF/NUL/control characters, obsolete folding, invalid URI/header grammar or conflicting singleton values, or infrastructure can append a second security-relevant singleton with another meaning;
- a response-header serialization failure after a committed mutation causes the mutation to be blindly retried rather than recovered through authoritative idempotency/operation/read semantics;
- authentication/authorization/existence-concealing protected errors can be served from a shared cache across principals/tenants;
- secret-bearing create/rotate response or realtime ticket-mint response is cacheable, persisted for replay, or re-presented by same-key idempotency retry after response loss;
- lost one-time-secret response causes automatic second credential/secret creation instead of observing the completed logical effect and requiring explicit recovery;
- secret rotation/reissue can invalidate the caller's only usable credential before a still-valid alternate/current authority or staged/overlap recovery path is proven, leaving the caller unable to authorize recovery without the lost secret;
- a documented `revoke` then `create` sequence is treated as recovery even though no surviving authority can authorize the create step;
- protected API/BFF response has no explicit cache class or can be shared across principals/tenants through framework/proxy/CDN defaults;
- shared-cache safety relies only on a caller-controlled tenant/principal header or `Vary` value instead of accepted public/protected authorization semantics;
- cache class/variance/current-auth revalidation semantics can become more permissive without compatibility/security review;
- protected artifact cache/CDN path bypasses current authorization/releasability/delivery-generation/active-stream fencing;
- browser-active/script-capable artifact bytes can execute inline on an application/BFF/session-bearing origin or other boundary sharing first-party ambient credentials/DOM/service-worker trust;
- an isolated active-content origin allows persistent storage/service-worker/same-origin control from one tenant/artifact/principal context to govern unrelated future protected content across a security boundary;
- a browser-visible artifact delivery bearer remains reusable/readable after active content begins executing and can be exfiltrated for later protected access or broader API authority;
- browser execution/media type is trusted solely from uploader-controlled filename, extension or `Content-Type`;
- artifact download filename can be controlled into ambiguous/deceptive values through bidi/control characters, path separators, reserved/special names, misleading extensions or conflicting `filename`/`filename*` parameters, or no safe server-generated fallback exists;
- unknown/untrusted/browser-active artifact can be served inline without accepted isolation instead of failing toward attachment/non-sniffable download semantics;
- active-inline artifact delivery can use an isolated origin yet bypass current artifact authorization/releasability/delivery-generation/active-stream fencing or turn its delegated capability into a general API credential;
- complex untrusted artifact/archive/document parsing, conversion, preview or metadata extraction runs in ordinary API/BFF business runtime with application secrets, unrestricted egress or unbounded CPU/memory/time/decompressed-output/nesting;
- archive extraction can escape the intended staging root through absolute/parent paths, path separator tricks, links or special/device files;
- archive processing accepts duplicate/aliased member names that collide after Unicode/case/path/platform normalization, permits scanned bytes to be overwritten/shadowed, or materializes members without no-follow atomic/no-replace equivalence;
- artifact/document XML parsing accepts a DTD under the default profile or can resolve attacker-controlled entities/includes/schemas/stylesheets/local files/network resources outside an explicitly accepted isolated exceptional profile;
- artifact processing automatically executes embedded scripts/macros or follows attacker-controlled URLs outside the accepted outbound/SSRF boundary;
- a generated preview/conversion is treated as `safe_inline` without independent output classification/delivery policy;
- external provider-native identifier becomes canonical resource identity such that provider replacement would break clients;
- an effectful idempotent endpoint lacks governed effective scope/fingerprint/duplicate/result/retention/external-ambiguity/recovery-continuity manifest semantics even though idempotency is enabled;
- retryable irreversible POST/command can execute twice because no atomic durable idempotency admission exists;
- idempotency retention/recovery authority expires inside an advertised safe retry/recovery interval and makes a completed irreversible effect executable again;
- restored/partially lost/older idempotency state interprets missing claim/result/tombstone as `never executed` or admits an effect before `(R,F]` recovery continuity is reconciled;
- response loss after committed idempotent mutation causes re-execution rather than replay/reconstruction;
- ambiguous external effect becomes retryable merely because HTTP timed out or a lease expired;
- same idempotency key with different request semantics can execute instead of conflicting;
- stale optimistic-concurrency mutation silently overwrites a newer protected state when the endpoint requires revision safety;
- list/history endpoint permits effectively unbounded interactive scans with no accepted bound/export path;
- cursor/snapshot/watermark remains usable to read protected data after current authority was revoked/suspended/reduced or tenant placement changed;
- URL-visible cursor reveals confidential/restricted tenant/filter/search/resource-key payload because it was merely encoded/signed rather than confidentiality-protected/server-side opaque;
- a browser-facing protected/reusable continuation token is placed in address/history-visible URL transport without proof that the exposed handle itself is non-sensitive for that surface;
- raw protected cursor or confidential query/search state can leak through normal logs, analytics, referrers, browser history or redirect/third-party URLs;
- client-authored filter/sort/include is converted into unrestricted database/query authority;
- bulk read/mutation treats batch membership as authorization for individual unauthorized resources or leaks existence through mixed per-item errors;
- `202 Accepted` is returned before the platform has durable responsibility for the operation;
- operation status depends on in-memory worker/queue state such that restart loses externally promised progress/outcome;
- possession of an `operation_id`/operation URL permits read/cancel/retry/result access without current authorization;
- artifact metadata appears available while object/integrity/current generation is not verified;
- protected artifact first byte can be released before current authorization/releasability/browser-delivery/safe-filename profile/generation-bound lease admission commits;
- artifact erasure can report success while stale delivery/upload/destructive authority can still release/recreate/destroy incorrectly;
- delayed import mutates tenant state using stale request-time human authorization after revocation;
- a `realtime-admission` endpoint lacks governed manifest metadata for ticket scope/expiry, current authority/placement, atomic single-winner consume, burn-on-ambiguity, replay recovery continuity or subscription separation;
- protected WebSocket receives `101` on an ambiguously framed/canonicalized request or without expected Origin/current auth/replay continuity/atomic consume;
- more than one gateway replica can receive `101` for one single-use realtime ticket;
- a consumed realtime ticket can become redeemable again after consume-before-`101` crash/ambiguity instead of remaining burned;
- replay-store loss/restore can resurrect a previously consumed ticket or missing state can be interpreted as unused without accepted continuity/epoch invalidation;
- ticket-bearing transport leaks through ordinary logs/analytics/history/referrer-like propagation contrary to the accepted profile;
- callback framing/signature verification can cover bytes different from those processed as the callback body;
- callback payload can choose a different tenant than trusted integration configuration;
- oversized callback reaches complete buffering/authentication/parser work without hard raw bound;
- duplicate/conflicting callback authentication/signature/freshness headers can be interpreted differently across hops;
- callback freshness evidence source or clock/window/sequence acceptance policy is absent from governed metadata, or changes without security-sensitive compatibility review;
- callback freshness evidence can be accepted without proof that it is bound to the authenticated callback body/identity or independently trusted protocol metadata;
- callback freshness/sequence admissibility can be widened beyond effective replay/ambiguity-retention authority so an old authenticated delivery becomes newly executable after ordinary replay state expires;
- callback replay admission can create more than one logical executor under concurrent delivery, or consume replay identity without durable work responsibility and without recoverable reconciliation;
- callback replay/ambiguity retention can expire while an unresolved or still-supported recovery state exists and thereby make the same logical effect newly executable;
- restored/partially lost/older callback replay state treats missing replay authority as unused or lets a still-fresh callback execute before surviving inbox/effect/provider-ack/audit/reconciliation state is reconciled;
- callback success can be acknowledged before the profile's declared durable-responsibility boundary;
- after a cross-authority irreversible callback effect may have succeeded but before its outcome is durably recorded, recovery can admit another effect attempt instead of requiring authoritative reconciliation;
- duplicate callback can repeat irreversible logical effect;
- same provider-local callback ID from two trusted tenant/source scopes collides under one dedup identity;
- body-carried callback event/replay identity can be parsed differently from the canonical payload consumed by the owning use case, allowing replay-key variation for the same logical event;
- provider callback XML parser accepts a DTD under the default profile or permits external entity/XInclude/external schema/stylesheet resolution to read local files or reach network/internal services outside an explicitly accepted isolated exceptional profile;
- provider callback returns success while required async work exists only in process memory;
- callback-supplied URL can trigger unrestricted outbound fetch/redirect and bypass the trusted connector/SSRF boundary;
- a supposedly compatible same-major change removes/renames/reinterprets accepted behavior or changes safe retry/security/consistency/HTTP-framing/structured-body/idempotency-recovery-continuity/response-header/path-query/cache/callback-freshness-replay-recovery/realtime-replay-admission/browser-delivery/cursor/archive/parser semantics;
- service extraction/provider/storage/gateway migration forces consumers or security semantics to change because public contract leaked internal topology or relied on parser disagreement;
- database/ORM model is serialized directly as the public contract without deliberate schema/authorization review.

## Traceability

Endpoint/contract tests SHOULD reference relevant `FR-*`, `INV-*`, `SEC-*`, `QA-*`, ADR/design sections and the specific Phase 09 operation ID.

High-risk fault tests SHOULD be executable in CI/integration environments before production implementation is considered release-ready.