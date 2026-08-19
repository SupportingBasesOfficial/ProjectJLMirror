# Compatibility, Versioning and Deprecation

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Principle

Contract evolution is explicit. JLMIRROR SHALL NOT treat application deployment version, database schema version or service extraction as a reason for external consumers to change.

## Major version namespace

Externally supported HTTP surfaces use an explicit major version in the URI:

```text
/api/v1/...
/bff/v1/...
/realtime/v1/...
/public/v1/...
/callbacks/v1/...
```

A major version is a semantic compatibility family. Patch/minor application releases do not appear in the URI.

## Compatibility within a major

Within one supported major, changes SHALL be backward compatible for conforming clients unless an explicitly accepted exception exists.

Generally compatible response evolution includes:

- adding a new optional response field;
- adding a new endpoint/resource family;
- adding a new optional request field whose omission preserves prior behavior;
- adding a new link/metadata field;
- adding a new value to an enum explicitly classified as open;
- increasing server capability without changing existing semantics.

## Breaking changes

The following are breaking by default:

- removing or renaming a field;
- changing a field's type or semantic meaning;
- changing tenant/global ownership/scope;
- changing a stable identifier's meaning;
- making a previously optional request field mandatory;
- reducing a documented allowed value/range in a way existing valid clients may violate;
- changing a closed-enum value set;
- changing success/error semantics in a way that alters safe retry or authorization behavior;
- changing idempotency scope/meaning such that an existing key can duplicate or suppress a different logical effect;
- changing pagination ordering/cursor semantics in a way that invalidates active traversal beyond the cursor contract's documented lifecycle;
- exposing previously hidden physical/provider implementation semantics as required client input.

Breaking changes require a new major contract or another explicitly governed compatibility mechanism.

## Open versus closed enums

Enum extensibility is part of the field schema:

```text
open enum   -> unknown future value must be tolerated by clients
closed enum -> unknown value indicates incompatible contract or client update requirement
```

Adding a new value to a closed enum is treated as breaking unless the field's compatibility classification is changed through governance before consumers rely on closure.

## Unknown response fields

Conforming clients MUST ignore response fields they do not understand unless the representation is explicitly closed.

Generated SDKs SHALL preserve this behavior rather than failing deserialization merely because a compatible field was added.

## Unknown request fields

Servers reject unknown request fields by default. This prevents typos and unsupported writes from appearing successful.

Request extensibility occurs through explicit versioned schemas or documented extension namespaces, not silent unknown-field passthrough.

## Semantic compatibility

Schema compatibility is necessary but not sufficient.

Changing a field from "current authoritative state" to "eventually consistent approximation", or changing whether an operation is idempotent/retry-safe, is a semantic breaking change even if the JSON schema is unchanged.

Contract review therefore evaluates behavior, consistency, security, ownership and error/retry semantics in addition to shape.

## Deprecation

A supported contract element is deprecated before removal when practical.

Deprecation SHALL identify:

- deprecated operation/field/version;
- recommended replacement;
- reason when useful;
- earliest removal boundary/version;
- migration notes;
- compatibility constraints.

Numeric minimum support/deprecation duration remains a commercial/SLO/governance decision until separately accepted. A removal SHALL NOT occur earlier than the accepted support policy applicable to that consumer class.

## No removal inside a supported major by default

Externally supported fields/routes SHOULD remain available for the lifetime of their supported major unless:

- continuing them creates a material security/compliance risk;
- the contract was explicitly experimental/non-stable;
- an accepted emergency governance decision documents the exception.

Normal cleanup pressure is not sufficient reason to break consumers.

## Experimental contracts

A contract MAY be labeled experimental/preview only when that lifecycle is explicit in the schema/docs and consumers are told that compatibility guarantees differ.

Experimental endpoints SHALL NOT silently become critical production dependencies without formal promotion to the normal supported contract policy.

## BFF compatibility

The first-party BFF may evolve more tightly with the first-party Web client than the machine API, but it still uses explicit major-version semantics and SHALL preserve the accepted browser security invariants.

A BFF change cannot bypass downstream API/domain governance merely because the browser is deployed by the same organization.

## Provider callback compatibility

Provider callback adapters version independently when external provider protocols require it. Provider-specific payload changes are normalized behind the adapter and SHALL NOT leak into unrelated public domain contracts.

Where a provider changes a callback protocol incompatibly, the adapter may temporarily support multiple provider versions while producing one stable JLMIRROR domain/application contract.

## Public projection compatibility

Public status/projection consumers may be unauthenticated and difficult to inventory. Their compatibility changes therefore require the same or stronger caution as authenticated public APIs.

## Webhook/event boundary

Outbound webhook/event envelope compatibility belongs to Phase 10. Phase 09 management APIs for subscriptions/configuration SHALL NOT assume that changing an HTTP management API major automatically changes the event envelope major.

## Database/schema changes

Expand/migrate/contract database evolution is internal. A database column/table rename does not trigger an API major version unless it changes externally meaningful semantics.

Mixed application/schema versions during rolling deployment SHALL continue serving the accepted API major combinations declared safe by migration/release design.

## Service extraction

Moving an owning context from the modular monolith into a separately deployed service SHALL NOT create a public API break.

Internal routing may change. Public operation identity, tenant scope, authorization, idempotency and resource representation remain stable unless a separately governed external contract change is accepted.

## Provider replacement

Replacing Zabbix, a payment provider, notification provider, object store or other external dependency SHALL NOT require consumers to replace canonical JLMIRROR resource IDs or paths.

Provider-specific capabilities that genuinely differ are exposed as explicit capability metadata or provider-specific extension contracts rather than redefining the core resource.

## Compatibility tests

CI SHALL compare proposed contract changes with the currently accepted baseline and flag likely breaking changes in:

- paths/methods;
- request requiredness/type;
- response fields/types;
- enum compatibility classification;
- status/error codes;
- operation idempotency declaration;
- authorization declaration;
- pagination/sort contract;
- resource identity/scope.

Automated schema diff is advisory for semantic compatibility; human/architecture review remains required for meaning changes.

## Version retirement

Retiring a major version is a governed product/operational process, not merely deleting routes.

Retirement includes consumer inventory where possible, migration guidance, telemetry on remaining usage, security/support posture and a controlled disablement plan.