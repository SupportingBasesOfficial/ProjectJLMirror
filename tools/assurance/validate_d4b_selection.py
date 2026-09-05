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
EXPECTED_REGISTRY_ROLE = "authenticated_authorized_distribution_index_compatibility_and_physical_mapping"
EXPECTED_VERSION = "positive_integer_family_revision"
EXPECTED_SOURCE_DECISIONS = {"OPEN-EVT-002", "OPEN-EVT-003", "OPEN-EVT-004"}
EXPECTED_SELECTION_KEYS = {
    "schema_version", "selection_id", "gate_id", "track_id", "selection_base_main_commit",
    "source_decisions", "evidence_completion", "selection_state", "selection_scope", "track_state",
    "serialization", "schema_catalog", "contract_version", "d4_gate_state", "d4_transport_authority",
    "canonical_product_implementation_authority", "wave4_implementation_authority", "production_authority",
    "c3_numeric_topology_authority", "d4_cd_completion_required", "separate_d4_acceptance_required",
    "historical_evidence_rule", "non_authority_rule",
}
EXPECTED_COMPLETION_KEYS = {
    "required_evidence_count", "credited_evidence_count", "evidence_plan_path",
    "axis_a_source_path", "axis_b_source_path", "axis_c_source_path",
    "axis_a_accepted_main_commit", "axis_b_accepted_main_commit", "axis_c_accepted_main_commit",
}
EXPECTED_SERIALIZATION_KEYS = {
    "selection_state", "surface_policy", "internal_broker", "outbound_webhook", "realtime_protocol",
    "unselected_eligible_alternatives", "divergence_rule",
}
EXPECTED_CATALOG_KEYS = {
    "selection_state", "mechanism", "canonical_authority", "registry_role", "registry_product",
    "unselected_eligible_alternatives", "replacement_rule",
}
EXPECTED_VERSION_KEYS = {
    "selection_state", "representation", "logical_domain", "zero_allowed", "ordering_authority",
    "deployment_api_provider_realtime_registry_version_authority", "unselected_eligible_alternatives",
    "breaking_change_rule", "surface_encoding_rule",
}
EXPECTED_PLAN_KEYS = {
    "schema_version", "gate_id", "track_id", "name", "source_decisions", "candidate", "candidate_status",
    "source_evidence_state", "ledger_credit_state", "required_evidence", "credited_evidence", "remaining_evidence",
    "current_run_auto_credit", "selection_state", "serialization_selection_state", "schema_catalog_selection_state",
    "contract_version_syntax_selection_state", "selection_record", "separate_selection_required",
    "separate_d4_acceptance_required", "d4_transport_authority", "canonical_product_implementation_authority",
    "wave4_implementation_authority", "production_authority", "c3_numeric_topology_authority",
}
EXPECTED_STATE_KEYS = {
    "schema_version", "gate_id", "gate_name", "canonical_base", "predecessor", "gate_state",
    "canonical_product_implementation_authority", "wave4_implementation_authority", "production_authority",
    "d4_transport_authority", "c3_numeric_topology_authority", "tracks", "explicit_c3_exclusions",
    "explicit_product_or_later_gate_exclusions", "acceptance_rule", "merge_rule",
}
EXPECTED_PREDECESSOR_KEYS = {"gate_id", "state", "canonical_commit"}
EXPECTED_TRACK_KEYS = {
    "track_id", "name", "source_decisions", "candidate", "candidate_status", "state",
    "required_evidence", "evidence_completed", "evidence_remaining",
}
EXPECTED_TRACK_IDS = {"D4-A", "D4-B", "D4-C", "D4-D"}
EXPECTED_D4A_DECISIONS = {"OPEN-EVT-001", "OPEN-EVT-005", "OPEN-REL-012.A"}
EXPECTED_D4C_DECISIONS = {"OPEN-EVT-008", "OPEN-EVT-009", "OPEN-EVT-010", "OPEN-EVT-011", "OPEN-EVT-012", "OPEN-EVT-013", "OPEN-EVT-014", "OPEN-EVT-015", "OPEN-EVT-025"}
EXPECTED_D4D_DECISIONS = {"OPEN-EVT-016", "OPEN-EVT-017", "OPEN-EVT-018"}
EXPECTED_DIVERGENCE_RULE = (
    "Internal broker and outbound webhook representations may differ only at the selected adapter/profile boundary; "
    "canonical logical contract meaning, identity, tenant scope, version semantics and equivalence obligations remain transport-independent."
)
EXPECTED_REPLACEMENT_RULE = (
    "A registry product may be introduced or replaced without changing logical contract identity only after its mapping, outage, "
    "authorization, provenance and historical-reader behavior conforms to the selected hybrid mechanism profile."
)
EXPECTED_BREAKING_CHANGE_RULE = (
    "A breaking semantic contract family change requires a newly reviewed positive integer family revision or an explicitly accepted migration; "
    "an existing revision cannot be rebound to different semantic meaning."
)
EXPECTED_SURFACE_ENCODING_RULE = (
    "Each selected wire profile encodes the same positive-integer logical revision using its native bounded integer representation; "
    "string spellings, lexical order and registry IDs are not contract-version authority."
)
EXPECTED_HISTORICAL_RULE = (
    "Axis A, Axis B and Axis C source manifests remain immutable historical evidence with selection_state=not_selected, "
    "current_run_auto_credit=false and ledger_credit=[]; this selection record is the current selection authority and must not rewrite earlier evidence truth."
)
EXPECTED_NON_AUTHORITY_RULE = (
    "Selecting D4-B contract profiles does not authorize Product or Wave4 implementation, create an outbound-webhook Product surface, "
    "choose a registry vendor, grant production deployment, select C3 numerics/topology, complete D4-C/D, or constitute full D4 acceptance."
)


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
    return isinstance(value, list) and len(value) == len(expected) and set(value) == expected


