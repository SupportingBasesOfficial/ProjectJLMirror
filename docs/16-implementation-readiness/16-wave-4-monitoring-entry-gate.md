# Wave 4 Monitoring Entry Gate

**Status:** proposed gate record  
**Base authority:** `main@d63b435ffa26fba7794187ceafaf0d5a9773223b`  
**Scope:** first Monitoring vertical entry prerequisites; no implementation authorization  
**Depends on:** accepted Implementation Readiness Gate, Waves 0–3, `CAP-MONITORING`, `FR-MON-001..006`, Monitoring ownership/data, Phase 09/10 contracts, Zabbix provider contract, `OPEN-REL-030`

## Purpose

Wave 4 is not a generic permission to start product code. The accepted sequencing rule requires exact Product/domain endpoint/data/authority contracts, while `impl.customer-telemetry@1` is separately blocked until `OPEN-REL-030` C2 selection/conformance evidence is accepted.

This gate prevents provider contracts, experimental code or infrastructure defaults from filling normative gaps silently.

## Canonical pre-state at base

At `main@d63b435ffa26fba7794187ceafaf0d5a9773223b` the repository already has:

- accepted Monitoring Product scope/requirements;
- Monitoring bounded-context/logical data ownership;
- generic Phase 09 Monitoring resource-family vocabulary;
- Phase 09/10 authority, transaction, async, recovery and collection laws;
- Waves 0–3 implementation substrate;
- accepted Zabbix trust/auth/poll/reconciliation profile;
- `OPEN-REL-030` with Tier 1 PostgreSQL pattern selected at mechanism level and TimescaleDB only a leading Tier 2 candidate pending evidence.

Still missing at that base:

- exact Monitoring canonical identity/lifecycle/negative-evidence/problem/health/current-metric semantics;
- exact endpoint/use-case contracts;
- explicit Zabbix problem/value normalization destination;
- accepted `OPEN-REL-030` conformance evidence.

The first three are **normative contract gaps**. The last is a distinct **C2 evidence gap**.

## Mandatory two-track progression

```text
TRACK A — normative authority
  Monitoring domain contract
  + Monitoring API contract
  + Zabbix normalization profile
  + this entry gate
  -> exact-HEAD adversarial review
  -> explicit merge authorization
  -> accepted contract base

TRACK B — C2 bounded evidence
  OPEN-REL-030 spike from exact accepted Track A base
  -> experimental/conformance code + reproducible evidence
  -> security/concurrency/recovery/capacity falsification
  -> reviewed C2 decision update
  -> explicit acceptance authorization

ONLY AFTER BOTH
  -> separate explicit Wave 4 implementation authorization
  -> canonical vertical implementation PR(s)
```

Track B cannot define missing Product/domain semantics by existing first. Track A cannot claim Track B evidence exists.

## Track A artifacts

### Monitoring domain contract

`docs/03-domains/monitoring-domain-contract.md` fixes:

- source/resource/metric/observation/problem/health/sync identities;
- strict provider-instance generation boundary for initial Zabbix mappings;
- explicit `metric_current_state` separate from history;
- source ordinary-edit vs replacement/fencing;
- current-state precedence vs semantic idempotency;
- authoritative negative evidence;
- severity/health/evidence vocabularies;
- historical completeness/gap semantics;
- dashboard/authorization/security/recovery/capacity boundaries.

### Monitoring API contract

`docs/09-api-contracts/monitoring-domain-api-contract.md` fixes:

```text
GET/POST    /monitoring-sources
GET/PATCH   /monitoring-sources/{source_id}
POST        /monitoring-sources/{source_id}:replace-instance
GET         /monitoring-resources
GET         /monitoring-resources/{resource_id}
GET         /metric-definitions
GET         /metric-definitions/{metric_definition_id}
GET         /metric-observations
GET         /problems
GET         /problems/{problem_id}
GET         /health-projections
GET         /health-projections/{resource_id}
GET         /monitoring-sync-operations
GET         /monitoring-sync-operations/{operation_id}
```

