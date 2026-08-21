# Review and Assurance Validation

**Status:** PROPOSED  
**Authority anchor:** `review-and-assurance-governance.md` in the same proposed change  
**Base authority:** accepted `main@6d8550b67ddeb6ca1ecac71df36a1185cd3b3c92`  
**Scope:** falsification vectors, automation privilege boundaries, evidence integrity and acceptance blockers for repository assurance  

## Purpose

This document makes the Review and Assurance Governance falsifiable.

It defines mandatory negative cases that prove JLMIRROR can use automated scanners, CI and external reviewers as evidence sources without allowing them to silently mutate canonical repository state, become normative authority or create a progression dependency.

## Automation privilege model

The canonical distinction is **effect authority**, not the literal absence of every API write permission.

A scanner may require narrowly scoped permission to publish non-canonical evidence such as a check result, annotation, security finding or SARIF/security-event record. That reporting permission does not authorize repository-content mutation.

### Default scanner authority

Automated analysis SHOULD operate with the minimum permissions required for its evidence function.

Unless a separately accepted workflow explicitly requires otherwise, scanner/validation automation SHALL NOT receive authority to:

- write repository contents;
- move or create normative branch refs;
- merge pull requests;
- enable auto-merge;
- rewrite history;
- modify releases/deployments as a side effect of analysis;
- create or modify dependency-update branches;
- resolve/dismiss review findings as if they were project authority;
- modify normative labels/status metadata in a way that itself claims acceptance.

Narrow evidence-publication permissions MAY exist for:

- checks/status results;
- annotations;
- security-event/SARIF publication;
- other non-canonical evidence sinks explicitly reviewed for the workflow.

Those permissions SHALL NOT be convertible into canonical source mutation through an unreviewed path.

## Untrusted contribution boundary

Workflows triggered by untrusted pull-request content SHALL NOT expose privileged repository, cloud, signing, deployment, package-publishing, production, tenant, provider or secret-management credentials to that content.

A pull request SHALL NOT gain greater authority merely because its code/documentation is being analyzed.

Where hosting-platform event types have different secret/token semantics, the selected trigger/profile must preserve this boundary.

## Scanner supply-chain boundary

A security or assurance scanner is itself a dependency and possible attack surface.

Workflow definitions and scanner dependencies SHALL be version-controlled/reviewed where applicable.

Mutable third-party action/tool references SHALL NOT silently redefine the behavior of an already-reviewed assurance workflow.

Where practical for the selected platform, third-party workflow dependencies SHOULD be pinned to immutable reviewed versions/digests/commit identities, with deliberate update review.

A scanner compromise SHALL NOT by itself grant repository-content mutation authority.

## Evidence integrity

An assurance result is bound to:

- repository;
- base SHA;
- HEAD SHA;
- scanner/review profile or version where material;
- relevant configuration identity;
- execution/review evidence sufficient to distinguish a current result from stale evidence.

A result produced for another HEAD, configuration or material scanner profile is not silently reused as current proof.

If evidence provenance cannot be established, the result is `unknown`, not `clean`.

## Mandatory governance vectors

The following vectors are required conceptually now and SHOULD become deterministic tests when repository tooling can encode them.

### AGV-001 — Older-SHA clean reuse

**Inject:** HEAD A receives a clean review; a later commit produces HEAD B.  
**Required:** HEAD B is not `READY_FOR_MERGE` based on the HEAD A result.  
**Forbidden:** stale clean evidence automatically follows the branch name.

### AGV-002 — Quota/outage laundering

**Inject:** an external reviewer returns quota exhaustion, timeout, outage or no result.  
**Required:** state records reviewer unavailability only; native assurance remains required.  
**Forbidden:** unavailable reviewer becomes `clean`, `approved` or semantic failure evidence.

### AGV-003 — Automated fix mutation

**Inject:** a scanner identifies a finding and has an available auto-fix capability.  
**Required:** finding is reported/blocks; correction is deliberate and creates a new reviewed HEAD.  
**Forbidden:** scanner silently patches a normative branch and preserves prior clean status.

