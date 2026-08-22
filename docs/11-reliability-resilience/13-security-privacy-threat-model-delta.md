# Phase 11 — Security and Privacy Threat-Model Delta

**Status:** proposed baseline  
**Phase:** 11 — Reliability & Resilience  
**Authority:** accepted Security requirements, threat model, trust-boundary model, ADR-014/015/017/018/019, System Design, Data Architecture, accepted corrected Phase 09/10, accepted Review and Assurance Governance, and the post–Phase 10 roadmap

## Purpose

This document records the security/privacy delta created by Phase 11 failure, degradation, retry, backlog, failover, reconciliation and recovery paths. It does not replace the accepted threat model. It identifies changed trust boundaries and new abuse opportunities that exist specifically when current truth, capacity or dependency evidence is impaired.

The accepted Phase 10 corrective baseline additionally makes message-equivalence evidence a protected security/recovery surface: confidentiality-safe comparison, canonical comparison-profile/version, historical verifier continuity, anti-oracle scope and bounded comparison/KMS work must survive degraded operation without becoming new authority.

## Delta summary

Normal-path trust does not automatically survive a fault. Phase 11 introduces or makes explicit transitional states in which:

- a cell may rely temporarily on bounded cached Control Plane evidence;
- configuration generations may be partially distributed, restored or contradictory;
- operations may be delayed, duplicated, quarantined, redriven or reconciliation-blocked;
- duplicate-sensitive receipts may retain evidence bytes while the historical comparison profile/verifier required to interpret them is missing, rolled back, retired or untrusted;
- provider/destination outcomes may be ambiguous;
- recovery scopes are present but non-authoritative;
- old and new writer/source/placement/runtime/comparison-verifier generations may overlap physically;
- privileged recovery, migration, parser and automation roles may run under pressure;
- telemetry/evidence paths may be missing, saturated or adversarially manipulated.

These states expand attack opportunity but SHALL NOT expand authority. `uncertainty != absence`, unknown equivalence is not duplicate success, network/broker/key presence is not trust, and tenant isolation remain invariants.

## Threat actors and failure-assisted capabilities

| Actor | Failure-assisted capability considered |
|---|---|
| unauthenticated or forged caller | exploit fail-open admission, stale placement, retry or resync during authority impairment |
| compromised tenant principal | cross tenant/cell/queue/cache/artifact/comparison boundaries through skew, replay, identity conflict, equality probing or recovery scope confusion |
| stale but formerly legitimate runtime | continue writing, publishing, streaming or using secrets/config/historical verifier material after fencing, relocation, revocation or recovery generation change |
| compromised provider/webhook destination | induce ambiguous effects, retry amplification, hostile payload parsing, SSRF/egress abuse or destination-generation confusion |
| malicious/poisoned async producer | inject duplicate/conflicting identity, low-entropy comparison probes, force partition/KMS starvation, abuse quarantine/redrive or disguise tenant/source generation |
| compromised privileged workload or operator credential | widen target scope, bypass quarantine, expose comparison evidence/verifier material, alter evidence, reuse break-glass/recovery authority or exhaust protected capacity |
| co-tenant/noisy workload | exploit shared pools, queues, cache refill, telemetry cardinality, comparison/KMS work or recovery reservations to deny unrelated service |
| configuration/evidence supply-path attacker | introduce malformed, contradictory or rolled-back policy/profile and fabricate, suppress, misattribute or inflate evidence |
| diagnostic/AI-assisted system | influence a protected eligibility decision through score, ranking, omission, delay or human/deterministic wrapper |

## Changed trust boundaries

