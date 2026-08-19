# Surface, Routing and Resource Identity

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Principle

External contract identity is logical. Physical topology is deliberately hidden behind platform routing and placement.

Clients interact with stable tenant, resource and operation identities. They do not select or persist cell IDs, database addresses, schema names, shard keys, region-internal hosts or provider-native storage identifiers as business routing authority.

For every externally reachable HTTP surface, `http-message-framing-and-canonicalization.md` establishes one canonical method/authority/request-target/header/body-framing interpretation before routing, authentication, tenant selection, authorization, cache or protected effects consume the request.

## Canonical top-level scopes

### Tenant-scoped machine API

Tenant-scoped machine routes use the explicit logical tenant path:

```text
/api/v1/tenants/{tenant_id}/...
```

`tenant_id` is an opaque immutable platform identifier. Supplying it expresses the intended tenant scope; it does not prove membership, permission or placement.

The server SHALL:

0. accept one canonical HTTP request interpretation at ingress, rejecting ambiguous framing, security-sensitive header conflicts, authority/proxy conflicts or request-target parser disagreement before protected logic;
1. authenticate the principal/credential from that canonical request;
2. validate the logical tenant selection/credential claims needed to identify the intended tenant without treating them as final membership/resource authorization;
3. resolve current trusted placement from authoritative control-plane metadata;
4. route the request to the authoritative cell/application owner using the same canonical request target interpreted at ingress;
5. have the cell validate current placement admission/version and construct the trusted `TenantContext`;
6. validate the request contract under that trusted route/context, including bounded path/query/header/body shape needed by the owning authorization/use case;
7. evaluate current membership or machine tenant scope plus the concrete permission/resource policy at the owning server-side boundary;
8. execute the owning application use case.

Request-contract validation before owning authorization does not permit protected resource existence or sensitive semantic validation to leak before the required authentication/tenant authority gates. Cheap transport-size/syntax rejection may occur earlier where safe, but caller-controlled fields are not consumed as trusted authorization inputs until validated under the authoritative context.

Canonical HTTP ingress is an earlier transport-security boundary, not a substitute for request-contract validation. It proves that every hop agrees on the request being evaluated; request-contract validation proves that the agreed request fields are valid/bounded for the owning authorization/use case.

Ingress/global checks MAY reject an obviously invalid/revoked credential or globally impossible tenant scope earlier, but they are only narrowing/fail-fast checks. They SHALL NOT substitute for the authoritative cell-owned membership, permission or resource-policy decision when that authority is cell-owned.

A stale or malicious client cannot choose a physical target by changing URI/query/header fields.

Untrusted `Forwarded`/`X-Forwarded-*`/Host-like metadata cannot become placement or routing authority. Trusted proxy metadata is normalized at the accepted edge boundary before routing.

### Platform/global machine API

Operations whose owner is truly platform-global use:

```text
/api/v1/platform/...
```

Platform-global routes are not a wildcard tenant bypass. Any operation that targets one or more tenants declares those targets explicitly and uses distinct privileged authorization/audit semantics.

Platform/global routes inherit the same canonical HTTP ingress; global privilege does not make ambiguous framing/header/authority input acceptable.

### Self/principal API

Principal-local resources that are not tenant-owned MAY use:

```text
/api/v1/me/...
```

A `/me` route SHALL NOT silently infer authority over an arbitrary tenant resource. Tenant-owned state remains tenant-scoped even when the caller has only one membership today.

### Browser BFF

The first-party Web application uses:

```text
/bff/v1/...
```

Tenant-scoped browser use cases SHOULD make the logical tenant explicit in the BFF contract when the user can belong to multiple tenants:

```text
/bff/v1/tenants/{tenant_id}/...
```

The BFF may expose presentation-oriented composition, but it may not encode physical placement or bypass downstream server authorization.

BFF session/Origin/CSRF handling operates on the canonical request produced by the accepted HTTP ingress profile; duplicate/conflicting session/security metadata cannot be interpreted differently by edge and BFF logic.

### Public projections

Deliberately public data uses a separate namespace:

```text
/public/v1/...
```

Protected tenant resources do not become public by moving under this prefix. Every public projection is explicitly modeled and reviewed.

Public routes still inherit canonical HTTP framing/request-target/cache semantics; unauthenticated does not mean parser ambiguity is safe.

## Resource identifiers

All externally durable resource identifiers SHALL be:

