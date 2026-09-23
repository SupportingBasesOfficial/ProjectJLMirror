# G5 Problem + Health — AI Task Packet

SLICE: `g5.problem-health@1`

GOAL: An authorized tenant user can inspect canonical Problems and Health for monitored resources with truthful lifecycle, evidence and currentness semantics.

## STOP CONDITIONS

Stop if implementation requires:

- modifying shared Monitoring/G1–G4 substrate;
- creating new Problem/Health persistence;
- direct provider reads/passthrough;
- resolving Problems from omission;
- computing Health in UI/BFF;
- treating no visible Problems as healthy;
- treating provider ACK as JLMirror ACK;
- adding Alerting/ACK/ITSM/notification behavior;
- production behavior.

## ALLOWED PATHS

```text
apps/g5-problem-health/
contracts/g5-problem-health/
implementation/g5-problem-health/
tests/g5/
tools/g5/
.github/workflows/g5-problem-health-runtime.yml
```

## IMPLEMENTATION CLAIM

```json
{"schema_version":1,"authorization_id":"g5.problem-health@1","slice_id":"g5.problem-health@1"}
```

Branch prefix: `impl/g5-problem-health`  
Required label: `jlmirror-slice:g5-problem-health`

## BINDING SEMANTICS

```text
problem_id = canonical platform identity
provider eventid != problem_id
provider acknowledged != JLMirror ACK
problem state != health projection
problem/health != alert state
incomplete omission != resolved
problem absence without completeness != healthy
stale/incomplete != healthy
out_of_scope/removed/historical != current health authority
```

## API

Use only accepted:

```text
GET /problems
GET /problems/{problem_id}
GET /health-projections
GET /health-projections/{monitoring_resource_id}
```

Actions: `monitoring.problem.read`, `monitoring.health.read`.

## TESTS

At minimum prove:

1. Problem active/resolved representation;
2. provider event ID remains external reference only;
3. provider ACK cannot become JLMirror ACK;
4. incomplete/stale omission never presents resolved;
5. historical active Problem is non-current;
6. Health canonical classes only;
7. healthy requires accepted completeness evidence from canonical projection;
8. stale/incomplete/out-of-scope/removed/historical health is never presented as fresh healthy authority;
9. cursor anchors revalidate same tenant/filter/generation;
10. Problem responses no-store;
11. Health responses private-revalidate;
12. cross-tenant/revoked fail closed;
13. browser E2E activation/recovery + health transition;
14. Wave 4 Problem/Health PostgreSQL conformance reuse;
15. runtime/container proof;
16. semantic scope rejects Alerting/ACK/ITSM/provider passthrough/new persistence.

```text
G5 != G6
PROBLEM != ALERT
HEALTH != ALERT
PROVIDER_ACK != JLMIRROR_ACK
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
