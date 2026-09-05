#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

SELECTION = Path("implementation/d4-eventing-async/d4-b-selection-record.json")
PLAN = Path("implementation/d4-eventing-async/d4-b-evidence-plan.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")
AXIS_A = Path("implementation/d4-eventing-async/source-evidence/d4-b-wire-schema-candidate-source.json")
AXIS_B = Path("implementation/d4-eventing-async/source-evidence/d4-b-catalog-tooling-candidate-source.json")
AXIS_C = Path("implementation/d4-eventing-async/source-evidence/d4-b-contract-version-candidate-source.json")

EXPECTED_BASE = "1104997c5bb97aae59373077a9e2f8d7570968b4"
EXPECTED_INTERNAL = "protobuf_profile"
EXPECTED_WEBHOOK = "bounded_json_plus_json_schema_profile"
EXPECTED_CATALOG = "hybrid_reviewed_git_plus_registry_catalog"
EXPECTED_VERSION = "positive_integer_family_revision"
EXPECTED_SOURCE_DECISIONS = {"OPEN-EVT-002", "OPEN-EVT-003", "OPEN-EVT-004"}


def load(root: Path, path: Path) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def validate(root: Path) -> list[str]:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    selection = load(root, SELECTION)
    plan = load(root, PLAN)
    state = load(root, STATE)
    axis_a = load(root, AXIS_A)
    axis_b = load(root, AXIS_B)
    axis_c = load(root, AXIS_C)

    require(selection.get("schema_version") == 1, "selection schema_version must be 1")
    require(selection.get("selection_id") == "d4-b-profile-selection-v1", "selection_id drift")
    require(selection.get("gate_id") == "D4" and selection.get("track_id") == "D4-B", "selection track identity drift")
    require(selection.get("selection_base_main_commit") == EXPECTED_BASE, "selection base drift")
    require(set(selection.get("source_decisions", [])) == EXPECTED_SOURCE_DECISIONS, "selection source decisions drift")
    require(selection.get("selection_state") == "selected", "D4-B selection must remain selected")
    require(selection.get("selection_scope") == "bounded_c2_contract_profile_selection_only", "D4-B selection scope drift")
    require(selection.get("track_state") == "selected_candidate", "D4-B selected track state drift")

    completion = selection.get("evidence_completion", {})
    require(completion.get("required_evidence_count") == 5, "selection required evidence count drift")
    require(completion.get("credited_evidence_count") == 5, "selection credited evidence count drift")
    require(completion.get("axis_a_accepted_main_commit") == "df62898b6d9fc36f2a10c0c3713679d2cbe05da8", "Axis A accepted commit drift")
    require(completion.get("axis_b_accepted_main_commit") == EXPECTED_BASE, "Axis B accepted commit drift")
    require(completion.get("axis_c_accepted_main_commit") == "9cfe67915b6081af015670d7f1edb7ecf11ffdf2", "Axis C accepted commit drift")

    serialization = selection.get("serialization", {})
    require(serialization.get("selection_state") == "selected", "serialization selection state drift")
    require(serialization.get("surface_policy") == "explicit_surface_bound_profiles", "serialization surface policy drift")
    require(serialization.get("internal_broker") == EXPECTED_INTERNAL, "internal broker serialization drift")
    require(serialization.get("outbound_webhook") == EXPECTED_WEBHOOK, "outbound webhook serialization drift")
    require(serialization.get("realtime_protocol") == "unchanged_phase10_canonical_json_baseline", "realtime protocol must remain independent")
    require(serialization.get("unselected_eligible_alternatives") == ["avro_profile"], "wire alternative inventory drift")

    catalog = selection.get("schema_catalog", {})
    require(catalog.get("selection_state") == "selected", "catalog selection state drift")
    require(catalog.get("mechanism") == EXPECTED_CATALOG, "catalog mechanism drift")
    require(catalog.get("canonical_authority") == "reviewed_git_contract_history", "reviewed Git authority drift")
    require(catalog.get("registry_product") is None, "registry vendor/product must remain unselected")
    require(set(catalog.get("unselected_eligible_alternatives", [])) == {"reviewed_git_catalog", "registry_backed_catalog"}, "catalog alternative inventory drift")

    version = selection.get("contract_version", {})
    require(version.get("selection_state") == "selected", "contract-version selection state drift")
    require(version.get("representation") == EXPECTED_VERSION, "contract-version representation drift")
    require(version.get("logical_domain") == "positive_integer", "contract-version logical domain drift")
    require(version.get("zero_allowed") is False, "contract-version zero must remain forbidden")
    require(version.get("ordering_authority") == "none_equality_only", "numeric version must not gain ordering authority")
    require(version.get("deployment_api_provider_realtime_registry_version_authority") == "none", "contract-version namespace authority leak")
    require(set(version.get("unselected_eligible_alternatives", [])) == {"semantic_version_like_contract_revision", "opaque_monotonic_contract_token"}, "version alternative inventory drift")

    for name, source in (("Axis A", axis_a), ("Axis B", axis_b), ("Axis C", axis_c)):
        require(source.get("selection_state") == "not_selected", f"{name} source history must remain not_selected")
        require(source.get("selection_authority") == "not_granted", f"{name} source history must retain no selection authority")
        require(source.get("current_run_auto_credit") is False, f"{name} source auto-credit history drift")
        require(source.get("ledger_credit") == [], f"{name} source ledger-credit history drift")

    axis_a_results = axis_a.get("candidate_results", {})
    require(axis_a_results.get(EXPECTED_INTERNAL) == "eligible_for_evidence_execution", "selected internal profile lacks eligible Axis A evidence")
    require(axis_a_results.get(EXPECTED_WEBHOOK) == "eligible_for_evidence_execution", "selected webhook profile lacks eligible Axis A evidence")
    require(axis_a_results.get("avro_profile") == "eligible_for_evidence_execution", "Axis A alternative evidence drift")

    axis_b_results = axis_b.get("candidate_results", {})
    require(axis_b_results.get(EXPECTED_CATALOG) == "eligible_for_evidence_execution", "selected catalog mechanism lacks eligible Axis B evidence")

    axis_c_results = axis_c.get("candidate_results", {})
    require(axis_c_results.get(EXPECTED_VERSION) == "eligible_for_evidence_execution", "selected contract-version representation lacks eligible Axis C evidence")

    expected_candidate = {
        "serialization": {
            "surface_policy": "explicit_surface_bound_profiles",
            "internal_broker": EXPECTED_INTERNAL,
            "outbound_webhook": EXPECTED_WEBHOOK,
        },
        "schema_catalog": EXPECTED_CATALOG,
        "contract_version": EXPECTED_VERSION,
    }
    require(plan.get("candidate") == expected_candidate, "D4-B evidence-plan selected candidate drift")
    require(plan.get("candidate_status") == "selected_c2_profile", "D4-B evidence-plan candidate status drift")
    require(plan.get("selection_state") == "selected", "D4-B evidence-plan selection state drift")
    require(plan.get("serialization_selection_state") == "selected_surface_bound", "D4-B serialization selection marker drift")
    require(plan.get("schema_catalog_selection_state") == "selected", "D4-B catalog selection marker drift")
    require(plan.get("contract_version_syntax_selection_state") == "selected", "D4-B version selection marker drift")
    require(plan.get("current_run_auto_credit") is False, "D4-B selection cannot invent source-run auto-credit")
    require(len(plan.get("credited_evidence", [])) == 5 and plan.get("remaining_evidence") == [], "D4-B selection must preserve 5/5 evidence accounting")
    require(plan.get("separate_selection_required") is False, "D4-B separate selection should be discharged by this record")
    require(plan.get("separate_d4_acceptance_required") is True, "full D4 acceptance must remain separate")

    tracks = {track.get("track_id"): track for track in state.get("tracks", []) if isinstance(track, dict)}
    d4b = tracks.get("D4-B", {})
    require(d4b.get("candidate") == expected_candidate, "global D4 state selected D4-B profile drift")
    require(d4b.get("candidate_status") == "selected_c2_profile", "global D4 state D4-B candidate status drift")
    require(d4b.get("state") == "selected_candidate", "global D4 state D4-B track state drift")
    require(len(d4b.get("evidence_completed", [])) == 5 and d4b.get("evidence_remaining") == [], "global D4 state D4-B evidence accounting drift")

    require(state.get("gate_state") == "scoped", "D4 must remain scoped")
    require(state.get("d4_transport_authority") == "selected_not_granted", "D4 transport authority must remain ungranted")
    require(state.get("canonical_product_implementation_authority") == "not_granted", "Product implementation authority must remain ungranted")
    require(state.get("wave4_implementation_authority") == "not_granted", "Wave4 implementation authority must remain ungranted")
    require(state.get("production_authority") == "none", "production authority must remain none")
    require(state.get("c3_numeric_topology_authority") == "not_selected", "C3 numeric/topology authority must remain not_selected")
    require(tracks.get("D4-C", {}).get("candidate") is None and tracks.get("D4-C", {}).get("evidence_completed") == [], "D4-C must remain open/uncredited")
    require(tracks.get("D4-D", {}).get("candidate") is None and tracks.get("D4-D", {}).get("evidence_completed") == [], "D4-D must remain open/uncredited")

    require(selection.get("d4_gate_state") == "scoped", "selection record must not accept D4")
    require(selection.get("d4_transport_authority") == "selected_not_granted", "selection record must not grant transport authority")
    require(selection.get("canonical_product_implementation_authority") == "not_granted", "selection record must not grant Product authority")
    require(selection.get("wave4_implementation_authority") == "not_granted", "selection record must not grant Wave4 authority")
    require(selection.get("production_authority") == "none", "selection record must not grant production authority")
    require(selection.get("c3_numeric_topology_authority") == "not_selected", "selection record must not select C3")
    require(selection.get("d4_cd_completion_required") is True, "selection record must keep D4-C/D completion required")
    require(selection.get("separate_d4_acceptance_required") is True, "selection record must require separate D4 acceptance")

    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4B_SELECTION_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4b_selection=PASS internal=protobuf webhook=bounded_json_json_schema catalog=hybrid_reviewed_git_registry contract_version=positive_integer equality_only=true evidence=5/5 source_history=immutable_not_selected registry_product=unselected d4=scoped authorities=not_granted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
