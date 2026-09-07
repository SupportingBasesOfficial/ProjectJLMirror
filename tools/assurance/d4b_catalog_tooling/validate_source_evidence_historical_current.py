#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = Path('implementation/d4-eventing-async/source-evidence/d4-b-catalog-tooling-candidate-source.json')
PLAN = Path('implementation/d4-eventing-async/d4-b-candidate-evaluation-plan.json')
LEDGER = Path('implementation/d4-eventing-async/d4-b-evidence-plan.json')
STATE = Path('implementation/d4-eventing-async/state-manifest.json')

EXPECTED_KEYS = {
    'schema_version','gate_id','track_id','axis','source_decision','canonical_base','mode','test_profile_only',
    'selection_state','selection_authority','current_run_auto_credit','ledger_credit','candidate_results',
    'equivalent_reviewed_catalog','required_proofs','candidate_profile_requirements','source_assertions','non_authority'
}
EXPECTED_RESULTS = {
    'reviewed_git_catalog': 'eligible_for_evidence_execution',
    'registry_backed_catalog': 'eligible_for_evidence_execution',
    'hybrid_reviewed_git_plus_registry_catalog': 'eligible_for_evidence_execution',
}
EXPECTED_PROOFS = {
    'reviewed_contract_is_canonical_authority',
    'version_provenance_and_history_are_retained',
    'semantic_manifest_is_compared_in_addition_to_payload_schema',
    'historical_reader_upcaster_and_comparison_profile_metadata_are_recoverable',
    'registry_or_catalog_access_is_authenticated_and_authorized',
    'tooling_outage_does_not_rewrite_or_silently_reinterpret_committed_historical_contracts',
    'compatibility_ci_detects_semantic_breaks_not_only_syntactic_schema_changes',
    'catalog_product_identity_does_not_become_contract_identity',
}
EXPECTED_REQUIREMENTS = {
    'reviewed_git_catalog': {
        'reviewed_commit_content_is_the_only_write_authority',
        'history_is_append_only_and_revision_content_is_immutable',
        'semantic_manifest_digest_and_payload_schema_digest_are_both_reviewed',
        'historical_reader_upcaster_and_comparison_profile_refs_are_versioned_with_contract_revision',
        'authenticated_reader_and_reviewer_roles_are_distinct',
        'catalog_read_outage_cannot_mutate_or_rebind_committed_history',
        'compatibility_ci_rejects_semantic_breaks_even_when_payload_schema_is_unchanged',
        'git_commit_or_blob_identity_is_provenance_not_logical_contract_identity',
    },
    'registry_backed_catalog': {
        'registry_registration_requires_preexisting_reviewed_contract_authority',
        'registry_subject_version_or_vendor_id_is_mapping_metadata_not_contract_identity',
        'reviewed_revision_history_and_semantic_manifest_remain_recoverable_without_registry_mutation_authority',
        'historical_reader_upcaster_and_comparison_profile_refs_are_not_derived_from_registry_product_ids',
        'registry_access_requires_authenticated_authorized_principal',
        'registry_outage_or_rebind_attempt_cannot_rewrite_durable_reviewed_contract_history',
        'compatibility_ci_uses_reviewed_semantic_manifest_in_addition_to_registry_schema_compatibility',
        'registry_product_replacement_preserves_logical_contract_identity',
    },
    'hybrid_reviewed_git_plus_registry_catalog': {
        'reviewed_git_contract_is_authority_and_registry_is_a_derived_distribution_index',
        'git_and_registry_provenance_are_both_retained_without_conflating_their_identifiers',
        'semantic_manifest_is_reviewed_in_git_and_mirrored_without_becoming_registry_defined',
        'historical_reader_upcaster_and_comparison_profile_metadata_remain_recoverable_from_reviewed_history',
        'both_review_and_registry_surfaces_require_authenticated_authorized_access',
        'registry_outage_falls_back_to_durable_reviewed_history_without_silent_reinterpretation',
        'compatibility_ci_rejects_semantic_breaks_before_registry_publish',
        'registry_replacement_changes_mapping_metadata_only_not_logical_contract_identity',
    },
}
EXPECTED_ASSERTIONS = {
    'all_three_concrete_catalog_classes_can_reach_eligible_for_evidence_execution_without_selecting_a_product',
    'reviewed_contract_content_is_authority_and_registry_registration_is_never_authority_by_itself',
    'reviewed_provenance_is_bound_into_reviewed_content_digest_and_registry_publish_requires_exact_committed_revision',
    'reviewed_content_digest_uses_explicit_structural_framing_so_field_boundary_bytes_cannot_alias',
    'semantic_manifest_digest_uses_deterministic_canonical_semantic_representation_not_raw_json_formatting',
    'semantic_manifest_numeric_equivalence_is_decimal_exact_and_normalizes_equivalent_json_number_spellings',
    'registry_mapping_metadata_is_immutable_per_reviewed_revision_and_exact_retry_is_idempotent',
    'payload_schema_compatibility_alone_is_insufficient_when_semantic_manifest_changes_break_authoritative_meaning',
    'contract_revision_history_is_append_only_and_old_revision_content_cannot_be_overwritten',
    'historical_reader_upcaster_and_comparison_profile_metadata_are_bound_to_each_reviewed_revision',
    'anonymous_or_unauthorized_catalog_access_fails_closed',
    'registry_outage_does_not_change_the_meaning_of_committed_historical_contracts',
    'registry_subject_version_vendor_id_git_sha_and_storage_location_are_provenance_or_mapping_metadata_not_contract_identity',
    'registry_product_replacement_preserves_logical_contract_identity_and_reviewed_content_digest',
    'wire_serialization_and_contract_version_axes_remain_independently_selectable',
}
EXPECTED_NON_AUTHORITY = {
    'd4b_wire_selection':'not_selected','d4b_catalog_selection':'not_selected','d4b_contract_version_selection':'not_selected',
    'd4_gate':'scoped','d4_transport_authority':'selected_not_granted','canonical_product_implementation_authority':'not_granted',
    'wave4_implementation_authority':'not_granted','production_authority':'none','c3_numeric_topology_authority':'not_selected',
}

