# D4-D OPEN-EVT-017 — Message Protection Ledger Promotion

## Scope

This change promotes the reviewed source evidence `message_protection_key_authority_and_historical_verifier_continuity` as the third D4-D ledger credit.

Promotion base: `28c5274b9ec99a5866eceaec1b76459c6b4ab4ef`.

Reviewed source:

- source PR: #112;
- exact reviewed source HEAD: `7d0ca86a582d2b695858c9f4437b459b21194922`;
- source squash/main commit: `28c5274b9ec99a5866eceaec1b76459c6b4ab4ef`;
- exact source review: `5134095776`;
- workflow run: `34144652834`, attempt `1`;
- job: `101813930120`;
- artifact: `10027183776`;
- artifact digest: `sha256:58f6e78324c924c4d41d8230b4e752e7ab64af5b2a95fe54115ded1890fdf9e6`;
- source-manifest SHA-256: `8d33a50b8748382586aa5b13e2e7427a57b66d8319066acf09f0e09a4ca31c35`.

## State transition

This promotion changes only the governed D4-D ledger/current-state projection:

- D4-D: `2/5 -> 3/5`;
- D4-wide: `23/26 -> 24/26`.

The source manifest remains an immutable historical snapshot of the source run at D4-D `2/5`, D4-wide `23/26`, with `ledger_credit=[]` and `current_run_auto_credit=false`.

## Newly credited evidence

`message_protection_key_authority_and_historical_verifier_continuity`

The cumulative D4-D credit set becomes:

1. `workload_identity_to_broker_credential_adapter_least_privilege`;
2. `tenant_and_contract_scoped_producer_consumer_authorization`;
3. `message_protection_key_authority_and_historical_verifier_continuity`.

Two evidence axes remain:

- `secret_credential_payload_exclusion_and_erasure_boundary`;
- `trace_context_observability_only_validation_and_redaction`.

## Authority boundary

This promotion does not select a D4-D candidate and does not grant D4-D selection authority. D4 remains `scoped`; D4 transport remains `selected_not_granted`; Product/Wave4 implementation authority remains `not_granted`; production authority remains `none`; C3 numeric/topology authority remains `not_selected`.

Candidate selection remains a separate gate. Full D4 acceptance remains a separate later action after all required evidence and track dispositions satisfy the canonical acceptance rule.
