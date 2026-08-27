# Wave 4 Monitoring Entry Gate

**Status:** proposed gate record  
**Base authority:** `main@d63b435ffa26fba7794187ceafaf0d5a9773223b`  
**Scope:** Monitoring first vertical entry prerequisites; no implementation authorization  
**Depends on:** accepted Implementation Readiness Gate, Waves 0–3, `CAP-MONITORING`, `FR-MON-001..006`, Monitoring bounded context/data ownership, Phase 09/10 contracts, Zabbix provider contract, `OPEN-REL-030`

## Purpose

Wave 4 is not a generic “start product code” phase. `docs/16-implementation-readiness/11-initial-implementation-sequencing.md` requires a Product/domain vertical slice to have exact endpoint/event/data/authority contracts before it starts, and separately states that `impl.customer-telemetry@1` remains blocked until the C2 mechanism required by `OPEN-REL-030` is selected and conformance evidence is accepted.

This gate records the exact Monitoring entry state so that:

- accepted Product/domain semantics are not confused with candidate implementation mechanisms;
- the Zabbix provider contract is not mistaken for the Monitoring domain contract;
- an evidence spike is not mistaken for canonical customer-telemetry implementation;
- endpoint implementation does not invent missing state/identity/authorization semantics;
- merging documentation does not silently become implementation authorization.

## Canonical pre-state at this gate base

At `main@d63b435ffa26fba7794187ceafaf0d5a9773223b`:

### Already present

- Product capability/scope for Monitoring (`CAP-MONITORING`, `FR-MON-001..006`);
- accepted Monitoring bounded-context ownership;
- accepted logical `monitoring` data ownership;
- generic Phase 09 resource-family vocabulary;
- accepted transaction/outbox/idempotency/recovery laws;
- accepted Phase 10 async semantics;
- accepted Waves 0–3 implementation substrate;
- Zabbix provider trust/auth/poll/reconciliation profile;
- `OPEN-REL-030` decision record with Tier 1 PostgreSQL mechanism selected at pattern level and TimescaleDB retained only as a leading Tier 2 candidate pending conformance.

### Still missing before this branch

- exact canonical Monitoring domain lifecycle/state semantics suitable for implementation;
- exact endpoint/use-case contracts under the Phase 09 endpoint template;
- explicit canonical problem severity/health/evidence vocabulary and Zabbix normalization destination;
- explicit source ordinary-edit vs replace-instance API contract;
- explicit public/query semantics for historical completeness/gaps;
- an accepted bounded `OPEN-REL-030` conformance evidence result.

The first five are **normative contract gaps**. The last is an **evidence-generating C2 gap**. They must not be closed by the same kind of artifact.

## Two-track governance split

The required progression is:

```text
TRACK A — normative contract authority
  Monitoring domain contract
    + Monitoring API contract
    + provider normalization propagation
  -> exact-HEAD review
  -> explicit merge authorization
  -> accepted contract base

TRACK B — C2 evidence authority
  bounded OPEN-REL-030 spike from accepted contract base
  -> experimental/conformance code + evidence only
  -> falsification / security / concurrency / recovery / capacity evidence
  -> reviewed C2 decision update
  -> explicit merge/acceptance authorization

ONLY AFTER BOTH
  -> explicit Wave 4 implementation authorization
  -> canonical Monitoring vertical implementation PR(s)
```

Track B SHALL NOT precede Track A in a way that lets candidate code define the missing domain/API semantics. Track A SHALL NOT claim Track B evidence exists.

## Track A — artifacts proposed by this branch

### 1. Monitoring domain contract

`docs/03-domains/monitoring-domain-contract.md` fixes:

- canonical logical identities for source/resource/metric/observation/problem/health/sync operation;
- source-instance generation and replacement semantics;
- current evidence vs stale/incomplete/reconciliation semantics;
- resource removal, metric retirement and problem resolution negative-evidence rules;
- canonical problem severity and health vocabularies;
- provider acknowledgement/tag non-authority;
- historical observation/completeness/gap semantics;
- current-state semantic idempotency;
- dashboard ownership boundary;
- authorization action vocabulary;
- recovery/relocation/fencing consequences.

### 2. Monitoring API contract

