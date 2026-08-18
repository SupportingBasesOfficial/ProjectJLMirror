# Realtime, Cache and Provider Boundaries

**Status:** proposed baseline  
**Primary ADRs:** ADR-011, ADR-012, ADR-013, ADR-017

## Realtime contract

Realtime signals optimize operator experience; they are not authoritative state.

A protected first-party browser connection requires an accepted BFF-minted connection capability, expected-Origin validation **and current authorization for the capability's principal/tenant/realtime scope before the protected WebSocket upgrade is accepted**. A capability proves bounded connection intent; it does not freeze session, membership, permission/scope or tenant-access authority until expiry. If current authority cannot be established safely at handshake time, the gateway rejects the upgrade and fails closed.

For replay resistance, capability admission also requires an atomic single-winner claim/consume against shared replay state before `101`. A replica-local or read-only "unused" check is insufficient in a horizontally scaled gateway because concurrent replicas could otherwise both admit the same single-use capability.

Every protected subscription also requires current authorization for its tenant/resource scope **and current trusted tenant placement/admission generation**, and both authorities MUST remain fresh for the lifetime of the subscription. Handshake authorization and subscription authorization are separate gates; passing the former does not authorize arbitrary later subscriptions.

Logical realtime envelope:

```text
message_id
message_type
contract_version
tenant_id
resource_scope/reference
occurred_at
correlation_id
sequence/cursor when the channel supports replay
payload
```

Clients reconnect and resynchronize authoritative state from API/read models. A missed realtime message must not permanently corrupt UI state.

## Browser realtime handshake

```text
Browser --authenticated same-site--> BFF
        <-- short-lived scoped connection capability
Browser --capability + expected Origin--> Realtime Gateway
        -- validate capability + CURRENT underlying authority -->
        -- verify replay-authority continuity / capability registration or epoch -->
        -- atomically consume replay identity (single winner) -->
        <-- HTTP 101 only if all protected admission checks pass --
```

Before returning `101 Switching Protocols` for a protected first-party browser socket, the gateway SHALL validate:

- allowlisted expected browser `Origin`;
- capability authenticity, expiry and intended principal/tenant/realtime scope;
- current session/credential, membership, permission/scope and tenant-access authority for the capability scope, either through a fresh authoritative evaluation or a trusted current authorization/session generation or revocation marker;
- applicable pre-upgrade abuse/connection-admission limits;
- replay-authority continuity proving that the capability is eligible under the currently trusted replay state/epoch;
- atomic replay admission by claiming/consuming the capability's unique identity in shared state as the final gate before successful upgrade.

For a single-use capability, exactly one concurrent presentation can transition the capability from unused/available to consumed. Every losing handshake MUST be rejected before `101`, including presentations handled by different gateway replicas. If a bounded-use contract is selected later, the allowed use count must be enforced through an equivalently atomic shared counter/claim operation.

Ambient session cookies alone are not sufficient authority for a protected direct browser socket. A revoked or stale underlying authority MUST be rejected before upgrade even when the capability's signature and expiry remain valid. If authorization freshness, replay-state continuity or atomic replay consumption cannot be established safely, no protected socket is admitted.

### Replay-authority continuity and loss

Replay-consumption state is correctness/security state for the entire capability validity/retry-safety window. It is not allowed to behave like disposable cache state.

A capability that was already consumed MUST remain rejected after replay-store process restart, node loss, snapshot restore or reinitialization while its signed representation remains otherwise valid. The gateway MUST NOT interpret missing replay state as evidence that a capability is unused.

The accepted implementation provides one of these equivalent contracts:

- **registered-state model:** the BFF registers stable capability identity/use-bound state in the shared replay authority before the capability is returned to the browser; admission requires the registration to exist; consumed state is retained/recoverable until at least capability expiry plus accepted safety margin; or
- **epoch/generation model:** each signed capability is bound to a trusted replay epoch/generation; replay-authority loss/reinitialization advances the current epoch before protected admission resumes, invalidating all outstanding capabilities from the lost epoch.

If replay state is restored to an older point, the platform reconciles consumed state or advances the epoch before admission. If it cannot prove safe continuity or a trustworthy current epoch, protected admission remains fail closed. Reminting after an epoch advance is an accepted availability cost.

If a gateway successfully consumes a single-use capability and then fails before completing the upgrade, the capability remains consumed and the client obtains a new one. The design prefers fail-safe credential burning over reopening replay eligibility after an ambiguous handshake failure.

## Realtime authorization and placement lifecycle

Long-lived connections do not freeze authorization or tenant placement at handshake time.

The gateway must support:

- current authorization during the HTTP handshake before accepting a protected browser WebSocket upgrade;
- replay-authority continuity validation before consuming a capability;
- atomic shared single-winner capability consumption before `101`;
- fresh authorization and current trusted placement/admission generation for each protected subscription;
- active invalidation/revocation when session, membership, role/permission or tenant access changes;
- placement-generation invalidation/retirement when a tenant relocates between cells;
- removal of affected subscriptions or connection termination after authorization revocation or source-placement retirement;
- periodic bounded authorization and placement/admission-generation revalidation as defense in depth;
- fail-closed protected admission/delivery when current authorization, current placement generation, replay-state continuity or replay-consumption uniqueness cannot be safely established;
- fresh authorization and placement resolution on reconnect/resubscribe.

