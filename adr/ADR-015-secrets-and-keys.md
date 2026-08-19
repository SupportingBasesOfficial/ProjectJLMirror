# ADR-015 — Secrets and Key-Management Architecture

**Status:** accepted  
**Date:** 2026-08-17  
**Reversibility:** costly for key lifecycle, reversible for provider

## Context

JLMIRROR holds provider/API/payment credentials and encryption keys. Database/config/log/queue leakage can create cross-tenant compromise. Rotation must not require redefining business entities.

Drivers: `INV-SECRET-001`, `SEC-SEC-*`, `SEC-SUPPLY-*`, `TM-010`, `TM-013`, `TM-014`.

## Decision

Production secrets SHALL live in a dedicated secret-management/KMS capability. Ordinary application/configuration/data records store **secret references**, not plaintext production secret values.

Runtimes receive least-privilege access to only the secret namespaces required for their role/cell/tenant workload. Secret values SHALL NOT enter queue payloads, integration events, logs, traces, metrics or audit snapshots.

Where encrypted secret material must be persisted by the application, use envelope-encryption semantics with versioned keys, authenticated encryption, explicit ciphertext metadata and rotation support. Root/master keys remain outside the application database.

Key/secret rotation, revocation and audit are first-class operational procedures. CI/CD production credentials use workload identity/short-lived credentials where the selected platform supports them.

No secret-manager/KMS vendor is selected by this ADR.

## Consequences

### Positive
- blast radius of database/source leak is reduced;
- rotation and least privilege are explicit;
- deployment configuration is safer.

### Negative / cost
- secret-manager availability and bootstrap identity become critical operational concerns;
- local development needs safe synthetic/local secret handling.

## Validation

Automated secret scanning, log/trace/event leakage tests, rotation rehearsal and runtime least-privilege tests. Loss of ordinary database dump must not reveal plaintext production provider credentials.

## Exit / revisit conditions

Provider may change while reference/key-lifecycle contract remains.