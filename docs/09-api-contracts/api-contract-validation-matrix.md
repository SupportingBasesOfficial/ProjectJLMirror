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
| Request schema | Unknown mutation fields rejected by default; types/nullability/bounds are explicit |
| Representation | Response is deliberate contract projection, not ORM/table/provider payload serialization |
| Provider identity | Provider-native IDs remain external references and cannot replace canonical platform resource identity |
| Error safety | Stable machine `code`; no stack/SQL/physical placement/secrets/cross-tenant existence leakage |
| Request correlation | Server request ID and effective correlation ID observable without becoming auth/idempotency authority |
| Response cache class | Every endpoint declares `no_store`, `private_revalidate`, `public_shared` or `artifact_delivery_guarded`; infrastructure defaults cannot choose a more permissive class |
| Protected cache isolation | Auth-dependent protected API/BFF response cannot be reused across principal/tenant boundary; `Vary`/caller metadata alone is not treated as authorization |
| Secret response caching | Initial secret-bearing response is `no_store`; secret cannot be served from browser/proxy/CDN/idempotency replay state |
| Public shared caching | Shared cache is allowed only for deliberately public projections with explicit safe variance/freshness/invalidation policy |
| Protected artifact caching | CDN/cache optimization preserves current auth/releasability/delivery-generation/active-stream fencing or is disabled/non-shared |
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
| Concurrent pagination | Live/snapshot/historical traversal semantics are explicitly documented |
| Filtering/sorting | Only allowlisted fields/operators; arbitrary client query grammar cannot become SQL injection/query-plan authority |
| Includes/expansion | Bounded include graph and independent authorization where referenced protected resources require it |
| Historical telemetry | Time/resource/metric query is bounded or converted to export; no unlimited history scan API |
| Bulk mutation | Maximum batch size + atomicity/per-item semantics + idempotency + partial failure are explicit |
| Large data | Oversized read/write workflow routes to governed export/import/operation rather than raising synchronous bounds indefinitely |
| `202` semantics | Durable operation exists before accepted response; `202` never falsely means business success |
| Operation durability | Operation status/progress/result survives worker restart and does not expose queue/node identity as canonical operation identity |
| Operation ambiguity | `reconciliation_required` cannot be turned into client retry eligibility without authoritative reconciliation |
| Operation cancel | Cancellation is modeled as request/state; worker interruption alone is not accepted business cancellation |
| Artifact identity | API exposes stable artifact metadata identity; object-store path/vendor URL is not canonical identity |
| Artifact release | Current auth + releasable state + generation-bound active delivery admission commit before first protected byte |
| Artifact erasure | API cannot report confirmed deletion/erasure while old capability/late lease/active stream/stale publisher/destructive-governance uncertainty remains |
| Delayed export | Current authorization checked before execution and release, not only at request creation |
| Delayed import | Worker re-establishes current tenant context/authority before protected mutation and on stale resumed stages |
| Realtime ticket mint | BFF authenticates current session and creates bounded tenant/principal/scope ticket; ticket is not general API credential |
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
| Provider callback durability | Success acknowledgement after async acceptance has durable replayable work authority |
| Version compatibility | Additive change obeys unknown-field/open-enum rules; breaking change requires governed version boundary |
| Semantic compatibility | Schema-compatible change does not silently alter consistency, idempotency, authorization, scope, cache or retry meaning |
| Cache compatibility | Cache class, shared-cache eligibility, variance, validator/revalidation/current-auth requirements and security-relevant freshness policy are reviewed as semantic contract; a more permissive cache policy cannot ship as an implementation-only change |
| Service extraction | Moving owner to new runtime/service does not change public IDs/routes/tenant semantics solely due to deployment topology |
| Provider replacement | New provider adapter does not force canonical resource IDs/schema to become provider-native |
| Contract source of truth | Machine-readable contract is reviewed canonical artifact; controller/ORM DTO does not define public schema by accident |
| Breaking-change CI | Contract diff detects structural risk; semantic review checks security/ownership/retry/consistency/cache changes |
| Client resilience | Official client ignores compatible unknown response fields/open enum values and only auto-retries operations marked safe |
| Data classification | Request/response/logging policy prevents secret/credential/regulated-data leakage |
| Abuse limits | Body/page/filter/include/bulk/export/expensive operation constraints are explicit or explicitly OPEN with implementation blocked |

