#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PLAN = Path("implementation/d4-eventing-async/d4-b-evidence-plan.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")
PROMOTION = Path("implementation/d4-eventing-async/ledger-promotions/d4-b-schema-contract-promotion-v1.json")
SOURCE = Path("implementation/d4-eventing-async/source-evidence/schema-contract/source-evidence-manifest.json")
EXPECTED_IDS = {
    "canonical_bounded_serialization_profile",
    "parser_ambiguity_and_duplicate_field_negative_vectors",
    "schema_catalog_semantic_manifest_compatibility_ci",
    "historical_reader_and_equivalence_profile_continuity",
    "contract_version_representation_and_breaking_change_vectors",
}
EXPECTED_D4A_IDS = {
    "capacity_envelope_baseline_growth_stress",
    "broker_neutral_anti_corruption_stub_swap",
    "regulated_payload_erasure_granularity",
    "exactly_once_guardrail_consumer_inbox_enforcement",
    "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency",
    "physical_naming_routing_and_cell_topology_adapter_mapping",
    "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark",
}
EXPECTED_TRACK_IDS = {"D4-A", "D4-B", "D4-C", "D4-D"}
EXPECTED_PROMOTION_KEYS = {
    "schema_version",
    "promotion_id",
    "gate_id",
    "track_id",
    "promotion_base",
    "source_pr",
    "source_reviewed_head",
    "source_review",
    "source_workflow",
    "source_manifest",
    "credited_evidence",
    "credit_count",
    "selection_state",
    "serialization_selection_state",
    "schema_catalog_selection_state",
    "contract_version_syntax_selection_state",
    "d4_gate_state",
    "d4_transport_authority",
    "canonical_product_implementation_authority",
    "wave4_implementation_authority",
    "production_authority",
    "c3_numeric_topology_authority",
    "separate_selection_required",
    "separate_d4_acceptance_required",
}
EXPECTED_SOURCE_REVIEW_KEYS = {"review_id", "review_mode", "material_threads_unresolved"}
EXPECTED_SOURCE_WORKFLOW_KEYS = {
    "workflow_id",
    "workflow_path",
    "workflow_event",
    "source_head_branch",
    "run_id",
    "run_attempt",
    "job_id",
    "job_name",
    "artifact_id",
    "artifact_name",
    "artifact_digest",
}
EXPECTED_SOURCE_MANIFEST_KEYS = {"path", "sha256"}
EXPECTED_SOURCE_HEAD = "0a5509442d4b55f6d4de989af9bb62a088198ab4"
EXPECTED_MANIFEST_SHA256 = "2b442fd7b8733105ba004cf7ae982dd3a64a7731d11187b1e0409270f1da118a"
EXPECTED_REVIEW_MODE = "independent_exact_head_adversarial_clean_with_fresh_codex_no_findings_reaction"
EXPECTED_SOURCE_WORKFLOW_ID = 349837736
EXPECTED_SOURCE_WORKFLOW_PATH = ".github/workflows/d4-b-schema-contract-source-evidence.yml"
EXPECTED_SOURCE_HEAD_BRANCH = "evidence/d4-b-schema-contract-source"


class DuplicateMemberError(ValueError):
    pass


