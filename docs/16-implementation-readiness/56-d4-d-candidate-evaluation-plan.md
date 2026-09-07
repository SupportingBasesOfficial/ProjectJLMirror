# D4-D Candidate Evaluation Plan

## Status

This artifact materializes the **candidate-evaluation boundary** for D4-D after D4-C evidence closure.

Canonical base: `7e8a395d22cdf0e7b474b887a1db4087d834057c`.

It does **not** select a D4-D candidate, grant D4 acceptance, credit any D4-D evidence, or grant product, Wave 4, production, or C3 numeric/topology authority.

## Source decisions

D4-D is bounded by the accepted Phase 10 OPEN decisions:

- `OPEN-EVT-016` — service-to-broker authentication/authorization;
- `OPEN-EVT-017` — message protection/KMS and historical verifier profile;
- `OPEN-EVT-018` — trace-context propagation.

The readiness overlay classifies all three as C2 replaceable implementation decisions. Their mechanisms may be evaluated, but fixed security semantics are not implementation discretion.

## Five evaluation axes

1. `workload_identity_to_broker_credential_adapter`
2. `tenant_and_contract_scoped_producer_consumer_authorization`
3. `message_protection_key_authority_and_historical_verifier_continuity`
4. `secret_credential_payload_exclusion_and_erasure_boundary`
5. `trace_context_observability_only_validation_and_redaction`

Each axis declares candidate classes and falsifiable `must_prove` obligations. Evaluation output is limited to evidence-execution eligibility, contract ineligibility, or insufficient evidence.

## Fixed boundaries

The plan requires that:

- broker/vendor identity never becomes canonical platform workload or tenant identity;
- broker authorization remains a projection of current platform authority;
- internal network or broker presence is never trust;
- secret/key material never enters ordinary messages, inbox payloads, logs, traces, or quarantine records;
- verifier loss fails closed for duplicate-sensitive effects;
- historical verifier continuity survives rotation or uses an equality-preserving governed migration;
- trace context remains observability-only and can never become tenant, authorization, idempotency, ordering, or message-identity authority;
- D4-D remains `candidate=null`, `not_selected`, and `0/5` until separately reviewed evidence and promotion steps occur.

## Current global state preserved

After this planning slice:

- D4-A remains `7/7`;
- D4-B remains `5/5`;
- D4-C remains `9/9`, candidate unselected;
- D4-D remains `0/5`, candidate unselected;
- D4-wide evidence remains `21/26`;
- D4 remains `scoped`;
- `d4_transport_authority=selected_not_granted`;
- product/Wave4 authority remains `not_granted`;
- production authority remains `none`;
- C3 numeric/topology authority remains `not_selected`.

## Next gate

A later slice may execute evidence for a D4-D axis only against this bounded plan. Evidence execution cannot auto-select a candidate or auto-credit the ledger. Selection, evidence promotion, D4 acceptance, and merge authorization remain separate governed actions.
