# Phase 13 — Implementation Readiness Closures

**Status:** proposed normative amendment  
**Owning gate:** Implementation Readiness

This file records explicit closure/splitting of Phase 13 OPEN decisions through a later accepted governance decision. Original OPEN IDs remain stable historical identifiers; this closure record is authoritative once merged.

## OPEN-PRT-008 — SPLIT FOR READINESS

Original question: workload-identity issuer/protocol/mechanism.

The source decision contains two readiness subdecisions with different gates and is therefore split rather than falsely closed as one unit.

### OPEN-PRT-008.A — protocol/trust-shape — SATISFIED on gate acceptance

**Closure:** `docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md#ir-d-002--internal-workload-identity-and-service-authentication`

Canonical workload identity/protocol shape is:

- SPIFFE-compatible workload URI identity;
- X.509-SVID-compatible short-lived certificate profile;
- current trust-bundle/issuer generation semantics;
- attested runtime evidence rather than caller-selected identity strings;
- environment/trust-domain isolation;
- service authentication explicitly separate from tenant/domain authorization.

This closes the C1 trust-boundary/profile decision needed to write protected service code.

### OPEN-PRT-008.B — issuer/attestation backend — remains OPEN C2

The concrete workload-identity issuer/control-plane/attestation product and runtime integration remain an evidence-generating implementation decision.

Closure evidence shall prove:

- the selected backend emits the accepted identity/certificate profile;
- runtime attestation cannot request arbitrary broader identities;
- rotation/revocation/trust-bundle currentness works across restart/recovery;
- environment isolation and portability are preserved;
- no product-native identity becomes canonical business/tenant authority.

Selecting SPIRE, a cloud workload-identity backend or another implementation merely because it exists does not close this residual subdecision.

## OPEN-PRT-011 — SATISFIED on gate acceptance

**Closure:** IR-D-002.

Internal service peer authentication uses mutual TLS with the current workload certificate profile. mTLS authenticates workload identity only; application tenant/domain authorization remains separate and current.

A narrow adapter may exchange workload identity for short-lived vendor credentials where a state port/broker cannot consume the profile directly, without creating broader canonical authority.

## OPEN-PRT-039 — SATISFIED on gate acceptance

**Closure:** `docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md#ir-d-003--concrete-runtime-generationfence-mechanism`

Initial concrete mechanism is a scope-local monotonically increasing positive PostgreSQL `BIGINT` fence epoch, stored/advanced transactionally in the owning authority state and checked at protected effect boundaries.

The epoch has no wrap/reset/reuse semantics. Wall-clock time, process identity and lease expiry are not fencing authority. Cross-authority effects retain stable operation/reconciliation semantics; a fence does not make an ambiguous outcome absent.

Restore/PITR cannot move effective fencing backwards; stale actors with lower epochs are rejected and uncertain continuity remains quarantined/reconciliation-blocked until reconciled/fenced forward.

## Remaining OPENs

No other `OPEN-PRT-*` item is closed here. `OPEN-PRT-008.B` and vendor products, topology, sizing, autoscaling numerics and other evidence-generating/production decisions remain OPEN under their readiness classes.