`docs/09-api-contracts/monitoring-domain-api-contract.md` fixes the initial accepted Monitoring endpoint set:

```text
GET/POST    /monitoring-sources
GET/PATCH   /monitoring-sources/{source_id}
POST        /monitoring-sources/{source_id}:replace-instance
GET         /monitoring-resources
GET         /monitoring-resources/{resource_id}
GET         /metric-definitions
GET         /metric-definitions/{metric_definition_id}
GET         /metric-observations            (mandatory bounded metric/time window)
GET         /problems
GET         /problems/{problem_id}
GET         /health-projections
GET         /health-projections/{resource_id}
GET         /monitoring-sync-operations
GET         /monitoring-sync-operations/{operation_id}
```

It also fixes current authorization, cache, cursor semantics, source mutation idempotency/concurrency, historical completeness representation, safe failure semantics and operation authority.

No tenant-facing manual `:sync/:retry/:resume`, source `DELETE`, provider write-back, alert acknowledgement, incident creation or mutable dashboard endpoint is created without Product authority.

### 3. Zabbix normalization propagation

The Zabbix profile must consume the new canonical Monitoring severity/metadata decisions:

```text
Not classified -> unknown
Information    -> informational
Warning        -> warning
Average        -> degraded
High           -> critical
Disaster       -> critical
```

Zabbix acknowledgement remains provider metadata and does not become JLMIRROR Alerting/ITSM acknowledgement. Zabbix tags remain bounded provider metadata/evidence and do not become tenant/authorization/resource identity.

## Readiness matrix after Track A acceptance

The table describes the state **if and only if this exact contract package is accepted**. It does not itself grant implementation authority.

| Slice/capability | Contract state after Track A | Evidence/mechanism state | Result |
|---|---|---|---|
| Monitoring domain semantics | exact proposed contracts become accepted | n/a | contract-ready |
| Monitoring source management API | exact endpoint/authority/idempotency contracts exist | credential-binding/secret mechanism remains C2 | contract-ready; mechanism selection still required where used |
| Zabbix provider trust/auth/reconciliation | accepted provider profile + Monitoring normalization destination | provider production numerics remain C3 | provider-contract-ready |
| `impl.customer-telemetry@1` | domain/API semantics exist | `OPEN-REL-030` conformance NOT YET accepted | **bounded-evidence-spike-only** |
| historical Tier 2 projection | semantics exist | TimescaleDB only leading candidate | **not canonical** |
| Monitoring read APIs backed by customer telemetry | contracts exist | ingestion/projection conformance still blocked | implementation authorization blocked with telemetry path |
| general integration-event broker for raw telemetry | not required by contract | broker C2 independent | no forced dependency |
| Alerting / ITSM / AIOps consumers | separate domain Product contracts | not activated by Monitoring | blocked until their own vertical contracts |

## Track B — exact bounded evidence program required next

After Track A is accepted, the next repository mutation should be a **separate evidence branch/PR**, not a production implementation branch.

Recommended lineage:

```text
base: exact accepted Track A squash on main
branch: evidence/open-rel-030-monitoring-conformance
artifact class: C2 bounded spike / conformance evidence
canonical product behavior: unchanged
```

The spike must produce reproducible evidence for at least these classes already required by the current `OPEN-REL-030` record and the new Monitoring contracts:

### Tier 1 PostgreSQL authority

- real multi-connection atomic create-or-observe;
- observation persistence + one historical projection obligation;
- current-state candidate CAS independent from first observation acceptance;
- transition identity + signal obligation atomicity;
- concurrent duplicate/replay behavior;
- crash injection before/inside/after commit boundaries;
- backlog when Tier 2 is unavailable;
- restore/PITR `(R,F]` continuity.

### Zabbix provider/current-state/history behavior

- single-winner fenced poll epoch/generation under concurrent scheduled/hint work;
- stale poll rejection;
- provider clock rollback without current-state freeze;
- repeated same current observation without duplicate semantic transition;
- same-second history saturation/checkpoint safety;
- late insertion beyond fast overlap recovered by independent bounded sweep;
- provider/proxy outage widening/reconciliation;
- visibility-anchor loss blocking negative inference;
- incomplete snapshot blocking remove/retire/resolve;
- relocation/PITR poll-authority continuity.

