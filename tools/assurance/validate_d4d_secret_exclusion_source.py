#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
from d4d_secret_exclusion_source import run_probes

MANIFEST=Path('implementation/d4-eventing-async/source-evidence/d4-d-secret-credential-exclusion/source-evidence-manifest.json')
STATE=Path('implementation/d4-eventing-async/state-manifest.json')
PLAN=Path('implementation/d4-eventing-async/d4-d-candidate-evaluation-plan.json')
FIRST='workload_identity_to_broker_credential_adapter_least_privilege'
SECOND='tenant_and_contract_scoped_producer_consumer_authorization'
THIRD='message_protection_key_authority_and_historical_verifier_continuity'
EXPECTED_ID='secret_credential_payload_exclusion_and_erasure_boundary'
EXPECTED_DECISION='OPEN-EVT-017'
EXPECTED_AXIS=EXPECTED_ID
EXPECTED_SOURCE_BASE='e899b4a422a72e998dc6d0b612ac93c5cb71eb6a'
EXPECTED_SUPERSEDED_PR=114
EXPECTED_SUPERSEDED_HEAD='c8d49ccf05113f0274287578bbc6965d220a677d'
EXPECTED_SUPERSEDED_REVIEW=5134974949
EXPECTED_MUST={
'ordinary_message_payloads_never_contain_secret_or_credential_material',
'inbox_logs_trace_and_quarantine_records_never_copy_secret_or_key_material',
'erasure_or_minimization_does_not_remove_last_required_non_secret_historical_verification_reference',
'secret_reference_resolution_is_narrowly_authorized_and_audited',
'secret_store_or_kms_outage_does_not_degrade_to_plaintext_or_unverified_acceptance',
'historical_verification_reference_is_not_bearer_authority',
'payload_redaction_and_erasure_preserve_required_correctness_evidence_without_preserving_secret_material'}
EXPECTED_PROBES={
'ordinary_payload_excludes_secret_credential_material',
'message_payload_mapping_is_immutable','source_payload_mutation_does_not_reach_message','nested_payload_sequence_is_immutable','nested_payload_mapping_is_immutable',
'reject_payload_password','reject_payload_secret','reject_payload_credential','reject_payload_token','reject_payload_api_key','reject_payload_private_key','reject_payload_key_material',
'reject_payload_unknown_classification','message_id_secret_material_rejected','tenant_id_secret_material_rejected',
'message_id_secret_handle_rejected','tenant_id_secret_handle_rejected','message_id_embedded_secret_handle_rejected','tenant_id_embedded_secret_handle_rejected',
'secret_reference_empty_handle_rejected','secret_reference_nonstring_handle_creation_rejected','secret_reference_nonstring_handle_resolution_rejected','secret_reference_nonpositive_generation_rejected','secret_reference_boolean_generation_rejected','secret_reference_fractional_generation_rejected','secret_reference_invalid_scope_rejected',
'verification_generation_nonpositive_rejected','verification_generation_boolean_rejected','verification_generation_fractional_rejected',
'verification_reference_namespace_rejected','verification_reference_noncanonical_id_rejected',
'secret_handle_verification_namespace_rejected','secret_handle_audit_namespace_rejected','verification_reference_alias_secret_handle_rejected','verification_reference_embedding_secret_handle_rejected','durable_authority_verification_reference_alias_rejected',
'audit_reference_is_derived_non_secret','secret_handle_scope_rejected','audit_reference_catalogued_handle_collision_rejected',
'unsupported_record_kind_rejected',
'sanitize_reconstructed_alias_rejected','erase_reconstructed_alias_rejected',
'sanitize_reconstructed_unhydrated_secret_ref_rejected','erase_reconstructed_unhydrated_secret_ref_rejected',
'sanitize_reconstructed_secret_message_id_rejected','erase_reconstructed_secret_message_id_rejected',
'sanitize_reconstructed_secret_tenant_id_rejected','erase_reconstructed_secret_tenant_id_rejected',
'sanitize_reconstructed_secret_handle_message_id_rejected','erase_reconstructed_secret_handle_message_id_rejected',
'sanitize_reconstructed_secret_handle_tenant_id_rejected','erase_reconstructed_secret_handle_tenant_id_rejected',
'sanitize_reconstructed_secret_payload_rejected','erase_reconstructed_secret_payload_rejected',
'sanitize_reconstructed_nonpositive_verification_generation_rejected','erase_reconstructed_nonpositive_verification_generation_rejected',
'sanitize_reconstructed_boolean_verification_generation_rejected','erase_reconstructed_boolean_verification_generation_rejected',
'sanitize_reconstructed_fractional_verification_generation_rejected','erase_reconstructed_fractional_verification_generation_rejected',
'secondary_records_exclude_secret_key_material',
'erasure_preserves_non_secret_historical_verification_reference',
'redaction_erasure_preserve_correctness_evidence',
'secret_resolution_is_narrowly_authorized_and_audited','second_configured_authority_handle_resolves','second_configured_authority_handle_detached_payload_rejected','uncatalogued_authority_handle_rejected','resolved_secret_material_rejected_under_business_classification',
'serialized_resolved_secret_material_rejected','nested_serialized_resolved_secret_material_rejected',
'positional_serialized_resolved_secret_material_rejected','nested_positional_serialized_resolved_secret_material_rejected',
'text_serialized_resolved_secret_material_rejected','positional_text_serialized_resolved_secret_material_rejected','nested_text_serialized_resolved_secret_material_rejected','json_scalar_escaped_secret_handle_rejected','duplicate_json_member_escaped_secret_handle_rejected','duplicate_json_member_serialized_secret_object_rejected','url_form_serialized_resolved_secret_material_rejected','url_form_nested_structural_secret_material_rejected','url_escaped_serialized_resolved_secret_material_rejected','double_url_escaped_serialized_resolved_secret_material_rejected','double_url_escaped_benign_payload_accepted_after_stabilization','over_decode_bound_secret_material_rejected','secret_handle_text_fragment_rejected',
'top_level_payload_key_secret_handle_rejected','nested_payload_key_secret_handle_rejected',
'fresh_worker_configured_handle_without_resolution_history_rejected','resolved_handle_without_attached_reference_rejected','resolved_handle_with_different_reference_rejected',
'json_parser_mapping_secret_shape_rejected','json_parser_positional_secret_shape_rejected','json_parser_nested_secret_shape_rejected',
'nested_list_secret_material_rejected','nested_object_secret_material_rejected','opaque_payload_value_type_rejected',
'unhydrated_secret_authority_rejected','unauthorized_resolution_fails_closed','truthy_nonboolean_authorization_rejected','cross_scope_resolution_fails_closed',
'reference_scope_mismatch_fails_closed','scope_not_allowlisted_fails_closed','allowed_scopes_string_container_rejected',
'secret_authority_outage_fails_closed','truthy_nonboolean_authority_availability_rejected','invalid_secret_authority_source_rejected','unknown_secret_handle_resolution_fails_closed',
'stale_generation_resolution_fails_closed','unknown_generation_resolution_fails_closed','authority_boolean_generation_rejected','authority_fractional_generation_rejected',
'historical_reference_is_not_bearer_authority','historical_verification_namespace_collision_fails_closed',
'bearer_secret_reference_rejected','resolve_bearer_secret_reference_rejected'}
REQUIRED=[FIRST,SECOND,THIRD,EXPECTED_ID,'trace_context_observability_only_validation_and_redaction']
CREDITED=[FIRST,SECOND,THIRD]