Metric-definition reads include the efficient `current_state` projection required by `FR-MON-003`; historical Tier 2 is not queried on each request to discover “latest”.

The API also fixes current auth/tenant routing, source mutation idempotency + `If-Match`, source replacement, canonical HTTPS endpoint input, errors/cache and finite history queries.

### Cursor governance

Monitoring collection continuation is deliberately constrained to Phase 09 `url_safe_non_sensitive_handle` semantics:

- exposed cursor contains/reveals no protected payload/credential/provider secret/physical topology;
- possession grants no continuation authority;
- current authorization occurs on every page.

Therefore this initial vertical **does not activate or reclassify `OPEN-API-019`**, which remains C5 for protected continuation-token semantics. A future need for protected cursor payload/token behavior returns to owning governance.

### Zabbix normalization profile

`docs/09-api-contracts/zabbix-monitoring-normalization-profile.md` resolves the provider contract's deferred normalization question:

```text
Not classified -> unknown
Information    -> informational
Warning        -> warning
Average        -> degraded
High           -> critical
Disaster       -> critical
```

Acknowledgement and tags remain bounded provider metadata only, never JLMIRROR Alerting/ITSM/tenant/authorization authority. Zabbix value classes map to canonical Monitoring value kinds.

## Product-scope exclusions

Track A does not create:

- source delete/retirement semantics;
- tenant-facing manual `:sync/:retry/:resume`;
- provider write-back;
- Alerting acknowledgement/lifecycle;
- ITSM mutation;
- AIOps product behavior;
- public SDKs;
- a mutable Monitoring-dashboard aggregate.

Monitoring dashboards may compose current metric state, inventory, health, problems, history and sync evidence; persistent presentation/cross-domain projections remain Reporting & Experience ownership.

## Readiness matrix if Track A is accepted

| Slice/capability | Contract state | Evidence/mechanism state | Result |
|---|---|---|---|
| Monitoring domain semantics | exact | n/a | contract-ready |
| source management API | exact | credential binding/secret mechanism still C2 | contract-ready, mechanism selection where used |
| Zabbix trust + normalization | exact | provider production numerics C3 | provider-contract-ready |
| current metric projection semantics/API | exact | backing acceptance path still depends on telemetry conformance | contract-ready, implementation blocked with customer telemetry |
| `impl.customer-telemetry@1` | exact domain/API semantics | `OPEN-REL-030` NOT conformed | **bounded-evidence-spike-only** |
| Tier 2 history | exact semantics | TimescaleDB only candidate | **not canonical** |
| protected cursor C5 | not required | remains deferred | **not activated** |
| raw telemetry general broker | not required | broker C2 independent | no forced dependency |
| Alerting/ITSM/AIOps | separate Product/domain authority | not activated | blocked by own vertical contracts |

## Track B — required next bounded evidence program

After Track A acceptance, next mutation is a separate evidence branch/PR, conceptually:

```text
base    exact accepted Track A squash
branch  evidence/open-rel-030-monitoring-conformance
class   C2 bounded spike / conformance evidence
product semantics unchanged
production authority none
```

### Tier 1 PostgreSQL evidence

Prove with real multi-connection PostgreSQL:

- atomic create-or-observe;
- observation + exactly one history projection obligation;
- current-state candidate CAS independent from first acceptance;
- current metric projection advancement and semantic no-op on repeated current observation;
- transition identity + signal obligation atomicity;
- duplicate/concurrent/replay behavior;
- crash injection around transaction boundaries;
- downstream Tier 2 outage/backlog;
- restore/PITR `(R,F]` continuity.

### Zabbix/current/history evidence

