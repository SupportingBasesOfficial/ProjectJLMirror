from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "implementation/d4-eventing-async/source-evidence/data-topology/source-evidence-manifest.json"
PLAN = ROOT / "implementation/d4-eventing-async/d4-a-evidence-plan.json"
STATE = ROOT / "implementation/d4-eventing-async/state-manifest.json"

EXPECTED_IDS = {
    "regulated_payload_erasure_granularity",
    "physical_naming_routing_and_cell_topology_adapter_mapping",
}
EXPECTED_KINDS = {
    "regulated_payload_erasure_granularity": "contract_policy_and_negative_runtime_probe",
    "physical_naming_routing_and_cell_topology_adapter_mapping": "topology_adapter_conformance",
}
EXPECTED_EXCEPTION_CONTROLS = [
    "per_tenant_topic_or_partition_assignment",
    "max_segment_retention_ceiling_satisfies_governed_erasure_sla",
    "explicit_erasure_governance_authority_signoff",
]


def main() -> None:
    source = json.loads(MANIFEST.read_text())
    plan = json.loads(PLAN.read_text())
    state = json.loads(STATE.read_text())
    d4a = next(t for t in state["tracks"] if t["track_id"] == "D4-A")

    assert source["canonical_base_commit"] == "63ced38f95b516b495db3f238e1a9e8689b184eb"
    assert set(source["evidence_ids"]) == EXPECTED_IDS
    assert source["evidence_kinds"] == EXPECTED_KINDS
    assert source["scope"] == "source_evidence_harness_only"
    assert source["current_run_auto_credit"] is False
    assert source["ledger_credit"] == []
    assert source["kafka_selection_state"] == "not_selected"
    assert source["live_kafka_broker_claimed"] is False
    assert source["capacity_benchmark_claimed"] is False
    assert source["ordering_benchmark_claimed"] is False
    assert source["recovery_benchmark_claimed"] is False

    payload = source["regulated_payload_policy"]
    assert payload["default_mode"] == "opaque_governed_reference"
    assert payload["raw_sensitive_or_regulated_value_bytes"] == "deny_by_default"
    assert payload["raw_payload_exception_requires_all"] == EXPECTED_EXCEPTION_CONTROLS

    topology = source["topology_adapter_policy"]
    assert topology["tenant_authorization_before_mapping"] is True
    assert topology["physical_names_are_contract_identity"] is False
    assert topology["replacement_mapping_requires_semantic_rewrite"] is False

    assert source["source_run_provenance"]["mode"] == "runtime_resolved_artifact_required"
    assert source["promotion_rule"] == "source_run_review_then_separate_ledger_promotion"

    # Source evidence must remain uncredited until a later governed promotion.
    assert EXPECTED_IDS.isdisjoint(set(plan["credited_evidence"]))
    assert EXPECTED_IDS.issubset(set(d4a["evidence_remaining"]))
    assert set(d4a["evidence_completed"]) == set(plan["credited_evidence"])

    assert state["gate_state"] == "scoped"
    assert state["d4_transport_authority"] == "not_selected_not_granted"
    assert state["canonical_product_implementation_authority"] == "not_granted"
    assert state["wave4_implementation_authority"] == "not_granted"
    assert state["production_authority"] == "none"
    assert state["c3_numeric_topology_authority"] == "not_selected"

    print("d4a_data_topology_source_manifest=PASS evidence=2 ledger_credit=0 kafka=not_selected authorities=not_granted")


if __name__ == "__main__":
    main()
