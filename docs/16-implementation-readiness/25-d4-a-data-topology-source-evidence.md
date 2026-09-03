# D4-A — Regulated Payload and Topology Source Evidence

**Status:** source-evidence harness only — no new ledger credit, no Kafka selection, no D4/Wave 4/Product/production/C3 authority granted  
**Canonical source base:** `main@63ced38f95b516b495db3f238e1a9e8689b184eb`  
**Track:** D4-A — broker transport, physical routing and anti-corruption boundary

## Purpose

This package executes the second preferred D4-A source-evidence block after the semantic-boundary package and its separate 2/7 ledger promotion.

It targets exactly two still-open evidence IDs:

- `regulated_payload_erasure_granularity`;
- `physical_naming_routing_and_cell_topology_adapter_mapping`.

This PR does **not** promote either ID. A green source run only produces immutable provenance for later exact-run review and a separate ledger-promotion action.

```text
SOURCE RUN != LEDGER CREDIT
PHYSICAL MAPPING != LOGICAL IDENTITY
BROKER ROUTE != TENANT AUTHORITY
OPAQUE REFERENCE != AUTHORIZATION
BOUNDED TEST EXCEPTION != PRODUCTION RETENTION POLICY
D4-A PARTIAL EVIDENCE != KAFKA SELECTION
```

## Evidence 1 — regulated-payload erasure granularity

The source harness implements the accepted Phase 10 classification boundary for ordinary async record values.

The default `sensitive_or_regulated` profile is reference-based:

- raw regulated record-value bytes are rejected unless an explicit exception satisfies **all** binding controls;
- the accepted ordinary representation is an opaque tenant-bound record reference;
- an executable governed opaque store proves one record/reference can be erased while a neighboring record remains present;
- a cross-tenant reference or cross-tenant erase attempt fails closed;
- `secret_or_credential` remains prohibited in ordinary async payloads.

The negative control intentionally attempts raw regulated payload publication without an exception and must fail.

### Raw regulated exception

The source boundary models the exception only to prove that its controls are conjunctive. Raw regulated bytes are eligible only if all of these are true together:

1. per-tenant topic or partition assignment is explicitly present;
2. a positive maximum segment-retention ceiling is present and is no longer than the governed erasure SLA used by the bounded test;
3. erasure-governance sign-off is explicitly present.

Negative controls independently remove each control and require rejection.

The bounded test values are not production retention numerics and do not grant C3 authority.

## Evidence 2 — physical naming/routing/topology adapter mapping

The topology evidence uses a logical delivery identity containing only logical tenant/contract/message semantics. `topic`, `consumer_group` and `cell` exist only in a `PhysicalRoute` returned by a replaceable `TopologyAdapter`.

The executable proof establishes:

- tenant + contract authorization is checked before route lookup;
- an unauthorized tenant cannot obtain a valid physical mapping even when that tenant/contract has a route entry elsewhere;
- arbitrary payload fields named `topic`, `consumer_group`, `cell` or `tenant_id` cannot override trusted mapping;
- replacing the physical mapping changes topic/group/cell while leaving the logical delivery identity unchanged;
- consumer semantics therefore do not require rewrite merely because physical placement changes.

No physical route field becomes contract identity, message identity, tenant authority, ordering authority or production topology authority.

## Source-only boundary

The package manifest is:

`implementation/d4-eventing-async/source-evidence/data-topology/source-evidence-manifest.json`

It explicitly records:

- `current_run_auto_credit=false`;
- `ledger_credit=[]`;
- prior reviewed ledger credit remains exactly the two semantic-boundary IDs already promoted;
- Kafka remains `not_selected`;
- D4 transport authority remains `not_selected_not_granted`;
- Product/Wave 4 implementation authority remains `not_granted`;
- production authority remains `none`;
- C3 numeric/topology authority remains `not_selected`.

The source workflow revalidates the machine-owned D4 state and D4-A evidence plan, then asserts that this run cannot add either new evidence ID to `evidence_completed`.

## Immutable provenance

A successful exact-HEAD workflow resolves its own GitHub Actions job ID at runtime and emits `d4a-source-run-provenance-v1` containing:

- exact repository SHA;
- workflow run ID and attempt;
- exact job ID/name;
- probe/package identity;
- SHA-256 of the source manifest bytes;
- exact evidence IDs and evidence kinds;
- `current_run_auto_credit=false`;
- `ledger_credit=[]`;
- the separate-promotion rule.

The provenance artifact is uploaded with a name containing exact source SHA, run ID and run attempt.

## Explicit non-claims

This source package does not claim:

- a live Kafka broker run;
- Kafka selection;
- capacity or throughput evidence;
- partition-ceiling or ordering evidence;
- outage/backlog/recovery evidence;
- production topic/group/cell names;
- production partition/replica counts;
- production retention/erasure numerics;
- Product or Wave 4 implementation authorization;
- production deployment readiness.

## Exit gate

This source PR is eligible for merge only after:

1. exact-HEAD CI is fully green;
2. the regulated-payload negative controls prove default raw-value rejection, isolated per-record erasure and conjunctive exception controls;
3. topology controls prove authorization-before-mapping and semantic stability across a physically different replacement mapping;
4. the source manifest and runtime provenance are exact-HEAD reviewed;
5. the existing 2/7 D4-A ledger remains unchanged by this source run;
6. panoramic adversarial review is CLEAN on the exact HEAD;
7. zero unresolved material review threads remain;
8. separate explicit user authorization is given for merge.

Only after this source run is reviewed may a later PR propose promotion of these two evidence IDs from 2/7 to 4/7.