An authorization revision/generation or equivalent mechanism may be used to efficiently identify stale authorization state. A placement/admission generation such as trusted `placement_version`/cell admission generation identifies whether a tenant subscription still belongs on the current gateway/cell. The accepted propagation/revalidation bounds are security/reliability SLO parameters and may not be unlimited.

### Placement changes and long-lived sockets

A protected tenant subscription admitted on a cell is associated with the placement/admission generation current at subscription time. When relocation retires that generation, the source gateway must stop delivery for the affected tenant and remove the subscription or terminate the connection within the accepted bound. A multi-tenant connection may remain only for subscriptions whose placement generation remains current.

The normal recovery path is client resubscription through the logical route: re-resolve current placement, reauthorize on the target generation, then snapshot/resynchronize authoritative API/read-model state. A best-effort relocation hint may accelerate this, but missed hints/invalidation messages are caught by bounded placement-generation revalidation. An open TCP/WebSocket transport on the source does not make a retired tenant subscription authoritative or healthy.

## Realtime topology

```text
Committed state / integration event
        |
        v
Realtime projection/fanout
        |
        v
Authorized current-placement cell gateway
        |
        v
Connected client
```

The selected pub/sub/fanout technology is replaceable behind the realtime port. Ephemeral fanout is not the authority for either business state, authorization truth or tenant placement truth.

## Cache classes

Caching is classified by correctness impact.

### Performance cache

Derived/reconstructable values. On cache loss, bypass/fallback to authoritative source under bounded concurrency when safe.

### Routing/placement cache

Contains trusted, versioned Control Plane placement metadata. May serve stable traffic only within bounded policy and must never override newer placement/admission state. Long-lived realtime subscriptions must revalidate the generation they were admitted under; a socket cannot indefinitely pin stale placement because a cache entry or connection stayed alive.

### Authorization/session acceleration cache

May accelerate policy/session checks but cannot invent authority. Revocation/invalidation semantics must prevent a cache entry from becoming indefinite authorization. If authoritative/local cryptographic verification cannot safely establish a decision, fail closed.

### Coordination/ephemeral state

Rate counters, circuit state, ephemeral locks or realtime fanout state may be ephemeral when loss only changes performance/degradation behavior and cannot change correctness or security authority.

Replay-consumption state for a protected single-use/bounded-use capability is **not ordinary ephemeral coordination state** during the capability validity window. It requires an accepted shared single-winner authority plus continuity semantics: either registered state that survives/reconciles through the accepted validity window, or a replay epoch/generation that safely invalidates all outstanding capabilities after authority loss. Missing replay state is rejection/invalidity, never proof of unused state.

### Idempotency/deduplication

If losing a record could duplicate irreversible business effects, the authoritative deduplication record is durable rather than cache-only.

## Cache key isolation

Every tenant-scoped cache key/topic includes an unambiguous immutable tenant identity and contract namespace. Resource keys do not rely on user-readable slug alone.

Example logical shape:

```text
<environment>:<cell>:<contract>:<tenant_id>:<resource...>:<version>
```

Exact syntax is implementation-specific; the isolation semantics are not.

## External provider boundary

Every provider integration is an adapter around a platform-owned port.

Outbound connector requirements include:

- destination/protocol policy and SSRF controls;
- connect/request/overall timeouts;
- bounded response size;
- redirect policy;
- rate/concurrency budgets;
- bounded retries and circuit behavior;
- secret retrieval by reference;
- normalized safe error mapping;
- structured telemetry without credentials.

## Inbound provider callback boundary

Inbound provider/webhook data is untrusted until both **authenticity/freshness** and **payload validity** are established.

The ingress first enforces a hard raw transport-body byte limit **before** complete buffering or signature/authentication work. `Content-Length` may permit earlier rejection but is not trusted as the only bound; streamed/chunked input is counted and terminated when it crosses the configured raw-body limit.

After the bounded raw body is available, where supported by the provider protocol, the callback adapter verifies the expected signature/MAC/certificate/authentication mechanism against the configured integration, uses the exact raw representation when required, enforces timestamp/nonce/event-ID replay controls, and binds the callback to the tenant/integration from trusted configuration rather than caller-provided routing claims.

Only after callback authentication/freshness checks does parsing/decompression/schema/semantic validation and normalization occur before domain state mutation. Parsed/decompressed output has its own bounded size/complexity limits to prevent expansion attacks.

Duplicate/replayed callbacks use stable provider event/operation identity and durable idempotency/deduplication when a repeated effect could be harmful.

If a provider cannot securely authenticate callbacks, the callback is treated according to an explicitly reviewed weaker-trust design—for example as a trigger to perform an authenticated provider read/reconciliation—rather than being silently trusted as a command.

## Provider identity mapping

Provider-native identifiers are stored as external references mapped to stable JLMIRROR resource IDs. Replacing or adding providers does not redefine internal resource identity.
