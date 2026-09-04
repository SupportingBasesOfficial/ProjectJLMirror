#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = Path("implementation/d4-eventing-async/source-evidence/d4-b-contract-version-candidate-source.json")
PLAN = Path("implementation/d4-eventing-async/d4-b-candidate-evaluation-plan.json")
LEDGER = Path("implementation/d4-eventing-async/d4-b-evidence-plan.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")

EXPECTED_MANIFEST_KEYS = {
    "schema_version", "gate_id", "track_id", "axis", "source_decision", "canonical_base", "mode",
    "test_vector_profile_only", "canonical_contract_version_syntax_selected", "selection_state",
    "selection_authority", "current_run_auto_credit", "ledger_credit", "candidate_results",
    "equivalent_reviewed_representation", "required_proofs", "source_assertions", "non_authority",
}
EXPECTED_RESULTS = {
    "positive_integer_family_revision": "eligible_for_evidence_execution",
    "semantic_version_like_contract_revision": "eligible_for_evidence_execution",
    "opaque_monotonic_contract_token": "eligible_for_evidence_execution",
}
EXPECTED_PROOFS = {
    "contract_version_is_distinct_from_deployment_api_provider_realtime_and_registry_versions",
    "breaking_semantic_change_requires_new_incompatible_contract_version_or_accepted_migration",
    "historical_messages_retain_original_version_semantics",
    "representation_has_one_canonical_parse_and_comparison_rule",
    "version_ordering_is_not_assumed_unless_the_selected_profile_explicitly_grants_it",
    "version_value_is_not_authorization_tenant_routing_or_message_identity_authority",
}
EXPECTED_ASSERTIONS = {
    "all_three_concrete_candidate_classes_have_bounded_deterministic_test_parsers",
    "all_three_concrete_candidate_classes_reject_noncanonical_or_ambiguous_test_vectors",
    "opaque_monotonic_candidate_requires_strictly_increasing_internal_issuance_sequence_while_external_tokens_remain_opaque",
    "comparison_surface_is_equality_only_and_exposes_no_ordering_authority",
    "unrelated_version_namespaces_cannot_substitute_for_contract_version",
    "breaking_semantic_change_cannot_reuse_the_same_contract_version_in_the_test_harness",
    "historical_message_version_bytes_are_preserved_without_reinterpretation",
    "candidate_adapter_output_contains_no_tenant_authorization_routing_or_message_identity_authority",
    "test_vector_encodings_are_noncanonical_evidence_fixtures_and_do_not_select_production_syntax",
}
EXPECTED_NON_AUTHORITY = {
    "d4b_mechanism_selection": "not_selected",
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
    req(manifest.get("axis") == "contract_version_representation", "source axis drift")
    req(manifest.get("source_decision") == "OPEN-EVT-004", "source decision drift")
    req(manifest.get("canonical_base") == "a871ac9c0ce7f33cf06fb70246bb902aff82900f", "source canonical base drift")
    req(manifest.get("mode") == "candidate_source_evidence_only", "source mode drift")
    req(manifest.get("test_vector_profile_only") is True, "test vectors must remain evidence-only")
    req(manifest.get("canonical_contract_version_syntax_selected") is False, "source evidence must not select canonical syntax")
    req(manifest.get("selection_state") == "not_selected", "source evidence must not select D4-B")
    req(manifest.get("selection_authority") == "not_granted", "source selection authority escalation")
    req(manifest.get("current_run_auto_credit") is False and manifest.get("ledger_credit") == [], "source evidence must not auto-credit ledger")
    req(manifest.get("candidate_results") == EXPECTED_RESULTS, "concrete candidate result inventory drift")
    req(manifest.get("equivalent_reviewed_representation") == "insufficient_evidence", "equivalent candidate class must remain unevaluated")
    proofs = manifest.get("required_proofs", [])
    req(isinstance(proofs, list) and set(proofs) == EXPECTED_PROOFS and len(proofs) == len(EXPECTED_PROOFS), "required proof inventory drift")
    assertions = manifest.get("source_assertions", [])
    req(isinstance(assertions, list) and set(assertions) == EXPECTED_ASSERTIONS and len(assertions) == len(EXPECTED_ASSERTIONS), "source assertion inventory drift")
    req(manifest.get("non_authority") == EXPECTED_NON_AUTHORITY, "non-authority boundary drift")

    axis = plan.get("axes", {}).get("contract_version_representation", {})
    req(axis.get("decision") == "OPEN-EVT-004", "accepted plan decision binding drift")
    candidates = set(axis.get("candidate_classes", []))
    req(set(EXPECTED_RESULTS).issubset(candidates), "source evaluated candidate not admitted by accepted plan")
    req("equivalent_reviewed_representation" in candidates, "accepted equivalent candidate class missing")
    req(set(axis.get("must_prove", [])) == EXPECTED_PROOFS, "accepted Axis C proof contract drift")
    req(plan.get("selection_state") == "not_selected" and plan.get("selection_authority") == "not_granted", "accepted plan selection drift")

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
            print(f"D4B_CONTRACT_VERSION_SOURCE_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4b_contract_version_source_manifest=PASS axis=OPEN-EVT-004 concrete_candidates=3 eligible=3 opaque_monotonic_issuance=required equivalent=insufficient_evidence selection=not_selected syntax_selected=false ledger_credit=0 d4=scoped authorities=not_granted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
