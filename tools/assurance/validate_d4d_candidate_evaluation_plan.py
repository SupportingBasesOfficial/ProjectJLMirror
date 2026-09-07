#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PLAN = Path("implementation/d4-eventing-async/d4-d-candidate-evaluation-plan.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")
EXPECTED_SOURCE_DECISIONS = ["OPEN-EVT-016", "OPEN-EVT-017", "OPEN-EVT-018"]
EXPECTED_AXES = {
    "workload_identity_to_broker_credential_adapter": "OPEN-EVT-016",
    "tenant_and_contract_scoped_producer_consumer_authorization": "OPEN-EVT-016",
    "message_protection_key_authority_and_historical_verifier_continuity": "OPEN-EVT-017",
    "secret_credential_payload_exclusion_and_erasure_boundary": "OPEN-EVT-017",
    "trace_context_observability_only_validation_and_redaction": "OPEN-EVT-018",
}
D4C_CREDITS = [
    "ack_after_durable_responsibility_and_lease_ambiguity",
    "quarantine_redrive_current_authority_and_dedup_preservation",
    "bounded_message_batch_compression_and_parser_limits",
    "scoped_content_equivalence_confidentiality_and_conflict_rejection",
    "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity",
    "producer_generation_nonresurrection_across_failover_restore",
    "privileged_bounded_replay_with_original_identity_and_effect_safety",
    "historical_reader_upcaster_semantic_and_equivalence_continuity",
    "recovery_generation_rf_inventory_reconciliation_and_activation_gates",
]
D4D_REQUIRED = [
    "workload_identity_to_broker_credential_adapter_least_privilege",
    "tenant_and_contract_scoped_producer_consumer_authorization",
    "message_protection_key_authority_and_historical_verifier_continuity",
    "secret_credential_payload_exclusion_and_erasure_boundary",
    "trace_context_observability_only_validation_and_redaction",
]
D4D_CREDITS = [D4D_REQUIRED[0]]
FORBIDDEN_OUTPUTS = ["selected", "preferred_without_evidence", "production_ready", "authority_granted"]
ALLOWED_OUTPUTS = ["eligible_for_evidence_execution", "ineligible_by_contract", "insufficient_evidence"]