- opaque strings;
- stable across mutable names/slugs;
- independent of provider-native IDs;
- independent of physical placement;
- safe to carry across tenant relocation and service extraction;
- unambiguous within the contract scope.

Clients MUST NOT infer creation time, cell, region, sequence, database key layout or provider identity from an ID unless a future contract explicitly documents such semantics.

Exact ID-generation technology remains an implementation decision until separately accepted.

## Provider-native identity

Provider IDs are exposed only as typed external references where product behavior requires them, for example:

```json
{
  "external_references": [
    {
      "provider": "example-provider",
      "source_id": "src_...",
      "external_id": "12345"
    }
  ]
}
```

Provider IDs SHALL NOT replace JLMIRROR resource IDs in canonical API paths.

## Human-readable identifiers

Ticket numbers, invoice numbers, slugs, names and other human-readable identifiers are attributes, not canonical primary identities.

Where lookup by human-readable value is supported, the contract SHALL define its tenant/global uniqueness scope and ambiguity behavior explicitly.

## URI design

### Resource nouns

Resource collections use plural nouns:

```text
/tenants/{tenant_id}/memberships
/tenants/{tenant_id}/monitoring-resources
/tenants/{tenant_id}/incidents
```

URI structure reflects stable contract/resource semantics, not source-code package layout.

### Request-target normalization

Canonical URI semantics do not permit edge/application disagreement.

The accepted surface profile rejects or canonically resolves malformed/ambiguous percent-encoding, dot segments, alternate/encoded path separators, conflicting authority forms or repeated decoding cases that could make a gateway route one logical resource while the owning service authorizes another.

Exact normalization rules may be surface-specific, but every participating hop consumes the same accepted method/path/query meaning. A proxy/service extraction cannot introduce an additional independent path interpretation.

### Nesting

Nesting is used only when the parent materially scopes identity or lifecycle. Deep nesting that mirrors database relationships is prohibited by default.

Preferred:

```text
/tenants/{tenant_id}/incidents/{incident_id}/comments
```

Avoid chains such as:

```text
/tenants/{tenant_id}/organizations/{org_id}/teams/{team_id}/users/{user_id}/...
```

when stable IDs already make the target unambiguous and the hierarchy is not a security/lifecycle boundary.

### Commands and state transitions

A state transition that is not naturally modeled as resource creation/update uses an explicit command-style suffix:

```text
POST /api/v1/tenants/{tenant_id}/incidents/{incident_id}:resolve
POST /api/v1/platform/tenants/{tenant_id}:suspend
```

Commands SHALL map to owning-domain use cases. They SHALL NOT become generic RPC escape hatches that expose arbitrary method names.

Directly PATCHing a `status` field is prohibited when the domain state machine requires policy, side effects, approvals or transition invariants that a generic field update would bypass.

### Operations as resources

Long-running or ambiguity-prone work is represented through stable operation resources rather than keeping an HTTP request open indefinitely or requiring the caller to guess whether work happened.

Tenant operation resources use:

```text
/api/v1/tenants/{tenant_id}/operations/{operation_id}
```

Platform-global operations use:

```text
/api/v1/platform/operations/{operation_id}
```

## Routing transparency

A successful tenant relocation SHALL NOT require external consumers to rewrite stored resource URLs or IDs. Existing logical URIs continue to resolve through current placement.

A physical topology change MAY transiently alter availability according to the accepted degradation/relocation contract, but it must not redefine the resource's public identity.

Adding/removing/replacing gateways, reverse proxies or service hops during topology evolution SHALL NOT change the canonical external request interpretation or permit routing/auth disagreement for the same wire request.

## Multi-region future

If residency/region intent becomes externally configurable, it is modeled as policy/configuration metadata. It is not encoded into canonical resource IDs.

Region-specific public hostnames MAY exist for latency/residency reasons, but canonical resource identity and authorization remain logical and portable.

Authority/host selection for such profiles is still canonicalized at trusted ingress; untrusted forwarding metadata cannot select a privileged region/tenant route.

## URL persistence

Clients MAY persist canonical resource URLs returned by the API. The platform therefore SHALL NOT return internal service discovery addresses or expiring infrastructure URLs as canonical resource identity.

Artifact delivery URLs and realtime endpoints are capabilities/transport endpoints, not canonical resource identifiers, and may be short-lived.

Canonical resource URLs reflect accepted logical path semantics, never an internal proxy-specific normalization quirk.