# D1 Ratification — Monitoring Track A after D0.1

**Status:** accepted ratification record when merged under the repository's explicit-authorization rule  
**Gate:** D1 procedural ratification  
**Ratification basis:** `main@afc96c6b2e059fa1f130ec7850c5fee3148602fd`  
**Scope:** governance revalidation only; no Monitoring semantic redesign; no Wave 4 implementation authorization

## Purpose

PR #37 accepted `ADR-021` and promoted the Wave 4 Monitoring Track A package on 2026-08-28. Its semantic content remains sound, but its stated prerequisite was procedurally invalid at merge time: PR #36's final Codex review arrived after PR #36 had already merged and exposed additional unresolved D0 P1 findings. PR #37 therefore advanced D1 while the repository was not yet demonstrably clean under the project's exact-HEAD assurance rules.

D0.1 subsequently repaired those findings in PR #38 and restored the missing prerequisite. This record revalidates the original D1 decision on the now-clean canonical base without re-opening or redefining the accepted Monitoring contracts.

## Provenance chain

```text
PR #36 — original D0 remediation
reviewed/merged before final semantic review completed
merge on main:
  6820c98d3197a5cff429a83940f457781d655768

PR #37 — original D1 acceptance
final branch HEAD:
  9dad1ef1c42a43617be7459359a73a6fa0eff9fc
squash on main:
  12e767477e3e44a115ca63a8f0cd41d369a67f3f
semantic result:
  ADR-021 accepted
  Monitoring Track A accepted
procedural defect:
  D0 was not actually clean when D1 merged

PR #38 — D0.1 post-merge remediation
exact reviewed HEAD:
  f98ad3034209efc011eccc1ca3b7090fb9f97b08
Deterministic Assurance:
  #1850 SUCCESS
Codex exact-HEAD semantic review:
  CLEAN — "Didn't find any major issues"
Native Assurance:
  recorded on the same exact HEAD
squash on main:
  afc96c6b2e059fa1f130ec7850c5fee3148602fd

CURRENT RATIFICATION BASE:
  main@afc96c6b2e059fa1f130ec7850c5fee3148602fd
```

## What D0.1 changed

D0.1 repaired two Identity/security mechanism classes and their failure/recovery propagation:

1. security-session/cache revocation safety across durable owning authorities and Redis acceleration, including fencing, partial-write safety, broad O(1) revocation, cleanup serialization, cache admission/recovery, partial partition and ownership preservation;
2. Keycloak OIDC Back-Channel Logout authenticity/provider-identity handling, including signature/algorithm/key validation, issuer-bound `sid`/`sub` mappings, replay scope and uncertainty handling.

The D0.1 delta was limited to:

- `docs/07-system-design/failure-and-degradation-matrix.md`;
- `docs/11-reliability-resilience/OPEN-REL-031-session-store-decision-record.md`;
- `docs/16-implementation-readiness/IR-D-001-keycloak-idp-decision-record.md`.

It did not alter the Monitoring domain contract, Monitoring API contract, Monitoring event contracts, Zabbix provider/normalization contracts, `ADR-021`, or the Wave 4 Monitoring entry-gate semantics.

## Revalidation question

The ratification asks one narrow question:

> Does the corrected D0.1 Identity/security baseline invalidate, contradict, weaken or require redesign of the Monitoring Track A semantics accepted by PR #37?

Answer: **no**.

### Authority ownership

D0.1 strengthens the rule that cached security evidence never launders authority across bounded contexts. That is compatible with Track A, which already requires every protected Monitoring request/effect to establish current tenant/resource authority and treats provider identity as non-authoritative platform metadata.

D0.1 does not move Monitoring-owned source/resource/metric/problem/health authority into Identity, Membership, Authorization, Keycloak or Redis.

### Current authorization and cache behavior

Track A's protected Monitoring reads/mutations already depend on current authorization rather than credential validity alone. D0.1 strengthens the mechanism used to establish current session/membership/permission/tenant-access evidence; it does not change the Monitoring resource or lifecycle semantics once authorization is established.

No Track A cache profile is relaxed. Protected Monitoring values/history/problems remain `no_store` where already specified, and `private_revalidate` remains server-side current-authority revalidation rather than an authorization TTL.

### Provider identity and Zabbix boundary

D0.1's Keycloak rule — provider identity is not platform identity — is the same architectural direction Track A applies to Zabbix: provider-native IDs remain external references behind an adapter and never become tenant/platform authority by themselves.

