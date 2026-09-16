# G2 Monitoring Source Onboarding — Implementation Authorization

**Status:** proposed exact-scope authorization  
**Canonical base:** `main@8e26b05596aeca2e45578908ca4afc4f1fa175d6`  
**Authorization ID:** `g2.monitoring-source-onboarding@1`

## Purpose

This is the separate implementation-authorization gate for the second AI-E2E product increment. It does not implement G2. It authorizes only the bounded user path required for an already-authorized tenant user to register an initial Zabbix Monitoring Source, submit only safe configuration plus an opaque credential-binding reference, observe durable validation/initial-sync state, and see controlled success/failure/reconciliation outcomes through the BFF/UI.

G2 MUST reuse the accepted Wave 4 Monitoring Source foundation and `wave4.zabbix-initial-validation-worker@1`. It MUST NOT create a parallel Monitoring model, duplicate source identity, or reinterpret provider-native identity as JLMirror authority.

## Authorization on acceptance

If this exact package is reviewed, accepted and separately merged:

```text
implementation_authority_before_merge = blocked
implementation_authority_after_merge = granted_for_exact_g2_monitoring_source_onboarding_only
```

The exact authorized slice is:

```text
g2.monitoring-source-onboarding@1
```

The observable outcome is an authorized tenant user creating an initial Zabbix Monitoring Source without exposing raw credentials, observing committed source identity and validation state, and receiving truthful controlled failure/reconciliation presentation while stale/cross-tenant authority fails closed.

`merge_authorization = not_granted` remains separate. This proposal does not authorize its own merge.

## Dependency boundary

G2 depends on the accepted G1 authorization contract and on accepted Wave 4 Monitoring substrate. The later G2 implementation MUST consume G1's authenticated tenant/BFF boundary rather than inventing another auth/session model.

If G1 implementation is not yet executable when G2 code is attempted, G2 may build against the accepted G1 contract and generated/test fixtures, but it MUST NOT weaken or bypass G1 authority to make G2 runnable.

## Existing Monitoring substrate to reuse

Canonical existing substrate includes, at minimum:

- `src/jlmirror_monitoring/**` Monitoring domain/application logic;
- `sql/wave4/**` Monitoring persistence and worker substrate;
- `implementation/wave-4/STATE.md` accepted initial-validation behavior;
- accepted Monitoring domain/API/provider contracts.

These shared existing paths are read-only under this authorization. G2-specific BFF/frontend composition belongs only in the G2 namespaces authorized below. There is deliberately **no G2 SQL namespace and no G2 domain-source namespace** in this authorization: source persistence and domain truth already exist in accepted Wave 4. If completing the slice requires changing accepted shared Monitoring substrate or adding parallel domain/persistence truth, implementation MUST stop and obtain a separate successor authorization.

## Implementation path authority

Allowed prefixes:

- `apps/g2-monitoring-source-onboarding/`;
- `contracts/g2-monitoring-source-onboarding/`;
- `implementation/g2-monitoring-source-onboarding/`;
- `tests/g2/`;
- `tools/g2/`.

Allowed exact path:

- `.github/workflows/g2-monitoring-source-onboarding-runtime.yml`.

Path admission alone is not sufficient. The trusted implementation-scope evaluator also applies a machine-verifiable semantic guard to executable G2 artifacts. It rejects forbidden G3/parallel-Monitoring path tokens and code markers such as canonical Monitoring resource/metric/problem/health/Alerting/replacement concepts or attempts to reference shared Monitoring implementation paths as writable implementation surface.

Required implementation PR identity:

- branch prefix `impl/g2-monitoring-source-onboarding`;
- label `jlmirror-slice:g2-monitoring-source-onboarding`;
- claim file `implementation/g2-monitoring-source-onboarding/IMPLEMENTATION_CLAIM.json`;
- exact authorization ID `g2.monitoring-source-onboarding@1`;
- same canonical repository;
- base is the repository current default branch and exact current default-branch tip when trusted evidence is produced.

Candidate-controlled relevance inference is forbidden. Once the trusted G2 scope command is invoked, omission of required branch/label/claim/path/semantic evidence fails closed.

## Product behavior authorized

The later implementation may expose only the minimum golden path required for:

