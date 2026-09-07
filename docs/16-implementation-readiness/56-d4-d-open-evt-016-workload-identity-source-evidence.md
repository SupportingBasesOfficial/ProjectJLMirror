# D4-D OPEN-EVT-016 — Workload Identity → Broker Credential Adapter Source Evidence

**Status:** source evidence only; non-promoting  
**Base:** `5bf77ec3d4f4a884b70a323d10358b7485db9a0b`

## Scope

This slice exercises the first D4-D evidence axis:

`workload_identity_to_broker_credential_adapter_least_privilege`

It consumes the accepted IR-D-002 workload identity boundary and tests a replaceable broker-credential adapter without selecting a broker credential product or workload-identity backend.

## Proved properties

- canonical IR-D-002 workload identity is authenticated before derivation;
- the adapter does not reopen issuer/attestation authority;
- broker credential identity is derived and replaceable, never canonical platform identity;
- least privilege is bound to exact service, environment, broker role and contract scope;
- network/broker presence alone is insufficient;
- stale/revoked/cross-environment identities and stale credential generations fail closed;
- broad roles, wildcard contracts and manufactured tenant authority fail closed;
- credential rotation preserves canonical workload identity;
- credential/secret material is excluded from ordinary message/log/quarantine-style records.

## Non-authority boundary

This source package does **not** credit the D4-D ledger, select a D4-D candidate, select a credential vendor, select the residual OPEN-PRT-008.B issuer/attestation backend, or grant D4/Product/Wave4/production/C3 authority.

Current state remains D4-A 7/7, D4-B 5/5, D4-C 9/9, D4-D 0/5, D4-wide 21/26.
