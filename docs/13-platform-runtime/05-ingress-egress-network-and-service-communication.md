# Phase 13 — Ingress, Egress, Network and Service-Communication Boundaries

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This document defines portable network and service-communication boundaries for JLMIRROR runtimes. Network topology is a transport/control surface, never a substitute for identity, authorization, tenant isolation, environment isolation or placement authority.

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
caller environment_class
callee capability/service profile
callee environment_class
cross-environment policy if classes differ
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
- same physical cloud account/project/subscription;
- same logical environment label;
- private IP or VPC/subnet membership;
- service-discovery registration;
- possession of a routable DNS name;
- broker/topic reachability;
- sidecar/mesh presence.

Each protected boundary authenticates the machine/workload principal and evaluates the application authority required by that operation.

## Environment network boundary

The canonical logical environment classes are `environment.development@1`, `environment.validation@1`, `environment.production@1` and `environment.recovery@1`.

Network rules:

- network reachability across environment classes is deny-by-default unless an accepted bounded dependency, promotion, validation or recovery path requires it;
- development/validation network paths SHALL NOT create access to production workload credentials, production placement authority or authoritative production tenant state merely because routes/firewall rules exist;
- a validation runtime may test production-equivalent protocol/topology semantics without becoming a production principal or accepting production tenant traffic by label;
- `environment.recovery@1` may reach affected production recovery authorities only under explicit recovery scope; such reachability does not permit normal production serving admission;
- cross-environment service calls, state-port access and connector egress preserve both caller and destination environment provenance where needed for authorization/audit;
- physical account/VPC/subnet/cluster separation MAY strengthen environment isolation, but physical co-location cannot weaken the logical boundary;
- Phase 14 may change physical environment mappings only while preserving these semantics under `OPEN-PRT-035`.

`PRTV-044` falsifies environment network/data/credential authority bleed.

## Egress classes

Every runtime profile receives one of:

- `egress.none@1` — no network egress except runtime-local/explicitly required platform control channels;
- `egress.platform-bounded@1` — approved platform/state/control dependencies only;
- `egress.connector-bounded@1` — approved external destinations through provider/integration policy;
- `egress.privileged-bounded@1` — narrowly scoped migration/recovery/admin destinations with explicit privileged authorization.

No general unrestricted-internet egress is assumed for serving runtimes. Egress capability is additionally bounded by the runtime's accepted environment class.

## Provider and webhook egress

External connector/webhook execution SHALL implement the accepted protections:

- destination policy based on accepted configuration, not caller-supplied unrestricted URLs;
- SSRF defenses across resolution/connect/redirect behavior;
- allowed protocol/address classes;
- redirect policy and revalidation;
- hard timeout/body/response bounds;
- connection/concurrency budgets and destination isolation;
- authentication/signing secret access only for the connector profile and environment class;
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

The canonical Phase 13 identity for semantically relevant runtime network/egress-policy currentness is `network_policy_generation`.

Rules:

- it is distinct from `runtime_generation`, `configuration_generation`, `workload_credential_generation`, `placement_version`, environment class and all upstream authorization/governance generations;
- rollback cannot re-open a prohibited destination, cross-environment path or retired privileged path silently;
- network policy change is compatibility/security-sensitive when it broadens accessible trust zones/capabilities/environments;
- runtime restart or a current `runtime_generation` is not sufficient evidence that the required `network_policy_generation` is active;
- observability records policy/profile/environment identity without exposing credentials or protected destination secrets;
- `PRTV-042` applies whenever an implementation attempts to use another generation as proof of network-policy currentness.

## Failure behavior

Network partition/reachability loss maps to the owning Phase 11 profile; Phase 13 does not invent automatic retries.

Trust failure remains distinct from reachability failure. A previously untrusted/compromised peer becoming reachable again does not restore trust without owning authority/evidence. Cross-environment reachability becoming available again likewise does not grant production or recovery authority.

## Validation obligations

Conformance tests SHALL falsify at least:

- unauthenticated internal call from reachable network;
- service identity attempting unauthorized tenant/domain capability;
- stale placement routed to old cell;
- connector destination/redirect escaping allowed policy;
- parser attempting egress;
- cross-cell direct mutation attempt;
- stale `network_policy_generation` reopening access;
- realtime relocation/drain requiring resync;
- one destination/provider exhausting unrelated egress capacity;
- generation-authority conflation under `PRTV-042`;
- development/validation runtime reaching production credential/state/placement authority by network convenience;
- recovery reachability treated as normal production-serving authority under `PRTV-044`.

Exact ingress controller, load balancer, service discovery, mesh, proxy, DNS and private-connectivity products remain OPEN.