No Zabbix generation, source identity, normalization, negative-evidence or replacement invariant is changed by D0.1.

### Transactions, fencing and recovery

D0.1 preserves the platform-wide rule that ordinary database transactions are not held open across external Redis/provider calls and that source-owner truth plus required durable responsibility/audit intent commit under the owning authority.

Track A already uses the same architectural laws for Monitoring source mutation, outbox publication, candidate validation, generation cutover and `(R,F]` recovery. D0.1 therefore strengthens shared cross-cutting reliability semantics without contradicting the Monitoring-specific state machines.

### Uncertainty is not absence

D0.1 explicitly preserves `uncertainty != absence` for identity mappings and restored cache authority. Track A already applies the same invariant to provider visibility, negative inference, source generation, scope reconciliation and recovery. No conflict exists.

## Ratified D1 state

The following PR #37 outcomes remain accepted and are hereby ratified on the restored clean prerequisite:

- `adr/ADR-021-monitoring-source-instance-replacement.md` remains **accepted**;
- `docs/03-domains/monitoring-domain-contract.md` remains **accepted**;
- `docs/09-api-contracts/monitoring-domain-api-contract.md` remains **accepted**;
- `docs/10-event-contracts/monitoring-domain-event-contracts.md` remains **accepted**;
- `docs/09-api-contracts/zabbix-monitoring-source-provider-contract.md` remains **accepted**;
- `docs/09-api-contracts/zabbix-monitoring-normalization-profile.md` remains **accepted**;
- `docs/16-implementation-readiness/16-wave-4-monitoring-entry-gate.md` remains the accepted Track A gate record;
- all 36 Track A acceptance criteria remain satisfied;
- Monitoring Track A remains accepted without semantic modification.

This ratification does **not** claim that ADR-021's implementation conformance evidence already exists. Its Validation section continues to bind implementation.

## Track B remains open

Nothing in D0.1 or this ratification closes `OPEN-REL-030`.

Track B remains the next Monitoring gate and must produce bounded, reproducible C2 evidence for the customer-telemetry storage/acceptance path before the Monitoring vertical can receive implementation authorization.

The Track B evidence branch must start from the exact canonical `main` resulting from this ratification, not from the historical PR #37 merge SHA or an older Track A branch.

Required evidence remains at least:

### Tier 1 PostgreSQL / publication

- atomic create-or-observe;
- real multi-connection concurrency;
- durable observation acceptance;
- outbox atomicity;
- current-state CAS;
- repeated same-current no-op;
- stable transition identity;
- duplicate/replay safety;
- crash injection and ambiguous outcomes;
- PITR and `(R,F]` reconciliation.

### Zabbix / currentness

- single-winner polling;
- stale source-generation rejection;
- provider clock rollback;
- same-second history saturation;
- late-history insertion;
- provider visibility loss/incomplete snapshots;
- generation collision/source cutover;
- relocation and PITR.

### Tier 2 candidate

TimescaleDB remains a **candidate only**, not canonical. Evidence must falsify or prove at least:

- tenant RLS isolation;
- compression/columnstore behavior;
- continuous aggregates/background jobs;
- application/reporting role boundaries;
- migration/restore;
- `SET`/`set_config`/`SET ROLE`/`search_path` behavior;
- `SECURITY DEFINER` boundaries;
- cross-tenant leakage resistance;
- capacity under the same security profile.

Any demonstrated cross-tenant leakage rejects the candidate.

## Governance boundary

This record does not:

- authorize Wave 4 product implementation;
- close `OPEN-REL-030`;
- close unrelated Identity/security C2 OPENs;
- make TimescaleDB canonical;
- select the complete application stack;
- activate Alerting, ITSM, Automation, AIOps, FinOps, Commercial, public SDK, outbound Monitoring subscription or browser realtime scope;
- weaken the requirement for exact-HEAD review and explicit owner merge authorization.

The state machine after this ratification is:

```text
D0.1 clean prerequisite
  -> D1 Monitoring Track A ratified
      -> D2 / OPEN-REL-030 Track B conformance
          -> later gates D3..D9
              -> explicit implementation authorization only at D9
```

`READY_FOR_MERGE` for the PR carrying this record is evidence only. The record becomes canonical only after exact-HEAD assurance and separate explicit owner authorization for merge.
