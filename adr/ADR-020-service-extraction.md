# ADR-020 — Selective Evolution to Distributed Services

**Status:** accepted  
**Date:** 2026-08-17  
**Reversibility:** costly per extraction

## Context

The modular monolith intentionally avoids premature service distribution, but some workloads may later require independent scaling/security/runtime/release ownership. Without extraction criteria, teams either never separate bottlenecks or create microservices for appearance.

Drivers: `AP-15`, `INV-DATA-*`, `INV-CONTRACT-001`, `QA-SCALE-001`.

## Decision

A bounded context/workload becomes an independently deployed service only when at least one durable driver exists and the distribution cost is justified:

- independent scale profile not economically met in current deployment;
- required fault/blast-radius isolation;
- materially stronger security/runtime boundary;
- incompatible runtime/language/library need;
- independent release cadence with stable contract;
- clear team ownership that benefits from deployment autonomy;
- data locality/residency need requiring separation.

Extraction prerequisites:

- explicit ownership already exists;
- stable application/API/event contracts exist;
- no direct cross-domain database mutation;
- observability/correlation spans the new network boundary;
- retries/timeouts/idempotency are defined;
- data migration/dual-run/cutover plan exists;
- SLO/operational owner exists.

Extracted services SHALL own their persistence boundary; the system SHALL NOT create a distributed monolith where services share and mutate the same internal tables.

## Consequences

### Positive
- services emerge from evidence;
- modular-monolith work is preserved;
- each network boundary has explicit semantics.

### Negative / cost
- extraction remains significant engineering/operations work;
- some local calls become eventually consistent/networked.

## Validation

Every extraction RFC/ADR must show the measured driver, expected benefit, SLO impact, data migration and rollback. If the benefit cannot justify network/ops cost, keep the module co-located.

## Exit / revisit conditions

This ADR governs the extraction policy itself and is expected to remain stable; individual services require their own ADRs.