#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys

import validate_source_evidence_historical_current as historical
from validate_source_evidence_historical_current import *  # noqa: F401,F403

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
D4D_SELECTED_PROFILE = {
    "workload_identity_to_broker_credential_adapter": "derived_short_lived_broker_native_credential_adapter",
    "tenant_and_contract_scoped_producer_consumer_authorization": "broker_acl_projection_adapter",
    "message_protection_key_authority_and_historical_verifier_continuity": "kms_backed_envelope_or_transport_protection_profile",
    "secret_credential_payload_exclusion_and_erasure_boundary": "reference_only_secret_authority_profile",
    "trace_context_observability_only_validation_and_redaction": "w3c_trace_context_bounded_profile",
}
D4D_CREDITS = [
    "workload_identity_to_broker_credential_adapter_least_privilege",
    "tenant_and_contract_scoped_producer_consumer_authorization",
    "message_protection_key_authority_and_historical_verifier_continuity",
    "secret_credential_payload_exclusion_and_erasure_boundary",
    "trace_context_observability_only_validation_and_redaction",
]
_original_load = historical.load


def _current_errors(state: dict, plan: dict) -> list[str]:
    errors: list[str] = []
    tracks = {t.get("track_id"): t for t in state.get("tracks", []) if isinstance(t, dict)}
    if set(tracks) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
        return ["D4 track inventory drift"]
    d4c, d4d = tracks["D4-C"], tracks["D4-D"]
    if plan.get("candidate") != D4C_SELECTED_PROFILE or plan.get("candidate_status") != "selected_c2_delivery_recovery_profile" or plan.get("selection_state") != "selected":
        errors.append("D4-C current ledger selected profile drift")
    if plan.get("credited_evidence") != historical.CURRENT_CREDITS or plan.get("remaining_evidence") != historical.CURRENT_REMAINING:
        errors.append("D4-C current ledger evidence drift")
    if d4c.get("candidate") != D4C_SELECTED_PROFILE or d4c.get("candidate_status") != "selected_c2_delivery_recovery_profile" or d4c.get("state") != "selected_candidate":
        errors.append("D4-C current state selected profile drift")
    if d4c.get("evidence_completed") != historical.CURRENT_CREDITS or d4c.get("evidence_remaining") != historical.CURRENT_REMAINING:
        errors.append("D4-C global projection drift")
    if d4d.get("candidate") != D4D_SELECTED_PROFILE or d4d.get("candidate_status") != "selected_c2_security_profile" or d4d.get("state") != "selected_candidate":
        errors.append("D4-D current selected profile drift")
    if d4d.get("evidence_completed") != D4D_CREDITS or d4d.get("evidence_remaining") != []:
        errors.append("D4-D current state must be exactly 5/5")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 26:
        errors.append("D4-wide credit count must be 26/26")
    return errors


def _project_state(state: dict) -> dict:
    projected = copy.deepcopy(state)
    d4c = next(t for t in projected["tracks"] if t.get("track_id") == "D4-C")
    d4c.update(candidate=None, candidate_status="not_selected", state="candidate_selection_open")
    d4d = next(t for t in projected["tracks"] if t.get("track_id") == "D4-D")
    d4d.update(candidate=None, candidate_status="not_selected", state="candidate_selection_open")
    d4d["evidence_completed"] = []
    d4d["evidence_remaining"] = list(d4d["required_evidence"])
    return projected


def _project_plan(plan: dict) -> dict:
    projected = copy.deepcopy(plan)
    projected["candidate"] = None
    projected["candidate_status"] = "not_selected"
    projected["selection_state"] = "not_selected"
    projected["selection_authority"] = "not_granted"
    projected["separate_selection_required"] = True
    projected.pop("selection_record", None)
    return projected


def main() -> int:
    state = _original_load(historical.STATE)
    plan = _original_load(historical.PLAN)
    current = _current_errors(state, plan)
    if current:
        for error in current:
            print(f"d4c_open_evt_015_source_validation=FAIL reason={error}", file=sys.stderr)
        return 1
    original = historical.load
    try:
        def projected_load(path):
            value = _original_load(path)
            if path == historical.STATE:
                return _project_state(value)
            if path == historical.PLAN:
                return _project_plan(value)
            return value
        historical.load = projected_load
        result = historical.main()
    finally:
        historical.load = original
    if result == 0:
        print("d4c_open_evt_015_current_projection=PASS d4c=9_of_9_selected d4d=5_of_5_selected d4wide=26_of_26 historical_oracle=preserved")
    return result

if __name__ == "__main__":
    raise SystemExit(main())