1. source onboarding form/state through the protected G1 shell/BFF;
2. `provider_profile=zabbix` initial source creation;
3. canonical HTTPS provider endpoint configuration under accepted static safety rules;
4. opaque `credential_binding_ref` submission without secret bytes;
5. bounded configured HostGroup scope references;
6. creation of the first active source generation/configuration/scope revision using accepted Monitoring semantics;
7. durable `validation_and_initial_sync` responsibility;
8. execution/reuse of the accepted Wave 4 initial validation worker;
9. source list/detail/status and validation-operation read models needed by the onboarding journey;
10. truthful UI states for pending/current/incomplete/reconciliation-required/unavailable outcomes;
11. bounded user-initiated retry/reconciliation admission only when it consumes already accepted worker semantics and does not invent retry cadence/capacity authority;
12. browser E2E proving allowed, forbidden, cross-tenant and stale-authority paths.

## Source-create semantics that remain binding

The later implementation must preserve the accepted API rules:

```text
POST /api/v1/tenants/{tenant_id}/monitoring-sources
action monitoring.source.manage
Idempotency-Key required
```

The canonical request carries safe source configuration and `credential_binding_ref`, never raw API token/secret bytes.

A successful create means the local source transaction committed. It does **not** mean the provider is reachable or trusted. DNS/provider/network calls MUST NOT be held inside the local source-configuration transaction.

Current authentication/tenant placement/current authorization are re-established before the Monitoring use case. Idempotency never freezes permission.

## Initial validation semantics that remain binding

The existing accepted worker is authoritative for this slice's provider validation behavior:

- credential material is resolved only through the abstract secret boundary;
- outbound use is fail-closed through accepted outbound-admission semantics;
- only configured HostGroup anchors are validated for the accepted initial worker;
- success may mark source evidence `current` only if claimed source generation/configuration/scope/provider binding remains current;
- missing configured HostGroup yields incomplete/reconciliation-required evidence, not mass absence;
- credential/auth/provider/egress/protocol failure yields unavailable/reconciliation-required evidence;
- stale in-flight responses cannot update current source evidence;
- no automatic retry cadence is invented by G2.

## Required invariants

```text
CURRENT_PLATFORM_AUTHORIZATION -> BEFORE_MONITORING_USE_CASE
CLIENT_TENANT_ID != TENANT_AUTHORITY
PROVIDER_IDENTITY != PLATFORM_IDENTITY
PROVIDER_NATIVE_ID != CANONICAL_IDENTITY
CREDENTIAL_BINDING_REF != SECRET_BYTES
PROVIDER_PAYLOAD != TENANT_AUTHORITY
SOURCE_CREATE_SUCCESS != PROVIDER_REACHABILITY_PROOF
IDEMPOTENCY != AUTHORIZATION
STALE_GENERATION_OR_REVISION_EVIDENCE != CURRENT_SOURCE_AUTHORITY
PROVIDER_FAILURE != RESOURCE_ABSENCE
G2_COMPOSITION != PARALLEL_MONITORING_DOMAIN
```

## Explicit non-authority

This gate does not authorize:

- Monitoring Source instance replacement candidate/cutover product flow;
- host/resource inventory ingestion or inventory UI;
- metric definition/current/history UI;
- Problem/Health UI;
- changes to Monitoring -> Alerting transport;
- Alert policy/lifecycle;
- ACK/notification/escalation;
- ITSM, Automation, AIOps, FinOps or Commercial behavior;
- concrete secret-manager product selection;
- concrete egress transport selection;
- production deployment/C3 numerics;
- raw provider credential persistence or browser exposure;
- provider-native authorization truth;
- modification of accepted shared Monitoring/G1 substrate without successor authorization.

## Historical authority rule

Earlier records remain immutable source-time truth. This successor gate grants only this exact G2 implementation authority after canonical merge.

```text
G1_AUTHORIZED != G2_AUTHORIZED
G2_AUTHORIZED != G3_AUTHORIZED
G2_AUTHORIZED != PRODUCTION_AUTHORIZED
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```

## Merge boundary

This document remains a proposal until the exact PR HEAD passes dedicated authorization validation, repository/deterministic assurance, panoramic/adversarial review with zero unresolved material findings, and separate explicit owner authorization for squash merge.
