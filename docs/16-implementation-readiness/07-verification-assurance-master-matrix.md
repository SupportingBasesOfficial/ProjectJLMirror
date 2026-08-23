# Implementation Readiness — Verification & Assurance Master Matrix

**Status:** proposed gate baseline

## Purpose

Every implementation slice must be falsifiable against accepted semantics. Compilation, deployment or a happy path is not sufficient evidence.

## Master matrix

| Assurance class | Minimum implementation evidence | Canonical upstream owner |
|---|---|---|
| authority/tenant | current auth, tenant derivation, stale authority rejection, cross-tenant negative tests | Product/Security/Phase 09/13 |
| HTTP canonicalization | parser/proxy equivalence, framing/path/query/header ambiguity rejection | Phase 09 |
| API idempotency | create-or-observe races, mismatch/in-progress, crash/recovery ambiguity | Phase 09/11 |
| callback/provider | exact authenticated representation, replay race, ack durability, post-effect ambiguity | Phase 09/11/15 |
| async delivery | outbox durability, broker ambiguity, inbox equivalence, redelivery, poison/quarantine | Phase 10/11 |
| replay/equivalence | same-ID/different-content, verifier outage/continuity/trust, anti-oracle bounds | Phase 10/11 |
| realtime | single-use admission, Origin/current auth, revocation, relocation, resync/gap | Phase 09/10/11 |
| reliability | dependency loss, timeout, retries, circuits where applicable, backpressure, noisy-neighbor | Phase 11 |
| observability | trace reconstruction, redaction, cardinality, telemetry loss, health/quarantine semantics | Phase 12 |
| workload identity | issuer/bundle rotation, cross-environment rejection, mTLS identity != tenant auth | IR-D-002/Security |
| runtime fencing | stale epoch, concurrent acquisition, restart/replacement, restore with higher surviving epoch | IR-D-003/Phase 11/13 |
| state ports | co-location authority separation, failure/recovery semantics, privilege boundaries | Phase 13 |
| parser/automation isolation | secret/network/state denial, escape/resource bounds, output classification | Phase 09/13 |
| release chain | untrusted source isolation, provenance, immutable artifact, config equivalence, runtime artifact proof | Phase 14 |
| deployment ambiguity | concurrent deploy fencing, timeout/lost response, same operation observe/reconcile | Phase 14 |
| schema/migration | expand/deploy/migrate/switch/observe/contract, mixed version, backfill resume/load | Data/Phase 14 |
| recovery | backup integrity, R/F, `(R,F]`, stale writer, partial admission, newer deny/erasure/crypto continuity | Phase 11–15 |
| operations | incident lifecycle, runbook authority limits, break-glass selectors, residual reconciliation | Phase 15 |
| capacity/cost | tenant skew, amplification, backlog, recovery/rollout double load, cost bounds | Phases 11–15 |
| supply-chain | pinned/reproducible inputs, least privilege, secret denial, verifier continuity | Phase 14 |

## Evidence levels

```text
L0 normative design evidence
L1 static/unit/contract evidence
L2 integration/concurrency/fault evidence
L3 deployment/runtime rehearsal evidence
L4 production eligibility/runtime evidence
```

Implementation Readiness accepts L0 definitions and requires each slice to declare which later L1–L4 evidence blocks slice merge, release or production.

## Deterministic repository assurance

Every implementation PR inherits observer-only deterministic assurance. Exact-HEAD success is evidence only and does not replace semantic review.

## Native Assurance propagation

A material implementation finding follows the same lifecycle:

```text
finding
 -> missing property
 -> owning authority
 -> correction
 -> class-wide panorama
 -> new HEAD
 -> rerun deterministic evidence
 -> exact-final-HEAD clean-room
```

## AI/tool boundary

AI/scanners may create tests/findings/hypotheses. They cannot waive a mandatory vector, convert unknown applicability to N/A, select protected authority or issue implementation/release/production authorization.