class DuplicateMemberError(ValueError):
    pass

def reject_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateMemberError(f'duplicate JSON member {key!r}')
        out[key] = value
    return out

def load(root: Path, path: Path) -> dict:
    value = json.loads((root / path).read_bytes(), object_pairs_hook=reject_duplicates)
    if not isinstance(value, dict):
        raise ValueError(f'{path} must be object')
    return value

def exact_list(value, expected: set[str]) -> bool:
    return isinstance(value, list) and len(value) == len(expected) and set(value) == expected

def validate(root: Path) -> list[str]:
    errors: list[str] = []
    def req(ok: bool, msg: str):
        if not ok:
            errors.append(msg)
    try:
        manifest, plan, ledger, state = (load(root, p) for p in (MANIFEST, PLAN, LEDGER, STATE))
    except (json.JSONDecodeError, DuplicateMemberError, ValueError) as exc:
        return [f'strict JSON parse failure: {exc}']

    req(set(manifest) == EXPECTED_KEYS, 'source manifest exact key schema drift')
    req(manifest.get('schema_version') == 1 and manifest.get('gate_id') == 'D4' and manifest.get('track_id') == 'D4-B', 'source identity drift')
    req(manifest.get('axis') == 'schema_registry_catalog_and_tooling' and manifest.get('source_decision') == 'OPEN-EVT-003', 'source axis/decision drift')
    req(manifest.get('canonical_base') == 'df62898b6d9fc36f2a10c0c3713679d2cbe05da8', 'source canonical base drift')
    req(manifest.get('mode') == 'candidate_source_evidence_only' and manifest.get('test_profile_only') is True, 'source mode drift')
    req(manifest.get('selection_state') == 'not_selected', 'catalog source evidence must not select')
    req(manifest.get('selection_authority') == 'not_granted', 'catalog selection authority escalation')
    req(manifest.get('current_run_auto_credit') is False and manifest.get('ledger_credit') == [], 'source evidence must not auto-credit ledger')
    req(manifest.get('candidate_results') == EXPECTED_RESULTS, 'candidate result inventory drift')
    req(manifest.get('equivalent_reviewed_catalog') == 'insufficient_evidence', 'equivalent catalog must remain insufficient')
    req(exact_list(manifest.get('required_proofs'), EXPECTED_PROOFS), 'required proof inventory drift')

    requirements = manifest.get('candidate_profile_requirements')
    req(isinstance(requirements, dict) and set(requirements) == set(EXPECTED_REQUIREMENTS), 'candidate requirement key drift')
    if isinstance(requirements, dict):
        for candidate, expected in EXPECTED_REQUIREMENTS.items():
            req(exact_list(requirements.get(candidate), expected), f'candidate requirement drift: {candidate}')
    req(exact_list(manifest.get('source_assertions'), EXPECTED_ASSERTIONS), 'source assertion inventory drift')
    req(manifest.get('non_authority') == EXPECTED_NON_AUTHORITY, 'non-authority boundary drift')

    axis = plan.get('axes', {}).get('schema_registry_catalog_and_tooling', {})
    req(axis.get('decision') == 'OPEN-EVT-003', 'accepted Axis B decision drift')
    req(set(axis.get('candidate_classes', [])) == set(EXPECTED_RESULTS) | {'equivalent_reviewed_catalog'}, 'accepted Axis B candidate inventory drift')
    req(exact_list(axis.get('must_prove'), EXPECTED_PROOFS), 'accepted Axis B proof contract drift')
    req(plan.get('selection_state') == 'not_selected' and plan.get('selection_authority') == 'not_granted', 'accepted plan selection drift')
    req(plan.get('separate_selection_required') is True and plan.get('separate_d4_acceptance_required') is True, 'separation guard drift')

    req(ledger.get('candidate') is None and ledger.get('selection_state') == 'not_selected', 'D4-B ledger selection drift')
    req(len(ledger.get('credited_evidence', [])) == 5 and ledger.get('remaining_evidence') == [], 'D4-B ledger 5/5 drift')
    tracks = state.get('tracks', [])
    req(isinstance(tracks, list) and len(tracks) == 4, 'D4 track inventory drift')
    if isinstance(tracks, list) and len(tracks) == 4:
        by = {t.get('track_id'): t for t in tracks if isinstance(t, dict)}
        req(set(by) == {'D4-A','D4-B','D4-C','D4-D'}, 'D4 track identity drift')
        if set(by) == {'D4-A','D4-B','D4-C','D4-D'}:
            req(by['D4-A'].get('candidate') == 'kafka' and len(by['D4-A'].get('evidence_completed', [])) == 7, 'D4-A regression')
            req(by['D4-B'].get('candidate') is None and by['D4-B'].get('state') == 'evidence_complete_selection_pending' and len(by['D4-B'].get('evidence_completed', [])) == 5, 'D4-B state drift')
            for sibling in ('D4-C','D4-D'):
                req(by[sibling].get('candidate') is None and by[sibling].get('evidence_completed') == [], f'{sibling} leak')
    req(state.get('gate_state') == 'scoped', 'D4 gate escalation')
    req(state.get('d4_transport_authority') == 'selected_not_granted', 'transport authority drift')
    req(state.get('canonical_product_implementation_authority') == 'not_granted', 'Product authority escalation')
    req(state.get('wave4_implementation_authority') == 'not_granted', 'Wave4 authority escalation')
    req(state.get('production_authority') == 'none', 'production authority escalation')
    req(state.get('c3_numeric_topology_authority') == 'not_selected', 'C3 authority escalation')
    return errors

def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else ROOT
    errors = validate(root)
    if errors:
        for error in errors:
            print(f'ERROR: {error}', file=sys.stderr)
        return 1
    print('d4b_catalog_tooling_source_manifest=PASS candidates=3 proofs=8 provenance=content_bound digest_frame=unambiguous semantic_manifest=canonical_decimal mapping_history=immutable selection=not_selected ledger_credit=0 d4=12/26')
    return 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
