#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
SOURCE = ROOT / "implementation/d4-eventing-async/source-evidence/d4-c-scoped-content-equivalence-source.json"
PLAN = ROOT / "implementation/d4-eventing-async/d4-c-candidate-evaluation-plan.json"
LEDGER = ROOT / "implementation/d4-eventing-async/d4-c-evidence-plan.json"
STATE = ROOT / "implementation/d4-eventing-async/state-manifest.json"
RESULTS = ROOT / "runtime-evidence/candidate-results.json"

EXPECTED_CANDIDATES = {
    "canonical_collision_resistant_fingerprint_profile": "ineligible_by_contract",
    "keyed_authenticated_digest_profile": "eligible_for_evidence_execution",
    "protected_retained_immutable_original_profile": "eligible_for_evidence_execution",
    "hybrid_equivalence_authority_profile": "eligible_for_evidence_execution",
}
EXPECTED_CREDITS = [
    "ack_after_durable_responsibility_and_lease_ambiguity",
    "quarantine_redrive_current_authority_and_dedup_preservation",
    "bounded_message_batch_compression_and_parser_limits",
    "scoped_content_equivalence_confidentiality_and_conflict_rejection",
    "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity",
    "producer_generation_nonresurrection_across_failover_restore",
]
EXPECTED_NON_AUTHORITY = {
    "d4c_mechanism_selection": "not_selected",
    "d4c_content_equivalence_profile_selection": "not_selected",
    "open_evt_011_ledger_credit": "uncredited",
    "d4c_ledger_credit": "current_3_of_9_unchanged",
    "d4d_ledger_credit": "0_of_5",
    "d4_gate": "scoped",
    "d4_transport_authority": "selected_not_granted",
    "canonical_product_implementation_authority": "not_granted",
    "wave4_implementation_authority": "not_granted",
    "production_authority": "none",
    "c3_numeric_topology_authority": "not_selected",
}
PROOF_TO_CHECKS = {
    "dedup_identity_is_consumer_contract_trusted_message_identity_scope_and_message_id_or_equivalent": ("dedup_identity_is_scoped_tuple",),
    "equivalence_is_evaluated_only_after_trusted_consumer_contract_and_message_scope_identity": ("trusted_identity_precedes_equivalence_work",),
    "repeated_scoped_identity_is_benign_duplicate_only_with_durable_equivalence_evidence": ("durable_equal_repeat_is_benign_duplicate", "missing_or_unverifiable_evidence_is_uncertainty"),
    "every_immutable_semantic_field_required_for_same_id_meaning_is_covered": ("all_required_immutable_semantic_fields_are_covered",),
    "same_scoped_id_with_different_immutable_content_fails_closed": ("conflicting_same_scoped_identity_fails_closed",),
    "comparison_evidence_uses_the_same_canonical_structured_interpretation_as_protected_contract_validation": ("same_canonical_interpretation_drives_validation_and_evidence",),
    "comparison_profile_and_version_are_stable_and_historically_recoverable": ("profile_version_is_explicit_and_historically_recoverable", "keyed_verifier_generation_is_explicit_and_recoverable"),
    "low_entropy_confidential_values_do_not_create_dictionary_or_cross_scope_equality_oracles": ("low_entropy_confidentiality_is_scope_safe",),
    "comparison_evidence_is_never_authorization_routing_ordering_or_bearer_authority": ("comparison_evidence_has_no_forbidden_authority",),
    "co_resident_inbox_and_effect_completion_is_atomic": ("co_resident_inbox_and_effect_are_atomic",),
    "cross_authority_effects_use_stable_operation_and_result_reconciliation": ("cross_authority_effect_uses_stable_operation_and_reconciliation",),
    "historical_equivalence_authority_survives_supported_horizon_or_is_replaced_by_governed_equality_preserving_migration": ("historical_authority_survives_or_migrates_equality_preserving",),
    "payload_erasure_cannot_remove_last_required_equivalence_authority_within_supported_horizon": ("payload_erasure_preserves_last_equivalence_authority",),
    "missing_or_unverifiable_equivalence_evidence_is_uncertainty_not_duplicate_success": ("missing_or_unverifiable_evidence_is_uncertainty",),
    "verification_work_is_bounded_and_access_controlled": ("verification_is_bounded_and_access_controlled",),
}

