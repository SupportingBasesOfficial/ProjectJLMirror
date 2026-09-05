#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PLAN = Path("implementation/d4-eventing-async/d4-c-candidate-evaluation-plan.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")

EXPECTED_PLAN_KEYS = {
    "schema_version", "gate_id", "track_id", "canonical_base", "mode", "selection_state",
    "selection_authority", "separate_selection_required", "separate_d4_acceptance_required",
    "source_decisions", "axes", "cross_axis_invariants", "evaluation_output_states", "forbidden_outputs",
}
EXPECTED_AXES = {
    "ack_visibility_lease_and_checkpoint": ("OPEN-EVT-008", "ack_after_durable_responsibility_and_lease_ambiguity"),
    "quarantine_and_redrive": ("OPEN-EVT-009", "quarantine_redrive_current_authority_and_dedup_preservation"),
    "bounded_message_payload_batch_and_compression": ("OPEN-EVT-010", "bounded_message_batch_compression_and_parser_limits"),
    "scoped_content_equivalence_authority": ("OPEN-EVT-011", "scoped_content_equivalence_confidentiality_and_conflict_rejection"),
    "outbox_claim_dispatch_and_ack_ambiguity": ("OPEN-EVT-012", "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity"),
    "producer_source_generation": ("OPEN-EVT-013", "producer_generation_nonresurrection_across_failover_restore"),
    "privileged_replay_and_event_history": ("OPEN-EVT-014", "privileged_bounded_replay_with_original_identity_and_effect_safety"),
    "historical_reader_and_upcaster": ("OPEN-EVT-015", "historical_reader_upcaster_semantic_and_equivalence_continuity"),
    "recovery_generation_reconciliation_and_activation": ("OPEN-EVT-025", "recovery_generation_rf_inventory_reconciliation_and_activation_gates"),
}
EXPECTED_AXIS_KEYS = {"decision", "evidence_id", "candidate_classes", "must_prove"}
EXPECTED_CANDIDATES = {
    "ack_visibility_lease_and_checkpoint": {
        "durable_inbox_claim_then_broker_ack_profile", "broker_visibility_lease_plus_durable_receipt_profile",
        "database_owned_work_claim_plus_broker_checkpoint_profile", "equivalent_reviewed_profile",
    },
    "quarantine_and_redrive": {
        "durable_platform_quarantine_store_with_broker_dlq_adapter", "broker_native_dlq_with_canonical_platform_quarantine_index",
        "hybrid_platform_quarantine_store_plus_broker_dlq", "equivalent_reviewed_profile",
    },
    "bounded_message_payload_batch_and_compression": {
        "contract_bound_application_limits_with_transport_precheck", "bounded_envelope_codec_profile",
        "layered_transport_and_application_bounds_profile", "equivalent_reviewed_profile",
    },
    "scoped_content_equivalence_authority": {
        "canonical_collision_resistant_fingerprint_profile", "keyed_authenticated_digest_profile",
        "protected_retained_immutable_original_profile", "hybrid_equivalence_authority_profile", "equivalent_reviewed_profile",
    },
    "outbox_claim_dispatch_and_ack_ambiguity": {
        "database_skip_locked_polling_claim_profile", "compare_and_swap_lease_claim_profile",
        "notification_assisted_polling_claim_profile", "equivalent_reviewed_profile",
    },
    "producer_source_generation": {
        "positive_integer_fenced_generation", "opaque_fenced_generation_token",
        "authority_issued_epoch_generation", "equivalent_reviewed_profile",
    },
    "privileged_replay_and_event_history": {
        "canonical_event_history_store_profile", "broker_retained_log_plus_authoritative_history_index_profile",
        "hybrid_history_archive_plus_replay_controller_profile", "equivalent_reviewed_profile",
    },
    "historical_reader_and_upcaster": {
        "in_process_versioned_reader_upcaster_registry", "sidecar_or_library_historical_reader_profile",
        "offline_replay_transform_pipeline_profile", "equivalent_reviewed_profile",
    },
    "recovery_generation_reconciliation_and_activation": {
        "restore_generation_fence_manifest_profile", "reconciliation_inventory_job_plus_activation_gate_profile",
        "hybrid_generation_manifest_plus_multi_store_reconciler_profile", "equivalent_reviewed_profile",
    },
}
EXPECTED_PROOFS = {
    "ack_visibility_lease_and_checkpoint": {
        "ack_or_checkpoint_never_precedes_durable_consumer_responsibility",
        "lease_or_visibility_expiry_is_treated_as_ambiguity_not_effect_absence",
        "broker_progress_is_never_business_effect_truth",
        "redelivery_or_offset_rewind_remains_safe_through_inbox_effect_idempotency",
        "offset_rewind_duplicate_handling_requires_scoped_id_content_equivalence_evidence_not_identity_alone",
        "same_scoped_identity_with_conflicting_immutable_content_fails_closed",
        "claim_ownership_and_takeover_are_fenced_against_concurrent_effect_execution",
        "crash_between_effect_responsibility_and_broker_ack_recovers_without_semantic_loss",
    },
    "quarantine_and_redrive": {
        "platform_quarantine_meaning_does_not_depend_on_broker_native_dlq_semantics",
        "bounded_retry_exhaustion_reaches_governed_quarantine",
        "redrive_requires_current_privileged_authority_and_is_audited",
        "redrive_cannot_bypass_inbox_dedup_equivalence_or_reconciliation",
        "same_identity_different_content_is_integrity_failure_not_benign_duplicate",
        "confidential_payload_and_equivalence_evidence_access_is_classification_scoped",
        "quarantine_payload_and_equivalence_evidence_retention_is_data_classification_governed_without_selecting_numeric_horizons",
        "broker_replacement_does_not_rewrite_quarantine_process_truth",
    },
    "bounded_message_payload_batch_and_compression": {
        "message_payload_and_batch_sizes_are_bounded_before_unbounded_allocation",
        "nesting_string_collection_and_field_counts_are_bounded",
        "decompression_work_and_output_are_bounded",
        "parser_recursion_and_cpu_amplification_fail_closed",
        "large_artifacts_and_raw_telemetry_are_referenced_or_routed_to_specialized_planes",
        "transport_limits_cannot_silently_weaken_contract_limits",
        "limit_failures_are_deterministic_observable_and_non_retry_amplifying",
    },
    "scoped_content_equivalence_authority": {
        "dedup_identity_is_consumer_contract_trusted_message_identity_scope_and_message_id_or_equivalent",
        "equivalence_is_evaluated_only_after_trusted_consumer_contract_and_message_scope_identity",
        "repeated_scoped_identity_is_benign_duplicate_only_with_durable_equivalence_evidence",
        "every_immutable_semantic_field_required_for_same_id_meaning_is_covered",
        "same_scoped_id_with_different_immutable_content_fails_closed",
        "comparison_evidence_uses_the_same_canonical_structured_interpretation_as_protected_contract_validation",
        "comparison_profile_and_version_are_stable_and_historically_recoverable",
        "low_entropy_confidential_values_do_not_create_dictionary_or_cross_scope_equality_oracles",
        "comparison_evidence_is_never_authorization_routing_ordering_or_bearer_authority",
        "co_resident_inbox_and_effect_completion_is_atomic",
        "cross_authority_effects_use_stable_operation_and_result_reconciliation",
        "historical_equivalence_authority_survives_supported_horizon_or_is_replaced_by_governed_equality_preserving_migration",
        "payload_erasure_cannot_remove_last_required_equivalence_authority_within_supported_horizon",
        "missing_or_unverifiable_equivalence_evidence_is_uncertainty_not_duplicate_success",
        "verification_work_is_bounded_and_access_controlled",
    },
    "outbox_claim_dispatch_and_ack_ambiguity": {
        "authoritative_mutation_and_required_outbox_fact_commit_atomically",
        "claim_takeover_is_fenced_and_does_not_create_concurrent_semantic_owners",
        "retry_workers_do_not_rewrite_immutable_fact_meaning",
        "broker_ack_ambiguity_retries_same_message_identity_and_semantic_content",
        "broker_outage_preserves_committed_backlog_without_loss",
        "dispatcher_restart_and_recovery_preserve_stable_message_identity_and_semantic_content",
        "cleanup_never_removes_the_last_recovery_authority_before_safe_horizon",
    },
    "producer_source_generation": {
        "current_source_generation_is_explicitly_validated_at_effectful_admission",
        "retired_generation_cannot_regain_current_authority",
        "restore_or_failover_cannot_resurrect_retired_source_authority",
        "historical_fact_identity_remains_distinct_from_current_source_authority",
        "tenant_logical_identity_is_independent_of_generation_and_placement",
        "generation_comparison_rule_is_unambiguous_and_does_not_infer_ungranted_ordering_semantics",
        "provider_or_broker_generation_is_not_platform_source_generation_by_implication",
    },
    "privileged_replay_and_event_history": {
        "replay_is_privileged_audited_bounded_and_currently_authorized",
        "replayed_message_preserves_original_identity_and_immutable_semantic_meaning",
        "replay_retains_or_recovers_required_equivalence_and_historical_verifier_authority",
        "unavailable_historical_comparison_authority_blocks_or_reconciles_duplicate_sensitive_effects_instead_of_trusting_identity_alone",
        "irreversible_effects_cannot_be_repeated_by_disabling_dedup",
        "projection_rebuild_uses_isolated_generation_or_target",
        "replay_cannot_exceed_safe_schema_data_dedup_equivalence_and_recovery_evidence",
        "history_storage_product_identity_does_not_become_message_or_contract_identity",
    },
    "historical_reader_and_upcaster": {
        "historical_semantic_meaning_is_immutable",
        "upcasting_cannot_fabricate_newer_historical_facts",
        "source_message_identity_tenant_and_occurrence_semantics_remain_traceable",
        "supported_retained_history_remains_interpretable",
        "equivalence_evidence_and_comparison_profile_semantics_are_preserved_or_deterministically_mapped",
        "reader_or_upcaster_version_is_explicit_and_historically_recoverable",
        "dynamic_untrusted_code_or_schema_execution_is_not_required_for_historical_read",
    },
    "recovery_generation_reconciliation_and_activation": {
        "restore_generation_and_fence_boundary_are_explicit_and_durable",
        "r_f_window_inventory_reconciles_broker_history_inbox_outbox_equivalence_and_external_effect_evidence",
        "webhook_recovery_preserves_stable_delivery_identity_semantic_snapshot_or_reproduction_authority_and_destination_generation_fences",
        "missing_restored_state_is_uncertainty_not_absence",
        "missing_or_older_content_comparison_evidence_is_not_safe_duplicate_proof",
        "missing_or_stale_historical_comparison_authority_blocks_duplicate_sensitive_effects",
        "duplicate_classification_and_effectful_async_admission_remain_fail_closed_until_continuity_equivalence_and_historical_authority_are_proven",
        "stale_producer_replay_authorization_and_destination_generations_do_not_revive",
        "obsolete_restored_verifier_or_profile_cannot_become_current_authority_for_unrelated_scope",
        "offset_outbox_or_inbox_state_cannot_override_surviving_external_audit_effect_or_equivalence_evidence",
        "effectful_async_activation_is_fail_closed_until_required_reconciliation_is_proven",
        "reconciliation_results_are_generation_scoped_auditable_and_reproducible",
    },
}
EXPECTED_CROSS = {
    "all_nine_axes_are_independently_selectable_and_no_candidate_choice_implies_another_axis_choice",
    "broker_native_features_may_accelerate_mechanics_but_never_replace_platform_business_or_recovery_truth",
    "message_identity_equivalence_ordering_generation_and_authorization_authorities_remain_distinct",
    "current_authority_is_reestablished_at_redrive_replay_and_recovery_activation",
    "historical_message_meaning_and_required_equivalence_verifier_authority_remain_reproducible_for_supported_horizons",
    "uncertainty_never_collapses_to_absence_safe_duplicate_or_effect_eligibility",
    "no_candidate_may_require_dynamic_untrusted_code_schema_or_parser_behavior",
    "d4a_and_d4b_selected_bounded_c2_profiles_are_preserved_without_modification",
    "d4c_existing_evidence_credit_remains_zero_and_no_evaluation_run_auto_credits_the_ledger",
    "d4d_remains_open_unselected_and_uncredited",
    "d4_gate_remains_scoped",
    "transport_product_wave4_production_and_c3_authorities_remain_unchanged_and_ungranted",
}
EXPECTED_OUTPUTS = {"eligible_for_evidence_execution", "ineligible_by_contract", "insufficient_evidence"}
EXPECTED_FORBIDDEN = {
    "selected", "preferred_without_evidence", "ledger_credit_granted", "full_d4_accepted", "production_ready", "authority_granted",
}
EXPECTED_D4A = "kafka"
EXPECTED_D4B = {
    "serialization": {
        "surface_policy": "explicit_surface_bound_profiles",
        "internal_broker": "protobuf_profile",
        "outbound_webhook": "bounded_json_plus_json_schema_profile",
    },
    "schema_catalog": "hybrid_reviewed_git_plus_registry_catalog",
    "contract_version": "positive_integer_family_revision",
}