def load(root: Path, path: Path) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    plan = load(root, PLAN)
    state = load(root, STATE)
    if plan.get("schema_version") != 1 or plan.get("gate_id") != "D4" or plan.get("track_id") != "D4-D":
        errors.append("plan identity must be schema v1 / D4 / D4-D")
    if plan.get("mode") != "candidate_evaluation_only":
        errors.append("mode must remain candidate_evaluation_only")
    if plan.get("selection_state") != "not_selected" or plan.get("selection_authority") != "not_granted":
        errors.append("candidate evaluation must not select or grant selection authority")
    if plan.get("separate_selection_required") is not True or plan.get("separate_d4_acceptance_required") is not True:
        errors.append("selection and D4 acceptance must remain separate")
    if plan.get("source_decisions") != EXPECTED_SOURCE_DECISIONS:
        errors.append("source decision inventory must be exactly OPEN-EVT-016/017/018")
    axes = plan.get("axes")
    if not isinstance(axes, dict) or list(axes) != list(EXPECTED_AXES):
        errors.append("D4-D must expose exactly the five ordered evaluation axes")
    else:
        for axis_name, decision in EXPECTED_AXES.items():
            axis = axes[axis_name]
            if axis.get("decision") != decision:
                errors.append(f"{axis_name}: wrong source decision")
            candidates = axis.get("candidate_classes")
            if not isinstance(candidates, list) or len(candidates) < 3 or len(candidates) != len(set(candidates)):
                errors.append(f"{axis_name}: candidate classes must be unique and plural")
            must_prove = axis.get("must_prove")
            if not isinstance(must_prove, list) or len(must_prove) < 6 or len(must_prove) != len(set(must_prove)):
                errors.append(f"{axis_name}: must_prove inventory is incomplete or duplicated")
    workload_proofs = axes.get("workload_identity_to_broker_credential_adapter", {}).get("must_prove", []) if isinstance(axes, dict) else []
    if "adapter_consumes_ir_d_002_canonical_workload_identity_without_reopening_issuer_or_attestation_authority" not in workload_proofs:
        errors.append("OPEN-EVT-016 adapter must consume IR-D-002 identity without reopening issuer/attestation authority")
    if plan.get("evaluation_output_states") != ALLOWED_OUTPUTS or plan.get("forbidden_outputs") != FORBIDDEN_OUTPUTS:
        errors.append("evaluation output authority boundary drift")
    invariants = plan.get("cross_axis_invariants")
    required_fragments = [
        "ir_d_002_canonical_workload_authentication_baseline_is_consumed_not_reopened",
        "broker_vendor_identity_never_becomes_platform_workload_or_tenant_identity",
        "broker_authorization_is_projection_of_current_platform_authority_not_a_parallel_business_authority",
        "message_protection_never_weakens_minimization_authorization_or_historical_equivalence_requirements",
        "trace_context_is_never_security_or_business_effect_authority",
        "d4d_evidence_remains_zero_of_five_until_separate_source_evidence_and_promotion",
        "d4d_candidate_remains_unselected_and_selection_authority_not_granted",
    ]
    if not isinstance(invariants, list) or any(x not in invariants for x in required_fragments):
        errors.append("historical cross-axis authority invariants are incomplete")

    tracks = {t.get("track_id"): t for t in state.get("tracks", []) if isinstance(t, dict)}
    if set(tracks) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
        errors.append("global D4 track inventory changed")
        return errors
    d4a, d4b, d4c, d4d = tracks["D4-A"], tracks["D4-B"], tracks["D4-C"], tracks["D4-D"]
    if d4a.get("candidate") != "kafka" or len(d4a.get("evidence_completed", [])) != 7 or d4a.get("evidence_remaining") != []:
        errors.append("D4-A accepted candidate/evidence must remain 7/7")
    if d4b.get("candidate_status") != "selected_c2_profile" or len(d4b.get("evidence_completed", [])) != 5 or d4b.get("evidence_remaining") != []:
        errors.append("D4-B selected profile/evidence must remain 5/5")
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open" or d4c.get("evidence_completed") != D4C_CREDITS or d4c.get("evidence_remaining") != []:
        errors.append("D4-C must remain 9/9 open/unselected")
    if d4d.get("source_decisions") != EXPECTED_SOURCE_DECISIONS:
        errors.append("D4-D state source decisions changed")
    if d4d.get("candidate") is not None or d4d.get("candidate_status") != "not_selected" or d4d.get("state") != "candidate_selection_open":
        errors.append("D4-D must remain open/unselected")
    if d4d.get("required_evidence") != D4D_REQUIRED or d4d.get("evidence_completed") != D4D_CREDITS or d4d.get("evidence_remaining") != D4D_REQUIRED[1:]:
        errors.append("current D4-D state must reflect exactly the separately promoted first credit")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 22:
        errors.append("D4-wide evidence must be exactly 22/26")
    authority = (state.get("gate_state"), state.get("d4_transport_authority"), state.get("canonical_product_implementation_authority"), state.get("wave4_implementation_authority"), state.get("production_authority"), state.get("c3_numeric_topology_authority"))
    if authority != ("scoped", "selected_not_granted", "not_granted", "not_granted", "none", "not_selected"):
        errors.append("global D4/product/Wave4/production/C3 authority boundary changed")
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4D_EVAL_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4d_candidate_evaluation_plan=PASS axes=5 ir_d_002=preserved selection=not_selected historical_plan_nonpromoting=true current_d4d=1_of_5 d4wide=22/26 authorities=unchanged")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
