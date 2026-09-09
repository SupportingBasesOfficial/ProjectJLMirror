#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

SELECTION = Path('implementation/d4-eventing-async/d4-d-selection-record.json')
LEDGER = Path('implementation/d4-eventing-async/d4-d-evidence-plan.json')
STATE = Path('implementation/d4-eventing-async/state-manifest.json')
EVALUATION = Path('implementation/d4-eventing-async/d4-d-candidate-evaluation-plan.json')
SOURCES = [
    Path('implementation/d4-eventing-async/source-evidence/d4-d-workload-identity/source-evidence-manifest.json'),
    Path('implementation/d4-eventing-async/source-evidence/d4-d-tenant-contract-authorization/source-evidence-manifest.json'),
    Path('implementation/d4-eventing-async/source-evidence/d4-d-message-protection-key-authority/source-evidence-manifest.json'),
    Path('implementation/d4-eventing-async/source-evidence/d4-d-secret-credential-exclusion/source-evidence-manifest.json'),
    Path('implementation/d4-eventing-async/source-evidence/d4-d-trace-context-observability/source-evidence-manifest.json'),
]
EXPECTED_BASE = '4b76249e351a1fe18e425541af6d10ae540b0af1'
EXPECTED_PROFILE = {
    'workload_identity_to_broker_credential_adapter': 'derived_short_lived_broker_native_credential_adapter',
    'tenant_and_contract_scoped_producer_consumer_authorization': 'broker_acl_projection_adapter',
    'message_protection_key_authority_and_historical_verifier_continuity': 'kms_backed_envelope_or_transport_protection_profile',
    'secret_credential_payload_exclusion_and_erasure_boundary': 'reference_only_secret_authority_profile',
    'trace_context_observability_only_validation_and_redaction': 'w3c_trace_context_bounded_profile',
}
EXPECTED_D4C_PROFILE = {
    'ack_visibility_lease_and_checkpoint': 'durable_inbox_claim_then_broker_ack_profile',
    'quarantine_and_redrive': 'hybrid_platform_quarantine_store_plus_broker_dlq',
    'bounded_message_payload_batch_and_compression': 'layered_transport_and_application_bounds_profile',
    'scoped_content_equivalence_authority': 'hybrid_equivalence_authority_profile',
    'outbox_claim_dispatch_and_ack_ambiguity': 'compare_and_swap_lease_claim_profile',
    'producer_source_generation': 'authority_issued_epoch_generation',
    'privileged_replay_and_event_history': 'hybrid_history_archive_plus_replay_controller_profile',
    'historical_reader_and_upcaster': 'in_process_versioned_reader_upcaster_registry',
    'recovery_generation_reconciliation_and_activation': 'hybrid_generation_manifest_plus_multi_store_reconciler_profile',
}
EXPECTED_PROFILE_RECORDS = {'workload_identity_to_broker_credential_adapter': {'selection_state': 'selected',
                                                    'mechanism_class': 'derived_short_lived_broker_native_credential_adapter',
                                                    'canonical_workload_identity_authority': 'IR-D-002',
                                                    'credential_role': 'replaceable_least_privilege_broker_credential_only',
                                                    'identity_provider_product': None,
                                                    'unselected_eligible_alternatives': ['workload_identity_mtls_broker_adapter',
                                                                                         'workload_oidc_token_exchange_broker_adapter',
                                                                                         'equivalent_reviewed_derived_credential_adapter']},
 'tenant_and_contract_scoped_producer_consumer_authorization': {'selection_state': 'selected',
                                                                'mechanism_class': 'broker_acl_projection_adapter',
                                                                'authority_source': 'current_platform_authority_projection',
                                                                'projection_scope': 'tenant_service_domain_role_and_contract',
                                                                'broker_or_policy_product': None,
                                                                'unselected_eligible_alternatives': ['broker_policy_engine_authorization_adapter',
                                                                                                     'scoped_token_or_credential_claim_authorization_adapter',
                                                                                                     'equivalent_reviewed_broker_authorization_adapter']},
 'message_protection_key_authority_and_historical_verifier_continuity': {'selection_state': 'selected',
                                                                         'mechanism_class': 'kms_backed_envelope_or_transport_protection_profile',
                                                                         'key_authority': 'secret_or_kms_authority',
                                                                         'historical_verifier_reference': 'non_secret_profile_and_key_generation_reference',
                                                                         'historical_verifier_loss_behavior': 'fail_closed_for_duplicate_sensitive_effects',
                                                                         'kms_product': None,
                                                                         'crypto_algorithm': None,
                                                                         'rotation_interval': None,
                                                                         'unselected_eligible_alternatives': ['secret_authority_backed_authenticated_equivalence_profile',
                                                                                                              'broker_native_encryption_plus_external_historical_verifier_profile',
                                                                                                              'equivalent_reviewed_key_and_verifier_profile']},
 'secret_credential_payload_exclusion_and_erasure_boundary': {'selection_state': 'selected',
                                                              'mechanism_class': 'reference_only_secret_authority_profile',
                                                              'ordinary_payload_secret_material': 'forbidden',
                                                              'historical_correctness_reference': 'non_secret_reference_only',
                                                              'secret_reference_bearer_authority': False,
                                                              'secret_store_product': None,
                                                              'unselected_eligible_alternatives': ['opaque_key_generation_reference_profile',
                                                                                                   'protected_external_secret_handle_profile',
                                                                                                   'equivalent_reviewed_secret_exclusion_profile']},
 'trace_context_observability_only_validation_and_redaction': {'selection_state': 'selected',
                                                               'mechanism_class': 'w3c_trace_context_bounded_profile',
                                                               'traceparent_profile': 'w3c_version_00_bounded_validated',
                                                               'tracestate_policy': 'bounded_canonical_and_removed_from_tenant_scoped_export',
                                                               'attribute_policy': 'deny_by_default_allowlisted_bounded_redacted',
                                                               'business_or_security_authority': 'none',
                                                               'tracing_product': None,
                                                               'unselected_eligible_alternatives': ['vendor_neutral_trace_correlation_profile',
                                                                                                    'broker_header_trace_adapter_profile',
                                                                                                    'equivalent_reviewed_trace_context_profile']}}