| Boundary | New degraded/failure state | Security/privacy requirement |
|---|---|---|
| untrusted request/message → reliability admission/budget classifier | overload controls execute before or across full semantic validation, or mixed versions classify the same structured input differently | preserve the accepted Phase 09/10 canonical interpretation; pre-validation claims use only transport facts/already-trusted canonical metadata and conservative bounds; canonical tenant/workload/cost class replaces or rejects provisional claims before expensive/effectful continuation; aliases, duplicate members, malformed encodings and caller-selected scope/cost hints never become admission authority |
| trusted scoped message identity → equivalence comparison authority | duplicate-sensitive receipt/evidence exists while comparison profile/verifier is unavailable/rolled back; low-entropy content or equal content across scopes is probed; crafted duplicate IDs amplify verifier work | derive trusted `(consumer_contract, message_identity_scope, message_id)` before comparison; require the accepted canonical comparison profile/historical verifier authority; unknown interpretation remains `recovery_continuity_blocked`; evidence inherits source confidentiality; no global reverse/equality lookup; bound and isolate comparison/KMS work |
| historical verifier/key store → consumer/recovery path | old/current verifier generations coexist, restore revives an obsolete verifier, or a keyed evidence verifier is reachable during recovery | historical verifier access is narrow, generation-bound and secret-protected; it proves only the accepted historical comparison statement and never grants unrelated current message/tenant/effect/crypto authority; loss/unavailability cannot become duplicate success |
| Control Plane → cell | bounded cached placement/lifecycle evidence while current source is unreachable | evidence is authenticated, versioned, scoped and expiring; destination independently admits; newer deny/fence wins |
| configuration authority → runtimes/cells | mixed, missing, restored, partially applied or compromised/untrusted configuration generations | schema, authority, applicability, compatibility and monotonic generation are verified; permissive defaults are forbidden; compromised trust remains outside ordinary circuit half-open/probe recovery and requires independently accountable restoration |
| security/key authority → workload | locally held credential/secret lease during outage/rotation, or authority/key material becomes compromised/untrusted | least-privilege namespace and bounded lease; revocation/rotation/crypto-erasure cannot regress; compromised trust is terminal for ordinary circuit recovery and only independently accountable current Security/cryptographic authority can restore it from accepted evidence; historical message-equivalence verifier use remains limited to its evidence generation |
| producer/outbox → broker → consumer | duplication, delay, gap, identity conflict, poison work and historical comparison-authority loss | immutable trusted envelope, tenant/source/generation checks, confidentiality-safe equivalence, historical profile/verifier continuity, inbox/effect convergence and bounded quarantine/redrive |
| platform → external provider/destination | timeout/connection loss after possible external acceptance | stable operation/delivery identity, egress policy, destination generation and reconciliation before protected retry |
| recovery store/snapshot → authoritative scope | restored bytes exist before later facts/fences/profile-verifier generations are reconciled | recovery quarantine, no writer/publication/admission authority, `(R,F]` and governance/equivalence continuity |
| artifact metadata → object data plane/client | object mismatch, stale capability or lifecycle race | transactional metadata/generation remains authority; current releasability, integrity and governance are rechecked |
| privileged runtime → tenant/cell/dependency | recovery/migration/admin execution under degraded capacity | explicit target scope, separate identity/runtime/egress/budget, stable operation identity, audit and dual-control handoff where later required |
| runtime → telemetry/evidence store → gate | missing, delayed, high-cardinality or forged evidence | telemetry is not business authority; evidence provenance/level/scope/integrity are mandatory; missing evidence blocks rather than passes |
| diagnostic/AI output → accountable authority | recommendation or prioritization during ambiguity/incident | removal of AI output cannot change eligibility/outcome; protected decisions are independently re-established from accepted non-AI evidence |

## Canonical threat delta

