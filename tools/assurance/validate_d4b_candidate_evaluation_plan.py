#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PLAN = Path("implementation/d4-eventing-async/d4-b-candidate-evaluation-plan.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")
D4B_LEDGER = Path("implementation/d4-eventing-async/d4-b-evidence-plan.json")

EXPECTED_PLAN_KEYS = {
    "schema_version", "gate_id", "track_id", "canonical_base", "mode", "selection_state",
    "selection_authority", "separate_selection_required", "separate_d4_acceptance_required",
    "source_decisions", "axes", "cross_axis_invariants", "evaluation_output_states", "forbidden_outputs",
}
EXPECTED_AXES = {
    "wire_serialization_and_schema_language": "OPEN-EVT-002",
    "schema_registry_catalog_and_tooling": "OPEN-EVT-003",
    "contract_version_representation": "OPEN-EVT-004",
}
EXPECTED_AXIS_KEYS = {
    "wire_serialization_and_schema_language": {"decision", "candidate_classes", "surface_policy", "must_prove"},
    "schema_registry_catalog_and_tooling": {"decision", "candidate_classes", "must_prove"},
    "contract_version_representation": {"decision", "candidate_classes", "must_prove"},
}
EXPECTED_CANDIDATES = {
    "wire_serialization_and_schema_language": {
        "bounded_json_plus_json_schema_profile", "protobuf_profile", "avro_profile", "equivalent_reviewed_profile",
    },
    "schema_registry_catalog_and_tooling": {
        "reviewed_git_catalog", "registry_backed_catalog", "hybrid_reviewed_git_plus_registry_catalog", "equivalent_reviewed_catalog",
    },
    "contract_version_representation": {
        "positive_integer_family_revision", "semantic_version_like_contract_revision", "opaque_monotonic_contract_token", "equivalent_reviewed_representation",
    },
}
EXPECTED_PROOFS = {
    "wire_serialization_and_schema_language": {
        "one_canonical_bounded_structured_interpretation", "duplicate_and_alias_protected_fields_fail_closed",
        "required_optional_null_and_enum_semantics_are_explicit", "historical_contract_meaning_remains_interpretable",
        "duplicate_sensitive_content_equivalence_is_deterministic_and_reproducible",
        "unknown_field_and_forward_compatibility_behavior_is_explicit", "parser_and_decompression_work_are_bounded",
        "no_dynamic_untrusted_schema_or_code_loading", "language_runtime_mapping_does_not_change_authoritative_contract_semantics",
    },
    "schema_registry_catalog_and_tooling": {
        "reviewed_contract_is_canonical_authority", "version_provenance_and_history_are_retained",
        "semantic_manifest_is_compared_in_addition_to_payload_schema",
        "historical_reader_upcaster_and_comparison_profile_metadata_are_recoverable",
        "registry_or_catalog_access_is_authenticated_and_authorized",
        "tooling_outage_does_not_rewrite_or_silently_reinterpret_committed_historical_contracts",
        "compatibility_ci_detects_semantic_breaks_not_only_syntactic_schema_changes",
        "catalog_product_identity_does_not_become_contract_identity",
    },
    "contract_version_representation": {
        "contract_version_is_distinct_from_deployment_api_provider_realtime_and_registry_versions",
        "breaking_semantic_change_requires_new_incompatible_contract_version_or_accepted_migration",
        "historical_messages_retain_original_version_semantics", "representation_has_one_canonical_parse_and_comparison_rule",
        "version_ordering_is_not_assumed_unless_the_selected_profile_explicitly_grants_it",
        "version_value_is_not_authorization_tenant_routing_or_message_identity_authority",
    },
}
EXPECTED_CROSS = {
    "wire_schema_catalog_and_contract_version_choices_are_independently_selectable",
    "a_catalog_or_registry_product_cannot_select_wire_serialization_by_implication",
    "a_wire_serialization_choice_cannot_select_catalog_or_contract_version_syntax_by_implication",
    "internal_and_external_surfaces_may_use_different reviewed_profiles_without_changing_canonical_domain_semantics",
    "historical_source_and_ledger_records_remain_immutable",
    "d4b_existing_five_of_five_evidence_credit_is_preserved_without_new_auto_credit",
    "d4a_kafka_bounded_c2_selection_and_exact_seven_of_seven_evidence_are_preserved",
    "d4c_and_d4d_remain_open_unselected_and_uncredited", "d4_gate_remains_scoped",
    "product_wave4_production_and_c3_authorities_remain_ungranted",
}
EXPECTED_OUTPUTS = {"eligible_for_evidence_execution", "ineligible_by_contract", "insufficient_evidence"}
EXPECTED_FORBIDDEN = {"selected", "preferred_without_evidence", "production_ready", "authority_granted"}
EXPECTED_D4B_EVIDENCE = {
    "canonical_bounded_serialization_profile", "parser_ambiguity_and_duplicate_field_negative_vectors",
    "schema_catalog_semantic_manifest_compatibility_ci", "historical_reader_and_equivalence_profile_continuity",
    "contract_version_representation_and_breaking_change_vectors",
}
EXPECTED_D4A_EVIDENCE = {
    "capacity_envelope_baseline_growth_stress", "broker_neutral_anti_corruption_stub_swap",
    "regulated_payload_erasure_granularity", "exactly_once_guardrail_consumer_inbox_enforcement",
    "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency",
    "physical_naming_routing_and_cell_topology_adapter_mapping",
    "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark",
}
EXPECTED_SELECTED = {
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


def validate(root: Path) -> list[str]:
    errors: list[str] = []

    def req(ok: bool, msg: str) -> None:
        if not ok:
            errors.append(msg)

    try:
        plan = load(root, PLAN)
        state = load(root, STATE)
        ledger = load(root, D4B_LEDGER)
    except (json.JSONDecodeError, DuplicateMemberError, ValueError) as exc:
        return [f"strict JSON parse failure: {exc}"]

    # Historical evaluation plan remains exactly non-selecting.
    req(set(plan) == EXPECTED_PLAN_KEYS, "evaluation plan exact key schema drift")
    req(plan.get("schema_version") == 1, "evaluation plan schema drift")
    req(plan.get("gate_id") == "D4" and plan.get("track_id") == "D4-B", "evaluation plan identity drift")
    req(plan.get("canonical_base") == "9aefb026d8b8a80abc72f1be5c853059718f5ae2", "evaluation canonical base drift")
    req(plan.get("mode") == "candidate_evaluation_only", "evaluation mode must remain non-selecting")
    req(plan.get("selection_state") == "not_selected", "historical evaluation plan must not be rewritten as selected")
    req(plan.get("selection_authority") == "not_granted", "evaluation selection authority must remain ungranted")
    req(plan.get("separate_selection_required") is True and plan.get("separate_d4_acceptance_required") is True, "historical evaluation plan separation guards drift")
    req(set(plan.get("source_decisions", [])) == set(EXPECTED_AXES.values()) and len(plan.get("source_decisions", [])) == 3, "source decision inventory drift")

    axes = plan.get("axes")
    req(isinstance(axes, dict) and set(axes) == set(EXPECTED_AXES), "exact three-axis evaluation inventory drift")
    if isinstance(axes, dict) and set(axes) == set(EXPECTED_AXES):
        for name, decision in EXPECTED_AXES.items():
            axis = axes[name]
            req(isinstance(axis, dict) and set(axis) == EXPECTED_AXIS_KEYS[name], f"{name} exact key schema drift")
            if isinstance(axis, dict):
                req(axis.get("decision") == decision, f"{name} decision binding drift")
                candidates = axis.get("candidate_classes", [])
                req(isinstance(candidates, list) and set(candidates) == EXPECTED_CANDIDATES[name] and len(candidates) == len(EXPECTED_CANDIDATES[name]), f"{name} candidate class inventory drift")
                proofs = axis.get("must_prove", [])
                req(isinstance(proofs, list) and set(proofs) == EXPECTED_PROOFS[name] and len(proofs) == len(EXPECTED_PROOFS[name]), f"{name} exact proof inventory drift")
        req(axes["wire_serialization_and_schema_language"].get("surface_policy") == "internal_broker_and_external_webhook_profiles_may_differ_only_when_canonical_semantics_conversion_and_historical_interpretation_are_explicit", "internal/external surface policy drift")

    req(isinstance(plan.get("cross_axis_invariants"), list) and set(plan["cross_axis_invariants"]) == EXPECTED_CROSS and len(plan["cross_axis_invariants"]) == len(EXPECTED_CROSS), "cross-axis exact invariant inventory drift")
    req(isinstance(plan.get("evaluation_output_states"), list) and set(plan["evaluation_output_states"]) == EXPECTED_OUTPUTS and len(plan["evaluation_output_states"]) == len(EXPECTED_OUTPUTS), "evaluation output state inventory drift")
    req(isinstance(plan.get("forbidden_outputs"), list) and set(plan["forbidden_outputs"]) == EXPECTED_FORBIDDEN and len(plan["forbidden_outputs"]) == len(EXPECTED_FORBIDDEN), "forbidden output inventory drift")

    # Current ledger may be selected only by the separately governed selection record.
    req(ledger.get("selection_state") == "selected" and ledger.get("candidate") == EXPECTED_SELECTED, "current D4-B selected ledger drift")
    req(ledger.get("candidate_status") == "selected_c2_profile", "current D4-B selected ledger status drift")
    req(ledger.get("selection_record") == "implementation/d4-eventing-async/d4-b-selection-record.json", "current D4-B selection record binding drift")
    req(ledger.get("current_run_auto_credit") is False, "current selection must not invent auto-credit")
    req(set(ledger.get("credited_evidence", [])) == EXPECTED_D4B_EVIDENCE and len(ledger.get("credited_evidence", [])) == 5 and ledger.get("remaining_evidence") == [], "D4-B 5/5 ledger drift")
    req(ledger.get("separate_selection_required") is False and ledger.get("separate_d4_acceptance_required") is True, "current D4-B selection/full-acceptance separation drift")

    tracks = state.get("tracks", [])
    req(isinstance(tracks, list) and len(tracks) == 4 and all(isinstance(t, dict) for t in tracks), "D4 track structure drift")
    if isinstance(tracks, list) and len(tracks) == 4 and all(isinstance(t, dict) for t in tracks):
        ids = [t.get("track_id") for t in tracks]
        req(len(ids) == len(set(ids)) and set(ids) == {"D4-A", "D4-B", "D4-C", "D4-D"}, "D4 track identity drift")
        if len(ids) == len(set(ids)) and set(ids) == {"D4-A", "D4-B", "D4-C", "D4-D"}:
            by_id = {t["track_id"]: t for t in tracks}
            d4a, d4b, d4c, d4d = by_id["D4-A"], by_id["D4-B"], by_id["D4-C"], by_id["D4-D"]
            req(d4a.get("candidate") == "kafka" and set(d4a.get("evidence_completed", [])) == EXPECTED_D4A_EVIDENCE and len(d4a.get("evidence_completed", [])) == 7, "D4-A Kafka 7/7 regression")
            req(d4b.get("candidate") == EXPECTED_SELECTED and d4b.get("candidate_status") == "selected_c2_profile", "D4-B current selected profile drift")
            req(d4b.get("state") == "selected_candidate" and set(d4b.get("evidence_completed", [])) == EXPECTED_D4B_EVIDENCE and len(d4b.get("evidence_completed", [])) == 5 and d4b.get("evidence_remaining") == [], "D4-B selected state/credit drift")
            for sibling in (d4c, d4d):
                req(sibling.get("candidate") is None and sibling.get("candidate_status") == "not_selected" and sibling.get("evidence_completed") == [], "D4-C/D must remain open and uncredited")
            req(sum(len(t.get("evidence_completed", [])) for t in tracks) == 12, "D4-wide evidence must remain 12/26")

    req(state.get("gate_state") == "scoped", "D4 gate must remain scoped")
    req(state.get("d4_transport_authority") == "selected_not_granted", "transport authority drift")
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
            print(f"D4B_EVAL_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4b_candidate_evaluation_plan=PASS historical_plan=not_selected axes=3 exact_schema=true current_selection=selected_c2_profile d4b=5_of_5 d4a=kafka_7_of_7 d4wide=12/26 d4=scoped authorities=not_granted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
