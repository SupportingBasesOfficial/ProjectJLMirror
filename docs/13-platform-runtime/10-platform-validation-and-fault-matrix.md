# Phase 13 — Platform Validation and Fault Matrix

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This document defines adversarial and fault vectors that falsify Phase 13 runtime contracts. A runtime that starts successfully or passes a vendor health probe is not sufficient evidence.

## Evidence classes

- design evidence — accepted Phase 13 contracts/manifests;
- deterministic conformance evidence — static/profile/configuration checks;
- security/isolation evidence — privilege, network, tenant and secret boundary tests;
- lifecycle/fault evidence — restart, partition, drain, replacement, relocation and stale-generation tests;
- capacity/cost evidence — saturation, skew and runaway-work tests;
- runtime evidence — later environment-specific proof.

## Mandatory vectors

### PRTV-001 — Edge-only dependency
**Inject:** disable/replace optional edge runtime while core API/worker capability remains available.  
**Required:** core application semantics remain executable on general-purpose runtime.  
**Forbidden:** business correctness depends on edge-only API/runtime limits.

### PRTV-002 — Internal network trust bypass
**Inject:** reachable internal workload without valid workload identity.  
**Required:** protected call rejected.  
**Forbidden:** private network/namespace membership grants trust.

### PRTV-003 — Service identity as tenant authority
**Inject:** valid service principal attempts another tenant/domain capability without required current application authority.  
**Required:** denied.  
**Forbidden:** machine identity becomes wildcard tenant authorization.

### PRTV-004 — Caller-selected physical placement
**Inject:** request/job supplies cell/database/schema/cluster target inconsistent with trusted placement.  
**Required:** ignored/rejected; trusted placement governs.  
**Forbidden:** caller metadata routes authoritative work physically.

### PRTV-005 — Stale placement generation
**Inject:** old placement version reaches former cell after relocation/fence.  
**Required:** destination rejects/re-resolves according to accepted placement semantics.  
**Forbidden:** stale source resumes writes because it is reachable.

### PRTV-006 — Control Plane outage with stable traffic
**Inject:** Control Plane unavailable while valid bounded last-known-good placement exists.  
**Required:** only profiles allowed by Phase 11 continue, within currentness bounds; topology-changing operations fail closed.  
**Forbidden:** cached placement grants unlimited/global authority.

### PRTV-007 — Control Plane stale cache after newer deny
**Inject:** cached active placement while destination has observed newer migration/suspension/decommission/version.  
**Required:** newer state wins; stale cache cannot override.  
**Forbidden:** cache resurrects older authority.

### PRTV-008 — Cell starts but current authority unknown
**Inject:** database/network reachable while placement/security/governance/reliability continuity cannot be established.  
**Required:** cell remains not-ready/quarantined for protected work.  
**Forbidden:** process liveness clears recovery quarantine.

### PRTV-009 — Runtime generation rollback
**Inject:** restored/old runtime generation reconnects to current dependencies.  
**Required:** stale generation cannot override current placement/config/security/governance fences.  
**Forbidden:** connectivity makes stale runtime authoritative.

### PRTV-010 — Graceful API drain
**Inject:** API replica enters drain with in-flight transactions.  
**Required:** new admission stops; in-flight outcomes remain bounded/discoverable; ambiguity is not treated as absence.  
**Forbidden:** forced exit silently replays protected effect.

### PRTV-011 — Worker drain/lease recovery
**Inject:** worker stops after accepting/partially executing durable work.  
**Required:** lease/redelivery follows Phase 10/11 durable outcome/reconciliation semantics.  
**Forbidden:** process death proves no effect.

### PRTV-012 — Realtime drain/relocation
**Inject:** cell/runtime drains or tenant relocates with open sockets.  
**Required:** admission stops and clients resubscribe/resync/current authority is re-established.  
**Forbidden:** socket pins old placement/authorization indefinitely.

### PRTV-013 — Credential rotation
**Inject:** workload credential generation rotates while replicas overlap.  
**Required:** accepted overlap/retirement rules preserve capability; old retired credential cannot create new authority.  
**Forbidden:** rotation requires business identity change or broad fallback credential.

### PRTV-014 — Credential revocation
**Inject:** serving workload credential revoked while process remains alive/reachable.  
**Required:** protected calls fail according to profile and currentness evidence.  
**Forbidden:** network presence or cached token makes revocation ineffective indefinitely.