### AGV-004 — Automatic dependency update

**Inject:** dependency advisory or newer version exists.  
**Required:** alert/report only under the default posture.  
**Forbidden:** ordinary security posture creates update commits/branches/PRs or merges a version change automatically.

### AGV-005 — Scanner write-token compromise

**Inject:** scanner/action execution is assumed compromised.  
**Required:** its token/authority cannot directly mutate normative source/branch state under the accepted scanner profile.  
**Forbidden:** security-analysis compromise grants `contents`/ref/merge mutation authority unnecessarily.

### AGV-006 — Reporting permission confused with code write

**Inject:** scanner needs to publish check/security evidence.  
**Required:** narrowly scoped reporting permission is permitted without repository-content mutation authority.  
**Forbidden:** governance either grants broad write authority for convenience or incorrectly prohibits necessary non-canonical evidence publication and thereby forces an unsafe workaround.

### AGV-007 — Untrusted PR secret exposure

**Inject:** attacker controls pull-request content.  
**Required:** analysis does not expose privileged secrets/tokens to attacker-controlled execution.  
**Forbidden:** workflow trigger/context turns untrusted contribution into trusted secret-bearing execution.

### AGV-008 — Mutable scanner dependency

**Inject:** upstream third-party scanner/action reference changes after workflow review.  
**Required:** accepted workflow dependency policy prevents silent semantic replacement where the platform permits immutable pinning, or records an explicitly reviewed equivalent control.  
**Forbidden:** mutable external reference can silently obtain new behavior/authority under previously accepted evidence.

### AGV-009 — Clean scanner overclaim

**Inject:** static/security scanners return no findings.  
**Required:** result is limited to covered scanner classes/profile and exact state.  
**Forbidden:** scanner clean is interpreted as proof of architectural, tenant, authorization, concurrency, recovery or business-logic security.

### AGV-010 — Finding-source discrimination

**Inject:** a material issue is discovered by a different reviewer/tool than the one used earlier.  
**Required:** finding is evaluated by property/impact and hardening restarts if valid.  
**Forbidden:** finding is ignored because the source is optional/non-canonical.

### AGV-011 — Thread premature resolution

**Inject:** text changes appear to address a historical review thread.  
**Required:** later exact-HEAD validation plus panoramic propagation precedes resolution.  
**Forbidden:** changed line alone is sufficient to erase unresolved finding evidence.

### AGV-012 — Automation acceptance laundering

**Inject:** CI/scanner can set a green status or label.  
**Required:** green evidence contributes to the gate but cannot grant normative acceptance or merge authorization.  
**Forbidden:** machine status is treated as user merge authorization.

### AGV-013 — Branch-name state confusion

**Inject:** a branch name remains constant while HEAD moves.  
**Required:** every material review re-resolves current HEAD.  
**Forbidden:** branch identity is used as a stable substitute for commit identity.

### AGV-014 — Evidence disappearance

**Inject:** prior external/CI review evidence becomes unavailable.  
**Required:** missing evidence becomes `unknown`; required checks are reconstructed/re-run as necessary.  
**Forbidden:** absence is interpreted as proof that no finding existed.

### AGV-015 — Auto-merge race

**Inject:** change is marked ready and HEAD/status subsequently changes.  
**Required:** explicit merge authorization is tied to the final reviewed HEAD and merge uses expected-head protection when available.  
**Forbidden:** auto-merge or stale authorization integrates a different HEAD.

### AGV-016 — Same-system independence overclaim

**Inject:** the same AI/reviewer authors corrections and performs the final clean-room pass.  
**Required:** procedural separation is recorded accurately and no claim of organizational/external independence is made.  
**Forbidden:** same-system re-review is represented as independent external attestation.

### AGV-017 — Generic waiver injection

**Inject:** a blocker/finding is labeled `waived`, `accepted risk`, `tool unavailable` or equivalent without an accepted waiver authority.  
**Required:** gate remains blocked/open according to owning authority.  
**Forbidden:** new informal disposition bypasses an applicable material blocker.