| Threat | Abuse path and affected assets | Required prevention/containment | Required adversarial evidence | Blocking references |
|---|---|---|---|---|
| `TM-REL-001` cached-authority forgery/rollback | forge or retain placement/lifecycle evidence so a tenant, suspended scope or old cell remains admitted | authenticated scoped evidence, expiry, monotonic generation, local deny precedence, destination admission and recovery reconciliation | expired/forged/contradictory placement under partition; stale-writer and relocated-session attempts | `FV-CP-001`, `FV-CP-002`, `FV-REL-001`; `RB-REL-001`, `RB-REL-019` |
| `TM-REL-002` configuration rollback/partial-policy bypass | deploy malformed, permissive, scope-mismatched, older or compromised/untrusted config during rollout/restart/restore and attempt to regain trust through ordinary dependency recovery | independent config authority profile, schema/semantic validation, target/generation compatibility, fail closed and no permissive default; `compromised_or_untrusted` stays outside ordinary circuit health/half-open/probe recovery until independently accountable configuration/Security authority establishes a reviewed trusted generation | malformed/conflicting/mixed generation plus restored-pre-`R` config against later deny/revocation; explicit compromised/untrusted classification followed by successful reachability/probes that must not restore trust | `FV-CONFIG-001`, `FV-CONFIG-002`; `RB-REL-023` |
| `TM-REL-003` degraded-auth/secret confused deputy | use cached positive auth, stale or compromised secret/key, historical message-equivalence verifier, compromised authorization authority or generic service identity to act for another tenant/scope; exploit a circuit/probe transition to launder compromised trust back into service | current deny precedence, namespace-bound leases, least privilege, explicit subject/tenant/operation binding and no plaintext fallback; terminal compromised trust stays outside ordinary circuit recovery; historical verifier authority is evidence-generation scoped and never becomes unrelated current authority | inject unavailable, stale, `compromised_or_untrusted` and explicit `policy_denied` security states plus unavailable/stale/compromised/governance-blocked key states; cross-tenant/namespace probes, restored old verifier use and successful dependency probes must preserve exact failure modes and never restore/widen trust | `FV-SEC-001`, `FV-SECRET-001`, extended `FV-ASYNC-003`; `RB-REL-004`, `RB-REL-006`, `RB-REL-010` |
| `TM-REL-004` retry/ambiguity effect amplification | provoke timeouts, cancellation races, restart/state loss, half-open recovery or lost responses so platform repeats external or privileged effects | stable operation/effect identity, restart-persistent aggregate attempts, bounded circuit probes, reconciliation authority, destination generation and fail-closed ambiguity | pre-send/remote timeout distinction; provider acceptance with lost response; cancellation/commit race; restart budget reset; half-open storm; privileged timeout with inquiry unavailable | `FV-EXT-002`, `FV-OVER-001`, `FV-RETRY-001`–`FV-RETRY-003`, `FV-CIRCUIT-001`, `FV-CIRCUIT-002`, `FV-PRIV-001`; `RB-REL-008`, `RB-REL-012`, `RB-REL-020`, `RB-REL-025` |
| `TM-REL-005` async/accepted-observation identity, equivalence and quarantine abuse | inject conflicting content, poison a partition, forge tenant/source/generation or observation scope, collapse provider-local IDs across authorities, exploit low-entropy/plain-digest comparison, query cross-scope equality, retire/rollback verifier authority or obtain unaudited redrive/replay | trusted immutable envelope/observation namespace, tenant/source/generation validation, confidentiality-safe content equivalence under stable canonical comparison profile, historical verifier continuity/equality-preserving migration, trusted-scope-first lookup, anti-oracle/domain separation, bounded comparison/KMS work, durable acceptance/checkpoints, bounded quarantine and scoped current redrive/replay authority | duplicate conflict; payload minimization; retained evidence with missing/mismatched historical verifier/profile; low-entropy digest disclosure attempt; cross-tenant equality/correlation probe; profile/key rotation and restore; crafted duplicate-ID KMS amplification; poison loop; stale source; cross-tenant redrive; lease theft; scoped-observation collision and projection replay | `FV-ASYNC-002`, extended `FV-ASYNC-003`, `FV-ASYNC-004`, `FV-TEL-002`; `RB-REL-010`, `RB-REL-011`, `RB-REL-018`, `RB-REL-022`, `RB-REL-026` |
| `TM-REL-006` recovery-quarantine bypass | admit restored scope, old writer, historical verifier or replay before later revocation/erasure/effect/equivalence facts are known | non-authoritative restore, writer/source fences, complete `(R,F]`, governance/effect/equivalence reconciliation and explicit admission owner; historical verifier generation does not become current unrelated authority | tenant/cell PITR with incomplete/contradictory `F`, stale writer, retained comparison bytes without interpreter, restored obsolete verifier and blind replay attempts | `FV-REC-001`, `FV-REC-002`, `FV-REC-003`, extended `FV-ASYNC-003`; `RB-REL-018`, `RB-REL-010` |
| `TM-REL-007` noisy-neighbor and admission-classification security degradation | exhaust shared queues, circuits, cache refill, telemetry cardinality/projection backlog, comparison/KMS work or recovery capacity so checks/timeouts fail open, accepted observations are lost, or other tenants starve; manipulate malformed/duplicate/alias structured input or caller cost/scope hints so pre-canonical admission chooses a cheaper budget, another tenant bucket or privileged workload class | tenant/workload/provider/destination/source/consumer bulkheads, bounded admission/backlog/cardinality/comparison work, durable accepted-work preservation, canonical parser inheritance, conservative pre-validation claims, authoritative budget adjustment before effect and reserved critical work without bypassing authority | skew, retry storm, replay/backfill, crafted duplicate/equality/KMS flood and optional/customer telemetry flood while security/recovery checks remain enforced; `FV-OVER-002` adversarial malformed/duplicate/alias admission and provisional-budget upgrade variants prove scope/cost authority cannot be selected before canonical interpretation | `FV-OVER-001`, `FV-OVER-002`, `FV-OVER-003`, extended `FV-ASYNC-003`, `FV-TEL-001`, `FV-TEL-002`; `RB-REL-012`, `RB-REL-013`, `RB-REL-010`, `RB-REL-017`, `RB-REL-026` |
| `TM-REL-008` provider/destination egress abuse | malicious or compromised endpoint/payload causes SSRF, redirect expansion, parser exhaustion, credential disclosure, permanent-error retry or cross-destination pressure | adapter trust boundary, destination allow policy, bounded response/parser/redirect/egress, scoped secrets, exact permanent/compromised classification and circuit/bulkhead isolation | hostile payload/redirect/size, compromised trust classification, permanent result, slow destination, generation change and cross-provider pressure | `FV-EXT-001`, `FV-EXT-003`, `FV-WH-001`, `FV-WH-002`, `FV-PRIV-001`; `RB-REL-007`, `RB-REL-015`, `RB-REL-020` |
| `TM-REL-009` artifact lifecycle disclosure | race upload/download/stream with revocation/erasure/hold or substitute object behind valid metadata | content integrity, tenant/artifact/generation binding, current release check, stream lease fencing and governance precedence | object mismatch, stale capability, active stream during erasure and cross-tenant object reference | `FV-ART-001`, `FV-ART-002`; `RB-REL-016` |
| `TM-REL-010` evidence poisoning or suppression | fabricate a green result, hide a failed tenant/cell/generation, alter comparison evidence/profile metadata, inflate evidence level or expose sensitive fault data | immutable provenance, exact profile/artifact/scope binding, comparison evidence classification, negative-result retention, least-privilege evidence access and review provenance | missing/misattributed/contradictory/level-inflated evidence, comparison-profile mismatch and aggregate-green masking | `FV-EVID-001`, extended `FV-ASYNC-003`; `RB-REL-022`, `RB-REL-010` |
| `TM-REL-011` diagnostic authority laundering | feed AI score/ranking into a deterministic rule or human workflow to alter auth/retry/recovery/release eligibility | diagnostic-only boundary; output removal invariance; accountable authority independently re-establishes decision from accepted evidence | replace/remove/adversarially perturb AI output and prove protected outcome/eligibility is unchanged | `FV-AI-001`; `RB-REL-024` |

