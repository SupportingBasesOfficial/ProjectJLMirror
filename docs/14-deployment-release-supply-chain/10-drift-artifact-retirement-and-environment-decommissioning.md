# Phase 14 — Drift, Artifact Retirement and Environment Decommissioning

**Status:** proposed baseline

## Drift definition

Drift is a material difference between accepted desired release state/evidence and observed deployed/runtime/configuration state.

Examples include unexpected artifact digest, configuration generation, runtime profile, principal/policy, environment mapping, schema state or deployment object.

## Drift evidence

Drift detection is observer/enforcement evidence. Detection does not authorize auto-fix unless a separately accepted bounded workflow deliberately creates a new reviewed state.

## Drift classification

- benign metadata drift — no semantic/authority effect;
- operational drift — capacity/topology difference within accepted semantics;
- compatibility drift — mixed-version/profile mismatch;
- security/authority drift — principal/secret/network/environment/trust broadening;
- recovery drift — stale generation/fence/quarantine mismatch.

Security/recovery drift fails closed for affected release admission.

## Artifact retirement

Artifact lifecycle:

```text
created -> verified -> promotable -> deployed/retained -> retired -> governance-eligible deletion
```

Retired artifacts cannot receive new production promotion. Evidence may be retained after bytes are no longer deployable.

Physical deletion requires retention, incident, legal-hold, rollback/recovery and audit considerations.

## Promotion retirement

Superseding an artifact/config/promotion prevents new deployment under stale authority while preserving evidence of historical execution.

## Environment decommissioning

Decommission of a physical environment mapping proves:

- no current deployment/promotion authority requires it;
- tenants/workloads/placement no longer depend on it;
- secrets/credentials/principals are retired;
- state ports/data/artifacts are migrated, retained or erased under owning governance;
- DNS/network/routing/egress paths cannot continue stale authority;
- audit/release evidence remains available;
- recovery obligations are dispositioned;
- physical deletion does not rewrite logical environment semantics.

## Cell decommission interaction

Release tooling cannot decommission a cell as an incidental deployment cleanup without Control Plane placement/lifecycle authority.

## Vendor exit

Registry/CI/CD/orchestrator replacement must preserve artifact/provenance/promotion/deployment identities/evidence and cannot require rewriting canonical application/runtime semantics.