def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def require(condition: bool, message: str) -> None:
    if not condition: raise AssertionError(message)

def main() -> int:
    source, plan, ledger, state = load(SOURCE), load(PLAN), load(LEDGER), load(STATE)
    results = load(RESULTS) if RESULTS.exists() else None
    axis = plan["axes"]["scoped_content_equivalence_authority"]
    require(source["schema_version"] == 1, "source schema drift")
    require(source["gate_id"] == "D4" and source["track_id"] == "D4-C", "wrong gate/track")
    require(source["axis"] == "scoped_content_equivalence_authority", "wrong axis")
    require(source["source_decision"] == axis["decision"] == "OPEN-EVT-011", "decision mismatch")
    require(source["evidence_id"] == axis["evidence_id"] == "scoped_content_equivalence_confidentiality_and_conflict_rejection", "evidence id mismatch")
    require(source["canonical_base"] == "3ee199dea84893571f09e20bfefdaa2903725450", "canonical base drift")
    require(source["mode"] == "candidate_source_evidence_only", "source mode escalation")
    require(source["selection_state"] == "not_selected", "source selected candidate")
    require(source["selection_authority"] == "not_granted", "source granted selection authority")
    require(source["current_run_auto_credit"] is False and source["ledger_credit"] == [], "source auto-credit escalation")
    require(source["candidate_results"] == EXPECTED_CANDIDATES, "candidate classification mismatch")
    require(source["equivalent_reviewed_profile"] == "insufficient_evidence", "equivalent profile must remain insufficient")
    require(source["required_proofs"] == axis["must_prove"], "must-prove contract drift")
    require(set(PROOF_TO_CHECKS) == set(axis["must_prove"]), "proof-to-runtime-check map does not cover exact must-prove contract")
    require(set(axis["candidate_classes"]) == set(EXPECTED_CANDIDATES) | {"equivalent_reviewed_profile"}, "candidate class drift")
    require(source["non_authority"] == EXPECTED_NON_AUTHORITY, "source non-authority boundary drift")
    required_assertions = {
        "dedup_key_is_exactly_consumer_contract_trusted_message_identity_scope_and_message_id",
        "untrusted_contract_or_scope_is_rejected_before_equivalence_evaluation",
        "immutable_semantic_content_is_canonicalized_once_and_the_same_bytes_feed_contract_interpretation_and_equivalence_evidence",
        "same_scoped_identity_with_equal_immutable_content_is_duplicate_only_when_durable_evidence_is_present_and_verifiable",
        "same_scoped_identity_with_conflicting_immutable_content_fails_closed_with_integrity_conflict",
        "missing_unknown_or_unverifiable_historical_profile_is_uncertainty_not_duplicate_success",
        "unkeyed_cross_scope_fingerprint_is_contract_ineligible_for_low_entropy_confidential_content",
        "keyed_digest_uses_scope_separated_authenticated_evidence_so_equal_low_entropy_content_does_not_expose_cross_scope_equality",
        "keyed_digest_records_explicit_verifier_key_generation_and_unknown_or_retired_generation_is_uncertainty",
        "protected_retained_original_comparison_requires_explicit_comparison_access_and_does_not_expose_a_bearer_or_routing_token",
        "hybrid_profile_retains_independent_equality_authority_across_governed_payload_erasure",
        "equivalence_records_contain_no_authorization_routing_ordering_or_bearer_authority",
        "co_resident_inbox_and_effect_completion_commit_or_roll_back_as_one_transaction",
        "cross_authority_effects_use_stable_operation_identity_and_durable_result_reconciliation",
        "profile_versions_are_explicit_and_equality_preserving_migration_is_verified_before_historical_authority_replacement",
        "verification_is_access_controlled_and_bounded_by_a_noncanonical_evidence_fixture_limit",
        "candidate_source_evidence_does_not_select_a_digest_key_store_database_effect_transport_or_production_topology",
    }
    require(set(source["source_assertions"]) == required_assertions, "source assertion coverage drift")
    require(ledger["ledger_credit_state"] == "six_of_nine", "current D4-C ledger must be 6/9 after OPEN-EVT-013 promotion")
    require(ledger["credited_evidence"] == EXPECTED_CREDITS, "current D4-C credits changed")
    require(source["evidence_id"] not in ledger["remaining_evidence"], "OPEN-EVT-011 must remain separately promoted")
    require(len(ledger["remaining_evidence"]) == 3, "D4-C remaining count drift")
    require(ledger["candidate"] is None and ledger["candidate_status"] == "not_selected", "D4-C candidate selected")
    require(ledger["selection_state"] == "not_selected" and ledger["selection_authority"] == "not_granted", "D4-C selection authority changed")
    require(ledger["current_run_auto_credit"] is False, "ledger auto-credit changed")
    tracks = {track["track_id"]:track for track in state["tracks"]}
    d4c,d4d = tracks["D4-C"],tracks["D4-D"]
    require(d4c["evidence_completed"] == EXPECTED_CREDITS, "state D4-C credits changed")
    require(d4c["evidence_remaining"] == ledger["remaining_evidence"], "state/ledger D4-C mismatch")
    require(d4c["candidate"] is None and d4c["candidate_status"] == "not_selected" and d4c["state"] == "candidate_selection_open", "D4-C state escalated")
    require(d4d["evidence_completed"] == [] and d4d["candidate"] is None and d4d["candidate_status"] == "not_selected", "D4-D changed")
    require(sum(len(track["evidence_completed"]) for track in state["tracks"]) == 18, "D4-wide must be 18/26")
    require(state["gate_state"] == "scoped", "D4 gate escalated")
    require(state["d4_transport_authority"] == "selected_not_granted", "transport authority changed")
    require(state["canonical_product_implementation_authority"] == "not_granted", "Product authority changed")
    require(state["wave4_implementation_authority"] == "not_granted", "Wave4 authority changed")
    require(state["production_authority"] == "none", "production authority changed")
    require(state["c3_numeric_topology_authority"] == "not_selected", "C3 authority changed")
    if results is not None:
        require(results["source_decision"] == source["source_decision"], "runtime decision mismatch")
        require(results["evidence_id"] == source["evidence_id"], "runtime evidence mismatch")
        require(results["candidate_results"] == EXPECTED_CANDIDATES, "runtime candidate classification mismatch")
        require(results["equivalent_reviewed_profile"] == "insufficient_evidence", "runtime equivalent profile drift")
        require(results["selection"] == "not_selected" and results["selection_authority"] == "not_granted", "runtime selection escalation")
        require(results["ledger_credit"] == [] and results["current_run_auto_credit"] is False, "runtime auto-credit escalation")
        fingerprint = "canonical_collision_resistant_fingerprint_profile"
        confidentiality_proof = "low_entropy_confidential_values_do_not_create_dictionary_or_cross_scope_equality_oracles"
        for candidate, status in EXPECTED_CANDIDATES.items():
            checks = results["checks"][candidate]
            for proof, check_names in PROOF_TO_CHECKS.items():
                proven = all(checks[name] is True for name in check_names)
                if status == "eligible_for_evidence_execution": require(proven, f"eligible candidate lacks proof {proof}: {candidate}")
                elif candidate == fingerprint and proof == confidentiality_proof: require(not proven, "unkeyed fingerprint must fail confidentiality proof")
                elif candidate == fingerprint: require(proven, f"fingerprint candidate has unrelated failure outside confidentiality proof: {proof}")
    print("d4c_open_evt_011_source_validation=PASS source_snapshot=3_of_9_unchanged proof_map=15_of_15 fingerprint=ineligible_only_by_confidentiality keyed_digest=eligible retained_original=eligible hybrid=eligible current_d4c=6/9 d4wide=18/26 selection=none authorities=unchanged")
    return 0

if __name__ == "__main__": raise SystemExit(main())
