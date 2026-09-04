#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = Path("implementation/d4-eventing-async/source-evidence/d4-b-wire-schema-candidate-source.json")
PLAN = Path("implementation/d4-eventing-async/d4-b-candidate-evaluation-plan.json")
LEDGER = Path("implementation/d4-eventing-async/d4-b-evidence-plan.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")

EXPECTED_MANIFEST_KEYS = {
    "schema_version", "gate_id", "track_id", "axis", "source_decision", "canonical_base", "mode",
    "test_profile_only", "selection_state", "selection_authority", "current_run_auto_credit", "ledger_credit",
    "candidate_results", "equivalent_reviewed_profile", "required_proofs", "candidate_profile_requirements",
    "official_source_facts", "source_assertions", "non_authority",
}
EXPECTED_RESULTS = {
    "bounded_json_plus_json_schema_profile": "eligible_for_evidence_execution",
    "protobuf_profile": "eligible_for_evidence_execution",
    "avro_profile": "eligible_for_evidence_execution",
}
EXPECTED_PROOFS = {
    "one_canonical_bounded_structured_interpretation",
    "duplicate_and_alias_protected_fields_fail_closed",
    "required_optional_null_and_enum_semantics_are_explicit",
    "historical_contract_meaning_remains_interpretable",
    "duplicate_sensitive_content_equivalence_is_deterministic_and_reproducible",
    "unknown_field_and_forward_compatibility_behavior_is_explicit",
    "parser_and_decompression_work_are_bounded",
    "no_dynamic_untrusted_schema_or_code_loading",
    "language_runtime_mapping_does_not_change_authoritative_contract_semantics",
}
EXPECTED_REQUIREMENTS = {
    "bounded_json_plus_json_schema_profile": {
        "strict_utf8_json_parser_rejects_duplicate_members_before_object_materialization",
        "protected_alias_groups_are_checked_before_contract_validation",
        "additional_properties_required_null_enum_numeric_depth_and_message_size_rules_are_explicit",
        "json_numbers_use_bounded_decimal_semantics_and_canonical_normalization_instead_of_binary_float_runtime_mapping",
        "content_equivalence_uses_canonical_semantic_normalization_not_input_member_order",
        "historical_payload_is_bound_to_reviewed_json_profile_and_schema_identity",
        "schema_resolution_must_not_fetch_or_execute_untrusted_dynamic_content",
    },
    "protobuf_profile": {
        "bounded_wire_predecoder_rejects_nonminimal_varints_uint64_overflow_and_reserved_field_numbers",
        "bounded_wire_predecoder_rejects_duplicate_protected_singular_fields_before_generated_binding_last_wins_behavior",
        "protected_oneof_duplicate_occurrences_and_cross_member_collisions_fail_closed_before_generated_binding_resolution",
        "required_optional_absence_and_enum_semantics_are_explicit_before_generated_runtime_mapping",
        "unknown_binary_fields_are_preserved_for_forward_compatibility_when_required",
        "protobuf_serialized_byte_order_is_not_contract_equivalence_authority",
        "repeated_field_occurrence_order_is_preserved_within_each_field_number_during_semantic_normalization",
        "historical_payload_is_bound_to_reviewed_protobuf_profile_and_schema_identity",
        "descriptor_or_dynamic_message_loading_from_untrusted_message_content_is_forbidden",
    },
    "avro_profile": {
        "original_writer_schema_identity_and_content_are_pinned_for_historical_interpretation",
        "reader_schema_resolution_is_explicit_and_missing_fields_require_defaults_or_failure",
        "writer_reader_field_type_compatibility_and_allowed_promotions_are_checked_before_value_resolution",
        "required_nullable_and_enum_semantics_are_explicit_after_writer_reader_resolution",
        "field_aliases_are_reviewed_and_ambiguous_aliases_fail_closed",
        "semantic_equivalence_is_computed_after_explicit_writer_reader_resolution_not_from_raw_schema_text",
        "historical_payload_is_bound_to_reviewed_avro_profile_and_writer_schema_identity",
        "writer_reader_schema_loading_is_bounded_to_reviewed_content_and_not_selected_by_message_payload",
    },
}
EXPECTED_SOURCE_FACTS = {
    ("https://protobuf.dev/programming-guides/encoding/", "protobuf_singular_duplicate_wire_values_are_normally_last_one_wins_and_serialization_order_is_not_guaranteed"),
    ("https://protobuf.dev/programming-guides/editions/", "protobuf_binary_unknown_fields_are_preserved_but_some_nonbinary_conversion_paths_can_lose_them"),
    ("https://avro.apache.org/docs/1.11.2/specification/", "avro_schema_resolution_uses_original_writer_schema_plus_reader_schema_with_defaults_or_failure_for_reader_only_fields"),
    ("https://json-schema.org/draft/2020-12/json-schema-validation", "json_schema_validation_does_not_itself_bound_arbitrary_precision_json_numbers"),
    ("https://json-schema.org/understanding-json-schema/reference/object", "json_schema_additional_properties_are_allowed_by_default_unless_profile_restricts_them"),
}
EXPECTED_ASSERTIONS = {
    "raw_candidate_defaults_are_not_automatically_equivalent_to_jlmirror_contract_requirements",
    "candidate_specific_guard_profiles_may_strengthen_default_parser_behavior_without_selecting_a_candidate",
    "all_three_concrete_candidates_can_reach_eligible_for_evidence_execution_under_explicit_guard_profiles",
    "unselected_compression_is_rejected_so_decompression_work_is_zero_and_bounded",
    "untrusted_message_content_cannot_select_schema_descriptor_or_executable_code",
    "historical_payload_profile_and_schema_binding_prevents_cross_profile_reinterpretation",
    "json_numeric_normalization_is_bounded_decimal_and_runtime_independent_within_the_evidence_profile",
    "protobuf_nonminimal_varints_uint64_overflow_and_reserved_field_numbers_fail_closed",
    "protobuf_last_one_wins_default_is_not_accepted_for_protected_fields",
    "protobuf_same_oneof_member_duplicates_and_cross_member_collisions_fail_closed",
    "protobuf_required_optional_absence_and_enum_semantics_are_explicit",
    "protobuf_raw_serialized_bytes_are_not_content_equivalence_authority",
    "protobuf_repeated_field_occurrence_order_remains_semantic_during_normalization",
    "avro_historical_interpretation_requires_writer_schema_continuity",
    "avro_writer_reader_type_compatibility_is_explicit_and_incompatible_types_fail_closed",
    "avro_required_nullable_and_enum_semantics_are_explicit_after_resolution",
    "json_schema_requires_explicit_platform_bounds_beyond_base_validation_vocabulary",
    "no_candidate_profile_loads_schema_or_executable_content_from_untrusted_message_payload",
    "internal_broker_and_external_webhook_profiles_remain_independently_selectable_under_one_canonical_domain_semantics",
}
EXPECTED_NON_AUTHORITY = {
    "d4b_wire_selection": "not_selected",
    "d4b_catalog_selection": "not_selected",
    "d4b_contract_version_selection": "not_selected",
    "d4_gate": "scoped",
    "d4_transport_authority": "selected_not_granted",
    "canonical_product_implementation_authority": "not_granted",
    "wave4_implementation_authority": "not_granted",
    "production_authority": "none",
    "c3_numeric_topology_authority": "not_selected",
}


