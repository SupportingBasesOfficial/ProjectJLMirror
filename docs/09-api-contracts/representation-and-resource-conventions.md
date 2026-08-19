# Representation and Resource Conventions

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Representation principle

External JSON is a deliberate contract projection. It is not an ORM serialization, database row dump, provider payload passthrough or internal class representation.

A representation may aggregate or omit internal fields when required by authorization, performance, privacy or ownership. Internal persistence changes SHALL NOT automatically change external JSON.

## JSON field naming

Canonical Phase 09 JSON field names use `snake_case`, consistent with existing JLMIRROR contract vocabulary such as `tenant_id`, `request_id`, `correlation_id`, `created_at` and `operation_id`.

Casing is part of the external contract and does not imply a database-column mapping.

## Common identity fields

A durable resource representation SHOULD expose, where applicable:

```json
{
  "id": "opaque-resource-id",
  "tenant_id": "opaque-tenant-id",
  "revision": "opaque-revision",
  "created_at": "2026-08-18T12:34:56.123Z",
  "updated_at": "2026-08-18T12:35:12.456Z"
}
```

`tenant_id` MAY be omitted from deliberately global resources or from tightly scoped nested representations where repetition provides no consumer value, but the contract's tenant scope remains explicit.

## Opaque revision

Resources subject to optimistic concurrency expose an opaque `revision` or equivalent strong validator. Clients MUST treat it as an uninterpreted token.

A revision SHALL NOT require clients to understand database sequence numbers, timestamps, WAL positions or storage versions.

## Time

Externally meaningful instants use timezone-aware UTC RFC-3339-style strings with a `Z` suffix where the API normalizes to UTC.

Examples:

```text
2026-08-18T12:34:56Z
2026-08-18T12:34:56.123Z
```

Event/business-local timezone is a separate field when local-calendar semantics matter.

The contract SHALL distinguish event/observed time from ingestion, creation or update time where those meanings differ.

## Money

Money is represented as exact decimal text plus ISO currency identity:

```json
{
  "amount": "1250.75",
  "currency": "BRL"
}
```

Floating-point representations that can silently change monetary precision are prohibited for contractually meaningful amounts.

## Quantities and units

Measured values whose unit is not intrinsic to the field SHALL carry explicit unit semantics. A generic numeric field named `value` without a contract-defined unit/type is insufficient for portable integrations.

## Booleans

Boolean semantics use JSON `true`/`false`. Integer/string aliases such as `0`, `1`, `yes` or `no` are not accepted unless a provider adapter is normalizing an external protocol before the domain/API boundary.

## Enumerations

Every externally exposed enum is classified as either:

- **open enum** — clients MUST tolerate unknown future values and use a documented fallback behavior;
- **closed enum** — the complete value set is part of the current major contract and adding a value is potentially breaking.

Operational/provider/category fields SHOULD default to open enums when future expansion is expected. State-machine fields MAY be closed when unknown states would make safe client behavior impossible.

The schema/contract SHALL declare the classification rather than relying on client assumptions.

## Optional versus nullable

Absence and explicit `null` are different contract states.

- an **absent** optional field means the representation does not provide a value under the current contract/context;
- explicit **`null`** means the field is present and its semantic value is intentionally empty/unknown/not-applicable according to that field's definition.

A field SHALL NOT become nullable merely as a convenience for implementation.

## Unknown response fields

Clients consuming a supported major version MUST ignore response fields they do not understand unless the contract explicitly marks the structure as closed.

This rule is required to permit compatible additive evolution.

## Unknown request fields

Server request schemas reject unknown fields by default. Silent acceptance of misspelled or unsupported mutation fields is prohibited because it can make a caller believe a requested change was applied when it was ignored.

An explicitly extensible metadata/object namespace MAY allow additional keys under documented size/type/name restrictions.

## Metadata/extensions

A `metadata` object is not a substitute for modeling known business concepts.

Extensible metadata, when supported, SHALL declare:

- key namespace/format;
- maximum key count;
- key/value size limits;
- supported value types;
- whether values are searchable/indexed;
- security/PII/secret classification;
- whether the server may preserve unknown entries.

Core invariant-bearing fields remain first-class schema fields.

## Resource references

A reference to another resource SHOULD use stable typed identity rather than embedding arbitrary internal representations:

```json
{
  "resource": {
    "type": "monitoring_resource",
    "id": "res_opaque"
  }
}
```

A route MAY return a richer embedded projection when explicitly documented. Embedding does not transfer ownership of the referenced resource.

## Lists and maps

Unbounded arbitrary maps are prohibited for high-cardinality business state. Collection fields declare maximum practical size or use separate paginated resources.

Large relationships are not embedded in a parent response merely because they are one-to-many in the database.

## Partial updates

`PATCH` uses an operation-specific partial request schema. Only fields explicitly declared mutable by that contract are accepted.

For each nullable/updatable field, the contract SHALL define what these cases mean:

- field absent;
- field present with a value;
- field present with `null`.

Generic mass assignment from request JSON into persistence/domain objects is prohibited.

## Full replacement

`PUT` is reserved for contracts that genuinely support full idempotent replacement of the externally modeled resource. It SHALL NOT be used as a generic update method when omitted fields have ambiguous meaning.

## Deletion representation

`DELETE` expresses a contract-level deletion/removal request. It does not promise immediate physical row deletion.

Where retention, legal hold, external cleanup or governed erasure makes completion asynchronous, the API returns/links to a long-running operation and exposes the externally meaningful lifecycle rather than pretending physical deletion completed synchronously.

## State transitions

Clients do not set protected lifecycle states directly unless the owning domain explicitly defines that state field as safely writable.

Policy-bearing transitions such as `approve`, `suspend`, `resolve`, `execute`, `cancel`, `decommission` or governed `erase` are explicit commands/use cases.

## Sensitive fields

Secrets, raw credentials, password-equivalent values and other non-retrievable secret material SHALL NOT appear in normal read representations after creation.

Where a secret can be created/rotated, the secret value MAY appear only in an explicit high-risk **initial secret-bearing response**. This is an **at-most-once application-presentation contract**, not a claim that the server can prove the client received the bytes across an unreliable network.

The platform SHALL NOT retain plaintext/recoverable secret material solely so an idempotency retry can reproduce that response. A same-operation replay after response loss MUST NOT re-present the secret. It returns only safe metadata/resource identity plus the documented secret-delivery recovery outcome from the idempotency contract.

Subsequent normal reads expose only metadata such as ID, label, status, scope, created time and last-used time as policy permits. If the caller lost the initial secret-bearing response, recovery requires an explicit authorized rotate/reissue/revoke flow that creates new secret material rather than retrieving the old secret.

## Resource shape evolution

The public resource representation is intentionally allowed to diverge from internal persistence over time. A future service extraction, storage migration or provider replacement SHALL preserve the external resource semantics or introduce a governed contract version rather than forcing consumers to follow internal migration details.