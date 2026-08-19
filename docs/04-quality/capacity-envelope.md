# Capacity Envelope

**Status:** accepted
**Measurements:** OPEN

The capacity-envelope framework, required dimensions and evidence discipline are accepted. Measured workload tiers, numeric thresholds and benchmark results remain OPEN.

Capacity-dependent technology, topology or specialization choices are not considered final merely because this framework is accepted. Before a later decision selects or materially specializes database/telemetry storage, queue/event transport, cache/replay infrastructure, WebSocket fan-out, worker concurrency or similar infrastructure **on capacity grounds**, that decision SHALL be tested against a stated workload envelope and the resulting evidence recorded.

Acceptance of architecture invariants justified independently by tenant isolation, ownership, consistency, security, recoverability, failure containment or portability does not depend on numeric capacity measurements already being available. Capacity evidence constrains later sizing, specialization, scale thresholds and technology choices; it does not retroactively make those accepted invariants provisional.

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

Capacity-dependent technology ADRs and later platform decisions for database topology, time-series storage, queue/event transport, cache, WebSocket fan-out and worker concurrency SHOULD reference measured tests against this envelope before those capacity-dependent selections or thresholds are declared final.