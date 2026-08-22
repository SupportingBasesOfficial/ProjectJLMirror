# Phase 13 — Isolated and Privileged Execution Profiles

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This document defines smaller trust envelopes for automation, untrusted parsing, interactive/administrative data work, migration and recovery. These capabilities are intentionally not hosted as ordinary API privileges.

## Isolation principle

Privilege is decomposed by purpose. A privileged capability receives only the target scope, state ports, network destinations, secret references and time/resource envelope needed for that operation.

No runtime profile may gain authority merely because it can execute arbitrary code.

## Automation execution

`runtime.automation@1` requires an execution record with:

```text
operation_id
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
- untrusted/user-authored content cannot request broader credentials/network than its accepted profile;
- runtime filesystem/process state is non-authoritative;
- cancellation/timeout does not prove no external effect occurred;
- outputs are bounded and classified before storage/release;
- ambiguous provider/external effects use accepted reconciliation semantics.

## Untrusted parsing/transformation

`runtime.untrusted-parser@1` is used when accepted artifact/import/content handling requires parser isolation.

Minimum properties:

- no general tenant DB or secret authority;
- deny-by-default external network;
- bounded input/output/CPU/memory/time/process count/storage;
- ephemeral workspace isolated between operations;
- active-content/parser result cannot directly trigger privileged execution;
- parser output is still untrusted structured data until owning contract validation completes;
- crash/timeout produces explicit processing outcome, not acceptance.

Exact sandbox/container/VM/wasm technology remains OPEN.

## Interactive query / data administration

Caller-authored SQL or equivalent privileged data query must not run under ordinary application DB-owner identity.

A compliant runtime provides:

- dedicated database/runtime principal;
- tenant binding the query author cannot override for pooled protected data, or an equivalent mediated/physically isolated surface;
- query timeout/row/byte/concurrency/cost bounds;
- current authorization and privileged audit;
- restricted network/secret access;
- no ability to mutate unrelated domain/control-plane state by default.

Interactive query capability does not become cross-tenant wildcard authority implicitly.

## Migration execution

`runtime.migration-admin@1` separates schema/data migration privilege from serving application roles.

Properties:

- explicit environment/cell/data scope;
- immutable migration identity/version supplied by later release authority;
- expected schema/config/generation preconditions;
- bounded lock/load/backfill behavior;
- reversible/forward-recovery contract where applicable;
- destructive steps require accepted fencing/governance predicates;
- mixed-version compatibility is checked before ordinary serving runtime depends on the new state.

Phase 14 owns release sequencing and artifact provenance; Phase 13 owns the runtime privilege/isolation capability.

## Recovery execution

`runtime.recovery@1` can perform narrowly accepted restore/reconciliation/fence/resumption preparation.

It SHALL NOT:

- restore old revocations/permissions as current;
- infer effect absence from restored missing inbox/outbox/operation evidence;
- recreate cryptographically erased key paths contrary to current governance;
- clear legal hold/erasure state from stale snapshot;
- resume tenant traffic solely because database/objects are reachable;
- bypass current placement/admission generation.

Recovery operations are auditable and retain the exact source recovery point/fence scope needed for `(R,F]` reconciliation.

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

## Credential lending prohibition

A privileged orchestrator SHALL NOT solve least privilege by handing its unrestricted credential to a child job/container/parser. The child receives a scoped identity/reference appropriate to its profile.

## Output and artifact handling

Privileged execution output is not automatically safe to expose. Logs, query results, reports, parser output and recovery diagnostics follow data classification, redaction, artifact lifecycle and current release authorization.

## Resource/cost isolation

Privileged and user-triggerable execution must be bounded by tenant/principal/operation/workload dimensions. One expensive query, import, report, script or recovery task cannot consume unlimited shared runtime/state-port capacity.

## Validation obligations

Tests SHALL cover:

- parser attempt to access secrets/network/state ports outside profile;
- automation target-scope escape;
- interactive query attempting to override tenant binding;
- application principal attempting migration/admin operation;
- migration principal used for ordinary serving traffic;
- recovery from old snapshot attempting to restore retired authority;
- timeout/cancellation with ambiguous external effect;
- privileged workload saturation affecting unrelated serving classes;
- child execution receiving broader credential than profile.

Any implementation that cannot enforce these boundaries must separate the affected profiles physically or choose a different runtime mechanism.