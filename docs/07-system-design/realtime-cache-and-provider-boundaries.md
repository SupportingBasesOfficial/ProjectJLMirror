# Realtime, Cache and Provider Boundaries

**Status:** proposed baseline  
**Primary ADRs:** ADR-011, ADR-012, ADR-013, ADR-017

## Realtime contract

Realtime signals optimize operator experience; they are not authoritative state.

A protected connection/subscription requires authentication plus authorization for tenant/resource scope before delivery, and that authority MUST remain fresh for the lifetime of the subscription.

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

## Realtime authorization lifecycle

Long-lived connections do not freeze authorization at handshake time.

The gateway must support:

- fresh authorization for each protected subscription;
- active invalidation/revocation when session, membership, role/permission or tenant access changes;
- removal of affected subscriptions or connection termination after revocation;
- periodic bounded authorization revalidation as defense in depth;
- fail-closed protected delivery when current authorization cannot be safely established;
- fresh evaluation on reconnect.

An authorization revision/generation or equivalent mechanism may be used to efficiently identify stale sockets. The accepted propagation/revalidation bound is a security/SLO parameter and may not be unlimited.

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

Rate counters, circuit state, ephemeral locks or realtime fanout state. Loss changes performance/degradation behavior but does not erase durable business truth.

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

Where supported by the provider protocol, the callback adapter verifies the expected signature/MAC/certificate/authentication mechanism against the configured integration, uses raw-body verification when required, enforces timestamp/nonce/event-ID replay controls, and binds the callback to the tenant/integration from trusted configuration rather than caller-provided routing claims.

Only after callback authentication/freshness checks does payload schema/size/semantic validation and normalization occur before domain state mutation.

Duplicate/replayed callbacks use stable provider event/operation identity and durable idempotency/deduplication when a repeated effect could be harmful.

If a provider cannot securely authenticate callbacks, the callback is treated according to an explicitly reviewed weaker-trust design—for example as a trigger to perform an authenticated provider read/reconciliation—rather than being silently trusted as a command.

## Provider identity mapping

Provider-native identifiers are stored as external references mapped to stable JLMIRROR resource IDs. Replacing or adding providers does not redefine internal resource identity.
