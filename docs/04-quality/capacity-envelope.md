# Capacity Envelope

**Status:** draft / open measurements

Architecture choices are not considered final until tested against a stated workload envelope.

## Required dimensions

The capacity model SHALL track at minimum:

- active tenants;
- users/principals per tenant;
- monitored resources/devices per tenant;
- metric definitions per resource;
- telemetry samples per second and per day;
- event/problem/alert rate;
- concurrent WebSocket connections and message rate;
- HTTP request rate by operation class;
- background jobs per second/minute and queue latency;
- integration/provider calls and provider rate limits;
- webhook/notification delivery rate;
- report generation concurrency and artifact volume;
- transactional database size/growth;
- telemetry size/growth and retention;
- audit size/growth and retention.

## Envelope tiers

Numbers are intentionally OPEN until validated. Capacity planning will define at least:

- **Baseline:** initial production target with headroom;
- **Growth:** expected near-term scale without architectural rework;
- **Stress:** validated failure/degradation boundary;
- **Rearchitecture trigger:** measured threshold that justifies storage specialization, placement expansion, or service extraction.

## Per-tenant skew

Averages are insufficient. The model SHALL include large-tenant skew because one tenant may dominate resources, metrics, queries, connections or automation load.

## Validation

Technology ADRs for database topology, time-series storage, queue/event transport, cache, WebSocket fan-out and worker concurrency SHOULD reference measured tests against this envelope.