## Release-blocking contract failures

The following failures block acceptance/release regardless of other success:

- public/BFF caller can choose or override physical tenant placement;
- tenant-scoped implementation performs cell-owned membership/resource authorization before trusted placement routing/cell admission/TenantContext/request-contract validation, or treats ingress authorization as a substitute for owning authorization;
- owning authorization consumes unvalidated caller-controlled request fields as trusted scope/resource/policy input;
- known cross-tenant resource ID returns or mutates protected state under the wrong tenant context;
- implementation exposes long-lived platform access/refresh credentials to first-party browser JavaScript;
- route authorization exists only in UI/BFF and not in owning server-side boundary;
- response contract exposes raw secret/token or sensitive internal topology;
- secret-bearing create/rotate response is cacheable, persisted for replay, or re-presented by same-key idempotency retry after response loss;
- lost one-time-secret response causes automatic second credential/secret creation instead of observing the completed logical effect and requiring explicit recovery;
- secret rotation/reissue can invalidate the caller's only usable credential before a still-valid alternate/current authority or staged/overlap recovery path is proven, leaving the caller unable to authorize recovery without the lost secret;
- a documented `revoke` then `create` sequence is treated as recovery even though no surviving authority can authorize the create step;
- protected API/BFF response has no explicit cache class or can be shared across principals/tenants through framework/proxy/CDN defaults;
- shared-cache safety relies only on a caller-controlled tenant/principal header or `Vary` value instead of accepted public/protected authorization semantics;
- cache class/variance/current-auth revalidation semantics can become more permissive without compatibility/security review;
- protected artifact cache/CDN path bypasses current authorization/releasability/delivery-generation/active-stream fencing;
- external provider-native identifier becomes canonical resource identity such that provider replacement would break clients;
- retryable irreversible POST/command can execute twice because no atomic durable idempotency admission exists;
- response loss after committed idempotent mutation causes re-execution rather than replay/reconstruction;
- ambiguous external effect becomes retryable merely because HTTP timed out or a lease expired;
- same idempotency key with different request semantics can execute instead of conflicting;
- stale optimistic-concurrency mutation silently overwrites a newer protected state when the endpoint requires revision safety;
- list/history endpoint permits effectively unbounded interactive scans with no accepted bound/export path;
- client-authored filter/sort/include is converted into unrestricted database/query authority;
- `202 Accepted` is returned before the platform has durable responsibility for the operation;
- operation status depends on in-memory worker/queue state such that restart loses externally promised progress/outcome;
- artifact metadata appears available while object/integrity/current generation is not verified;
- protected artifact first byte can be released before current authorization/releasability/generation-bound lease admission commits;
- artifact erasure can report success while stale delivery/upload/destructive authority can still release/recreate/destroy incorrectly;
- delayed import mutates tenant state using stale request-time human authorization after revocation;
- protected WebSocket receives `101` without expected Origin/current auth/replay continuity/atomic consume;
- more than one gateway replica can receive `101` for one single-use realtime ticket;
- replay-store loss can resurrect a previously consumed ticket;
- callback payload can choose a different tenant than trusted integration configuration;
- oversized callback reaches complete buffering/authentication/parser work without hard raw bound;
- duplicate callback can repeat irreversible logical effect;
- same provider-local callback ID from two trusted tenant/source scopes collides under one dedup identity;
- provider callback returns success while required async work exists only in process memory;
- a supposedly compatible same-major change removes/renames/reinterprets accepted behavior or changes safe retry/security/consistency/cache semantics;
- service extraction/provider/storage migration forces consumers to change because public contract leaked internal topology;
- database/ORM model is serialized directly as the public contract without deliberate schema/authorization review.

## Traceability

Endpoint/contract tests SHOULD reference relevant `FR-*`, `INV-*`, `SEC-*`, `QA-*`, ADR/design sections and the specific Phase 09 operation ID.

High-risk fault tests SHOULD be executable in CI/integration environments before production implementation is considered release-ready.