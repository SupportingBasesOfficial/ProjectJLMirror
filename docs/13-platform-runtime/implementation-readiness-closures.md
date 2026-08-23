# Phase 13 — Implementation Readiness Closures

**Status:** proposed normative amendment  
**Owning gate:** Implementation Readiness

This file records explicit closure of Phase 13 OPEN decisions through a later accepted governance decision. Original OPEN IDs remain stable historical identifiers; this closure record is authoritative once merged.

## OPEN-PRT-008 — SATISFIED

**Closure:** `docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md#ir-d-002--internal-workload-identity-and-service-authentication`

Canonical workload identity is a SPIFFE-compatible URI identity with an X.509-SVID-compatible short-lived certificate profile. No SPIRE/service-mesh vendor is selected.

## OPEN-PRT-011 — SATISFIED

**Closure:** same IR-D-002 profile.

Internal service peer authentication uses mutual TLS with the current workload certificate profile. mTLS authenticates workload identity only; application tenant/domain authorization remains separate and current.

A narrow adapter may exchange workload identity for short-lived vendor credentials where a state port/broker cannot consume the profile directly, without creating broader canonical authority.

## OPEN-PRT-039 — SATISFIED

**Closure:** `docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md#ir-d-003--concrete-runtime-generationfence-mechanism`

Initial concrete mechanism is a scope-local monotonically increasing 64-bit fence epoch stored/advanced transactionally in the owning PostgreSQL authority state and checked at protected effect boundaries. Wall-clock time, process identity and lease expiry are not fencing authority.

Restore/PITR cannot move effective fencing backwards; stale actors with lower epochs are rejected and uncertain continuity remains quarantined/reconciliation-blocked.

## Remaining OPENs

No other `OPEN-PRT-*` item is closed here. Vendor products, topology, sizing, autoscaling numerics and other evidence-generating/production decisions remain OPEN under their readiness classes.