EXPECTED_CREDITS = [
    'workload_identity_to_broker_credential_adapter_least_privilege',
    'tenant_and_contract_scoped_producer_consumer_authorization',
    'message_protection_key_authority_and_historical_verifier_continuity',
    'secret_credential_payload_exclusion_and_erasure_boundary',
    'trace_context_observability_only_validation_and_redaction',
]
EXPECTED_SOURCE_DECISIONS = ['OPEN-EVT-016', 'OPEN-EVT-017', 'OPEN-EVT-018']
EXPECTED_SELECTION_KEYS = {
    'schema_version','selection_id','gate_id','track_id','selection_base_main_commit','source_decisions',
    'evidence_completion','selection_state','selection_scope','track_state','profile','cross_axis_rules',
    'd4_gate_state','d4_transport_authority','canonical_product_implementation_authority',
    'wave4_implementation_authority','production_authority','c3_numeric_topology_authority',
    'separate_d4_acceptance_required','historical_evidence_rule','non_authority_rule'
}
EXPECTED_CROSS = {
    'broker_vendor_identity_never_becomes_platform_workload_or_tenant_identity',
    'broker_authorization_remains_projection_of_current_platform_authority',
    'internal_network_or_broker_presence_never_establishes_trust',
    'secret_key_or_credential_material_never_enters_ordinary_messages_inbox_logs_trace_or_quarantine',
    'historical_verifier_continuity_survives_rotation_or_requires_equality_preserving_governed_migration',
    'trace_context_remains_observability_only_and_never_business_or_security_authority',
    'selected_mechanism_classes_remain_replaceable_adapters_not_platform_business_authority',
}


def load(root: Path, path: Path) -> dict:
    return json.loads((root / path).read_text(encoding='utf-8'))


