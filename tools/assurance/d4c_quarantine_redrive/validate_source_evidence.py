#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from evaluate_candidates import CANDIDATES, evaluate_all

SOURCE = Path("implementation/d4-eventing-async/source-evidence/d4-c-quarantine-redrive-source.json")
PLAN = Path("implementation/d4-eventing-async/d4-c-candidate-evaluation-plan.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")
CREDIT_008 = "ack_after_durable_responsibility_and_lease_ambiguity"
EVIDENCE = "quarantine_redrive_current_authority_and_dedup_preservation"
CREDIT_010 = "bounded_message_batch_compression_and_parser_limits"
CREDIT_011 = "scoped_content_equivalence_confidentiality_and_conflict_rejection"
CURRENT_CREDITS = [CREDIT_008, EVIDENCE, CREDIT_010, CREDIT_011]
EXPECTED_ASSERTIONS = [
    "all_three_concrete_candidate_classes_share_one_platform_quarantine_process_truth",
    "retry_budget_exhaustion_transitions_to_governed_quarantine_without_inferring_production_retry_numerics",
    "retry_count_cannot_regress_retry_budget_cannot_rebind_and_quarantine_cannot_be_reopened_by_redelivery",
    "tenant_authority_context_is_distinct_from_consumer_message_identity_scope",
    "tenant_authority_context_cannot_be_rebound_for_the_same_scoped_message_identity",
    "redrive_without_current_privileged_authority_is_rejected",
    "redrive_authority_is_current_tenant_scoped_and_classification_scoped",
    "cross_tenant_redrive_authority_is_rejected",
    "every_redrive_attempt_is_audited_with_current_actor_tenant_scope_and_reason",
    "redrive_reenters_normal_dedup_equivalence_and_reconciliation_admission",
    "same_scoped_identity_with_conflicting_immutable_content_is_rejected_as_integrity_failure",
    "confidential_payload_and_equivalence_evidence_require_tenant_and_classification_scoped_access",
    "retention_is_expressed_as_governed_policy_class_not_selected_numeric_horizon",
    "broker_native_dlq_identity_is_adapter_metadata_not_platform_quarantine_identity",
    "broker_replacement_preserves_platform_quarantine_record_identity_and_redrive_history",
    "candidate_source_evidence_does_not_select_a_candidate_broker_dlq_or_production_topology",
]
EXPECTED_NON_AUTHORITY = {
    "d4c_mechanism_selection": "not_selected",
    "d4c_content_equivalence_profile_selection": "not_selected",
    "d4c_ledger_credit": "current_1_of_9_unchanged",
    "d4d_ledger_credit": "0_of_5",
    "d4_gate": "scoped",
    "d4_transport_authority": "selected_not_granted",
    "canonical_product_implementation_authority": "not_granted",
    "wave4_implementation_authority": "not_granted",
    "production_authority": "none",
    "c3_numeric_topology_authority": "not_selected",
}

class DuplicateKeyError(ValueError):
    pass

def _no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateKeyError(f"duplicate JSON member: {key}")
        out[key] = value
    return out

def load(root: Path, path: Path):
    return json.loads((root / path).read_text(encoding="utf-8"), object_pairs_hook=_no_duplicates)

