from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "implementation/d4-eventing-async/source-evidence/schema-contract/source-evidence-manifest.json"
STATE = ROOT / "implementation/d4-eventing-async/state-manifest.json"
EXPECTED_IDS = {
    "canonical_bounded_serialization_profile",
    "parser_ambiguity_and_duplicate_field_negative_vectors",
    "schema_catalog_semantic_manifest_compatibility_ci",
    "historical_reader_and_equivalence_profile_continuity",
    "contract_version_representation_and_breaking_change_vectors",
}


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8"))
    assert source["schema_version"] == 1
    assert source["package_id"] == "d4-b-schema-contract-source-v1"
    assert source["canonical_base_commit"] == "790f967446bf039ba4d5f618c9f30494c720ee7c"
    assert source["track"] == "D4-B"
    assert set(source["source_decisions"]) == {"OPEN-EVT-002", "OPEN-EVT-003", "OPEN-EVT-004"}
    assert set(source["evidence_ids"]) == EXPECTED_IDS and len(source["evidence_ids"]) == 5
    assert source["candidate"] is None and source["candidate_status"] == "not_selected"
    assert source["current_run_auto_credit"] is False and source["ledger_credit"] == []
    assert source["serialization_selection_state"] == "not_selected"
    assert source["schema_catalog_selection_state"] == "not_selected"
    assert source["contract_version_syntax_selection_state"] == "not_selected"
    assert source["reference_profile"]["authority"] == "test_reference_only_not_wire_selection"
    assert source["d4_transport_authority"] == "selected_not_granted"
    assert source["canonical_product_implementation_authority"] == "not_granted"
    assert source["wave4_implementation_authority"] == "not_granted"
    assert source["production_authority"] == "none"
    assert source["c3_numeric_topology_authority"] == "not_selected"

    tracks = {track["track_id"]: track for track in state["tracks"]}
    d4a, d4b, d4c, d4d = tracks["D4-A"], tracks["D4-B"], tracks["D4-C"], tracks["D4-D"]
    assert d4a["candidate"] == "kafka" and d4a["candidate_status"] == "selected_c2_candidate"
    assert d4a["state"] == "selected_candidate" and len(d4a["evidence_completed"]) == 7
    assert d4b["candidate"] is None and d4b["candidate_status"] == "not_selected"
    assert d4b["state"] == "candidate_selection_open"
    assert set(d4b["required_evidence"]) == EXPECTED_IDS
    assert d4b["evidence_completed"] == [] and set(d4b["evidence_remaining"]) == EXPECTED_IDS
    for sibling in (d4c, d4d):
        assert sibling["candidate"] is None and sibling["candidate_status"] == "not_selected"
        assert sibling["evidence_completed"] == []
    assert state["gate_state"] == "scoped"
    assert state["d4_transport_authority"] == "selected_not_granted"
    assert state["canonical_product_implementation_authority"] == "not_granted"
    assert state["wave4_implementation_authority"] == "not_granted"
    assert state["production_authority"] == "none"
    assert state["c3_numeric_topology_authority"] == "not_selected"

    print(
        "d4b_schema_contract_source_manifest=PASS evidence_ids=5 source_credit=0 candidate=not_selected "
        "d4a=kafka_selected d4b=open d4c_d=open authorities=not_granted reference_profile=test_only"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