- single-winner fenced poll epoch/generation across scheduled/hint work;
- stale poll/retired placement rejection;
- clock rollback without current-state freeze;
- same current observation without duplicate semantic transition;
- current metric state remains last-known + explicitly stale when authority is stale;
- same-second history saturation/checkpoint safety;
- delayed insertion beyond fast overlap recovered by independent bounded sweep;
- provider/proxy outage widening/reconciliation;
- visibility-anchor loss blocks negative inference;
- incomplete snapshot blocks remove/retire/resolve;
- new Zabbix generation cannot alias reused native IDs with old mappings;
- PITR/relocation poll-authority continuity.

### Tier 2 candidate security

If TimescaleDB remains candidate, attack exact intended features/roles:

```text
raw hypertables
compression/columnar states used
continuous aggregates/materializations
projection worker
application/reporting/read roles
background refresh/compression/retention jobs
migration/DDL/ops/recovery roles
SET/set_config/SET ROLE/session authorization/search_path/helper-function abuse
backup/PITR restored role/policy/object state
```

One Tenant B row reachable under Tenant A's normal trust class rejects that profile.

### Tier 2 capacity under same security profile

Measure representative multi-tenant ingest/skew, bounded time-range queries, compression/retention/rollup, background-job load, downstream outage/backlog/drain and storage/cost dimensions **without disabling required isolation**.

Security-weakened benchmark results are invalid evidence.

## Evidence artifacts

Track B must retain machine/reviewer-consumable provenance:

```text
exact base/head
candidate/version/config
schema/migration
repo-owned test/fault harness
security matrix
workload/dataset definition
measured output
known failures/limits
cleanup/no-production-authority statement
C2 conclusion: accept | reject | further bounded evidence
```

Unit-green != capacity proof; benchmark-green != security/concurrency/recovery proof.

## Decisions intentionally not made

This gate does not select IdP/session/CSRF, general async broker/topology, message-equivalence crypto/backend, protected cursor C5, production topology/counts, production numerics, Alerting/ITSM/AIOps, manual tenant sync controls, source delete/retirement or cross-domain dashboard persistence.

## Track A acceptance criteria

Exact-final-HEAD review must prove:

1. every Monitoring concept has one owner/canonical identity;
2. Zabbix generation boundary cannot merge reused native IDs;
3. source ordinary edit cannot bypass explicit replacement;
4. base URL input cannot embed credentials/query/fragment and remains SSRF/egress controlled;
5. current metric state is explicitly separate from history;
6. fenced poll progress does not manufacture semantic state changes;
7. history acceptance is independent from current candidacy;
8. incomplete/uncertain snapshots cannot create absence/resolution;
9. severity/ack/tags/native IDs cannot become tenant/domain authority;
10. history completeness is evidence-backed;
11. Phase 09 current-auth/idempotency/precondition/cache/error/collection laws are preserved;
12. cursor class remains URL-safe/non-sensitive and does not silently reclassify C5;
13. `OPEN-REL-030` remains open and TimescaleDB remains non-canonical;
14. no Waves 0–3 implementation substrate changes;
15. exact final HEAD has P0/P1/P2=0 and no unresolved review thread.

A clean Track A gate still requires separate explicit user merge authorization.

## Advancement state machine

```text
CURRENT BASE d63b435f...
  Wave 4 Monitoring entry          BLOCKED ON CONTRACT + C2 EVIDENCE

AFTER TRACK A ACCEPTED
  Monitoring contract authority    READY
  OPEN-REL-030                     STILL C2 OPEN
  customer telemetry               BOUNDED EVIDENCE SPIKE ONLY
  protected cursor C5              UNCHANGED / NOT ACTIVATED
  canonical Wave 4 implementation  NOT AUTHORIZED

AFTER TRACK B ACCEPTED
  Monitoring contract authority    READY
  OPEN-REL-030                     SELECTED + CONFORMED FOR ACCEPTED PROFILE
  Wave 4 implementation            ELIGIBLE FOR SEPARATE EXPLICIT AUTHORIZATION
```

No CI result, candidate code, external reviewer or AI output can skip a transition.
