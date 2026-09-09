#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import validate_d4b_selection_historical as historical
from validate_d4b_selection_historical import *  # noqa: F401,F403

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
_legacy_load = historical.load


def _current_sibling_errors(state: dict) -> list[str]:
    errors: list[str] = []
    tracks = {t.get("track_id"): t for t in state.get("tracks", []) if isinstance(t, dict)}
    d4c = tracks.get("D4-C", {})
    d4d = tracks.get("D4-D", {})
    if d4c.get("candidate") != D4C_SELECTED_PROFILE or d4c.get("candidate_status") != "selected_c2_delivery_recovery_profile" or d4c.get("state") != "selected_candidate":
        errors.append("D4-C current selected sibling state drift")
    if not isinstance(d4c.get("evidence_remaining"), list): errors.append("D4-C remaining evidence must be an exact list")
    elif d4c.get("evidence_completed") != D4C_CREDITS or d4c.get("evidence_remaining") != []: errors.append("D4-C current sibling must remain 9/9")
    if d4d.get("candidate") != D4D_SELECTED_PROFILE or d4d.get("candidate_status") != "selected_c2_security_profile" or d4d.get("state") != "selected_candidate": errors.append("D4-D current sibling selected security profile drift")
    if not isinstance(d4d.get("evidence_remaining"), list): errors.append("D4-D remaining evidence must be an exact list")
    elif d4d.get("evidence_completed") != D4D_CREDITS or d4d.get("evidence_remaining") != []: errors.append("D4-D current sibling must be exactly 5/5")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 26: errors.append("D4-wide current evidence must be exactly 26/26")
    return errors


def _historical_projection(state: dict) -> dict:
    projected = copy.deepcopy(state)
    d4c = next(t for t in projected["tracks"] if t.get("track_id") == "D4-C")
    d4c["candidate"] = None
    d4c["candidate_status"] = "not_selected"
    d4c["state"] = "candidate_selection_open"
    d4c["evidence_completed"] = []
    d4c["evidence_remaining"] = list(d4c["required_evidence"])
    d4d = next(t for t in projected["tracks"] if t.get("track_id") == "D4-D")
    d4d["candidate"] = None
    d4d["candidate_status"] = "not_selected"
    d4d["state"] = "candidate_selection_open"
    d4d["evidence_completed"] = []
    d4d["evidence_remaining"] = list(d4d["required_evidence"])
    return projected


def validate(root: Path) -> list[str]:
    state = json.loads((root / STATE).read_text(encoding="utf-8")); current = _current_sibling_errors(state)
    if current: return current
    original_load = historical.load
    try:
        def projected_load(inner_root: Path, path: Path) -> dict:
            value = _legacy_load(inner_root, path); return _historical_projection(value) if path == STATE else value
        historical.load = projected_load
        return historical.validate(root)
    finally: historical.load = original_load


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd(); errors = validate(root)
    if errors:
        for error in errors: print(f"D4B_SELECTION_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4b_selection=PASS historical_oracle=preserved current_sibling_d4c=9_of_9_selected current_sibling_d4d=5_of_5_selected d4wide=26_of_26")
    return 0
if __name__ == "__main__": raise SystemExit(main(sys.argv))
