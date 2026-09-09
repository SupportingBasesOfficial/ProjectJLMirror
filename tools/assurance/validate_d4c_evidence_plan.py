#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import validate_d4c_evidence_plan_historical_current as historical

PLAN = historical.PLAN
STATE = historical.STATE
PROMOTION_025 = historical.PROMOTION_025
SOURCE_025 = historical.SOURCE_025
CREDIT_025 = historical.CREDIT_025
CREDITS = historical.CREDITS
HISTORICAL_PROMOTIONS = historical.HISTORICAL_PROMOTIONS
D4C_SELECTED_PROFILE = {
    "ack_visibility_lease_and_checkpoint": "durable_inbox_claim_then_broker_ack_profile",
    "quarantine_and_redrive": "hybrid_platform_quarantine_store_plus_broker_dlq",
    "bounded_message_payload_batch_and_compression": "layered_transport_and_application_bounds_profile",
    "scoped_content_equivalence_authority": "hybrid_equivalence_authority_profile",
    "outbox_claim_dispatch_and_ack_ambiguity": "compare_and_swap_lease_claim_profile",
    "producer_source_generation": "authority_issued_epoch_generation",
    "privileged_replay_and_event_history": "hybrid_history_archive_plus_replay_controller_profile",
    "historical_reader_and_upcaster": "in_process_versioned_reader_upcaster_registry",
    "recovery_generation_reconciliation_and_activation": "hybrid_generation_manifest_plus_multi_store_reconciler_profile",
}
D4D_CREDITS = [
    "workload_identity_to_broker_credential_adapter_least_privilege",
    "tenant_and_contract_scoped_producer_consumer_authorization",
    "message_protection_key_authority_and_historical_verifier_continuity",
    "secret_credential_payload_exclusion_and_erasure_boundary",
    "trace_context_observability_only_validation_and_redaction",
]
D4D_SELECTED_PROFILE = {
    "workload_identity_to_broker_credential_adapter": "derived_short_lived_broker_native_credential_adapter",
    "tenant_and_contract_scoped_producer_consumer_authorization": "broker_acl_projection_adapter",
    "message_protection_key_authority_and_historical_verifier_continuity": "kms_backed_envelope_or_transport_protection_profile",
    "secret_credential_payload_exclusion_and_erasure_boundary": "reference_only_secret_authority_profile",
    "trace_context_observability_only_validation_and_redaction": "w3c_trace_context_bounded_profile",
}


def _current_errors(state: dict, plan: dict) -> list[str]:
    errors: list[str] = []
    tracks = {t.get("track_id"): t for t in state.get("tracks", []) if isinstance(t, dict)}
    if set(tracks) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
        return ["D4 track inventory drift"]
    d4c = tracks["D4-C"]
    d4d = tracks["D4-D"]
    if plan.get("candidate") != D4C_SELECTED_PROFILE or plan.get("candidate_status") != "selected_c2_delivery_recovery_profile" or plan.get("selection_state") != "selected" or plan.get("selection_authority") != "selection_record" or plan.get("separate_selection_required") is not False:
        errors.append("D4-C current ledger selection drift")
    if plan.get("credited_evidence") != historical.CREDITS or plan.get("remaining_evidence") != [] or plan.get("ledger_credit_state") != "nine_of_nine":
        errors.append("D4-C current ledger evidence drift")
    if d4c.get("candidate") != D4C_SELECTED_PROFILE or d4c.get("candidate_status") != "selected_c2_delivery_recovery_profile" or d4c.get("state") != "selected_candidate":
        errors.append("D4-C current selected profile drift")
    if d4c.get("evidence_completed") != historical.CREDITS or d4c.get("evidence_remaining") != []:
        errors.append("D4-C state credit drift: must remain exactly 9/9")
    if d4d.get("candidate") != D4D_SELECTED_PROFILE or d4d.get("candidate_status") != "selected_c2_security_profile" or d4d.get("state") != "selected_candidate":
        errors.append("D4-D selected security profile drift")
    if d4d.get("evidence_completed") != D4D_CREDITS or d4d.get("evidence_remaining") != []:
        errors.append("D4-D state/credit leakage: current state must be exactly 5/5")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 26:
        errors.append("D4-wide credited evidence must be exactly 26/26")
    authority = (state.get("gate_state"),state.get("d4_transport_authority"),state.get("canonical_product_implementation_authority"),state.get("wave4_implementation_authority"),state.get("production_authority"),state.get("c3_numeric_topology_authority"))
    if authority != ("separately_accepted", "selected_not_granted", "not_granted", "not_granted", "none", "not_selected"):
        errors.append("global authority drift")
    return errors


def _historical_state(state: dict) -> dict:
    projected = copy.deepcopy(state)
    projected["gate_state"] = "scoped"
    d4c = next(t for t in projected["tracks"] if t.get("track_id") == "D4-C")
    d4c["candidate"] = None
    d4c["candidate_status"] = "not_selected"
    d4c["state"] = "candidate_selection_open"
    d4d = next(t for t in projected["tracks"] if t.get("track_id") == "D4-D")
    d4d["candidate"] = None
    d4d["candidate_status"] = "not_selected"
    d4d["state"] = "candidate_selection_open"
    d4d["evidence_completed"] = []
    d4d["evidence_remaining"] = list(d4d["required_evidence"])
    return projected


def _historical_plan(plan: dict) -> dict:
    projected = copy.deepcopy(plan)
    projected["candidate"] = None
    projected["candidate_status"] = "not_selected"
    projected["selection_state"] = "not_selected"
    projected["selection_authority"] = "not_granted"
    projected["separate_selection_required"] = True
    projected.pop("selection_record", None)
    return projected


def validate(root: Path) -> list[str]:
    state = json.loads((root / STATE).read_text(encoding="utf-8"))
    plan = json.loads((root / PLAN).read_text(encoding="utf-8"))
    current = _current_errors(state, plan)
    if current:
        return current
    original_load = historical.load
    try:
        def projected_load(path: Path):
            value = original_load(path)
            if path == root / STATE:
                return _historical_state(value)
            if path == root / PLAN:
                return _historical_plan(value)
            return value
        historical.load = projected_load
        return historical.validate(root)
    finally:
        historical.load = original_load


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4C_PROMOTION_ERROR: {error}")
        return 1
    print("d4c_open_evt_025_promotion=PASS historical_gate=scoped historical_oracle=byte_preserved current_gate=separately_accepted d4c=9_of_9_selected d4d=5_of_5_selected d4wide=26_of_26 authorities=unchanged")
    return 0
if __name__ == "__main__": raise SystemExit(main())