def validate(root: Path) -> list[str]:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    try:
        selection = load(root, SELECTION)
        plan = load(root, PLAN)
        state = load(root, STATE)
        axis_a = load(root, AXIS_A)
        axis_b = load(root, AXIS_B)
        axis_c = load(root, AXIS_C)
    except (json.JSONDecodeError, DuplicateMemberError, ValueError) as exc:
        return [f"strict JSON parse failure: {exc}"]

    require(set(selection) == EXPECTED_SELECTION_KEYS, "selection exact key schema drift")
    require(selection.get("schema_version") == 1, "selection schema_version must be 1")
    require(selection.get("selection_id") == "d4-b-profile-selection-v1", "selection_id drift")
    require(selection.get("gate_id") == "D4" and selection.get("track_id") == "D4-B", "selection track identity drift")
    require(selection.get("selection_base_main_commit") == EXPECTED_BASE, "selection base drift")
    require(exact_list(selection.get("source_decisions"), EXPECTED_SOURCE_DECISIONS), "selection source decisions drift")
    require(selection.get("selection_state") == "selected", "D4-B selection must remain selected")
    require(selection.get("selection_scope") == "bounded_c2_contract_profile_selection_only", "D4-B selection scope drift")
    require(selection.get("track_state") == "selected_candidate", "D4-B selected track state drift")

    completion = selection.get("evidence_completion", {})
    require(isinstance(completion, dict) and set(completion) == EXPECTED_COMPLETION_KEYS, "selection evidence-completion exact key schema drift")
    require(completion.get("required_evidence_count") == 5, "selection required evidence count drift")
    require(completion.get("credited_evidence_count") == 5, "selection credited evidence count drift")
    require(completion.get("evidence_plan_path") == PLAN.as_posix(), "selection evidence-plan provenance path drift")
    require(completion.get("axis_a_source_path") == AXIS_A.as_posix(), "Axis A source provenance path drift")
    require(completion.get("axis_b_source_path") == AXIS_B.as_posix(), "Axis B source provenance path drift")
    require(completion.get("axis_c_source_path") == AXIS_C.as_posix(), "Axis C source provenance path drift")
    require(completion.get("axis_a_accepted_main_commit") == "df62898b6d9fc36f2a10c0c3713679d2cbe05da8", "Axis A accepted commit drift")
    require(completion.get("axis_b_accepted_main_commit") == EXPECTED_BASE, "Axis B accepted commit drift")
    require(completion.get("axis_c_accepted_main_commit") == "9cfe67915b6081af015670d7f1edb7ecf11ffdf2", "Axis C accepted commit drift")

    serialization = selection.get("serialization", {})
    require(isinstance(serialization, dict) and set(serialization) == EXPECTED_SERIALIZATION_KEYS, "serialization exact key schema drift")
    require(serialization.get("selection_state") == "selected", "serialization selection state drift")
    require(serialization.get("surface_policy") == "explicit_surface_bound_profiles", "serialization surface policy drift")
    require(serialization.get("internal_broker") == EXPECTED_INTERNAL, "internal broker serialization drift")
    require(serialization.get("outbound_webhook") == EXPECTED_WEBHOOK, "outbound webhook serialization drift")
    require(serialization.get("realtime_protocol") == "unchanged_phase10_canonical_json_baseline", "realtime protocol must remain independent")
    require(serialization.get("unselected_eligible_alternatives") == ["avro_profile"], "wire alternative inventory drift")
    require(serialization.get("divergence_rule") == EXPECTED_DIVERGENCE_RULE, "serialization divergence rule drift")

    catalog = selection.get("schema_catalog", {})
    require(isinstance(catalog, dict) and set(catalog) == EXPECTED_CATALOG_KEYS, "catalog exact key schema drift")
    require(catalog.get("selection_state") == "selected", "catalog selection state drift")
    require(catalog.get("mechanism") == EXPECTED_CATALOG, "catalog mechanism drift")
    require(catalog.get("canonical_authority") == "reviewed_git_contract_history", "reviewed Git authority drift")
    require(catalog.get("registry_role") == EXPECTED_REGISTRY_ROLE, "registry role drift")
    require(catalog.get("registry_product") is None, "registry vendor/product must remain unselected")
    require(exact_list(catalog.get("unselected_eligible_alternatives"), {"reviewed_git_catalog", "registry_backed_catalog"}), "catalog alternative inventory must be an exact list")
    require(catalog.get("replacement_rule") == EXPECTED_REPLACEMENT_RULE, "catalog replacement rule drift")

    version = selection.get("contract_version", {})
    require(isinstance(version, dict) and set(version) == EXPECTED_VERSION_KEYS, "contract-version exact key schema drift")
    require(version.get("selection_state") == "selected", "contract-version selection state drift")
    require(version.get("representation") == EXPECTED_VERSION, "contract-version representation drift")
    require(version.get("logical_domain") == "positive_integer", "contract-version logical domain drift")
    require(version.get("zero_allowed") is False, "contract-version zero must remain forbidden")
    require(version.get("ordering_authority") == "none_equality_only", "numeric version must not gain ordering authority")
    require(version.get("deployment_api_provider_realtime_registry_version_authority") == "none", "contract-version namespace authority leak")
    require(exact_list(version.get("unselected_eligible_alternatives"), {"semantic_version_like_contract_revision", "opaque_monotonic_contract_token"}), "contract-version alternative inventory must be an exact list")
    require(version.get("breaking_change_rule") == EXPECTED_BREAKING_CHANGE_RULE, "contract-version breaking-change rule drift")
    require(version.get("surface_encoding_rule") == EXPECTED_SURFACE_ENCODING_RULE, "contract-version surface-encoding rule drift")

    require(selection.get("historical_evidence_rule") == EXPECTED_HISTORICAL_RULE, "selection historical-evidence rule drift")
    require(selection.get("non_authority_rule") == EXPECTED_NON_AUTHORITY_RULE, "selection non-authority rule drift")

    require(set(plan) == EXPECTED_PLAN_KEYS, "D4-B evidence-plan exact key schema drift")
    require(exact_list(plan.get("source_decisions"), EXPECTED_SOURCE_DECISIONS), "D4-B evidence-plan source decision drift")

    require(set(state) == EXPECTED_STATE_KEYS, "D4 state exact key schema drift")
    predecessor = state.get("predecessor", {})
    require(isinstance(predecessor, dict) and set(predecessor) == EXPECTED_PREDECESSOR_KEYS, "D4 predecessor exact key schema drift")
    state_tracks = state.get("tracks")
    require(isinstance(state_tracks, list) and len(state_tracks) == 4 and all(isinstance(track, dict) for track in state_tracks), "D4 tracks must be exactly four objects")
    tracks: dict[str, dict] = {}
    if isinstance(state_tracks, list) and len(state_tracks) == 4 and all(isinstance(track, dict) for track in state_tracks):
        ids = [track.get("track_id") for track in state_tracks]
        require(len(ids) == len(set(ids)) and set(ids) == EXPECTED_TRACK_IDS, "D4 track identity drift")
        for track in state_tracks:
            track_id = track.get("track_id")
            require(set(track) == EXPECTED_TRACK_KEYS, f"{track_id} exact track key schema drift")
            decisions = track.get("source_decisions")
            expected_decisions = {
                "D4-A": EXPECTED_D4A_DECISIONS,
                "D4-B": EXPECTED_SOURCE_DECISIONS,
                "D4-C": EXPECTED_D4C_DECISIONS,
                "D4-D": EXPECTED_D4D_DECISIONS,
            }.get(track_id, set())
            require(exact_list(decisions, expected_decisions), f"{track_id} source decision inventory drift")
            if isinstance(track_id, str):
                tracks[track_id] = track

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
    require(plan.get("selection_record") == SELECTION.as_posix(), "D4-B evidence-plan selection-record binding drift")
    require(plan.get("current_run_auto_credit") is False, "D4-B selection cannot invent source-run auto-credit")
    require(len(plan.get("credited_evidence", [])) == 5 and plan.get("remaining_evidence") == [], "D4-B selection must preserve 5/5 evidence accounting")
    require(plan.get("separate_selection_required") is False, "D4-B separate selection should be discharged by this record")
    require(plan.get("separate_d4_acceptance_required") is True, "full D4 acceptance must remain separate")

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
    print("d4b_selection=PASS exact_authoritative_schemas=true provenance_paths=bound alternatives=array_typed internal=protobuf webhook=bounded_json_json_schema catalog=hybrid_reviewed_git_registry registry_role=downstream_non_authority contract_version=positive_integer equality_only=true evidence=5/5 source_history=immutable_not_selected registry_product=unselected d4=scoped authorities=not_granted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
