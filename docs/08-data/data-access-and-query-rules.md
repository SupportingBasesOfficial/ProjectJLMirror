# Data Access and Query Rules

**Status:** accepted

## Repository/application boundary

Transport handlers do not issue domain SQL directly. Owning application/domain modules expose use cases/query contracts; infrastructure adapters implement persistence.

A domain never mutates another domain's tables simply because they share a database.

## Query ownership

Cross-domain reads use one of:

- explicit owning-domain query/application contract;
- read model/projection built for the consumer;
- accepted cross-domain relational read where documented and still owner-safe.

High-fanout dashboards/reporting prefer projections rather than arbitrary joins across every operational schema.

## Current versus history

Current-state API queries read current-state transactional projections. Historical telemetry queries use time-range-bounded telemetry access. No current-state screen should depend on scanning full history for every resource.

## Pagination

Large collections use stable cursor/keyset pagination where offset cost or concurrent mutation makes offset unsuitable. Sort keys include deterministic tie-breaker identity.

The API contract phase will define external cursor encoding; database queries must support it with matching indexes.

## Read replicas

Future read replicas may serve explicitly stale-tolerant queries. A query requiring read-after-write/strong consistency remains on authoritative writer or an equivalently consistent path. Code does not silently move every read to replicas.

## Direct SQL/data administration

Interactive SQL is a privileged administrative capability, not a normal repository bypass.

It uses:

- dedicated least-privilege database/query principal;
- explicit tenant scope resolved by trusted platform control;
- a tenant binding that caller-authored SQL cannot replace;
- read-only default;
- statement/transaction timeout;
- row/result-size limits;
- restricted dangerous operations;
- immutable audit;
- no database superuser or normal migration-owner credential.

### Tenant binding rule

The normal application transaction may use a server-set transaction-local tenant GUC because the SQL statements are platform-owned. **Interactive arbitrary SQL may not rely on that mutable GUC as its sole RLS authority.**

An implementation must use a tenant-bound database principal/protected principal-to-tenant mapping, a mediated query/read-model surface, or a physically tenant-isolated target with equivalent enforcement. The query principal cannot change its tenant authority through `SET`, `set_config`, role/session-authorization changes, search-path tricks or caller-controlled helper functions.

If the implementation cannot prove that invariant, direct SQL to pooled protected base tables is not offered.

Read-only transaction state does not by itself solve tenant switching; isolation is validated independently.

## Query observability

Slow/high-cost query telemetry includes cell, owning domain/query name, tenant-safe identifier, duration/rows and trace correlation without logging parameter secrets/PII.

## N+1 and fanout

Repository/query design treats N+1 queries and per-resource external calls as correctness-at-scale concerns. Batch/read-model patterns are designed before high-cardinality endpoints are released.

## Schema leakage

Public/API contracts do not mirror database rows by default. Renaming an internal table/column must not automatically become an external breaking change.
