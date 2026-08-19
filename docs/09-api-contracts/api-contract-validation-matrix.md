# API Contract Validation Matrix

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

This matrix turns the Phase 09 contract model into review and implementation evidence gates. Passing a schema validator or happy-path controller test is not sufficient.

| Area | Required evidence before an endpoint/contract is accepted for implementation/release |
|---|---|
| Contract ownership | One accepted owning domain/use case; route does not become a generic cross-domain mutation owner |
| Logical identity | Resource IDs remain stable/opaque across provider replacement, tenant relocation and service extraction |
| Physical routing isolation | Caller cannot select cell/database/schema/shard/cluster/secret reference through public path/query/header/body |
| Tenant scope | Tenant-scoped operation carries explicit logical tenant scope and validates current credential + placement + authoritative membership/resource authorization |
| Tenant auth ordering | When membership/resource authority is cell-owned: authenticate -> logical tenant -> trusted placement -> route -> cell admission -> TenantContext -> request-contract validation -> owning membership/permission/resource authorization; ingress prechecks cannot substitute for the owning decision |
| Authorization input safety | Owning authorization consumes only request fields validated under the trusted TenantContext/route; earlier cheap size/syntax checks cannot convert caller input into trusted authorization/resource scope or leak protected existence |
| Cross-tenant admin | Cross-tenant behavior uses distinct privileged platform operation; no wildcard tenant bypass on ordinary routes |
| Browser boundary | First-party browser protected API flow remains behind BFF; browser JS does not receive long-lived platform access/refresh credentials |
| Browser origin/CORS | Credentialed BFF is deny-by-default for untrusted origins; any cross-origin profile uses explicit allowlist/credential policy and never wildcard credentialed origin; CORS is not authorization |
| Request schema | Unknown mutation fields rejected by default; types/nullability/bounds are explicit |
| Representation | Response is deliberate contract projection, not ORM/table/provider payload serialization |
| Provider identity | Provider-native IDs remain external references and cannot replace canonical platform resource identity |
| Error safety | Stable machine `code`; no stack/SQL/physical placement/secrets/cross-tenant existence leakage |
| Request correlation | Server request ID and effective correlation ID observable without becoming auth/idempotency authority |
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
| XML/document active features | XML/XML-derived artifact processing disables DTD/external entities/XInclude/external schemas/stylesheets/resource resolution by default or uses an explicitly isolated deny-by-default resolver with trusted pinned resources |
| Idempotency admission | Required effectful POST/command atomically create-or-observes durable claim before protected effect |
| Idempotency fingerprint | Same key/scope with different semantic request conflicts before execution |
| Idempotency concurrency | Simultaneous same key/fingerprint yields one logical executor |
| Idempotency response loss | Retry after committed result but lost response replays/reconstructs logical result without re-execution |
| One-time-secret response loss | Same-key retry after lost secret-bearing response does not duplicate effect and does not re-present/retain secret; safe metadata identifies the completed resource and explicit recovery semantics are deterministic |
| Lockout-safe secret recovery | Before a secret rotation/reissue can invalidate the caller's only usable credential, the contract proves a still-valid alternate/current authority or a staged/overlap cutover that can authorize recovery without the lost new secret; revoke-plus-create is not treated as recovery when no authority remains to create |
| Idempotency external ambiguity | Timeout/lease expiry with possible external effect yields operation/reconciliation; does not authorize blind retry |
| Optimistic concurrency | Lost-update-sensitive mutation requires current revision/`If-Match`; missing/stale precondition has deterministic no-mutation response |
| State transitions | Protected domain state-machine transitions use owning command semantics; generic PATCH cannot bypass transition policy |
| Pagination | Deterministic order + tie-breaker; opaque cursor; no unbounded list contract |
| Cursor scope | Cursor cannot be replayed to weaken tenant/filter/sort/endpoint scope and exposes no sensitive topology |
| Cursor confidentiality | URL-visible cursor reveals no confidential/restricted tenant/filter/search/resource-key payload; protected cursor state uses server-side opaque handle, confidentiality+integrity protection or equivalent; encoding/signing alone is insufficient for protected plaintext |
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
| Realtime ticket mint | BFF authenticates current session and creates bounded tenant/principal/scope ticket; ticket is not general API credential and mint response is `no_store` |
| Realtime ticket transport | Ticket-bearing URL/transport is transient, redacted and excluded from normal logs/analytics/history/referrer-like propagation under the accepted profile |
| Realtime pre-101 | Expected Origin + ticket + current underlying auth + placement + replay continuity + atomic single-winner consume all pass before `101` |
| Realtime concurrency | Same single-use ticket presented to replicas yields at most one `101`; every loser rejected pre-upgrade |
| Realtime crash after consume | Ticket remains burned; remint required |
| Realtime replay-state recovery | Replay-state loss/restore cannot make consumed ticket redeemable; missing state never means unused |
| Realtime subscription separation | Successful connection does not grant arbitrary subscriptions; Phase 10 must preserve current subscription authorization |
| Provider callback raw bound | Chunked/streamed over-limit body rejected before complete buffering/signature work |
| Provider callback auth | Invalid authenticity/freshness rejected before protected domain mutation |
| Provider callback tenant binding | Payload tenant/account fields cannot reroute callback away from trusted integration mapping |
| Provider callback replay | Exact replay cannot repeat protected effect; same raw event ID across trusted scopes does not collide |
| Provider callback parse bound | Authenticated compressed/structured payload remains bounded after decompression/parsing |
| Provider callback XML safety | XML callback profile disables DTD/external entities/XInclude/external schema/stylesheet/resource resolution by default; local-file/network entity resolution is rejected unless an isolated deny-by-default resolver profile explicitly permits trusted pinned resources |
| Provider callback durability | Success acknowledgement after async acceptance has durable replayable work authority |
| Provider callback SSRF | Callback-supplied URL cannot cause arbitrary outbound fetch; follow-up retrieval uses trusted provider destination/protocol/redirect/size/timeout policy |
| Version compatibility | Additive change obeys unknown-field/open-enum rules; breaking change requires governed version boundary |
| Semantic compatibility | Schema-compatible change does not silently alter consistency, idempotency, authorization, scope, cache or retry meaning |
| Cache compatibility | Cache class, shared-cache eligibility, variance, validator/revalidation/current-auth requirements and security-relevant freshness policy are reviewed as semantic contract; a more permissive cache policy cannot ship as an implementation-only change |
| Security-metadata compatibility | Weakening cursor confidentiality/logging, safe-filename handling, artifact browser-delivery/parser isolation or XML external-resolution policy is reviewed as a security-sensitive semantic change even if schemas remain unchanged |
| Service extraction | Moving owner to new runtime/service does not change public IDs/routes/tenant semantics solely due to deployment topology |
| Provider replacement | New provider adapter does not force canonical resource IDs/schema to become provider-native |
| Contract source of truth | Machine-readable contract is reviewed canonical artifact; controller/ORM DTO does not define public schema by accident |
| Breaking-change CI | Contract diff detects structural risk; semantic review checks security/ownership/retry/consistency/cache/browser-delivery/cursor/parser changes |
| Client resilience | Official client ignores compatible unknown response fields/open enum values and only auto-retries operations marked safe |
| Data classification | Request/response/URL/logging policy prevents secret/credential/regulated/confidential-data leakage |
| Abuse limits | Body/page/filter/include/bulk/export/expensive operation constraints are explicit or explicitly OPEN with implementation blocked |

