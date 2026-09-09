#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'assurance'))
import validate_d4d_selection as validator

CURRENT_SUMMARY_WORKFLOWS = [
    Path('.github/workflows/d4-d-open-evt-016-ledger-promotion.yml'),
    Path('.github/workflows/d4-d-open-evt-016-tenant-contract-ledger-promotion.yml'),
    Path('.github/workflows/d4-d-open-evt-017-message-protection-ledger-promotion.yml'),
    Path('.github/workflows/d4-d-open-evt-017-secret-exclusion-ledger-promotion.yml'),
    Path('.github/workflows/d4-d-open-evt-018-trace-context-ledger-promotion.yml'),
]


def baseline():
    return (
        validator.load(ROOT, validator.SELECTION),
        validator.load(ROOT, validator.LEDGER),
        validator.load(ROOT, validator.STATE),
        validator.load(ROOT, validator.EVALUATION),
        [validator.load(ROOT, path) for path in validator.SOURCES],
    )


def must_fail(mutator, fragment: str) -> None:
    values = [copy.deepcopy(x) for x in baseline()]
    mutator(*values)
    errors = validator.validate_records(*values)
    if not any(fragment in error for error in errors):
        raise AssertionError(f'expected failure containing {fragment!r}, got {errors!r}')


def validate_current_selection_audit_summaries() -> None:
    expected = 'current_selection=selected_c2_security_profile'
    for path in CURRENT_SUMMARY_WORKFLOWS:
        text = (ROOT / path).read_text(encoding='utf-8')
        if expected not in text:
            raise AssertionError(f'{path}: current D4-D selection audit summary drift')


def falsify_selected_profile_contract() -> None:
    def inject_topology(selection, ledger, state, evaluation, sources):
        selection['profile']['trace_context_observability_only_validation_and_redaction']['production_topology'] = 'unauthorized'
    must_fail(inject_topology, 'selected profile nested contract drift')
    for axis in validator.EXPECTED_PROFILE_RECORDS:
        for field in validator.EXPECTED_PROFILE_RECORDS[axis]:
            def drift(selection, ledger, state, evaluation, sources, a=axis, f=field):
                selection['profile'][a][f] = 'unauthorized_override'
            must_fail(drift, 'selected profile nested contract drift')
        def smuggle(selection, ledger, state, evaluation, sources, a=axis):
            selection['profile'][a]['production_topology'] = 'unauthorized'
        must_fail(smuggle, 'selected profile nested contract drift')

    for index in (0, 1, 2):
        def remove_production(*values, i=index):
            values[i].pop('production_authority', None)
        must_fail(remove_production, 'production authority escalation')


def main() -> int:
    values = baseline()
    errors = validator.validate_records(*values)
    if errors:
        raise AssertionError(f'canonical D4-D selection failed validation: {errors!r}')

    validate_current_selection_audit_summaries()

    def mutate_profile(selection, ledger, state, evaluation, sources):
        selection['profile']['trace_context_observability_only_validation_and_redaction']['mechanism_class'] = 'vendor_neutral_trace_correlation_profile'
    must_fail(mutate_profile, 'trace_context_observability_only_validation_and_redaction mechanism selection drift')

    def mutate_ledger_candidate(selection, ledger, state, evaluation, sources):
        ledger['candidate']['workload_identity_to_broker_credential_adapter'] = 'workload_oidc_token_exchange_broker_adapter'
    must_fail(mutate_ledger_candidate, 'current ledger selected profile drift')

    def mutate_state_candidate(selection, ledger, state, evaluation, sources):
        next(t for t in state['tracks'] if t['track_id'] == 'D4-D')['candidate']['tenant_and_contract_scoped_producer_consumer_authorization'] = 'broker_policy_engine_authorization_adapter'
    must_fail(mutate_state_candidate, 'state selected profile drift')

    def rewrite_historical_plan(selection, ledger, state, evaluation, sources):
        evaluation['selection_state'] = 'selected'
        evaluation['selection_authority'] = 'selection_record'
    must_fail(rewrite_historical_plan, 'historical evaluation plan must remain not_selected')

    for index in range(len(validator.SOURCES)):
        def rewrite_source(selection, ledger, state, evaluation, sources, i=index):
            sources[i]['candidate'] = {'selected': True}
            sources[i]['candidate_status'] = 'selected'
        must_fail(rewrite_source, f'source {index} historical candidate must remain null')

    def add_unknown_selection_claim(selection, ledger, state, evaluation, sources):
        selection['d4_acceptance_state'] = 'accepted'
    must_fail(add_unknown_selection_claim, 'selection record top-level schema drift')

    def grant_product(selection, ledger, state, evaluation, sources):
        selection['canonical_product_implementation_authority'] = 'granted'
    must_fail(grant_product, 'selection Product authority escalation')

    def grant_transport(selection, ledger, state, evaluation, sources):
        ledger['d4_transport_authority'] = 'granted'
    must_fail(grant_transport, 'ledger transport authority escalation')

    def accept_d4(selection, ledger, state, evaluation, sources):
        state['gate_state'] = 'separately_accepted'
    must_fail(accept_d4, 'D4 must remain scoped')

    def select_kms_vendor(selection, ledger, state, evaluation, sources):
        selection['profile']['message_protection_key_authority_and_historical_verifier_continuity']['kms_product'] = 'vendor-x'
    must_fail(select_kms_vendor, 'KMS product/crypto/numeric selection forbidden')

    def select_crypto(selection, ledger, state, evaluation, sources):
        selection['profile']['message_protection_key_authority_and_historical_verifier_continuity']['crypto_algorithm'] = 'specific-algorithm'
    must_fail(select_crypto, 'KMS product/crypto/numeric selection forbidden')

    def make_trace_authoritative(selection, ledger, state, evaluation, sources):
        selection['profile']['trace_context_observability_only_validation_and_redaction']['business_or_security_authority'] = 'tenant_authority'
    must_fail(make_trace_authoritative, 'trace context authority drift')

    def regress_credit(selection, ledger, state, evaluation, sources):
        ledger['credited_evidence'].pop()
        ledger['remaining_evidence'] = [validator.EXPECTED_CREDITS[-1]]
    must_fail(regress_credit, 'current ledger credits drift')

    falsify_selected_profile_contract()

    print('d4d_selection_falsification=PASS profile_drift=blocked historical_rewrite=blocked authority_escalation=blocked product_binding=blocked evidence_regression=blocked audit_summary=bound')
    return 0


if __name__ == '__main__':
    main()