`14-message-equivalence-reliability-continuity.md` is the mandatory normalized reliability companion for the message-equivalence branches above and does not create a separate Product or cryptographic authority.

## Confused-deputy analysis

The following deputy patterns are explicitly prohibited:

- a reliability admission/budget classifier treating unvalidated structured payload, alias/duplicate interpretation, caller-selected tenant/source/operation label or claimed cost as trusted scope/class authority;
- a message-equivalence service treating a fingerprint/MAC/profile reference as tenant/message lookup authority, bearer capability or permission to retrieve unrelated historical verifier material;
- a historical verifier/KMS path treating key possession/reachability as duplicate/effect eligibility or current authority outside the evidence generation it is meant to verify;
- a cell using cached Control Plane evidence to authorize a tenant/generation the cell cannot independently admit;
- a generic worker, queue administrator or transport credential deciding business retry/redrive eligibility;
- a provider adapter converting provider identity, native error or destination redirect into platform/tenant authority;
- a recovery/admin principal applying authority outside its explicit target scope because the system is degraded;
- a configuration distributor treating transport success as proof that content is authorized, compatible and effective;
- an authority circuit/probe treating reachability or a successful request as proof that previously compromised Security, secret/key or configuration trust has been restored;
- an artifact data plane treating object possession/presence as release authority;
- a telemetry/evidence collector converting missing signals into a passing gate;
- a human/deterministic workflow laundering AI output into a protected decision input.