### AGV-018 — Scanner configuration drift

**Inject:** scanner rules/configuration materially weaken while source code stays unchanged.  
**Required:** evidence profile/config identity changes and prior stronger clean evidence is not misrepresented as validation under the new profile.  
**Forbidden:** security-control weakening is invisible because application files did not change.

### AGV-019 — PR template checkbox laundering

**Inject:** author marks all assurance checkboxes without supporting evidence.  
**Required:** checkboxes are declarations/navigation aids only; actual evidence remains reviewable.  
**Forbidden:** checkbox state becomes self-authenticating gate proof.

### AGV-020 — Automated branch creation

**Inject:** a security/dependency service can create branches/PRs automatically.  
**Required:** capability is disabled under the default observer posture.  
**Forbidden:** background service creates project-state divergence without a deliberate operator action.

## Native gate evidence checklist

For each exact-final-HEAD gate, verify as applicable:

- [ ] base SHA is exact and accepted for the change;
- [ ] HEAD SHA is re-read immediately before final review evidence;
- [ ] changed-file scope matches the intended bounded change;
- [ ] no hidden automation changed the branch since review began;
- [ ] external reviewer absence/quota is recorded only as context;
- [ ] deterministic checks are bound to the same HEAD/profile;
- [ ] security scanners have no unnecessary canonical-state mutation authority;
- [ ] untrusted contribution paths do not receive privileged secrets;
- [ ] scanner/action dependencies are governed against silent behavior drift;
- [ ] material findings were corrected by missing property, not only by line;
- [ ] panoramic propagation covered applicable enforcement surfaces;
- [ ] P0/P1/P2 count is zero on the final HEAD;
- [ ] final clean-room/adversarial pass is complete;
- [ ] unresolved historical threads/findings are dispositioned only after later evidence;
- [ ] `READY_FOR_MERGE` is not represented as merge authorization;
- [ ] merge authorization, if later given, is pinned to the reviewed HEAD.

## Acceptance blockers

The assurance-governance change is not acceptable while any applicable condition remains:

- an external AI/reviewer is still the only defined path to a clean gate;
- quota/outage can be interpreted as clean evidence;
- automated analysis can silently mutate normative source/branch state under the default posture;
- dependency/security automation can create ordinary background update PRs/commits contrary to the observer-only rule;
- scanners require broad code/ref/merge write authority without an explicit reviewed need;
- untrusted PR content can receive privileged secrets/credentials through the assurance workflow;
- third-party scanner dependencies can silently change privileged workflow behavior without reviewed control where immutable pinning/equivalent protection is available;
- clean scanner output can be used as complete security proof;
- a clean result can survive a material HEAD change without revalidation;
- historical findings can be resolved before later exact-HEAD and panoramic evidence;
- same-system clean-room review is falsely described as independent external attestation;
- an informal waiver/disposition can bypass material P0/P1/P2 or accepted blockers;
- merge can occur automatically or against a HEAD different from the explicitly authorized reviewed HEAD.

## Current repository application

The repository is currently specification-first and contains no authorized Product/runtime implementation baseline.

Therefore:

- semantic/document assurance is immediately applicable;
- secret leakage prevention/scanning is applicable immediately because secrets may be committed to documentation/configuration as well as code;
- dependency/code static analysis becomes materially applicable when corresponding manifests/source are introduced under accepted implementation scope;
- enabling a code scanner before there is supported code is not itself meaningful evidence and SHALL NOT be used to claim implementation security readiness.

## Fixed properties

This validation fixes:

- least-privilege scanner authority;
- distinction between evidence-publication permission and canonical-state mutation permission;
- untrusted contribution secret isolation;
- scanner supply-chain governance;
- exact state/profile binding of evidence;
- required falsification vectors for tool independence and observer-only automation;
- permanent blockers against auto-mutation and evidence laundering.

Exact CI products, scanner vendors, permission syntax, workflow triggers and ruleset products remain implementation choices subject to these properties.
