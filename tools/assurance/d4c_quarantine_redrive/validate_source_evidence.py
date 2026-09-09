#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
from pathlib import Path

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
_legacy_load = historical.load


def _current_errors(state: dict) -> list[str]:
    errors: list[str] = []
    tracks = {t.get("track_id"): t for t in state.get("tracks", []) if isinstance(t, dict)}
    if set(tracks) != {"D4-A", "D4-B", "D4-C", "D4-D"}: return ["D4 track identity drift"]
    d4c, d4d = tracks["D4-C"], tracks["D4-D"]
    if d4c.get("candidate") != D4C_SELECTED_PROFILE or d4c.get("candidate_status") != "selected_c2_delivery_recovery_profile" or d4c.get("state") != "selected_candidate": errors.append("D4-C current selected profile drift")
    if d4c.get("evidence_completed") != historical.CURRENT_CREDITS or d4c.get("evidence_remaining") != []: errors.append("D4-C current 9/9 ledger drift")
    if d4d.get("candidate") != D4D_SELECTED_PROFILE or d4d.get("candidate_status") != "selected_c2_security_profile" or d4d.get("state") != "selected_candidate": errors.append("D4-D current selected profile drift")
    if d4d.get("evidence_completed") != D4D_CREDITS or d4d.get("evidence_remaining") != []: errors.append("D4-D current state must be exactly 5/5")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 26: errors.append("D4-wide evidence count must be 26/26")
    return errors


def _project(state: dict) -> dict:
    projected = copy.deepcopy(state)
    d4c = next(t for t in projected["tracks"] if t.get("track_id") == "D4-C")
    d4c.update(candidate=None, candidate_status="not_selected", state="candidate_selection_open")
    d4d = next(t for t in projected["tracks"] if t.get("track_id") == "D4-D")
    d4d["evidence_completed"] = []
    d4d["evidence_remaining"] = list(d4d["required_evidence"])
    d4d.update(candidate=None, candidate_status="not_selected", state="candidate_selection_open")
    return projected


def validate(root: Path) -> list[str]:
    state = _legacy_load(root, historical.STATE); current = _current_errors(state)
    if current: return current
    original = historical.load
    try:
        def projected_load(inner_root: Path, path: Path):
            value = _legacy_load(inner_root, path); return _project(value) if path == historical.STATE else value
        historical.load = projected_load; return historical.validate(root)
    finally: historical.load = original


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("."); errors = validate(root)
    if errors:
        for error in errors: print(f"D4C_OPEN_EVT_009_SOURCE_ERROR: {error}")
        return 1
    print("d4c_quarantine_redrive_source=PASS historical_oracle=preserved current_d4c=9_of_9_selected current_d4d=5_of_5_selected current_d4wide=26_of_26")
    return 0
if __name__ == "__main__": raise SystemExit(main())