class DuplicateMemberError(ValueError):
    pass


def reject_duplicates(pairs: list[tuple[str, object]]) -> dict:
    out: dict = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateMemberError(f"duplicate JSON member {key!r}")
        out[key] = value
    return out


def load(root: Path, path: Path) -> dict:
    value = json.loads((root / path).read_bytes(), object_pairs_hook=reject_duplicates)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return value


def _exact_string_set(value: object, expected: set[str]) -> bool:
    return isinstance(value, list) and len(value) == len(expected) and set(value) == expected


def validate(root: Path) -> list[str]:
    errors: list[str] = []

    def req(ok: bool, message: str) -> None:
        if not ok:
            errors.append(message)

    try:
        manifest = load(root, MANIFEST)
        plan = load(root, PLAN)
        ledger = load(root, LEDGER)
        state = load(root, STATE)
    except (json.JSONDecodeError, DuplicateMemberError, ValueError) as exc:
        return [f"strict JSON parse failure: {exc}"]

    req(set(manifest) == EXPECTED_MANIFEST_KEYS, "source manifest exact key schema drift")
    req(manifest.get("schema_version") == 1, "source schema drift")
    req(manifest.get("gate_id") == "D4" and manifest.get("track_id") == "D4-B", "source identity drift")
    req(manifest.get("axis") == "wire_serialization_and_schema_language", "source axis drift")
    req(manifest.get("source_decision") == "OPEN-EVT-002", "source decision drift")
    req(manifest.get("canonical_base") == "9cfe67915b6081af015670d7f1edb7ecf11ffdf2", "source canonical base drift")
    req(manifest.get("mode") == "candidate_source_evidence_only", "source mode drift")
    req(manifest.get("test_profile_only") is True, "candidate profiles must remain evidence-only")
    req(manifest.get("selection_state") == "not_selected", "source evidence must not select D4-B wire profile")
    req(manifest.get("selection_authority") == "not_granted", "source selection authority escalation")
    req(manifest.get("current_run_auto_credit") is False and manifest.get("ledger_credit") == [], "source evidence must not auto-credit ledger")
    req(manifest.get("candidate_results") == EXPECTED_RESULTS, "concrete candidate result inventory drift")
    req(manifest.get("equivalent_reviewed_profile") == "insufficient_evidence", "equivalent candidate class must remain unevaluated")
    req(_exact_string_set(manifest.get("required_proofs"), EXPECTED_PROOFS), "required proof inventory drift")

    requirements = manifest.get("candidate_profile_requirements")
    req(isinstance(requirements, dict) and set(requirements) == set(EXPECTED_REQUIREMENTS), "candidate requirement key inventory drift")
    if isinstance(requirements, dict) and set(requirements) == set(EXPECTED_REQUIREMENTS):
        for candidate, expected in EXPECTED_REQUIREMENTS.items():
            req(_exact_string_set(requirements.get(candidate), expected), f"candidate requirement drift for {candidate}")

    facts = manifest.get("official_source_facts")
    fact_pairs: set[tuple[str, str]] = set()
    if isinstance(facts, list):
        for item in facts:
            if isinstance(item, dict) and set(item) == {"source", "fact"} and isinstance(item.get("source"), str) and isinstance(item.get("fact"), str):
                fact_pairs.add((item["source"], item["fact"]))
    req(isinstance(facts, list) and len(facts) == len(EXPECTED_SOURCE_FACTS) and fact_pairs == EXPECTED_SOURCE_FACTS, "official source fact inventory drift")
    req(_exact_string_set(manifest.get("source_assertions"), EXPECTED_ASSERTIONS), "source assertion inventory drift")
    req(manifest.get("non_authority") == EXPECTED_NON_AUTHORITY, "non-authority boundary drift")

    axis = plan.get("axes", {}).get("wire_serialization_and_schema_language", {})
    req(axis.get("decision") == "OPEN-EVT-002", "accepted Axis A decision binding drift")
    candidates = axis.get("candidate_classes", [])
    req(isinstance(candidates, list) and set(candidates) == set(EXPECTED_RESULTS) | {"equivalent_reviewed_profile"}, "accepted Axis A candidate inventory drift")
    req(_exact_string_set(axis.get("must_prove"), EXPECTED_PROOFS), "accepted Axis A proof contract drift")
    req(plan.get("selection_state") == "not_selected" and plan.get("selection_authority") == "not_granted", "accepted plan selection drift")
    req(plan.get("separate_selection_required") is True and plan.get("separate_d4_acceptance_required") is True, "accepted separation guard drift")

    req(ledger.get("candidate") is None and ledger.get("selection_state") == "not_selected", "D4-B ledger selection drift")
    req(len(ledger.get("credited_evidence", [])) == 5 and ledger.get("remaining_evidence") == [], "D4-B ledger 5/5 drift")

    tracks = state.get("tracks", [])
    req(isinstance(tracks, list) and len(tracks) == 4, "D4 track inventory drift")
    if isinstance(tracks, list) and len(tracks) == 4:
        ids = [track.get("track_id") for track in tracks if isinstance(track, dict)]
        req(len(ids) == 4 and len(set(ids)) == 4 and set(ids) == {"D4-A", "D4-B", "D4-C", "D4-D"}, "D4 track identity drift")
        if len(ids) == 4 and len(set(ids)) == 4:
            by_id = {track["track_id"]: track for track in tracks}
            req(by_id["D4-A"].get("candidate") == "kafka" and len(by_id["D4-A"].get("evidence_completed", [])) == 7, "D4-A Kafka 7/7 regression")
            req(by_id["D4-B"].get("candidate") is None and by_id["D4-B"].get("state") == "evidence_complete_selection_pending" and len(by_id["D4-B"].get("evidence_completed", [])) == 5, "D4-B current-state drift")
            for sibling in (by_id["D4-C"], by_id["D4-D"]):
                req(sibling.get("candidate") is None and sibling.get("evidence_completed") == [], "D4-C/D sibling leak")

    req(state.get("gate_state") == "scoped", "D4 gate escalation")
    req(state.get("d4_transport_authority") == "selected_not_granted", "transport authority drift")
    req(state.get("canonical_product_implementation_authority") == "not_granted", "Product authority escalation")
    req(state.get("wave4_implementation_authority") == "not_granted", "Wave4 authority escalation")
    req(state.get("production_authority") == "none", "production authority escalation")
    req(state.get("c3_numeric_topology_authority") == "not_selected", "C3 authority escalation")
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else ROOT
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4B_WIRE_SCHEMA_SOURCE_ERROR: {error}", file=sys.stderr)
        return 1
    print(
        "d4b_wire_schema_source_manifest=PASS axis=OPEN-EVT-002 concrete_candidates=3 eligible=3 "
        "canonical_varints=required uint64_varints=bounded protobuf_oneof_duplicates=blocked "
        "avro_type_resolution=required runtime_mapping=bounded historical_binding=required decompression=identity_only "
        "equivalent=insufficient_evidence selection=not_selected ledger_credit=0 d4=scoped authorities=not_granted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
