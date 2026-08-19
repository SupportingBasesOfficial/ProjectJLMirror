# Surface, Routing and Resource Identity

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Principle

External contract identity is logical. Physical topology is deliberately hidden behind platform routing and placement.

Clients interact with stable tenant, resource and operation identities. They do not select or persist cell IDs, database addresses, schema names, shard keys, region-internal hosts or provider-native storage identifiers as business routing authority.

## Canonical top-level scopes

### Tenant-scoped machine API

Tenant-scoped machine routes use the explicit logical tenant path:

```text
/api/v1/tenants/{tenant_id}/...
```

`tenant_id` is an opaque immutable platform identifier. Supplying it expresses the intended tenant scope; it does not prove membership, permission or placement.

The server SHALL:

1. authenticate the principal/credential at the ingress boundary;
2. validate the logical tenant selection/credential claims needed to identify the intended tenant without treating them as final membership/resource authorization;
3. resolve current trusted placement from authoritative control-plane metadata;
4. route the request to the authoritative cell/application owner;
5. have the cell validate current placement admission/version and construct the trusted `TenantContext`;
6. validate the request contract under that trusted route/context, including bounded path/query/header/body shape needed by the owning authorization/use case;
7. evaluate current membership or machine tenant scope plus the concrete permission/resource policy at the owning server-side boundary;
8. execute the owning application use case.

Request-contract validation before owning authorization does not permit protected resource existence or sensitive semantic validation to leak before the required authentication/tenant authority gates. Cheap transport-size/syntax rejection may occur earlier where safe, but caller-controlled fields are not consumed as trusted authorization inputs until validated under the authoritative context.

Ingress/global checks MAY reject an obviously invalid/revoked credential or globally impossible tenant scope earlier, but they are only narrowing/fail-fast checks. They SHALL NOT substitute for the authoritative cell-owned membership, permission or resource-policy decision when that authority is cell-owned.

A stale or malicious client cannot choose a physical target by changing URI/query/header fields.

### Platform/global machine API

Operations whose owner is truly platform-global use:

```text
/api/v1/platform/...
```

Platform-global routes are not a wildcard tenant bypass. Any operation that targets one or more tenants declares those targets explicitly and uses distinct privileged authorization/audit semantics.

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

### Public projections

Deliberately public data uses a separate namespace:

```text
/public/v1/...
```

Protected tenant resources do not become public by moving under this prefix. Every public projection is explicitly modeled and reviewed.

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

## Multi-region future

If residency/region intent becomes externally configurable, it is modeled as policy/configuration metadata. It is not encoded into canonical resource IDs.

Region-specific public hostnames MAY exist for latency/residency reasons, but canonical resource identity and authorization remain logical and portable.

## URL persistence

Clients MAY persist canonical resource URLs returned by the API. The platform therefore SHALL NOT return internal service discovery addresses or expiring infrastructure URLs as canonical resource identity.

Artifact delivery URLs and realtime endpoints are capabilities/transport endpoints, not canonical resource identifiers, and may be short-lived.