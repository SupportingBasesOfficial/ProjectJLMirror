# API & Contracts Overview

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts  
**Depends on:** accepted Product/Requirements/Security/Architecture/ADR/System Design/Data Architecture baseline

## Purpose

This phase defines the stable external and boundary-facing contract model through which JLMIRROR capabilities are consumed. It translates accepted domain, security, runtime and data invariants into HTTP/browser/realtime-admission representations without making transport models the owner of business semantics.

The contract baseline is designed for the platform's maximum intended evolution: new bounded contexts, new providers, new storage engines, dedicated cells, service extraction, new clients and substantially larger scale SHALL be able to appear without forcing existing consumers to understand physical placement, database schemas, provider-native models or internal process topology.

The objective is not to pre-implement every future capability. The objective is to ensure that capabilities implemented later fit an already coherent contract system rather than creating one-off APIs that become structural debt.

## Contract surfaces

JLMIRROR distinguishes these surfaces because their trust, compatibility and lifecycle requirements differ:

1. **Platform/Public Machine API** — versioned HTTP API for authorized external machine principals and approved integrations.
2. **First-party Browser BFF API** — browser-facing confidential-session boundary. It may compose platform use cases for the Web client but SHALL NOT become a second business domain.
3. **Protected Realtime Admission** — BFF-mediated capability minting plus direct protected WebSocket admission under accepted Origin/current-authorization/replay rules. Phase 09 owns admission representation; Phase 10 owns asynchronous message/event envelope mechanics.
4. **Provider Callback Ingress** — adapter-owned inbound HTTP contracts subject to provider-specific authentication plus accepted raw-body/freshness/replay/tenant-binding rules.
5. **Public Projection API** — deliberately public/versioned projections such as public status output; it never exposes internal tables or protected tenant resources by default.
6. **Internal Service/Application Contracts** — typed application contracts that may later cross process boundaries. HTTP is not required merely because an internal module has an explicit contract.

A surface MAY share domain schemas or generated types with another surface when semantics are genuinely identical, but shared implementation SHALL NOT erase the trust boundary between surfaces.

## Normative design goals

### Contract stability over implementation stability

Public contract identity SHALL remain independent of:

- PostgreSQL table/schema names;
- ORM entities;
- provider-native identifiers and payloads;
- cell/database/cluster placement;
- queue/cache/pub-sub vendor;
- monolith versus extracted service placement;
- internal class/module/file names;
- object-storage paths or signed-URL vendor formats.

An internal implementation may change without a public breaking change when the externally meaningful semantics remain equivalent.

### Explicit ownership

Every protected operation SHALL name one owning bounded context/application capability. A transport route does not gain permission to mutate multiple domain owners directly simply because the client wants one screen to update several things.

Cross-domain orchestration is represented by an owning use case/process contract, not by exposing distributed storage coupling to the caller.

### Explicit tenant semantics

Every tenant-scoped contract SHALL carry an unambiguous logical `tenant_id` through its contract scope. A caller may identify the logical tenant it intends to operate on, but that value is never authority for physical placement and never bypasses membership/authorization.

### Explicit retry semantics

Every effectful contract SHALL classify whether client retry is:

- inherently safe;
- safe only with the Phase 09 idempotency contract;
- unsafe without first resolving an operation resource;
- prohibited because a new business decision is required.

"Client can retry on timeout" is never an undocumented assumption.

### Explicit consistency semantics

Every operation SHALL identify whether its response represents:

- committed authoritative state;
- accepted durable asynchronous work;
- a stale-tolerant/derived projection;
- a reconciliation/ambiguous outcome requiring operation tracking.

A `2xx` response does not silently mean more consistency than the owning use case can prove.

## Initial URI namespaces

The proposed major-version namespaces are:

```text
/api/v1/...       versioned machine/platform API
/bff/v1/...       first-party browser BFF contract
/realtime/v1/...  protected realtime handshake/admission endpoint
/public/v1/...    deliberate unauthenticated/public projections
/callbacks/v1/... provider/integration callback adapters where a generic prefix is applicable
```

Exact hostnames/deployment routing remain infrastructure choices. URI paths never encode cell, database, shard, region-internal host, provider secret or other physical placement authority.

## API major version

`v1` is the first externally supported major contract family. Compatible additive evolution occurs within a major version under the compatibility rules in this phase. Breaking semantic changes require a new major contract or another explicitly accepted compatibility mechanism.

Major API version is a contract version, not a deployment version. Multiple application releases may serve the same API major.

## Contract-first rule

A new externally consumed use case is not implementation-ready until its contract declares at minimum:

- owning domain/capability;
- stable operation identity/name;
- surface and major version;
- method/path or non-HTTP invocation shape;
- actor/principal classes;
- tenant/global scope;
- required authorization action/scope;
- request schema and size/complexity bounds;
- response/result semantics;
- consistency class;
- idempotency/retry behavior;
- optimistic-concurrency behavior where applicable;
- long-running-operation behavior where applicable;
- stable error codes/classes;
- audit class;
- observability/request-correlation requirements;
- compatibility/deprecation implications;
- data classification and secret/PII handling constraints.

The canonical endpoint template in this phase makes those fields reviewable before implementation.

## What Phase 09 intentionally does not finalize

Phase 09 does not select:

- queue/event-broker technology;
- broker acknowledgement/partition mechanics;
- event/message envelope details owned by Phase 10;
- cloud/orchestrator/storage vendors;
- telemetry physical engine;
- exact identity-provider or token protocol not already accepted elsewhere;
- numeric SLO/RPO/RTO/capacity targets without evidence;
- domain capabilities that have not been accepted by Product/Requirements.

Phase 09 MAY define exact HTTP representations where Gate B intentionally delegated them here, including path/version conventions, error representation, idempotency header semantics, pagination/cursor representation, long-running operation resources and conditional request conventions.

## Maximum-state evolution test

Before a Phase 09 contract is accepted, reviewers SHOULD ask whether the contract remains coherent if all of the following become true later:

- tens or hundreds of thousands of tenants exist;
- some tenants live in dedicated cells/regions;
- Monitoring telemetry uses a specialized engine;
- high-volume domains are extracted into services;
- multiple provider adapters coexist for the same capability;
- browser, CLI, automation agents and third-party integrations consume the platform concurrently;
- a resource is relocated while clients remain active;
- old and new application versions coexist during rolling deployment;
- an operation times out after an external side effect may already have happened;
- a customer changes plan, identity provider, region, provider or isolation class without changing logical resource identity.

If a contract requires callers to understand or rewrite around those implementation changes, the contract is not sufficiently decoupled.