# D4-D OPEN-EVT-016 Ledger Promotion

## Status

This slice promotes exactly one previously reviewed D4-D source-evidence item into the current D4 ledger:

`workload_identity_to_broker_credential_adapter_least_privilege`

Promotion base: `491c99784637d20189034807a1722371a90a54ee`.

## Source authority

The promoted source is PR #108, reviewed at exact source HEAD:

`4442b4f2ca398eb92833c89abecc835a47598b59`

The promotion is bound to the post-ready source run, exact job, immutable artifact digest and source-manifest SHA-256 recorded in `d4-d-open-evt-016-promotion-v1.json`.

The source manifest remains immutable and non-promoting:

- `current_run_auto_credit=false`;
- `ledger_credit=[]`;
- source-time D4-D remains `0/5`;
- source-time D4-wide remains `21/26`.

The promotion record, not the source run itself, grants the current ledger credit.

## Current state after promotion

- D4-A remains `7/7` selected Kafka at bounded C2 scope;
- D4-B remains `5/5` selected contract profile;
- D4-C remains `9/9`, candidate unselected;
- D4-D becomes `1/5`, candidate unselected;
- D4-wide becomes `22/26`.

Remaining D4-D evidence:

1. `tenant_and_contract_scoped_producer_consumer_authorization`;
2. `message_protection_key_authority_and_historical_verifier_continuity`;
3. `secret_credential_payload_exclusion_and_erasure_boundary`;
4. `trace_context_observability_only_validation_and_redaction`.

## Authority boundary

This promotion does not select a D4-D candidate or broker credential product. IR-D-002 remains canonical internal workload identity/service-authentication authority. The residual issuer/attestation backend choice remains separate.

The following remain unchanged:

- D4 gate: `scoped`;
- D4 transport authority: `selected_not_granted`;
- canonical Product implementation authority: `not_granted`;
- Wave 4 implementation authority: `not_granted`;
- production authority: `none`;
- C3 numeric/topology authority: `not_selected`.

Selection, later D4-D credits, full D4 acceptance, merge and production authority remain separate governed actions.
