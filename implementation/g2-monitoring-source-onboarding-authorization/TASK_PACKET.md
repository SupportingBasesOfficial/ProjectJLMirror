# G2 Monitoring Source Onboarding — AI Task Packet

SLICE: `g2.monitoring-source-onboarding@1`  
GOAL: An authorized tenant user can register an initial Zabbix Monitoring Source without exposing raw credentials, observe validation/initial-sync state, and see truthful success/failure/reconciliation outcomes through the protected JLMirror shell.  
BASE SHA: supplied by the later implementation PR and MUST equal its exact current default-branch base.  
AUTHORITY: `implementation/g2-monitoring-source-onboarding-authorization/AUTHORIZATION_MANIFEST.json` plus the accepted Monitoring/G1 authority paths named there.  
DEPENDENCIES: accepted G1 identity/tenant/BFF contract; accepted Wave 4 Monitoring Source foundation; accepted Wave 4 initial validation worker.

## STOP CONDITIONS

STOP and request successor authorization if any of the following is required:

- modifying existing shared paths such as `src/jlmirror_monitoring/**`, `sql/wave4/**`, `src/jlmirror_authority/**`, accepted shared API/event/governance contracts, or G1 implementation namespaces;
- adding a new G2 persistence/domain model for Monitoring Source truth;
- changing Monitoring Source canonical identity/generation semantics;
- changing provider-instance replacement/cutover semantics;
- introducing raw provider credentials into browser/API body/ordinary database/log state;
- selecting a concrete secret manager or concrete egress transport as platform authority;
- adding inventory, metrics, problems, health, Alerting, ITSM, Automation, AIOps, FinOps, Commercial or production behavior;
- inventing retry cadence/capacity numerics that are still OPEN;
- weakening current authorization, tenant placement, idempotency, revision or stale-evidence fencing rules.

## ALLOWED PATHS

Prefixes:

```text
apps/g2-monitoring-source-onboarding/
contracts/g2-monitoring-source-onboarding/
implementation/g2-monitoring-source-onboarding/
tests/g2/
tools/g2/
```

Exact path:

```text
.github/workflows/g2-monitoring-source-onboarding-runtime.yml
```

There is intentionally no `sql/g2/` or `src/jlmirror_g2/` authority. Canonical Monitoring persistence/domain behavior already exists and remains read-only. Every other existing path is read-only unless a successor authorization says otherwise.

Path admission is necessary but not sufficient: executable G2 artifacts are also scanned by the trusted base-owned evaluator for forbidden G3/parallel-Monitoring path tokens and code markers. Attempting to hide inventory, resource, metric, problem, health, Alerting, replacement/cutover or shared-Monitoring write behavior under an allowed G2 path MUST fail scope attestation.

## IMPLEMENTATION CLAIM

The implementation PR MUST contain:

```json
{
  "schema_version": 1,
  "authorization_id": "g2.monitoring-source-onboarding@1",
  "slice_id": "g2.monitoring-source-onboarding@1"
}
```

at:

```text
implementation/g2-monitoring-source-onboarding/IMPLEMENTATION_CLAIM.json
```

Branch prefix:

```text
impl/g2-monitoring-source-onboarding
```

Required label:

```text
jlmirror-slice:g2-monitoring-source-onboarding
```

## DB

Do not add G2-owned canonical persistence. Reuse accepted Monitoring Source persistence semantics from Wave 4.

Canonical business truth remains the accepted Monitoring Source state in the existing Monitoring substrate. Do not duplicate `monitoring_source`, source generation, scope revision, validation operation or provider mapping identity in a parallel G2-owned model.

If implementation discovers a real persistence change is required, STOP and request successor authorization.

## DOMAIN

Consume existing Monitoring domain behavior rather than reimplementing it.

Binding invariants:

```text
monitoring_source_id = JLMirror canonical identity
provider native IDs = external evidence only
active source generation = current generation authority
credential_binding_ref = opaque secret-binding reference, not secret bytes
source create commit = local configuration success, not provider reachability proof
stale generation/configuration/scope evidence cannot update current source evidence
provider failure/omission cannot create resource-absence truth
```

G2 owns only BFF/frontend/orchestration composition necessary to expose the onboarding outcome.

## API / BFF

Consume the accepted Monitoring API contract and G1 current-auth boundary.

Minimum journey:

```text
protected shell
 -> current tenant admission
 -> current monitoring.source.manage authorization
 -> create source
 -> durable validation operation
 -> source/status read
 -> visible user state
```

Initial create contract:

```text
POST /api/v1/tenants/{tenant_id}/monitoring-sources
Idempotency-Key required
action monitoring.source.manage
```

Canonical request fields are limited to accepted safe source configuration:

- `provider_profile=zabbix`;
- bounded `display_name`;
- canonical HTTPS `provider_configuration.base_url`;
- opaque `credential_binding_ref`;
- bounded `configured_provider_scope.host_group_refs`.

