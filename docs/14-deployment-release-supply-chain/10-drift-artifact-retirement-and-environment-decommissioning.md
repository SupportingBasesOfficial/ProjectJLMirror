# Phase 14 — Drift, Artifact Retirement and Environment Decommissioning

**Status:** proposed baseline

## Drift definition

Drift is a material difference between accepted desired release state/evidence and observed deployed/runtime/configuration/authority state.

Examples include unexpected source trust class, release-policy profile, artifact digest, runtime-observed artifact identity, configuration generation, runtime profile, principal/policy, environment mapping, validation-scope evidence, cell runtime/schema compatibility metadata, schema state or deployment object.

## Drift evidence

Drift detection is observer/enforcement evidence. Detection does not authorize auto-fix unless a separately accepted bounded workflow deliberately creates a new reviewed state.

A drift detector's own desired-state view is not automatically authoritative when the drift concerns an independently owned current authority such as Control Plane placement/cell compatibility, release-policy/verifier trust, Security revocation or Phase 13 recovery quarantine.

## Drift classification

- benign metadata drift — no semantic/authority effect;
- operational drift — capacity/topology difference within accepted semantics;
- compatibility drift — mixed-version/profile/validation-scope or cell compatibility mismatch;
- artifact-integrity drift — observed running artifact identity differs from approved immutable artifact;
- source/release-policy drift — source trust, evaluator principal, approval, policy or verifier state differs from current accepted authority;
- security/authority drift — principal/secret/network/environment/trust broadening;
- recovery drift — stale generation/fence/quarantine or restored-obsolete authority mismatch.

Security, artifact-integrity, source/release-policy and recovery drift fail closed for affected release admission. Compatibility drift blocks incompatible rollout/placement until reconciled.

`RLV-043`, `RLV-044` and `RLV-046` are canonical falsification paths for running-artifact, release-policy and cell-compatibility drift.

## Desired vs observed runtime state

Deployment-controller desired state is one evidence source. Runtime verification independently establishes the immutable artifact identity/equivalent actually executing.

A controller declaring artifact A while runtime evidence shows artifact B is not repaired by updating the desired-state record to B. The deployment remains drifted/blocked until the unexpected runtime state is investigated and deliberately reconciled.

## Release-policy/verifier drift

A restored or stale CI/CD control plane that exposes an older approval, principal mapping, signing issuer or verifier policy is drift against current accepted release authority.

Reachability or successful pipeline startup cannot make that historical state current. Current authority is reconciled forward before privileged release actions resume.

## Cell compatibility drift

Observed/deployed runtime-schema state is compared with current trusted Control Plane cell compatibility metadata.

If a cell is running a combination not admitted by current metadata/mixed-version contracts, affected placement/release admission is blocked. Release tooling does not silently rewrite Control Plane compatibility authority to match the observed deployment.

## Artifact retirement

Artifact lifecycle:

```text
created -> verified -> promotable -> deployed/retained -> retired -> governance-eligible deletion
```

Retired artifacts cannot receive new production promotion. Evidence may be retained after bytes are no longer deployable.

Physical deletion requires retention, incident, legal-hold, rollback/recovery, historical verifier continuity and audit considerations.

## Promotion and approval retirement

Superseding an artifact/config/promotion or retiring an approval prevents new deployment under stale authority while preserving evidence of historical execution.

Restore of an older release database cannot reactivate that promotion/approval silently.

## Verifier/evidence retirement

Signing/provenance verifier profiles or release-policy evidence required to interpret historical artifacts remain available for the required evidence horizon or are migrated through a reviewed verification-preserving mechanism before retirement.

Retirement that makes historical release evidence uninterpretable can invalidate rollback/incident/reconciliation capability and is therefore governed, not ordinary cleanup.

## Environment decommissioning

Decommission of a physical environment mapping proves:

- no current deployment/promotion authority requires it;
- tenants/workloads/placement no longer depend on it;
- current cell compatibility/Control Plane state no longer admits required workloads there;
- secrets/credentials/principals are retired;
- state ports/data/artifacts are migrated, retained or erased under owning governance;
- DNS/network/routing/egress paths cannot continue stale authority;
- audit/release/provenance/verifier evidence remains available as required;
- recovery obligations are dispositioned;
- physical deletion does not rewrite logical environment semantics.

## Cell decommission interaction

Release tooling cannot decommission a cell as an incidental deployment cleanup without Control Plane placement/lifecycle authority.

A cell is not decommissioned solely because the deployment system reports zero desired replicas; current placement, durable work, recovery and cell compatibility authorities must agree with decommissioning.

## Vendor exit

Registry/CI/CD/orchestrator replacement must preserve source trust, release-policy currentness, artifact/provenance/promotion/deployment/runtime-observation identities/evidence and cell compatibility integration without requiring canonical application/runtime semantics to be rewritten.