#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
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
    if set(tracks) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
        return ["D4 track inventory drift"]
    d4a, d4b, d4c, d4d = (tracks[x] for x in ("D4-A", "D4-B", "D4-C", "D4-D"))
    if d4a.get("candidate") != "kafka" or len(d4a.get("evidence_completed", [])) != 7 or d4a.get("evidence_remaining") != []:
        errors.append("D4-A current state drift")
    if d4b.get("candidate_status") != "selected_c2_profile" or d4b.get("state") != "selected_candidate" or len(d4b.get("evidence_completed", [])) != 5 or d4b.get("evidence_remaining") != []:
        errors.append("D4-B current selected profile drift")
    if d4c.get("candidate") != D4C_SELECTED_PROFILE or d4c.get("candidate_status") != "selected_c2_delivery_recovery_profile" or d4c.get("state") != "selected_candidate" or len(d4c.get("evidence_completed", [])) != 9 or d4c.get("evidence_remaining") != []:
        errors.append("D4-C current selected 9/9 drift")
    if d4d.get('candidate') != {'workload_identity_to_broker_credential_adapter': 'derived_short_lived_broker_native_credential_adapter', 'tenant_and_contract_scoped_producer_consumer_authorization': 'broker_acl_projection_adapter', 'message_protection_key_authority_and_historical_verifier_continuity': 'kms_backed_envelope_or_transport_protection_profile', 'secret_credential_payload_exclusion_and_erasure_boundary': 'reference_only_secret_authority_profile', 'trace_context_observability_only_validation_and_redaction': 'w3c_trace_context_bounded_profile'} or d4d.get('candidate_status') != 'selected_c2_security_profile' or d4d.get('state') != 'selected_candidate':
        errors.append("D4-D current selection drift")
    if d4d.get("evidence_completed") != D4D_CREDITS or d4d.get("evidence_remaining") != []:
        errors.append("D4-D current state must be exactly 5/5")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 26:
        errors.append("D4-wide current state must be 26/26")
    if (state.get("gate_state"), state.get("d4_transport_authority"), state.get("canonical_product_implementation_authority"), state.get("wave4_implementation_authority"), state.get("production_authority"), state.get("c3_numeric_topology_authority")) != ("scoped", "selected_not_granted", "not_granted", "not_granted", "none", "not_selected"):
        for field, (expected, message) in {'gate_state': ('scoped', 'D4 gate escalation'), 'd4_transport_authority': ('selected_not_granted', 'transport authority escalation'), 'canonical_product_implementation_authority': ('not_granted', 'Product authority escalation'), 'wave4_implementation_authority': ('not_granted', 'Wave4 authority escalation'), 'production_authority': ('none', 'production authority escalation'), 'c3_numeric_topology_authority': ('not_selected', 'C3 authority escalation')}.items():
            if state.get(field) != expected:
                errors.append(message)
    return errors


def _historical_state(state: dict) -> dict:
    projected = copy.deepcopy(state)
    by = {t["track_id"]: t for t in projected["tracks"]}
    d4b = by["D4-B"]
    d4b["candidate"] = None
    d4b["candidate_status"] = "not_selected"
    d4b["state"] = "evidence_complete_selection_pending"
    for track_id in ("D4-C", "D4-D"):
        track = by[track_id]
        track["candidate"] = None
        track["candidate_status"] = "not_selected"
        track["state"] = "candidate_selection_open"
        track["evidence_completed"] = []
        track["evidence_remaining"] = list(track["required_evidence"])
    return projected


def _historical_ledger(ledger: dict) -> dict:
    projected = copy.deepcopy(ledger)
    projected["candidate"] = None
    projected["candidate_status"] = "not_selected"
    projected["selection_state"] = "not_selected"
    return projected


def validate(root: Path) -> list[str]:
    state = json.loads((root / historical.STATE).read_text(encoding="utf-8"))
    current = _current_errors(state)
    ledger = _legacy_load(root, historical.LEDGER)
    if ledger.get("candidate") != {'serialization': {'surface_policy': 'explicit_surface_bound_profiles', 'internal_broker': 'protobuf_profile', 'outbound_webhook': 'bounded_json_plus_json_schema_profile'}, 'schema_catalog': 'hybrid_reviewed_git_plus_registry_catalog', 'contract_version': 'positive_integer_family_revision'} or ledger.get("candidate_status") != "selected_c2_profile" or ledger.get("selection_state") != "selected":
        current.append("D4-B ledger selection drift")
    if current:
        return current
    original = historical.load
    try:
        def projected_load(inner_root: Path, path: Path) -> dict:
            value = _legacy_load(inner_root, path)
            if path == historical.STATE:
                return _historical_state(value)
            if path == historical.LEDGER:
                return _historical_ledger(value)
            return value
        historical.load = projected_load
        return historical.validate(root)
    finally:
        historical.load = original


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else historical.ROOT
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4B_CATALOG_SOURCE_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4b_catalog_tooling_source=PASS historical_oracle=preserved current_d4b=5_of_5_selected current_d4c=9_of_9_selected current_d4d=5_of_5 d4wide=26_of_26")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
