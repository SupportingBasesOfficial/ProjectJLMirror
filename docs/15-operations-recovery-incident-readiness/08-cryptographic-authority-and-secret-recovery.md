# Phase 15 — Cryptographic Authority and Secret Recovery

**Status:** proposed baseline

## Purpose

Define operational recovery of keys, verifier authority and secret references without making KMS/HSM/secret-manager vendor behavior normative.

## Core laws

```text
KEY OBJECT RESTORED != KEY AUTHORITY CURRENT
SECRET VALUE RECOVERED != ACCESS AUTHORITY
OLD VERIFIER REACHABLE != CURRENT VERIFIER AUTHORITY
CRYPTO RECOVERY != REVOCATION/ERASURE REVERSAL
```

## Recovery classes

Operational crypto recovery distinguishes:

- current encryption/decryption authority needed for accepted serving;
- historical verification authority needed to interpret retained evidence;
- signing/attestation/verifier authority for release evidence;
- workload/service secret-reference authority;
- crypto-erasure/revocation decisions that must not regress.

## Historical verification

Historical verifier/key generations may be narrowly available to prove historical equality/provenance when accepted contracts require it. That does not make them current authority for unrelated work.

If historical evidence cannot be interpreted under its accepted profile, the owning path remains reconciliation/recovery blocked until an accepted continuity-preserving migration or trusted authority restores the required proof.

## Secret recovery

Secrets remain referenced rather than embedded in runbooks/evidence. Recovery procedures use scoped identities and approved secret-reference purposes. Operators do not copy production secrets into lower environments or tickets/logs to prove configuration equality.

## Revocation and erasure continuity

A restore must reconcile revocations, rotations, destroyed keys, crypto-erasure intent, tenant erasure and legal-hold decisions after `R`. Missing snapshot evidence never resurrects a revoked credential/key or re-exposes erased data.

## Break-glass interaction

Break-glass may permit a narrowly accepted cryptographic recovery action but cannot bypass key currentness, tenant scope, erasure/legal hold, dual-control requirements where applicable or audit.

## Compromise

Suspected compromised crypto authority is not an ordinary availability outage. Affected privileged paths fail closed until independently accountable Security authority establishes trusted currentness/replacement disposition.

## DR portability

Concrete KMS/HSM/secret-manager vendor, key algorithm and regional topology remain OPEN. Recovery semantics require inventory, generation/currentness, revocation, evidence interpretability, backup/escrow where authorized and exit/migration proof.

## Evidence

Operational evidence records non-secret key/verifier/reference identities/generations, authority decisions, recovery scope, revocation/erasure reconciliation, verification result and reviewer attribution. Secret/key material is never stored as ordinary operational evidence.