def validate(root:Path):
    e=[]
    m=json.loads((root/MANIFEST).read_text())
    state=json.loads((root/STATE).read_text())
    plan=json.loads((root/PLAN).read_text())
    if m.get('evidence_id')!=EXPECTED_ID or m.get('source_decision')!=EXPECTED_DECISION:e.append('wrong source evidence identity')
    if m.get('source_base')!=EXPECTED_SOURCE_BASE:e.append('corrected source base drift')
    lineage=m.get('correction_lineage',{})
    if lineage.get('supersedes_source_pr')!=EXPECTED_SUPERSEDED_PR or lineage.get('supersedes_source_head')!=EXPECTED_SUPERSEDED_HEAD or lineage.get('superseded_codex_review_id')!=EXPECTED_SUPERSEDED_REVIEW or lineage.get('promotion_eligible_source_must_be_this_corrected_lineage_or_later') is not True:e.append('correction lineage drift')
    if set(m.get('must_prove',[]))!=EXPECTED_MUST:e.append('must_prove drift')
    if m.get('secret_reference_authority')!='reference_only_secret_or_kms_resolution_with_non_bearer_historical_references':e.append('secret reference authority drift')
    if m.get('current_run_auto_credit') is not False or m.get('ledger_credit')!=[]:e.append('source evidence must remain non-promoting at source time')
    if m.get('candidate') is not None or m.get('candidate_status')!='not_selected' or m.get('selection_authority')!='not_granted':e.append('source evidence must not select D4-D')
    st=m.get('source_time_state',{})
    if st.get('d4d')!='3_of_5_unselected' or st.get('d4wide')!='24_of_26':e.append('source-time snapshot must remain 3/5 and 24/26')
    axis=plan['axes'][EXPECTED_AXIS]
    if axis.get('decision')!=EXPECTED_DECISION or set(axis.get('must_prove',[]))!=EXPECTED_MUST:e.append('candidate-plan/source must_prove mismatch')
    tracks={t['track_id']:t for t in state['tracks']}; d=tracks['D4-D']
    if d.get('candidate') is not None or d.get('candidate_status')!='not_selected' or d.get('state')!='candidate_selection_open':e.append('D4-D state must remain open/unselected')
    if d.get('required_evidence')!=REQUIRED or d.get('evidence_completed')!=CREDITED or d.get('evidence_remaining')!=REQUIRED[3:]:e.append('current D4-D state must remain exactly three separately promoted credits')
    if sum(len(t['evidence_completed']) for t in state['tracks'])!=24:e.append('D4-wide current state must remain 24/26')
    if state.get('gate_state')!='scoped' or state.get('d4_transport_authority')!='selected_not_granted' or state.get('canonical_product_implementation_authority')!='not_granted' or state.get('wave4_implementation_authority')!='not_granted' or state.get('production_authority')!='none' or state.get('c3_numeric_topology_authority')!='not_selected':e.append('authority leakage')
    proofs=run_probes()
    if set(proofs)!=EXPECTED_PROBES:e.append('executed probe set drift')
    bad=[k for k,v in proofs.items() if not v]
    if bad:e.append('behavior probes failed: '+','.join(bad))
    return e

if __name__=='__main__':
    root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd()
    errors=validate(root)
    [print('D4D_SECRET_EXCLUSION_SOURCE_ERROR:',x,file=sys.stderr) for x in errors]
    if errors:raise SystemExit(1)
    print('d4d_secret_exclusion_source=PASS source_snapshot=3_of_5 source_auto_credit=false current_d4d=3_of_5 d4wide=24/26 selection=not_selected authorities=unchanged probes=115 corrected_lineage=true')