## Release-blocking contract failures

The following failures block acceptance/release regardless of other success:

- public/BFF caller can choose or override physical tenant placement;
- tenant-scoped implementation performs cell-owned membership/resource authorization before trusted placement routing/cell admission/TenantContext/request-contract validation, or treats ingress authorization as a substitute for owning authorization;
- owning authorization consumes unvalidated caller-controlled request fields as trusted scope/resource/policy input;
- known cross-tenant resource ID returns or mutates protected state under the wrong tenant context;
- implementation exposes long-lived platform access/refresh credentials to first-party browser JavaScript;
- credentialed BFF permits arbitrary/wildcard untrusted origins or treats CORS as authorization;
- route authorization exists only in UI/BFF and not in owning server-side boundary;
- response contract exposes raw secret/token or sensitive internal topology;
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
- artifact/document XML parsing can resolve attacker-controlled external entities/includes/schemas/stylesheets/local files/network resources outside an explicitly accepted isolated resolver profile;
- artifact processing automatically executes embedded scripts/macros or follows attacker-controlled URLs outside the accepted outbound/SSRF boundary;
- a generated preview/conversion is treated as `safe_inline` without independent output classification/delivery policy;
- external provider-native identifier becomes canonical resource identity such that provider replacement would break clients;
- retryable irreversible POST/command can execute twice because no atomic durable idempotency admission exists;
- response loss after committed idempotent mutation causes re-execution rather than replay/reconstruction;
- ambiguous external effect becomes retryable merely because HTTP timed out or a lease expired;
- same idempotency key with different request semantics can execute instead of conflicting;
- stale optimistic-concurrency mutation silently overwrites a newer protected state when the endpoint requires revision safety;
- list/history endpoint permits effectively unbounded interactive scans with no accepted bound/export path;
- cursor/snapshot/watermark remains usable to read protected data after current authority was revoked/suspended/reduced or tenant placement changed;
- URL-visible cursor reveals confidential/restricted tenant/filter/search/resource-key payload because it was merely encoded/signed rather than confidentiality-protected/server-side opaque;
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
- protected WebSocket receives `101` without expected Origin/current auth/replay continuity/atomic consume;
- more than one gateway replica can receive `101` for one single-use realtime ticket;
- replay-store loss can resurrect a previously consumed ticket;
- ticket-bearing transport leaks through ordinary logs/analytics/history/referrer-like propagation contrary to the accepted profile;
- callback payload can choose a different tenant than trusted integration configuration;
- oversized callback reaches complete buffering/authentication/parser work without hard raw bound;
- duplicate callback can repeat irreversible logical effect;
- same provider-local callback ID from two trusted tenant/source scopes collides under one dedup identity;
- provider callback XML parser permits DTD/external entity/XInclude/external schema/stylesheet resolution to read local files or reach network/internal services outside an explicitly accepted isolated resolver profile;
- provider callback returns success while required async work exists only in process memory;
- callback-supplied URL can trigger unrestricted outbound fetch/redirect and bypass the trusted connector/SSRF boundary;
- a supposedly compatible same-major change removes/renames/reinterprets accepted behavior or changes safe retry/security/consistency/cache/browser-delivery/cursor/parser semantics;
- service extraction/provider/storage migration forces consumers to change because public contract leaked internal topology;
- database/ORM model is serialized directly as the public contract without deliberate schema/authorization review.

## Traceability

Endpoint/contract tests SHOULD reference relevant `FR-*`, `INV-*`, `SEC-*`, `QA-*`, ADR/design sections and the specific Phase 09 operation ID.

High-risk fault tests SHOULD be executable in CI/integration environments before production implementation is considered release-ready.