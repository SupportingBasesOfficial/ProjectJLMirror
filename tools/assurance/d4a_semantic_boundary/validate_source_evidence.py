from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "implementation/d4-eventing-async/source-evidence/semantic-boundary/source-evidence-manifest.json"
CONSUMER = ROOT / "implementation/d4-eventing-async/source-evidence/semantic-boundary/consumer-registry/protected-consumer.json"
STATE = ROOT / "implementation/d4-eventing-async/state-manifest.json"
PLAN = ROOT / "implementation/d4-eventing-async/d4-a-evidence-plan.json"
EXPECTED_IDS = {"broker_neutral_anti_corruption_stub_swap", "exactly_once_guardrail_consumer_inbox_enforcement"}
EXPECTED_KINDS = {
    "broker_neutral_anti_corruption_stub_swap": "candidate_plus_alternate_transport_conformance",
    "exactly_once_guardrail_consumer_inbox_enforcement": "contract_registration_negative_control",
}
EXPECTED_PROVENANCE_FIELDS = {
    "repository_sha", "workflow_run_id", "workflow_run_attempt", "job_id", "job_name", "probe",
    "source_manifest_sha256", "evidence_ids", "evidence_kinds", "current_run_auto_credit",
    "ledger_credit", "promotion_rule",
}
EXPECTED_EFFECT_BINDING = {
    "profile": "atomic_local",
    "implementation": "SQLiteAtomicInboxEffectGuard",
    "contract": "sqlite_atomic_inbox_effect_v1",
}


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    consumer = json.loads(CONSUMER.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8"))
    plan = json.loads(PLAN.read_text(encoding="utf-8"))

    assert set(source["evidence_ids"]) == EXPECTED_IDS and len(source["evidence_ids"]) == 2
    assert source["evidence_kinds"] == EXPECTED_KINDS
    assert source["scope"] == "source_evidence_harness_only"
    for key in ("live_kafka_broker_claimed", "capacity_benchmark_claimed", "ordering_benchmark_claimed", "recovery_benchmark_claimed", "current_run_auto_credit"):
        assert source[key] is False
    assert source["ledger_credit"] == []
    assert source["kafka_selection_state"] == "not_selected"
    assert source["d4_transport_authority"] == "not_selected_not_granted"
    assert source["canonical_product_implementation_authority"] == "not_granted"
    assert source["wave4_implementation_authority"] == "not_granted"
    assert source["production_authority"] == "none"
    assert source["c3_numeric_topology_authority"] == "not_selected"
    assert source["promotion_rule"] == "source_run_review_then_separate_ledger_promotion"

    provenance = source["source_run_provenance"]
    assert set(provenance) == {"mode", "artifact_schema", "artifact_name_prefix", "required_fields"}
    assert provenance["mode"] == "runtime_resolved_artifact_required"
    assert provenance["artifact_schema"] == "d4a-source-run-provenance-v1"
    assert provenance["artifact_name_prefix"] == "d4-a-semantic-boundary-source"
    assert set(provenance["required_fields"]) == EXPECTED_PROVENANCE_FIELDS
    assert len(provenance["required_fields"]) == len(EXPECTED_PROVENANCE_FIELDS)

    inbox = consumer["inbox"]
    assert inbox["durable"] is True
    assert inbox["dedup_identity"] == "consumer_contract+message_identity_scope+message_id"
    assert inbox["effect_protection"] == EXPECTED_EFFECT_BINDING

    plan_items = {item["evidence_id"]: item for item in plan["required_evidence"]}
    for evidence_id, kind in EXPECTED_KINDS.items():
        assert plan_items[evidence_id]["evidence_kind"] == kind

    promoted = set(plan["credited_evidence"])
    assert EXPECTED_IDS.issubset(promoted)
    assert plan["current_run_auto_credit"] is False
    d4a = next(track for track in state["tracks"] if track["track_id"] == "D4-A")
    assert set(d4a["evidence_completed"]) == promoted
    assert set(d4a["evidence_completed"]).isdisjoint(d4a["evidence_remaining"])
    assert state["gate_state"] == "scoped"
    assert state["d4_transport_authority"] == "not_selected_not_granted"
    assert state["canonical_product_implementation_authority"] == "not_granted"
    assert state["wave4_implementation_authority"] == "not_granted"
    assert state["production_authority"] == "none"
    assert state["c3_numeric_topology_authority"] == "not_selected"

    print(
        "d4a_semantic_source_manifest=PASS evidence_ids=2 source_ledger_credit=0 "
        f"promoted_ledger_credit={len(promoted)} live_kafka_claim=false "
        "provenance=runtime_artifact_required effect_guard=executable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