### Tier 2 candidate security

For TimescaleDB, if retained as candidate, attack the exact features intended for production:

- raw hypertables;
- compressed/columnar states actually used;
- continuous aggregates and backing/materialization objects;
- projection workers;
- application/reporting/read roles;
- background refresh/compression/retention jobs;
- migration/DDL and operational roles;
- `SET`, `set_config`, role/session authorization, search-path and helper-function abuse;
- backup/PITR/recovery role/policy/object restoration.

One leaked Tenant B row under Tenant A context rejects the tested profile.

### Tier 2 capacity under the same security profile

Measure, without disabling required isolation:

- representative multi-tenant ingest;
- per-tenant skew/noisy-neighbor pressure;
- bounded time-range queries;
- retention/compression/rollup behavior;
- background-job load;
- downstream outage/backlog/drain;
- storage growth/cost dimensions sufficient to inform later C3 production numerics.

A benchmark obtained by weakening required tenant isolation is invalid evidence.

## Evidence artifact requirements

The Track B PR must include machine/reviewer-consumable evidence sufficient to reproduce or falsify each claim:

```text
spike manifest + exact base/head
candidate/version/config profile
schema/migration used by spike
commands/test harness owned by repository
fault/concurrency scenarios
security isolation matrix
capacity dataset/workload description
measured results with provenance
known limitations/failures
cleanup / no production authority statement
C2 decision conclusion: accept candidate | reject candidate | further bounded evidence required
```

A passing benchmark is not a substitute for security/concurrency/recovery evidence. A passing unit test is not a production capacity claim.

## Decisions intentionally not made by this gate

This gate does not select:

- identity provider/session/CSRF C2 choices;
- general async broker/product/topology;
- message-equivalence cryptographic mechanism/backend;
- production cell/region counts;
- production SLO/RPO/RTO/retention/poll/page/window/backlog numerics;
- Alerting/ITSM/AIOps product slices;
- public SDKs;
- manual tenant synchronization/retry controls;
- source retirement/deletion semantics;
- cross-domain dashboard persistence.

Those remain under their owning Product/C2/C3 authority and cannot be smuggled into the Monitoring implementation as framework defaults.

## Gate acceptance criteria

Track A is ready for acceptance only when exact-final-HEAD review proves:

1. every Monitoring concept implemented by the proposed API has one owner and one canonical identity;
2. source ordinary edit cannot bypass explicit provider-instance replacement/generation semantics;
3. provider/native identity/severity/tag/ack cannot become tenant/platform authority;
4. current-state ordering is fenced but semantic transition remains idempotent;
5. historical acceptance is independent from current-state candidacy;
6. historical query completeness never means “no error occurred”; it is evidence-backed;
7. incomplete/uncertain snapshots never create authoritative absence;
8. API operations satisfy tenant/current-authorization/idempotency/concurrency/cache/error/recovery semantics from Phase 09;
9. dashboard composition does not transfer Monitoring ownership into a generic presentation aggregate;
10. `OPEN-REL-030` remains explicitly open and no candidate telemetry store is declared canonical without evidence;
11. no Wave 0–3 implementation substrate is modified by this normative contract PR;
12. P0/P1/P2 findings and review threads are zero on the exact final HEAD.

Even after a clean Track A gate, merge requires separate explicit user authorization.

## Advancement states

```text
CURRENT BASE d63b435f...
  Wave 4 Monitoring entry        BLOCKED ON CONTRACT + C2 EVIDENCE

AFTER TRACK A ACCEPTED
  Monitoring contract authority  READY
  OPEN-REL-030                   STILL C2 OPEN
  customer telemetry             BOUNDED EVIDENCE SPIKE ELIGIBLE ONLY
  canonical Wave 4 implementation NOT AUTHORIZED

AFTER TRACK B ACCEPTED
  Monitoring contract authority  READY
  OPEN-REL-030                   selected + conformed for accepted candidate/profile
  Wave 4 implementation          ELIGIBLE FOR SEPARATE EXPLICIT AUTHORIZATION
```

This state machine is the gate. No CI status, candidate code, external reviewer or AI output can skip a transition.