### PRTV-015 — Secret-reference privilege escape
**Inject:** runtime requests secret reference class outside its profile.  
**Required:** denied and auditable without secret disclosure.  
**Forbidden:** reference possession or general secret principal grants access.

### PRTV-016 — Stale configuration weakens policy
**Inject:** old config generation permits egress/authority disallowed by current accepted config.  
**Required:** stale runtime is blocked/quarantined or uses accepted bounded last-known-good semantics only where permitted.  
**Forbidden:** rollback reopens retired authority.

### PRTV-017 — Product authority laundering through config
**Inject:** feature flag/deployed component suggests a Product-gated capability is enabled/disabled while upstream applicability remains OPEN.  
**Required:** Product state remains governed upstream.  
**Forbidden:** runtime configuration resolves Product authority.

### PRTV-018 — Connector SSRF/redirect boundary
**Inject:** configured/requested external target attempts to escape accepted destination/protocol/address/redirect policy.  
**Required:** egress denied/revalidated within connector contract.  
**Forbidden:** network product/default bypasses application egress policy.

### PRTV-019 — Parser network escape
**Inject:** untrusted parser attempts arbitrary external egress.  
**Required:** denied unless a separately accepted bounded fetch capability exists.  
**Forbidden:** parser inherits normal application internet access.

### PRTV-020 — Parser secret/state-port escape
**Inject:** parser attempts application DB, secret manager or privileged state port.  
**Required:** denied.  
**Forbidden:** sandbox shares broad application credentials.

### PRTV-021 — Automation target-scope escape
**Inject:** automation requests target/credential/network beyond operation profile.  
**Required:** denied; execution remains bounded.  
**Forbidden:** arbitrary code implies arbitrary platform authority.

### PRTV-022 — Interactive query tenant-binding override
**Inject:** caller-authored query attempts to alter pooled tenant binding.  
**Required:** tenant binding remains outside query author's control or equivalent isolation prevents escape.  
**Forbidden:** SQL text chooses protected tenant scope.

### PRTV-023 — Application principal attempts migration/admin
**Inject:** ordinary serving principal executes schema-owner/destructive admin operation.  
**Required:** denied.  
**Forbidden:** application owner == migration/database superuser.

### PRTV-024 — Migration principal used for serving
**Inject:** privileged migration credential/process receives normal user traffic.  
**Required:** architecture/runtime policy rejects role reuse.  
**Forbidden:** privileged principal becomes serving shortcut.

### PRTV-025 — Recovery restores retired authority
**Inject:** old snapshot contains pre-revocation permission/credential/placement/governance state.  
**Required:** current forward evidence/fences govern before protected resume.  
**Forbidden:** snapshot state becomes current because it restored successfully.

### PRTV-026 — Reliability-state loss after restore
**Inject:** restored inbox/outbox/idempotency/replay state is missing later evidence.  
**Required:** `(R,F]` reconciliation / recovery block applies.  
**Forbidden:** missing restored evidence means operation never happened.

### PRTV-027 — Stateful port vendor-semantic mismatch
**Inject:** replacement port implementation offers similar API but weaker transaction/durability/fence/failure semantics.  
**Required:** compatibility/conformance failure.  
**Forbidden:** SDK/protocol compatibility is accepted as semantic compatibility.

### PRTV-028 — Ephemeral cache becomes authority
**Inject:** cache/coordination state missing or stale.  
**Required:** business/security/recovery correctness falls back to owning authority or accepted fail-closed path.  
**Forbidden:** ordinary cache hit/miss decides irreversible protected outcome unless specialized authority explicitly owns it.

### PRTV-029 — Stale leader after failover
**Inject:** old coordinator continues running after new leader/lease epoch.  
**Required:** fenced stale work rejected where concurrent authority unsafe.  
**Forbidden:** two leaders both create protected effects from process-local belief.

### PRTV-030 — Noisy tenant/workload saturation
**Inject:** one tenant/provider/destination/report/parser/worker class exhausts its envelope.  
**Required:** unrelated workloads retain bounded capacity or declared degradation.  
**Forbidden:** one dimension consumes unbounded global runtime/state-port capacity.

### PRTV-031 — Scale-down with durable obligations
**Inject:** replicas/workers reduced while requests/jobs/realtime/exports remain active.  
**Required:** drain semantics preserve discoverable durable responsibility and resync/retry correctness.  
**Forbidden:** autoscaling deletes obligation/effect evidence.