class DuplicateMemberError(ValueError):
    pass


def reject_duplicate_members(pairs: list[tuple[str, object]]) -> dict:
    out: dict = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateMemberError(f"duplicate JSON member {key!r}")
        out[key] = value
    return out


def load(root: Path, path: Path) -> dict:
    value = json.loads((root / path).read_bytes(), object_pairs_hook=reject_duplicate_members)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a JSON object")
    return value


def exact_list(value: object, expected: set[str]) -> bool:
    return (
        isinstance(value, list)
        and all(type(item) is str for item in value)
        and len(value) == len(expected)
        and len(set(value)) == len(value)
        and set(value) == expected
    )


def validate(root: Path) -> list[str]:
    errors: list[str] = []

    def req(ok: bool, msg: str) -> None:
        if not ok:
            errors.append(msg)

    try:
        plan = load(root, PLAN)
        state = load(root, STATE)
    except (json.JSONDecodeError, DuplicateMemberError, ValueError) as exc:
        return [f"strict JSON parse failure: {exc}"]

    req(set(plan) == EXPECTED_PLAN_KEYS, "D4-C evaluation plan exact key schema drift")
    req(type(plan.get("schema_version")) is int and plan.get("schema_version") == 1, "D4-C evaluation schema version drift")
    req(plan.get("gate_id") == "D4" and plan.get("track_id") == "D4-C", "D4-C evaluation identity drift")
    req(plan.get("canonical_base") == "70a7256b23c43cbd64eb9c02cdcd9091b847204e", "D4-C evaluation canonical base drift")
    req(plan.get("mode") == "candidate_evaluation_only", "D4-C evaluation mode must remain non-selecting")
    req(plan.get("selection_state") == "not_selected", "D4-C evaluation plan must remain not selected")
    req(plan.get("selection_authority") == "not_granted", "D4-C evaluation selection authority must remain ungranted")
    req(plan.get("separate_selection_required") is True and plan.get("separate_d4_acceptance_required") is True, "D4-C selection/acceptance separation drift")

    expected_decisions = {v[0] for v in EXPECTED_AXES.values()}
    req(exact_list(plan.get("source_decisions"), expected_decisions), "D4-C source decision inventory drift")

    axes = plan.get("axes")
    req(isinstance(axes, dict) and set(axes) == set(EXPECTED_AXES), "D4-C exact nine-axis inventory drift")
    if isinstance(axes, dict) and set(axes) == set(EXPECTED_AXES):
        seen_evidence: set[str] = set()
        for name, (decision, evidence_id) in EXPECTED_AXES.items():
            axis = axes.get(name)
            req(isinstance(axis, dict) and set(axis) == EXPECTED_AXIS_KEYS, f"{name} exact key schema drift")
            if not isinstance(axis, dict):
                continue
            req(axis.get("decision") == decision, f"{name} decision binding drift")
            req(axis.get("evidence_id") == evidence_id, f"{name} evidence binding drift")
            req(exact_list(axis.get("candidate_classes"), EXPECTED_CANDIDATES[name]), f"{name} candidate class inventory drift")
            req(exact_list(axis.get("must_prove"), EXPECTED_PROOFS[name]), f"{name} exact proof inventory drift")
            if isinstance(axis.get("evidence_id"), str):
                seen_evidence.add(axis["evidence_id"])
        req(len(seen_evidence) == 9, "D4-C evidence IDs must be one-to-one with axes")

    req(exact_list(plan.get("cross_axis_invariants"), EXPECTED_CROSS), "D4-C cross-axis invariant inventory drift")
    req(exact_list(plan.get("evaluation_output_states"), EXPECTED_OUTPUTS), "D4-C evaluation output inventory drift")
    req(exact_list(plan.get("forbidden_outputs"), EXPECTED_FORBIDDEN), "D4-C forbidden output inventory drift")

    tracks = state.get("tracks")
    req(isinstance(tracks, list) and len(tracks) == 4 and all(isinstance(t, dict) for t in tracks), "D4 track structure drift")
    if isinstance(tracks, list) and len(tracks) == 4 and all(isinstance(t, dict) for t in tracks):
        by_id = {t.get("track_id"): t for t in tracks}
        req(set(by_id) == {"D4-A", "D4-B", "D4-C", "D4-D"}, "D4 track identity drift")
        if set(by_id) == {"D4-A", "D4-B", "D4-C", "D4-D"}:
            d4a, d4b, d4c, d4d = by_id["D4-A"], by_id["D4-B"], by_id["D4-C"], by_id["D4-D"]
            req(d4a.get("candidate") == EXPECTED_D4A and d4a.get("state") == "selected_candidate" and len(d4a.get("evidence_completed", [])) == 7 and d4a.get("evidence_remaining") == [], "D4-A selected 7/7 regression")
            req(d4b.get("candidate") == EXPECTED_D4B and d4b.get("state") == "selected_candidate" and len(d4b.get("evidence_completed", [])) == 5 and d4b.get("evidence_remaining") == [], "D4-B selected 5/5 regression")
            req(d4c.get("candidate") is None and d4c.get("candidate_status") == "not_selected" and d4c.get("state") == "candidate_selection_open", "D4-C state must remain open/unselected")
            req(d4c.get("evidence_completed") == [] and exact_list(d4c.get("required_evidence"), {v[1] for v in EXPECTED_AXES.values()}) and exact_list(d4c.get("evidence_remaining"), {v[1] for v in EXPECTED_AXES.values()}), "D4-C evidence must remain 0/9")
            req(d4d.get("candidate") is None and d4d.get("candidate_status") == "not_selected" and d4d.get("state") == "candidate_selection_open" and d4d.get("evidence_completed") == [], "D4-D must remain open/unselected/uncredited")
            req(sum(len(t.get("evidence_completed", [])) for t in tracks) == 12, "D4-wide evidence must remain 12/26")

    req(state.get("gate_state") == "scoped", "D4 gate must remain scoped")
    req(state.get("d4_transport_authority") == "selected_not_granted", "D4 transport authority drift")
    req(state.get("canonical_product_implementation_authority") == "not_granted", "Product authority escalation")
    req(state.get("wave4_implementation_authority") == "not_granted", "Wave4 authority escalation")
    req(state.get("production_authority") == "none", "production authority escalation")
    req(state.get("c3_numeric_topology_authority") == "not_selected", "C3 authority escalation")
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4C_EVAL_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4c_candidate_evaluation_plan=PASS mode=candidate_evaluation_only axes=9 selection=not_selected ledger_credit=0 d4a=7_of_7 d4b=5_of_5 d4c=0_of_9 d4d=0_of_5 d4wide=12/26 d4=scoped authorities=unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
