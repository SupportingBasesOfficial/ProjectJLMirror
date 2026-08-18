# Realtime, Cache and Provider Boundaries

**Status:** proposed baseline  
**Primary ADRs:** ADR-011, ADR-012, ADR-013, ADR-017

## Realtime contract

Realtime signals optimize operator experience; they are not authoritative state.

A protected first-party browser connection requires an accepted BFF-minted connection capability, expected-Origin validation **and current authorization for the capability's principal/tenant/realtime scope before the protected WebSocket upgrade is accepted**. A capability proves bounded connection intent; it does not freeze session, membership, permission/scope or tenant-access authority until expiry. If current authority cannot be established safely at handshake time, the gateway rejects the upgrade and fails closed.

For replay resistance, capability admission also requires an atomic single-winner claim/consume against shared replay state before `101`. A replica-local or read-only "unused" check is insufficient in a horizontally scaled gateway because concurrent replicas could otherwise both admit the same single-use capability.

Every protected subscription also requires current authorization for its tenant/resource scope, and that authority MUST remain fresh for the lifetime of the subscription. Handshake authorization and subscription authorization are separate gates; passing the former does not authorize arbitrary later subscriptions.

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
        -- atomically consume replay identity (single winner) -->
        <-- HTTP 101 only if all protected admission checks pass --
```

Before returning `101 Switching Protocols` for a protected first-party browser socket, the gateway SHALL validate:

- allowlisted expected browser `Origin`;
- capability authenticity, expiry and intended principal/tenant/realtime scope;
- current session/credential, membership, permission/scope and tenant-access authority for the capability scope, either through a fresh authoritative evaluation or a trusted current authorization/session generation or revocation marker;
- applicable pre-upgrade abuse/connection-admission limits;
- atomic replay admission by claiming/consuming the capability's unique identity in shared state as the final gate before successful upgrade.

For a single-use capability, exactly one concurrent presentation can transition the capability from unused/available to consumed. Every losing handshake MUST be rejected before `101`, including presentations handled by different gateway replicas. If a bounded-use contract is selected later, the allowed use count must be enforced through an equivalently atomic shared counter/claim operation.

Ambient session cookies alone are not sufficient authority for a protected direct browser socket. A revoked or stale underlying authority MUST be rejected before upgrade even when the capability's signature and expiry remain valid. If authorization freshness or atomic replay consumption cannot be established safely, no protected socket is admitted.

If a gateway successfully consumes a single-use capability and then fails before completing the upgrade, the capability remains consumed and the client obtains a new one. The design prefers fail-safe credential burning over reopening replay eligibility after an ambiguous handshake failure.

## Realtime authorization lifecycle

Long-lived connections do not freeze authorization at handshake time.

The gateway must support:

- current authorization during the HTTP handshake before accepting a protected browser WebSocket upgrade;
- atomic shared single-winner capability consumption before `101`;
- fresh authorization for each protected subscription;
- active invalidation/revocation when session, membership, role/permission or tenant access changes;
- removal of affected subscriptions or connection termination after revocation;
- periodic bounded authorization revalidation as defense in depth;
- fail-closed protected admission/delivery when current authorization or replay-consumption uniqueness cannot be safely established;
- fresh evaluation on reconnect.

An authorization revision/generation or equivalent mechanism may be used to efficiently identify stale capabilities/sockets. The accepted propagation/revalidation bound is a security/SLO parameter and may not be unlimited.

## Realtime topology

```text
Committed state / integration event
        |
        v
Realtime projection/fanout
        |
        v
Authorized cell gateway
        |
        v
Connected client
```

The selected pub/sub/fanout technology is replaceable behind the realtime port. Ephemeral fanout is not the authority for either business state or authorization truth.

## Cache classes

Caching is classified by correctness impact.

### Performance cache

Derived/reconstructable values. On cache loss, bypass/fallback to authoritative source under bounded concurrency when safe.

### Routing/placement cache

Contains trusted, versioned Control Plane placement metadata. May serve stable traffic only within bounded policy and must never override newer placement state.

### Authorization/session acceleration cache

May accelerate policy/session checks but cannot invent authority. Revocation/invalidation semantics must prevent a cache entry from becoming indefinite authorization. If authoritative/local cryptographic verification cannot safely establish a decision, fail closed.

### Coordination/ephemeral state

Rate counters, circuit state, ephemeral locks or realtime fanout state. Loss changes performance/degradation behavior but does not erase durable business truth. Replay-consumption state for a single-use protected capability is correctness-critical during its validity window and therefore requires an accepted shared single-winner authority rather than best-effort replica-local state.

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