def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        source = load(root, SOURCE); plan = load(root, PLAN); state = load(root, STATE)
    except Exception as exc:
        return [str(exc)]
    expected_scalars = {
        "schema_version": 1, "gate_id": "D4", "track_id": "D4-C", "axis": "quarantine_and_redrive",
        "source_decision": "OPEN-EVT-009", "evidence_id": EVIDENCE,
        "canonical_base": "48734ede4bceb6b4f25f7ac5c9f84ced9563e351", "mode": "candidate_source_evidence_only",
        "selection_state": "not_selected", "selection_authority": "not_granted", "current_run_auto_credit": False,
    }
    for key, expected in expected_scalars.items():
        if source.get(key) != expected or type(source.get(key)) is not type(expected): errors.append(f"source scalar drift: {key}")
    if source.get("ledger_credit") != []: errors.append("source ledger credit must remain empty")
    try:
        axis = plan["axes"]["quarantine_and_redrive"]
    except Exception:
        axis = {}; errors.append("accepted OPEN-EVT-009 axis missing")
    if axis.get("decision") != "OPEN-EVT-009" or axis.get("evidence_id") != EVIDENCE: errors.append("accepted axis binding drift")
    if source.get("required_proofs") != axis.get("must_prove"): errors.append("required proof inventory drift from accepted plan")
    concrete = [c for c in axis.get("candidate_classes", []) if c != "equivalent_reviewed_profile"]
    if concrete != list(CANDIDATES): errors.append("candidate class inventory drift from accepted plan")
    if source.get("source_assertions") != EXPECTED_ASSERTIONS: errors.append("source assertion inventory drift")
    if source.get("non_authority") != EXPECTED_NON_AUTHORITY: errors.append("source non-authority boundary drift")
    runtime = evaluate_all()
    if source.get("candidate_results") != runtime.get("candidate_results"): errors.append("candidate results drift from executable harness")
    if source.get("equivalent_reviewed_profile") != "insufficient_evidence" or runtime.get("equivalent_reviewed_profile") != "insufficient_evidence": errors.append("equivalent reviewed profile must remain insufficient_evidence")
    if runtime.get("selection") != "not_selected" or runtime.get("ledger_credit") != []: errors.append("runtime escaped source-only boundary")
    if not all(all(checks.values()) for checks in runtime.get("checks", {}).values()): errors.append("one or more executable source proofs failed")
    if runtime.get("test_retry_budget_is_noncanonical_fixture") is not True: errors.append("test retry budget lost noncanonical-fixture guard")
    if runtime.get("test_fingerprint_profile") != "sha256_fixture_only_noncanonical": errors.append("test fingerprint profile lost explicit noncanonical guard")
    tracks_raw = state.get("tracks", [])
    if not isinstance(tracks_raw, list) or len(tracks_raw) != 4:
        errors.append("D4 track structure drift"); return errors
    ids = [t.get("track_id") for t in tracks_raw if isinstance(t, dict)]
    if len(ids) != 4 or len(set(ids)) != 4 or set(ids) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
        errors.append("D4 track identity drift"); return errors
    tracks = {t["track_id"]: t for t in tracks_raw}; d4a,d4b,d4c,d4d=tracks["D4-A"],tracks["D4-B"],tracks["D4-C"],tracks["D4-D"]
    if d4a.get("candidate") != "kafka" or len(d4a.get("evidence_completed", [])) != 7: errors.append("D4-A accepted state drift")
    if d4b.get("candidate_status") != "selected_c2_profile" or len(d4b.get("evidence_completed", [])) != 5: errors.append("D4-B accepted state drift")
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open": errors.append("D4-C selection leakage")
    expected_remaining = [x for x in d4c.get("required_evidence", []) if x not in CURRENT_CREDITS]
    if d4c.get("evidence_completed") != CURRENT_CREDITS or d4c.get("evidence_remaining") != expected_remaining: errors.append("D4-C current 4/9 ledger drift")
    if d4d.get("candidate") is not None or d4d.get("evidence_completed") != []: errors.append("D4-D state leakage")
    if sum(len(t.get("evidence_completed", [])) for t in tracks_raw) != 16: errors.append("D4-wide evidence count drift")
    for key, expected in {
        "gate_state": "scoped", "d4_transport_authority": "selected_not_granted",
        "canonical_product_implementation_authority": "not_granted", "wave4_implementation_authority": "not_granted",
        "production_authority": "none", "c3_numeric_topology_authority": "not_selected",
    }.items():
        if state.get(key) != expected: errors.append(f"global authority drift: {key}")
    return errors

def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    errors = validate(root)
    if errors:
        for error in errors: print(f"D4C_OPEN_EVT_009_SOURCE_ERROR: {error}")
        return 1
    print("d4c_quarantine_redrive_source=PASS candidates=3 source_snapshot_nonpromoting=true current_d4c=4_of_9 current_d4wide=16_of_26 selection=not_selected")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
