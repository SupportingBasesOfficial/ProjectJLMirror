# D4-D OPEN-EVT-017 — Message Protection / Key Authority / Historical Verifier Source Evidence

## Scope

This package provides source evidence for the D4-D axis `message_protection_key_authority_and_historical_verifier_continuity` derived from OPEN-EVT-017.

It is intentionally non-promoting. It does not credit the D4-D ledger, select a D4-D candidate, grant selection authority, or change D4/Product/Wave4/production/C3 authority.

## Source-time boundary

Canonical source base: `99cb8a887bd9acdcf955a1eed37347cadcbfc086`.

At source time:

- D4-A: 7/7 selected;
- D4-B: 5/5 selected;
- D4-C: 9/9, candidate unselected;
- D4-D: 2/5, candidate unselected;
- D4-wide: 23/26;
- D4 remains scoped;
- `current_run_auto_credit=false`;
- `ledger_credit=[]`.

## Authority model under test

Message protection is governed by a secret/KMS authority boundary. The broker, ciphertext, retained comparison evidence, key-generation references, restored verifier material, or a transport encryption feature do not become platform authorization or current key authority.

The evidence model requires:

- data classification to drive protection, storage, delivery, logging, and retention behavior;
- key material to remain non-exportable behind the secret/KMS authority;
- retained evidence to carry only non-secret comparison-profile and key-generation references;
- historical verifier continuity across supported duplicate-sensitive/recovery horizons;
- equality-preserving migration before retiring required historical verifier authority;
- fail-closed behavior when verifier generations are missing or unknown;
- restored obsolete verifier/profile state to remain non-current and scope-bounded;
- rotation to preserve historical comparison without exposing secret material;
- encryption never to substitute for minimization or authorization.

## Must-prove obligations

1. data classification controls protection, storage, delivery, logging, and retention;
2. key material remains behind secret/KMS authority;
3. retained evidence contains only non-secret profile and key-generation references;
4. historical verifier authority remains available for the supported equivalence horizon or is equality-preserving migrated;
5. verifier loss or unknown generation fails closed for duplicate-sensitive effects;
6. restored old verifier/profile state cannot become current authority for unrelated scope;
7. key/profile rotation preserves historical comparison without secret exposure;
8. encryption does not replace minimization or authorization.

## Executable probes

The harness exercises positive and negative cases for:

- restricted classification policy requiring protected delivery, bounded confidential retention, and no ordinary logging;
- non-exportable key authority;
- retained reference-only evidence without secret material;
- current and historical generation verification;
- missing and unknown verifier generations;
- scope/profile mismatch;
- key rotation preserving historical verifier continuity;
- equality-preserving migration to a new generation;
- restored obsolete verifier rejection;
- unrelated-scope rejection after restore;
- authorization bypass attempts hidden behind encryption;
- minimization bypass attempts hidden behind encryption;
- exportable key-material authority rejection.

## Governance invariants

A successful source run proves only that the source package satisfies the OPEN-EVT-017 message-protection axis contract. It does not promote `message_protection_key_authority_and_historical_verifier_continuity` into `evidence_completed`.

A future promotion must independently bind the exact reviewed source HEAD, workflow run/attempt, job, uploaded provenance artifact and digest, source-manifest digest, and exact promotion base before D4-D may move from 2/5 to 3/5.

Candidate selection remains a separate gate after evidence execution. Full D4 acceptance remains separate after all tracks satisfy their own requirements.
