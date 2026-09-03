from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "implementation/d4-eventing-async/source-evidence/data-topology/source-evidence-manifest.json"
STATE = ROOT / "implementation/d4-eventing-async/state-manifest.json"
PLAN = ROOT / "implementation/d4-eventing-async/d4-a-evidence-plan.json"
EXPECTED_BASE = "63ced38f95b516b495db3f238e1a9e8689b184eb"
EXPECTED_IDS = {
    "regulated_payload_erasure_granularity",
    "physical_naming_routing_and_cell_topology_adapter_mapping",
}
EXPECTED_KINDS = {
    "regulated_payload_erasure_granularity": "contract_policy_and_negative_runtime_probe",
    "physical_naming_routing_and_cell_topology_adapter_mapping": "topology_adapter_conformance",
}
EXPECTED_PRIOR_CREDIT = {
    "broker_neutral_anti_corruption_stub_swap",
    "exactly_once_guardrail_consumer_inbox_enforcement",
}
EXPECTED_PROVENANCE_FIELDS = {
    "repository_sha",
    "workflow_run_id",
    "workflow_run_attempt",
    "job_id",
    "job_name",
    "probe",
    "source_manifest_sha256",
    "evidence_ids",
    "evidence_kinds",
    "current_run_auto_credit",
    "ledger_credit",
    "promotion_rule",
}


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8"))
    plan = json.loads(PLAN.read_text(encoding="utf-8"))

    assert source["schema_version"] == 1
    assert source["package_id"] == "d4-a-data-topology-source-v1"
    assert source["canonical_base_commit"] == EXPECTED_BASE
    assert source["track"] == "D4-A"
    assert set(source["evidence_ids"]) == EXPECTED_IDS and len(source["evidence_ids"]) == 2
    assert source["evidence_kinds"] == EXPECTED_KINDS
    assert source["scope"] == "source_evidence_harness_only"
    assert source["current_run_auto_credit"] is False
    assert source["ledger_credit"] == []
    assert set(source["prior_promoted_ledger_credit"]) == EXPECTED_PRIOR_CREDIT
    assert len(source["prior_promoted_ledger_credit"]) == 2
    for key in (
        "live_kafka_broker_claimed",
        "capacity_benchmark_claimed",
        "ordering_benchmark_claimed",
        "recovery_benchmark_claimed",
    ):
        assert source[key] is False
    assert source["kafka_selection_state"] == "not_selected"
    assert source["d4_transport_authority"] == "not_selected_not_granted"
    assert source["canonical_product_implementation_authority"] == "not_granted"
    assert source["wave4_implementation_authority"] == "not_granted"
    assert source["production_authority"] == "none"
    assert source["c3_numeric_topology_authority"] == "not_selected"
    assert source["promotion_rule"] == "source_run_review_then_separate_ledger_promotion"

    provenance = source["source_run_provenance"]
    assert provenance["mode"] == "runtime_resolved_artifact_required"
    assert provenance["artifact_schema"] == "d4a-source-run-provenance-v1"
    assert provenance["artifact_name_prefix"] == "d4-a-data-topology-source"
    assert set(provenance["required_fields"]) == EXPECTED_PROVENANCE_FIELDS
    assert len(provenance["required_fields"]) == len(EXPECTED_PROVENANCE_FIELDS)

    plan_items = {item["evidence_id"]: item for item in plan["required_evidence"]}
    for evidence_id, evidence_kind in EXPECTED_KINDS.items():
        assert plan_items[evidence_id]["evidence_kind"] == evidence_kind
    assert set(plan["credited_evidence"]) == EXPECTED_PRIOR_CREDIT
    assert plan["ledger_credit_state"] == "two_of_seven"
    assert plan["selection_state"] == "not_selected"
    assert plan["current_run_auto_credit"] is False

    d4a = next(track for track in state["tracks"] if track["track_id"] == "D4-A")
    assert set(d4a["evidence_completed"]) == EXPECTED_PRIOR_CREDIT
    assert EXPECTED_IDS.issubset(set(d4a["evidence_remaining"]))
    assert len(d4a["evidence_remaining"]) == 5
    assert state["gate_state"] == "scoped"
    assert state["d4_transport_authority"] == "not_selected_not_granted"
    assert state["canonical_product_implementation_authority"] == "not_granted"
    assert state["wave4_implementation_authority"] == "not_granted"
    assert state["production_authority"] == "none"
    assert state["c3_numeric_topology_authority"] == "not_selected"

    print(
        "d4a_data_topology_source_manifest=PASS evidence_ids=2 source_credit=0 prior_credit=2 "
        "kafka=not_selected authorities=not_granted provenance=runtime_artifact_required"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