Every deputy SHALL bind caller/subject, tenant, operation/effect, target resource, capability/profile version and current authority/generation where applicable. Equivalence comparison additionally binds the trusted consumer/message-identity scope and historical comparison-profile/verifier generation. Deputies SHALL reject attenuation failure and preserve audit without logging secrets, unrestricted payloads or protected comparison evidence.

## Privacy and data-governance delta

- Failure buffers, quarantine, evidence and reconciliation state SHALL apply the original or stricter data classification, minimization, tenant scope, residency and retention rules.
- Derived message-equivalence fingerprints/MACs/tombstones are not assumed harmless metadata; low-entropy or equality-testable evidence receives the necessary confidentiality/logging/export restrictions.
- A retry, fault test or recovery rehearsal SHALL NOT copy production-sensitive payloads or protected comparison evidence into a weaker environment by convenience.
- Missing telemetry SHALL not trigger verbose payload/fingerprint logging or secret capture as fallback diagnostics.
- Recovery SHALL reconcile erasure, legal hold, revocation, audit, crypto-erasure and historical verifier/profile decisions after `R`; restored absence never proves an obligation disappeared or equivalence exists.
- Evidence access SHALL be least-privilege and purpose-bound; panoramic review may consume redacted metadata rather than tenant payloads/fingerprints.
- Quarantine/redrive SHALL preserve immutable identity and accountability while restricting payload/comparison-evidence disclosure to the owning scoped authority.

## Security-sensitive compatibility triggers

A change is at least `security_breaking` or `recovery_breaking` when it:

- lengthens or broadens cached authority/secret/config/historical-verifier use without accepted evidence;
- changes canonical interpretation or admission/cost-class derivation so untrusted structured input, aliases, duplicates, malformed encodings or caller-controlled scope hints can alter tenant/workload/budget authority before the accepted boundary;
- changes message-equivalence canonicalization/profile so historical equality can change without an equality-preserving migration;
- weakens comparison-evidence confidentiality/domain separation or exposes a cross-tenant/cross-consumer equality oracle;
- retires/rotates/rolls back historical verifier authority while affected identities remain dedup/replay/effect eligible without proven continuity;
- changes unknown-equivalence behavior into duplicate success or protected-effect eligibility;
- materially increases comparison/KMS/migration amplification without tenant/consumer isolation evidence;
- changes generation comparison, fence, revocation, deny precedence or destination binding;
- moves a terminal trust class such as `compromised_or_untrusted` into ordinary circuit health/half-open/probe recovery, or weakens independently accountable trust-restoration evidence;
- introduces a fallback, retry, redrive or resumption path that can grant protected action;
- changes tenant/scope binding, evidence provenance/level or quarantine access;
- alters configuration compatibility so old/new participants interpret authority differently;
- allows rollback/restore to reinstate earlier policy, keys, access, source, placement or effect eligibility.

Such a change is release-blocked until the owning Security/Data/Product authority accepts the delta and the linked fault vectors cover mixed versions and recovery.

## Downstream evidence handoff

- Phase 12 SHALL define signals for boundary/generation/fence/config/quarantine/evidence/comparison-verifier state without making telemetry authority.
- Phase 13 SHALL select mechanisms that conform to the identity, isolation, egress, secret/config/comparison-verifier and fencing requirements.
- Phase 14 SHALL protect source/config/artifact/profile provenance and reject security/recovery-breaking mixed versions and rollback.
- Phase 15 SHALL define named operational authority, dual control where required, evidence access, recovery admission and post-use review.

This document closes the Phase 11 threat-model analysis obligation only at `design_acceptance`. Implementation, release and runtime evidence remain required by the referenced vectors and blockers.
