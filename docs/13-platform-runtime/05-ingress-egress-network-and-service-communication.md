# Phase 13 — Ingress, Egress, Network and Service-Communication Boundaries

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This document defines portable network and service-communication boundaries for JLMIRROR runtimes. Network topology is a transport/control surface, never a substitute for identity, authorization, tenant isolation or placement authority.

## Ingress classes

### Public/browser ingress

Public traffic enters through accepted edge/WAF/routing capability and then the BFF/API/realtime boundary appropriate to the contract.

Requirements:

- transport/client metadata is untrusted until validated;
- logical tenant selection follows accepted API rules and trusted placement resolution;
- caller cannot select physical cell/database/schema/secret/cluster;
- public health surfaces expose only minimum safe state;
- request size/framing/canonicalization rules from Phase 09 remain authoritative.

### Internal service ingress

Internal calls require authenticated workload identity and explicit service capability authorization. Internal origin does not relax tenant/current-authority checks required by the called application contract.

### Provider callback ingress

Provider callbacks remain under Phase 09 canonical HTTP/raw-byte/authentication/freshness/replay contracts. Phase 13 supplies a bounded ingress/runtime profile; it does not reinterpret provider authenticity.

## Service communication contract

Every protected service call declares:

```text
caller workload profile
callee capability/service profile
authenticated machine principal
tenant-context requirement
current authority requirement
request/response size/time bounds
network destination class
failure/degradation profile
observability/correlation binding
```

Exact internal protocol/service-discovery/mesh implementation remains OPEN.

## Network trust law

The following do not create authority by themselves:

- same host/node;
- same cluster/namespace;
- private IP or VPC/subnet membership;
- service-discovery registration;
- possession of a routable DNS name;
- broker/topic reachability;
- sidecar/mesh presence.

Each protected boundary authenticates the machine/workload principal and evaluates the application authority required by that operation.

## Egress classes

Every runtime profile receives one of:

- `egress.none@1` — no network egress except runtime-local/explicitly required platform control channels;
- `egress.platform-bounded@1` — approved platform/state/control dependencies only;
- `egress.connector-bounded@1` — approved external destinations through provider/integration policy;
- `egress.privileged-bounded@1` — narrowly scoped migration/recovery/admin destinations with explicit privileged authorization.

No general unrestricted-internet egress is assumed for serving runtimes.

## Provider and webhook egress

External connector/webhook execution SHALL implement the accepted protections:

- destination policy based on accepted configuration, not caller-supplied unrestricted URLs;
- SSRF defenses across resolution/connect/redirect behavior;
- allowed protocol/address classes;
- redirect policy and revalidation;
- hard timeout/body/response bounds;
- connection/concurrency budgets and destination isolation;
- authentication/signing secret access only for the connector profile;
- ambiguous external outcomes remain reconciliation-sensitive.

DNS, proxy, service-mesh or cloud-network products cannot weaken these application-visible invariants.

## Untrusted parser/active-content egress

`runtime.untrusted-parser@1` uses `egress.none@1` by default. A parser that genuinely requires external retrieval needs a separately reviewed bounded fetch capability; parser-controlled arbitrary egress is prohibited.

## Realtime network boundary

Realtime runtime may accept long-lived connections, but:

- successful network connection does not freeze authority;
- reconnect/resubscribe follows current placement/auth semantics;
- relocation/drain can force resync;
- realtime fanout transport identities are non-authoritative physical details;
- resource limits isolate connection storms from API/worker capacity.

## Cross-cell communication

Ordinary tenant operational mutations do not require synchronous writes to two cells. Cross-cell communication uses deliberate Control Plane, projection, event or relocation mechanisms under accepted semantics.

A source cell cannot directly mutate target-cell tenant operational state merely because network connectivity exists.

## Network policy generation

Network/egress policy has a versioned/configuration identity sufficient to detect stale policy where stale access would broaden authority.

Rules:

- rollback cannot re-open a prohibited destination or retired privileged path silently;
- network policy change is compatibility/security-sensitive when it broadens accessible trust zones/capabilities;
- runtime restart is not sufficient evidence that new policy is active;
- observability records policy/profile identity without exposing credentials or protected destination secrets.

## Failure behavior

Network partition/reachability loss maps to the owning Phase 11 profile; Phase 13 does not invent automatic retries.

Trust failure remains distinct from reachability failure. A previously untrusted/compromised peer becoming reachable again does not restore trust without owning authority/evidence.

## Validation obligations

Conformance tests SHALL falsify at least:

- unauthenticated internal call from reachable network;
- service identity attempting unauthorized tenant/domain capability;
- stale placement routed to old cell;
- connector destination/redirect escaping allowed policy;
- parser attempting egress;
- cross-cell direct mutation attempt;
- stale network policy reopening access;
- realtime relocation/drain requiring resync;
- one destination/provider exhausting unrelated egress capacity.

Exact ingress controller, load balancer, service discovery, mesh, proxy, DNS and private-connectivity products remain OPEN.