def reject_duplicate_members(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateMemberError(f"duplicate JSON member {key!r}")
        result[key] = value
    return result


def parse_strict_json(raw: bytes | str) -> object:
    return json.loads(raw, object_pairs_hook=reject_duplicate_members)


def load(root: Path, path: Path) -> dict:
    value = parse_strict_json((root / path).read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"{path.as_posix()} top-level JSON value must be an object")
    return value


def validate(root: Path) -> list[str]:
    errors: list[str] = []

    def req(cond: bool, msg: str) -> None:
        if not cond:
            errors.append(msg)

    try:
        plan = load(root, PLAN)
        state = load(root, STATE)
        promotion = load(root, PROMOTION)
        source_path = root / SOURCE
        source_bytes = source_path.read_bytes()
        source_value = parse_strict_json(source_bytes)
        if not isinstance(source_value, dict):
            raise ValueError(f"{SOURCE.as_posix()} top-level JSON value must be an object")
        source = source_value
    except (json.JSONDecodeError, DuplicateMemberError, ValueError) as exc:
        return [f"strict JSON parse failure: {exc}"]

    state_tracks = state.get("tracks")
    if not isinstance(state_tracks, list) or not all(isinstance(track, dict) for track in state_tracks):
        return ["D4 tracks must be exactly four objects with unique identities"]
    track_ids = [track.get("track_id") for track in state_tracks]
    if len(state_tracks) != 4 or len(track_ids) != len(set(track_ids)) or set(track_ids) != EXPECTED_TRACK_IDS:
        return ["D4 track identities must be exactly D4-A/D4-B/D4-C/D4-D with no duplicates"]
    tracks = {track["track_id"]: track for track in state_tracks}
    d4b = tracks["D4-B"]

    req(plan.get("schema_version") == 1 and plan.get("gate_id") == "D4" and plan.get("track_id") == "D4-B", "D4-B plan identity drift")
    req(set(plan.get("required_evidence", [])) == EXPECTED_IDS and len(plan.get("required_evidence", [])) == 5, "D4-B required evidence drift")
    req(set(plan.get("credited_evidence", [])) == EXPECTED_IDS and len(plan.get("credited_evidence", [])) == 5, "D4-B credited evidence drift")
    req(plan.get("remaining_evidence") == [], "D4-B remaining evidence must be empty after reviewed promotion")
    req(plan.get("source_evidence_state") == "reviewed_source_run_available", "D4-B source evidence state drift")
    req(plan.get("ledger_credit_state") == "five_of_five", "D4-B ledger credit state drift")
    req(plan.get("candidate") is None and plan.get("candidate_status") == "not_selected", "D4-B plan must remain candidate-neutral")
    req(plan.get("selection_state") == "not_selected", "D4-B selection must remain not_selected")
    req(plan.get("serialization_selection_state") == "not_selected", "serialization must remain not_selected")
    req(plan.get("schema_catalog_selection_state") == "not_selected", "schema catalog must remain not_selected")
    req(plan.get("contract_version_syntax_selection_state") == "not_selected", "contract version syntax must remain not_selected")
    req(plan.get("current_run_auto_credit") is False, "source runs must not auto-credit")
    req(plan.get("separate_selection_required") is True and plan.get("separate_d4_acceptance_required") is True, "selection and D4 acceptance must remain separate")
    req(plan.get("d4_transport_authority") == "selected_not_granted", "D4-B plan transport authority drift")
    req(plan.get("canonical_product_implementation_authority") == "not_granted", "D4-B plan Product authority drift")
    req(plan.get("wave4_implementation_authority") == "not_granted", "D4-B plan Wave 4 authority drift")
    req(plan.get("production_authority") == "none", "D4-B plan production authority drift")
    req(plan.get("c3_numeric_topology_authority") == "not_selected", "D4-B plan C3 authority drift")

    req(set(promotion) == EXPECTED_PROMOTION_KEYS, "promotion exact key schema drift")
    req(promotion.get("schema_version") == 1 and promotion.get("gate_id") == "D4" and promotion.get("track_id") == "D4-B", "promotion identity envelope drift")
    req(promotion.get("promotion_id") == "d4-b-schema-contract-promotion-v1", "promotion identity drift")
    req(promotion.get("promotion_base") == "4c80d4bf79d9b16d499cfd2f5e723b6dc8a93609", "promotion base drift")
    req(promotion.get("source_pr") == 64, "source PR drift")
    req(promotion.get("source_reviewed_head") == EXPECTED_SOURCE_HEAD, "source reviewed HEAD drift")
    review = promotion.get("source_review", {})
    req(isinstance(review, dict) and set(review) == EXPECTED_SOURCE_REVIEW_KEYS, "source review exact key schema drift")
    req(review.get("review_id") == 5108877160, "source review provenance drift")
    req(review.get("review_mode") == EXPECTED_REVIEW_MODE, "source review mode drift")
    req(review.get("material_threads_unresolved") == 0, "source review must have zero unresolved material threads")
    workflow = promotion.get("source_workflow", {})
    req(isinstance(workflow, dict) and set(workflow) == EXPECTED_SOURCE_WORKFLOW_KEYS, "source workflow exact key schema drift")
    req(workflow.get("workflow_id") == EXPECTED_SOURCE_WORKFLOW_ID, "source workflow id provenance drift")
    req(workflow.get("workflow_path") == EXPECTED_SOURCE_WORKFLOW_PATH, "source workflow path provenance drift")
    req(workflow.get("workflow_event") == "pull_request", "source workflow event provenance drift")
    req(workflow.get("source_head_branch") == EXPECTED_SOURCE_HEAD_BRANCH, "source workflow branch provenance drift")
    req(workflow.get("run_id") == 33832558443 and workflow.get("run_attempt") == 1, "source workflow run provenance drift")
    req(workflow.get("job_id") == 100898421033 and workflow.get("job_name") == "D4-B schema contract source evidence", "source job provenance drift")
    req(workflow.get("artifact_id") == 9922185873, "source artifact id drift")
    req(workflow.get("artifact_name") == "d4-b-schema-contract-source-0a5509442d4b55f6d4de989af9bb62a088198ab4-33832558443-1", "source artifact name drift")
    req(workflow.get("artifact_digest") == "sha256:3d8f585ea3e594edc40179a0232c2d00d5133fb652961fa60337dae48b4313dc", "source artifact digest drift")
    source_manifest = promotion.get("source_manifest", {})
    req(isinstance(source_manifest, dict) and set(source_manifest) == EXPECTED_SOURCE_MANIFEST_KEYS, "source manifest exact key schema drift")
    req(source_manifest.get("path") == SOURCE.as_posix(), "promotion source-manifest path drift")
    req(source_manifest.get("sha256") == EXPECTED_MANIFEST_SHA256, "promotion source-manifest digest drift")
    req(set(promotion.get("credited_evidence", [])) == EXPECTED_IDS and len(promotion.get("credited_evidence", [])) == 5 and promotion.get("credit_count") == 5, "promotion credit set drift")
    req(promotion.get("selection_state") == "not_selected", "promotion must not select a D4-B candidate")
    req(promotion.get("serialization_selection_state") == "not_selected", "promotion serialization selection drift")
    req(promotion.get("schema_catalog_selection_state") == "not_selected", "promotion schema catalog selection drift")
    req(promotion.get("contract_version_syntax_selection_state") == "not_selected", "promotion contract version syntax selection drift")
    req(promotion.get("d4_gate_state") == "scoped", "promotion must not accept D4")
    req(promotion.get("d4_transport_authority") == "selected_not_granted", "promotion transport authority drift")
    req(promotion.get("canonical_product_implementation_authority") == "not_granted", "promotion Product authority drift")
    req(promotion.get("wave4_implementation_authority") == "not_granted", "promotion Wave 4 authority drift")
    req(promotion.get("production_authority") == "none", "promotion production authority drift")
    req(promotion.get("c3_numeric_topology_authority") == "not_selected", "promotion C3 authority drift")
    req(promotion.get("separate_selection_required") is True and promotion.get("separate_d4_acceptance_required") is True, "promotion must preserve separate selection and D4 acceptance")

    req(hashlib.sha256(source_bytes).hexdigest() == EXPECTED_MANIFEST_SHA256, "source manifest byte drift")
    req(source.get("current_run_auto_credit") is False and source.get("ledger_credit") == [], "immutable source package must remain nonpromoting")
    req(source.get("candidate") is None and source.get("candidate_status") == "not_selected", "source package must remain candidate-neutral")
    req(set(source.get("evidence_ids", [])) == EXPECTED_IDS and len(source.get("evidence_ids", [])) == 5, "source evidence IDs drift")
    req(source.get("serialization_selection_state") == "not_selected", "source serialization selection drift")
    req(source.get("schema_catalog_selection_state") == "not_selected", "source schema catalog selection drift")
    req(source.get("contract_version_syntax_selection_state") == "not_selected", "source contract version syntax selection drift")

    req(d4b.get("state") == "evidence_complete_selection_pending", "D4-B state must be evidence-complete selection-pending")
    req(d4b.get("candidate") is None and d4b.get("candidate_status") == "not_selected", "D4-B state must not silently select a candidate")
    req(set(d4b.get("evidence_completed", [])) == EXPECTED_IDS and len(d4b.get("evidence_completed", [])) == 5, "D4-B state credit drift")
    req(d4b.get("evidence_remaining") == [], "D4-B state remaining evidence must be empty")
    d4a = tracks["D4-A"]
    req(d4a.get("candidate") == "kafka" and d4a.get("candidate_status") == "selected_c2_candidate", "D4-A selected candidate drift")
    req(d4a.get("state") == "selected_candidate", "D4-A selected state drift")
    req(set(d4a.get("evidence_completed", [])) == EXPECTED_D4A_IDS and len(d4a.get("evidence_completed", [])) == 7, "D4-A exact 7/7 evidence membership drift")
    req(d4a.get("evidence_remaining") == [], "D4-A evidence_remaining drift")
    for track_id in ("D4-C", "D4-D"):
        sibling = tracks[track_id]
        req(sibling.get("candidate") is None and sibling.get("candidate_status") == "not_selected", f"{track_id} candidate must remain unselected")
        req(sibling.get("evidence_completed") == [], f"{track_id} must remain uncredited")

    req(state.get("gate_state") == "scoped", "D4 must remain scoped")
    req(state.get("d4_transport_authority") == "selected_not_granted", "transport authority must remain selected_not_granted")
    req(state.get("canonical_product_implementation_authority") == "not_granted", "Product authority must remain not_granted")
    req(state.get("wave4_implementation_authority") == "not_granted", "Wave 4 authority must remain not_granted")
    req(state.get("production_authority") == "none", "production authority must remain none")
    req(state.get("c3_numeric_topology_authority") == "not_selected", "C3 authority must remain not_selected")
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4B_LEDGER_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4b_ledger_promotion=PASS credited=5/5 candidate=not_selected selection=separate source_immutable=true strict_json=true unique_tracks=true source_workflow=exact promotion_record=exact_schema_pinned d4a=exact_7_of_7 d4=scoped authorities=not_granted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
