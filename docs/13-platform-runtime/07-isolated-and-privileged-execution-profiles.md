# Phase 13 — Isolated and Privileged Execution Profiles

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This document defines smaller trust envelopes for automation, untrusted parsing, interactive/administrative data work, migration and recovery. These capabilities are intentionally not hosted as ordinary API privileges and are additionally constrained by their canonical logical environment class.

## Isolation principle

Privilege is decomposed by purpose. A privileged capability receives only the target scope, environment class, state ports, network destinations, secret references and time/resource envelope needed for that operation.

No runtime profile may gain authority merely because it can execute arbitrary code, run in a privileged physical account/cluster, or carries a `production`/`recovery` environment label.

## Canonical environment constraint

Privileged and isolated execution uses the fixed Phase 13 logical classes:

```text
environment.development@1
environment.validation@1
environment.production@1
environment.recovery@1
```

Rules:

- every execution record carries the exact environment class;
- development/validation execution cannot acquire production credentials/state/tenant authority merely to improve fidelity;
- production privileged execution still requires explicit current operation/admin authority; environment label is not sufficient;
- `runtime.recovery@1` executes only in validation/recovery classes under the manifest; recovery reachability/restored data never creates normal production serving authority;
- migration/admin execution may target production only through current release/admin authorization and Phase 14 invocation controls;
- parser/automation children inherit only the environment/profile scope of their accepted parent operation and never a broader physical host/orchestrator credential;
- moving an execution implementation between physical environment mappings remains `OPEN-PRT-035`/Phase 14 and must preserve this semantic boundary.

`PRTV-044` applies to all privileged cross-environment data/credential/network paths.

## Automation execution

`runtime.automation@1` requires an execution record with:

```text
operation_id
environment_class
tenant/target scope
automation profile/version
current authorization evidence where required
credential-context reference
allowed egress profile
time/resource bounds
input/output classification
terminal/reconciliation state
```

Rules:

- execution occurs outside the primary API process;
- untrusted/user-authored content cannot request broader credentials/network/environment than its accepted profile;
- runtime filesystem/process state is non-authoritative;
- cancellation/timeout does not prove no external effect occurred;
- outputs are bounded and classified before storage/release;
- ambiguous provider/external effects use accepted reconciliation semantics;
- validation/development automation cannot be pointed at production targets with production credentials absent a separately accepted privileged operation.

## Untrusted parsing/transformation

`runtime.untrusted-parser@1` is used when accepted artifact/import/content handling requires parser isolation.

Minimum properties:

- no general tenant DB or secret authority;
- deny-by-default external network;
- bounded input/output/CPU/memory/time/process count/storage;
- ephemeral workspace isolated between operations and environment classes;
- active-content/parser result cannot directly trigger privileged execution;
- parser output is still untrusted structured data until owning contract validation completes;
- crash/timeout produces explicit processing outcome, not acceptance;
- parser access to recovery/production data remains mediated by the owning operation, never direct environment authority.

Exact sandbox/container/VM/wasm technology remains OPEN.

## Interactive query / data administration

Caller-authored SQL or equivalent privileged data query must not run under ordinary application DB-owner identity.

A compliant runtime provides:

- exact `environment_class`, tenant and data scope;
- dedicated database/runtime principal;
- tenant binding the query author cannot override for pooled protected data, or an equivalent mediated/physically isolated surface;
- query timeout/row/byte/concurrency/cost bounds;
- current authorization and privileged audit;
- restricted network/secret access;
- no ability to mutate unrelated domain/control-plane state by default.

Interactive query capability does not become cross-tenant or cross-environment wildcard authority implicitly. Validation/development query capability does not grant direct production data access by convenience.

## Migration execution

`runtime.migration-admin@1` separates schema/data migration privilege from serving application roles.

Properties:

- explicit environment/cell/data scope;
- immutable migration identity/version supplied by later release authority;
- expected schema/config/generation preconditions;
- bounded lock/load/backfill behavior;
- reversible/forward-recovery contract where applicable;
- destructive steps require accepted fencing/governance predicates;
- mixed-version compatibility is checked before ordinary serving runtime depends on the new state;
- a migration principal authorized in development/validation is not reusable in production without explicit production release/admin authority;
- migration does not carry production tenant data into validation/development except through a separate governed data path.

Phase 14 owns release sequencing and artifact provenance; Phase 13 owns the runtime privilege/isolation/environment capability.

## Recovery execution

`runtime.recovery@1` can perform narrowly accepted restore/reconciliation/fence/resumption preparation in `environment.recovery@1` or bounded validation scenarios.

It SHALL NOT:

- restore old revocations/permissions as current;
- infer effect absence from restored missing inbox/outbox/operation evidence;
- recreate cryptographically erased key paths contrary to current governance;
- clear legal hold/erasure state from stale snapshot;
- resume tenant traffic solely because database/objects/network are reachable;
- bypass current placement/admission generation;
- become ordinary production-serving authority because recovered state is complete or physically colocated with production;
- export protected recovery data into development/validation without owning governance/minimization authority.

Recovery operations are auditable and retain the exact source recovery point/fence scope needed for `(R,F]` reconciliation. Production handoff is an authority transition through current production predicates, not an environment relabel.

## Privileged separation matrix

| Capability | Ordinary API principal | Dedicated privileged principal |
|---|---|---|
| serve domain requests | yes | no |
| schema owner / destructive migration | no | yes |
| direct administrative SQL | no | yes |
| broad recovery/fence operations | no | yes |
| untrusted parser | no privileged data access | isolated parser principal |
| automation external credential | only if API itself owns that direct use | target-specific automation/worker profile |
| secret/key administration | no | separate security/key authority |

The matrix applies independently in each environment class; a privileged principal in one class is not automatically the same authority in another.

## Credential lending prohibition

A privileged orchestrator SHALL NOT solve least privilege by handing its unrestricted credential to a child job/container/parser. The child receives a scoped identity/reference appropriate to its runtime profile and environment class.

## Output and artifact handling

Privileged execution output is not automatically safe to expose. Logs, query results, reports, parser output and recovery diagnostics follow data classification, redaction, artifact lifecycle, environment scope and current release authorization.

Cross-environment output movement is a governed data transfer, not a filesystem/object copy convenience.

## Resource/cost isolation

Privileged and user-triggerable execution must be bounded by environment/tenant/principal/operation/workload dimensions. One expensive query, import, report, script or recovery task cannot consume unlimited shared runtime/state-port capacity.

## Validation obligations

Tests SHALL cover:

- parser attempt to access secrets/network/state ports outside profile/environment;
- automation target-scope or environment escape;
- interactive query attempting to override tenant/environment binding;
- application principal attempting migration/admin operation;
- migration principal used for ordinary serving traffic or reused across environment classes without authority;
- recovery from old snapshot attempting to restore retired authority;
- recovery reachability treated as production serving readiness;
- timeout/cancellation with ambiguous external effect;
- privileged workload saturation affecting unrelated serving classes;
- child execution receiving broader credential/environment scope than profile;
- production data/credentials entering development/validation without governed authority under `PRTV-044`.

Any implementation that cannot enforce these boundaries must separate the affected profiles/environments physically or choose a different runtime mechanism.
