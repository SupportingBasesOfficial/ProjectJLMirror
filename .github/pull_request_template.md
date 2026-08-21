## Problem

What problem does this change solve?

## Exact repository state

- Base branch / SHA:
- Head branch / SHA:
- Changed-file scope:
- Upstream normative authority:

A review or clean result for an older HEAD does not validate the current HEAD.

## Canonical impact

Which product, requirement, invariant, ADR, contract, data, security, operational, recovery, compatibility, capacity, or governance authorities are affected?

## Invariants / trust boundaries

List invariants and trust boundaries touched by this change.

## Findings and panoramic propagation

For every material finding addressed, identify the missing property and the related enforcement surfaces reviewed (specialized contract, overview, manifest/profile, validation, security, recovery, compatibility, fault vectors, blockers, OPEN registry, traceability) where applicable.

## Validation / assurance

- [ ] Exact base, branch, HEAD and changed-file scope verified from the repository
- [ ] Relevant deterministic tests or document consistency checks completed
- [ ] Authority/hierarchy and upstream-contract impact reviewed
- [ ] Tenant-isolation and trust-boundary impact reviewed
- [ ] Security/privacy impact reviewed
- [ ] Failure/concurrency/retry/idempotency/ambiguity behavior reviewed where applicable
- [ ] Recovery/PITR/`(R,F]`/fencing impact reviewed where applicable
- [ ] Compatibility and mixed-version impact reviewed
- [ ] Capacity/performance/cost/amplification impact reviewed
- [ ] Governance/OPEN/blocker/no-waiver discipline reviewed
- [ ] Cross-document panoramic propagation completed for material findings
- [ ] Final exact-HEAD adversarial/clean-room review completed before `READY_FOR_MERGE`

## Automated tooling posture

- [ ] Automated tools used by this change only observe/analyze/report/block unless a separate reviewed mutation was explicitly authorized
- [ ] No auto-fix, automatic dependency update, automated security-fix PR, auto-merge or silent canonical-state mutation is relied upon
- [ ] Tool/AI output is treated as evidence, not normative authority or merge authorization

## External review context

Record external reviewer/tool evidence when available. Quota, outage, latency or absence is not a clean signal and does not replace the native assurance gate.

## Merge gate

`READY_FOR_MERGE` does not authorize merge. Merge requires a separate explicit authorization and should be pinned to the exact reviewed HEAD.

## ADR / RFC

Link the ADR or RFC when the change is architecturally significant.