def validate_records(selection: dict, ledger: dict, state: dict, evaluation: dict, sources: list[dict]) -> list[str]:
    errors: list[str] = []
    def req(ok: bool, message: str) -> None:
        if not ok:
            errors.append(message)

    req(set(selection) == EXPECTED_SELECTION_KEYS, 'selection record top-level schema drift')
    req(selection.get('schema_version') == 1, 'selection schema_version drift')
    req(selection.get('selection_id') == 'd4-d-bounded-c2-security-profile-selection-v1', 'selection id drift')
    req(selection.get('gate_id') == 'D4' and selection.get('track_id') == 'D4-D', 'selection gate/track drift')
    req(selection.get('selection_base_main_commit') == EXPECTED_BASE, 'selection base drift')
    req(selection.get('source_decisions') == EXPECTED_SOURCE_DECISIONS, 'selection source decisions drift')
    req(selection.get('selection_state') == 'selected', 'selection must be selected')
    req(selection.get('selection_scope') == 'bounded_c2_security_profile_selection_only', 'selection scope drift')
    req(selection.get('track_state') == 'selected_candidate', 'selection track state drift')
    req(set(selection.get('cross_axis_rules', [])) == EXPECTED_CROSS and len(selection.get('cross_axis_rules', [])) == len(EXPECTED_CROSS), 'cross-axis rule inventory drift')

    completion = selection.get('evidence_completion', {})
    req(completion.get('required_evidence_count') == 5 and completion.get('credited_evidence_count') == 5, 'selection evidence completion drift')
    req(completion.get('evidence_plan_path') == LEDGER.as_posix(), 'selection evidence plan path drift')
    req(completion.get('candidate_evaluation_plan_path') == EVALUATION.as_posix(), 'selection evaluation plan path drift')
    req(completion.get('source_manifest_paths') == [p.as_posix() for p in SOURCES], 'selection source manifest inventory drift')

    profile = selection.get('profile', {})
    req(set(profile) == set(EXPECTED_PROFILE), 'selected profile axis inventory drift')
    req(profile == EXPECTED_PROFILE_RECORDS, 'selected profile nested contract drift')
    eval_axes = evaluation.get('axes', {})
    for axis, expected in EXPECTED_PROFILE.items():
        axis_record = profile.get(axis, {})
        req(axis_record.get('selection_state') == 'selected', f'{axis} selection state drift')
        req(axis_record.get('mechanism_class') == expected, f'{axis} mechanism selection drift')
        req(expected in eval_axes.get(axis, {}).get('candidate_classes', []), f'{axis} selected mechanism was not evidence-eligible')

    req(profile.get('workload_identity_to_broker_credential_adapter', {}).get('identity_provider_product') is None, 'identity provider product must remain unselected')
    authz = profile.get('tenant_and_contract_scoped_producer_consumer_authorization', {})
    req(authz.get('authority_source') == 'current_platform_authority_projection', 'broker authorization authority source drift')
    req(authz.get('broker_or_policy_product') is None, 'broker/policy product must remain unselected')
    protection = profile.get('message_protection_key_authority_and_historical_verifier_continuity', {})
    req(protection.get('key_authority') == 'secret_or_kms_authority', 'KMS/secret authority boundary drift')
    req(protection.get('kms_product') is None and protection.get('crypto_algorithm') is None and protection.get('rotation_interval') is None, 'KMS product/crypto/numeric selection forbidden')
    secret = profile.get('secret_credential_payload_exclusion_and_erasure_boundary', {})
    req(secret.get('ordinary_payload_secret_material') == 'forbidden' and secret.get('secret_reference_bearer_authority') is False, 'secret exclusion boundary drift')
    req(secret.get('secret_store_product') is None, 'secret-store product must remain unselected')
    trace = profile.get('trace_context_observability_only_validation_and_redaction', {})
    req(trace.get('business_or_security_authority') == 'none', 'trace context authority drift')
    req(trace.get('tracing_product') is None, 'tracing product must remain unselected')

    req(evaluation.get('mode') == 'candidate_evaluation_only', 'historical evaluation mode drift')
    req(evaluation.get('selection_state') == 'not_selected' and evaluation.get('selection_authority') == 'not_granted', 'historical evaluation plan must remain not_selected')
    req(evaluation.get('separate_selection_required') is True and evaluation.get('separate_d4_acceptance_required') is True, 'historical evaluation separation drift')

    for index, source in enumerate(sources):
        req(source.get('candidate') is None, f'source {index} historical candidate must remain null')
        req(source.get('candidate_status') == 'not_selected', f'source {index} historical candidate status drift')
        req(source.get('selection_authority') == 'not_granted', f'source {index} historical selection authority drift')
        req(source.get('current_run_auto_credit') is False, f'source {index} historical auto-credit drift')
        req(source.get('ledger_credit') == [], f'source {index} historical ledger credit drift')

    req(ledger.get('candidate') == EXPECTED_PROFILE, 'D4-D current ledger selected profile drift')
    req(ledger.get('candidate_status') == 'selected_c2_security_profile', 'D4-D current ledger candidate status drift')
    req(ledger.get('ledger_credit_state') == 'five_of_five', 'D4-D evidence completion drift')
    req(ledger.get('credited_evidence') == EXPECTED_CREDITS and ledger.get('remaining_evidence') == [], 'D4-D current ledger credits drift')
    req(ledger.get('selection_state') == 'selected' and ledger.get('selection_authority') == 'selection_record', 'D4-D current selection authority drift')
    req(ledger.get('selection_record') == SELECTION.as_posix(), 'D4-D selection record binding drift')
    req(ledger.get('separate_selection_required') is False and ledger.get('separate_d4_acceptance_required') is True, 'D4-D selection/acceptance separation drift')
    req(ledger.get('current_run_auto_credit') is False, 'selection must not become auto-credit authority')

    tracks = {t.get('track_id'): t for t in state.get('tracks', []) if isinstance(t, dict)}
    d4d = tracks.get('D4-D', {})
    req(d4d.get('candidate') == EXPECTED_PROFILE, 'D4-D state selected profile drift')
    req(d4d.get('candidate_status') == 'selected_c2_security_profile' and d4d.get('state') == 'selected_candidate', 'D4-D state selection drift')
    req(d4d.get('evidence_completed') == EXPECTED_CREDITS and d4d.get('evidence_remaining') == [], 'D4-D state evidence drift')
    d4c = tracks.get('D4-C', {})
    req(d4c.get('candidate') == EXPECTED_D4C_PROFILE and d4c.get('candidate_status') == 'selected_c2_delivery_recovery_profile' and d4c.get('state') == 'selected_candidate', 'D4-C current selected sibling projection drift')
    req(len(d4c.get('evidence_completed', [])) == 9 and d4c.get('evidence_remaining') == [], 'D4-C current evidence projection drift')
    req(sum(len(t.get('evidence_completed', [])) for t in tracks.values()) == 26, 'D4-wide evidence must remain 26/26')

    for obj, label in ((selection, 'selection'), (ledger, 'ledger'), (state, 'state')):
        req(obj.get('d4_transport_authority') == 'selected_not_granted', f'{label} transport authority escalation')
        req(obj.get('canonical_product_implementation_authority') == 'not_granted', f'{label} Product authority escalation')
        req(obj.get('wave4_implementation_authority') == 'not_granted', f'{label} Wave4 authority escalation')
        req(obj.get('production_authority') == 'none', f'{label} production authority escalation')
        req(obj.get('c3_numeric_topology_authority') == 'not_selected', f'{label} C3 authority escalation')
    req(selection.get('d4_gate_state') == 'scoped', 'historical D4-D selection gate drift')
    req(state.get('gate_state') == 'separately_accepted', 'current D4 gate acceptance drift')
    req(selection.get('separate_d4_acceptance_required') is True, 'historical D4-D selection must preserve separate acceptance requirement')
    return errors


def validate(root: Path) -> list[str]:
    return validate_records(
        load(root, SELECTION),
        load(root, LEDGER),
        load(root, STATE),
        load(root, EVALUATION),
        [load(root, path) for path in SOURCES],
    )


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f'D4D_SELECTION_ERROR: {error}', file=sys.stderr)
        return 1
    print('d4d_selection=PASS profile=selected_c2_security_profile evidence=5_of_5 d4wide=26_of_26 d4c=current_selected d4=separately_accepted historical_selection_gate=scoped authorities=unchanged')
    return 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
