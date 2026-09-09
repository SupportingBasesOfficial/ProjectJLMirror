# Wave 4 Monitoring/Zabbix — Implementation Authorization

**Status:** proposed exact-scope authorization  
**Canonical base:** `main@860dbf5ffab465504f75ae7a13f13a13ed3bcd7f`  
**Authorization ID:** `wave4.monitoring-zabbix.vertical@1`

## Purpose

This record is the separate explicit implementation-authorization gate required before canonical Wave 4 Monitoring product code may begin.

It does not implement Monitoring. It defines exactly what a later implementation PR may implement and what remains forbidden.

## Authorization on acceptance

If this exact authorization package is reviewed, accepted and separately merged, canonical implementation may begin for exactly:

- `impl.customer-telemetry@1`, limited to the accepted D2 Track B profile;
- `impl.provider-integration@1`, limited to the accepted Monitoring/Zabbix subprofile.

Those slices may consume already accepted Waves 1–3 substrate as dependencies. This is not a re-authorization or expansion of those substrate slices.

The implementation remains bound to the accepted Monitoring domain, API, event, telemetry-data, Zabbix provider and normalization contracts.

## What this enables in practical product terms

After this authorization becomes canonical, implementation PRs may begin building the first real JLMirror Monitoring vertical, including bounded work for:

- Monitoring domain runtime and use cases;
- Monitoring transactional/durable data structures and migrations required by accepted contracts;
- customer telemetry acceptance/current/history/projection implementation;
- Zabbix read-only provider adapter and normalization;
- provider/customer-telemetry workers;
- accepted Monitoring API/BFF surfaces;
- accepted Monitoring event publication/consumption joins;
- observability, release and recovery joins required by the authorized slices;
- end-to-end tests proving tenant/current-authority, generation, scope, idempotency, ambiguity and recovery boundaries.

Implementation remains incremental by coherent vertical/use-case slices. Authorization does not require one PR per table, entity, endpoint or internal object.

## Product Experience / frontend boundary

This authorization deliberately does **not** authorize frontend route creation.

The following are non-equivalences:

```text
DATABASE TABLE != FRONTEND ROUTE
DOMAIN ENTITY != FRONTEND ROUTE
API ENDPOINT != FRONTEND ROUTE
USE CASE != FRONTEND ROUTE
BACKEND MODULE != NAVIGATION DESTINATION
```

Future frontend work is governed by Product Experience Architecture. Navigation must be designed around user tasks, workflows and context, with progressive disclosure of depth. Multiple backend capabilities may compose one coherent product surface, and one product surface may expose tabs, panels, drawers, drill-downs or contextual actions without becoming multiple primary routes.

The target frontend remains complete, professional, intuitive and operationally deep; simplicity at the surface must not remove expert capability underneath.

## Existing substrate consumed, not newly granted

The authorized Monitoring vertical may consume the already accepted implementation substrate for:

- identity/BFF/current authorization;
- control-plane placement/currentness;
- platform runtime boundaries;
- transactional cell data;
- async outbox/inbox/idempotency/reconciliation;
- observability;
- release/supply-chain assurance.

Consumption never permits Monitoring code to redefine those owners.

## Explicit non-authority

This gate does not authorize:

- production deployment;
- `OPEN-REL-020` C3 production capacity/performance/cost numerics;
- production partition topology;
- production retry/backoff/jitter values;
- production retention/replay/quarantine horizons;
- Alerting, ITSM, Automation, AIOps, FinOps or Commercial product behavior;
- unrelated providers;
- Zabbix/provider write-back;
- public/outbound Monitoring webhooks;
- browser realtime activation;
- public SDK/public projection families;
- privileged direct-query surfaces;
- a frontend information architecture or route tree.

## Historical authority rule

D2, D3 and D4 records that state Wave 4/Product implementation authority was not granted remain immutable historical truth. They record the authority state at those transitions.

This authorization is a successor authority. It does not rewrite predecessor snapshots.

```text
HISTORICAL NOT_GRANTED != CURRENT AUTHORIZATION REGRESSION
SUCCESSOR AUTHORIZATION != PREDECESSOR REWRITE
```

## Implementation law after acceptance

Every later Monitoring implementation PR must prove that its changed code belongs to this exact authorization scope and accepted contracts.

Code presence, route registration, database migration, feature flag, framework convention or provider capability cannot expand Product authority.

```text
ELIGIBLE_FOR_AUTHORIZATION != AUTHORIZED_TO_IMPLEMENT
AUTHORIZED_TO_IMPLEMENT != PRODUCTION_AUTHORIZED
AUTHORIZED BACKEND CAPABILITY != FRONTEND ROUTE
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```

## Merge boundary

This document is a proposal until the exact PR HEAD passes dedicated authorization validation, deterministic assurance, panoramic/adversarial review and zero unresolved material findings, followed by separate explicit user authorization for squash merge.