No raw credential bytes.

Required reads may expose source list/detail and validation/sync operation state under accepted `monitoring.source.read` / `monitoring.sync.read` semantics. The browser talks through the BFF. Client state, URL possession and provider payloads never become authority.

## FRONTEND

Implement only the G2 onboarding experience, not a generic Monitoring dashboard.

Required states:

- empty/no source onboarding entry;
- create form;
- local create committed / validation pending;
- current/validated;
- incomplete;
- reconciliation required;
- unavailable;
- retry/recheck action when admitted by accepted backend semantics;
- forbidden/current-authorization-lost;
- sparse not-found/cross-tenant behavior where applicable.

Do not display a successful provider connection before durable accepted validation evidence exists. Do not display raw tokens/secrets after submission because they are never part of the Monitoring request/state contract.

## PROVIDER / WORKER

Reuse `wave4.zabbix-initial-validation-worker@1`.

Its accepted behavior remains binding:

- resolves credential via abstract `CredentialResolver` boundary;
- obtains fail-closed outbound admission;
- performs only accepted HostGroup validation for configured anchors;
- validates completion against current generation/configuration/scope/provider-binding authority;
- stale response cannot update current evidence;
- missing configured HostGroup -> `incomplete` + `reconciliation_required`;
- credential/auth/provider/egress/protocol failure -> `unavailable` + `reconciliation_required`;
- success -> current only when all currentness fences pass.

The G2 slice MUST NOT replace this worker with a second provider validator.

## FAILURE

At minimum prove:

- malformed/unsafe source configuration rejected before effect;
- raw-secret field/unknown field rejected;
- unauthenticated/unauthorized/cross-tenant create denied;
- idempotent replay returns same logical result under current authorization;
- same key/different fingerprint rejected;
- provider validation can fail without rolling back canonical local source creation;
- missing HostGroup does not create mass negative inference;
- credential resolution failure is safe and non-leaking;
- unsafe/unprovable egress fails closed;
- stale worker completion cannot update current source evidence;
- loss/revocation of current user authority prevents subsequent protected reads/actions;
- UI never upgrades stale/incomplete evidence to healthy/current.

## SECURITY

Prove:

- tenant context is established by current platform authority before Monitoring use;
- browser never receives long-lived machine/provider credentials;
- raw provider token is absent from request/response persistence/log fixtures;
- provider-native identifiers and payloads do not decide tenant placement;
- BFF/session possession alone does not bypass current authorization;
- stale/changed source authority fences worker completion;
- source endpoint validation performs no network call while the local source-configuration transaction is open.

## OBSERVABILITY

Expose only policy-safe operational evidence required to explain onboarding state. Logs/traces MUST NOT copy raw credentials or confidential provider payloads.

At minimum make it possible to correlate tenant-safe operation context, `monitoring_source_id`, validation/sync operation id, current evidence state and safe failure class without turning correlation metadata into authorization authority.

## TESTS

Required layers:

1. contract/shape tests for create/read/status DTOs;
2. BFF/current-authorization tests;
3. existing Wave 4 persistence and worker reuse proof;
4. provider fixture success case;
5. missing HostGroup controlled-failure case;
6. credential/auth/provider/egress failure cases;
7. stale-generation/revision completion fencing case;
8. cross-tenant/forbidden tests;
9. browser E2E from protected shell through create -> pending -> current;
10. browser E2E controlled failure/reconciliation presentation;
11. runtime/container proof for components introduced by G2;
12. adversarial path + semantic-scope validation.

## RUN

The implementation MUST provide exact local/container commands inside its authorized namespace and make them CI-parity commands. The runtime workflow may execute only bounded G2 proof responsibilities and must not gain deployment/status/secrets authority beyond the accepted governance profile.

## DONE

G2 is done only when machine-verifiable evidence proves:

```text
browser -> BFF -> current tenant authorization -> Monitoring source create
 -> canonical local source commit
 -> durable validation responsibility
 -> accepted Wave4 initial-validation worker/provider fixture
 -> durable source evidence state
 -> BFF read
 -> browser-visible truthful status
```

for both success and controlled failure/reconciliation cases.

Additionally:

- exact implementation HEAD CI is green;
- complete diff is inside canonical G2 allowlist;
- semantic scope guard reports no forbidden G3/parallel-Monitoring authority;
- trusted `/jlmirror-g2-scope-attest` evidence matches exact head/base;
- trusted `/jlmirror-g2-scope-ready` live readiness matches exact current head/base/default-tip/label;
- review has zero unresolved material findings;
- no merge occurs without separate explicit owner authorization.

## FORBIDDEN

```text
G2 != G3 resource inventory
G2 != source instance replacement product flow
G2 != Monitoring dashboard breadth
G2 != Alerting
G2 != secret-manager selection
G2 != production authority
GREEN_STATUS != MERGE_AUTHORIZATION
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
