# Realtime, Cache and Provider Boundaries

**Status:** proposed baseline  
**Primary ADRs:** ADR-011, ADR-012, ADR-013, ADR-017

## Realtime contract

Realtime signals optimize operator experience; they are not authoritative state.

A protected subscription requires authentication plus authorization for tenant/resource scope before delivery.

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

The selected pub/sub/fanout technology is replaceable behind the realtime port.

## Cache classes

Caching is classified by correctness impact.

### Performance cache

Derived/reconstructable values. On cache loss, bypass/fallback to authoritative source under bounded concurrency when safe.

### Routing/placement cache

Contains trusted, versioned Control Plane placement metadata. May serve stable traffic only within bounded policy and must never override newer placement state.

### Authorization/session acceleration cache

May accelerate policy/session checks but cannot invent authority. If authoritative/local cryptographic verification cannot safely establish a decision, fail closed.

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

Inbound provider/webhook data is untrusted and is validated for contract, size and semantic constraints before becoming domain state.

## Provider identity mapping

Provider-native identifiers are stored as external references mapped to stable JLMIRROR resource IDs. Replacing or adding providers does not redefine internal resource identity.