### PRTV-032 — Second-cell provisioning
**Inject:** create a new cell from accepted platform contracts.  
**Required:** conformance/identity/ports/observability validate before tenant admission; wrong-placement tenant rejected.  
**Forbidden:** new cell needs new logical API/event/tenant identity semantics.

### PRTV-033 — Tenant relocation source/target race
**Inject:** source and target both receive stale/concurrent work around placement cutover.  
**Required:** placement/admission generations/fences yield one authoritative write path according to relocation contract.  
**Forbidden:** caller chooses winning cell or both accept effectful work.

### PRTV-034 — Relocation temporary double load
**Inject:** data transfer/backfill/reconciliation plus normal serving pressure.  
**Required:** multidimensional capacity/bulkheads prevent relocation from silently exhausting unrelated tenants.  
**Forbidden:** relocation is treated as free/background capacity.

### PRTV-035 — Observability/runtime semantic drift
**Inject:** vendor runtime readiness/health state disagrees with accepted Phase 12 profile meaning.  
**Required:** adapter/mapping preserves accepted semantics; vendor boolean cannot redefine readiness/quarantine.  
**Forbidden:** orchestrator status becomes Phase 12 authority.

### PRTV-036 — Vendor portability rehearsal
**Inject:** map a runtime/state/network/identity capability to an alternative implementation.  
**Required:** canonical tenant/API/event/failure/health/runtime profile semantics remain unchanged; gaps are explicit compatibility failures.  
**Forbidden:** vendor replacement requires silent semantic contract rewrite.

### PRTV-037 — Co-location privilege union
**Inject:** co-locate two runtime profiles or worker specializations whose original principals/secret/state/egress sets differ.  
**Required:** effective principal and policy remain no broader than the declared co-location decision; otherwise co-location fails conformance and requires separation/upstream change.  
**Forbidden:** physical co-location silently creates the union of both profiles' privileges.

### PRTV-038 — Quarantine bypass
**Inject:** quarantined runtime becomes reachable/healthy or operator requests direct activation without revalidation of the owning current-authority predicates.  
**Required:** no direct `quarantined -> active`; transition proceeds through `validating` or controlled retirement.  
**Forbidden:** reachability/tool/operator convenience clears quarantine.

### PRTV-039 — State-port authority collapse
**Inject:** one physical backend/credential serves audit, customer telemetry, observability, transactional or reliability state and implementation treats those logical ports as one authority.  
**Required:** logical ownership, credentials, durability/failure/recovery semantics remain independently enforceable.  
**Forbidden:** physical co-location merges authority or lets ordinary telemetry/log mutation satisfy audit/business/reliability truth.

### PRTV-040 — Artifact/object release bypass
**Inject:** object bytes/upload URL exist while authoritative artifact lifecycle/delivery generation/lease/current governance does not permit release.  
**Required:** protected release denied; object-store success/capability alone is not release authority.  
**Forbidden:** runtime exposes bytes solely because storage reports them present.

### PRTV-041 — Secret value leakage through runtime materialization
**Inject:** runtime receives connector/state/service secret material and emits config snapshot, env diagnostic, log, trace, metric, event/job, crash/export or ordinary audit snapshot.  
**Required:** protected secret value is excluded; only permitted non-secret reference/provenance is observable.  
**Forbidden:** secret injection at runtime becomes a reason to expose secret value in ordinary evidence.

### PRTV-042 — Generation-authority conflation
**Inject:** implementation presents one current generation (for example runtime/config/network credential) while another owning generation (placement/security/governance/replay/artifact) is stale or incompatible.  
**Required:** each authority is checked under its own contract; one green/current generation cannot substitute for another.  
**Forbidden:** `runtime_generation`, `configuration_generation`, `workload_credential_generation`, `placement_version` or `network_policy_generation` is treated as a universal currentness token.

## Acceptance criteria

Phase 13 SHALL NOT reach `READY_FOR_MERGE` while a material runtime/isolation/lifecycle/identity/network/state-port/capacity/recovery property lacks an expected outcome, owner/evidence path or evidence-backed `NO_APPLICABLE_CASE` for a genuinely conditional case.

The runtime semantic manifest SHALL reference applicable vectors for every canonical runtime profile and worker specialization. Co-location, quarantine, port-authority, artifact-release, secret-materialization and generation-separation claims SHALL be covered by `PRTV-037..042` where applicable.

Future implementation/release gates execute applicable vectors against exact implementation/release states. This design matrix is not proof that a future runtime has passed them.