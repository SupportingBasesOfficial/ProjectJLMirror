#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from evaluate_candidates import CANDIDATES, PROOFS, PROOF_CHECKS, evaluate_all  # noqa: E402

MANIFEST = Path("implementation/d4-eventing-async/source-evidence/d4-c-outbox-claim-dispatch-source.json")
PLAN = Path("implementation/d4-eventing-async/d4-c-candidate-evaluation-plan.json")
LEDGER = Path("implementation/d4-eventing-async/d4-c-evidence-plan.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")
AXIS = "outbox_claim_dispatch_and_ack_ambiguity"
DECISION = "OPEN-EVT-012"
EVIDENCE = "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity"
BASE = "aa36c4dcff1bed03178942ee05b6b8ef1fc03d08"
CURRENT_CREDITS = [
    "ack_after_durable_responsibility_and_lease_ambiguity",
    "quarantine_redrive_current_authority_and_dedup_preservation",
    "bounded_message_batch_compression_and_parser_limits",
    "scoped_content_equivalence_confidentiality_and_conflict_rejection",
]
EXPECTED_PROOFS = (
    "authoritative_mutation_and_required_outbox_fact_commit_atomically",
    "claim_takeover_is_fenced_and_does_not_create_concurrent_semantic_owners",
    "retry_workers_do_not_rewrite_immutable_fact_meaning",
    "broker_ack_ambiguity_retries_same_message_identity_and_semantic_content",
    "broker_outage_preserves_committed_backlog_without_loss",
    "dispatcher_restart_and_recovery_preserve_stable_message_identity_and_semantic_content",
    "cleanup_never_removes_the_last_recovery_authority_before_safe_horizon",
)
EXPECTED_PROOF_CHECKS = {
    EXPECTED_PROOFS[0]: (
        "atomic_commit_all_or_nothing",
        "business_snapshot_isolated_from_caller_mutation",
        "mutable_mapping_key_rejected",
        "scalar_subclass_mapping_key_rejected",
        "message_identity_fixed_at_commit",
    ),
    EXPECTED_PROOFS[1]: (
        "preexpiry_takeover_rejected",
        "expired_claim_cannot_dispatch",
        "inflight_takeover_fenced_before_broker_handoff",
        "post_handoff_takeover_completion_is_ambiguous_and_deduplicated",
        "broker_acceptance_atomic_under_concurrency",
        "stale_owner_fenced_after_takeover",
        "expired_claim_cannot_mark_terminal",
        "superseded_claim_cannot_mark_terminal",
        "inflight_terminal_takeover_cas_rejected",
        "terminal_claim_write_atomic_under_concurrency",
        "single_current_claim_owner",
    ),
    EXPECTED_PROOFS[2]: (
        "coherent_immutable_fact_rewrite_rejected",
        "retry_preserves_identity",
        "retry_preserves_semantic_content",
    ),
    EXPECTED_PROOFS[3]: (
        "ack_lost_retry_same_identity",
        "ack_lost_retry_same_content",
        "ambiguous_ack_cannot_mark_terminal",
        "foreign_identity_ack_cannot_mark_terminal",
        "foreign_content_ack_cannot_mark_terminal",
        "broker_conflicting_content_rejected",
    ),
    EXPECTED_PROOFS[4]: ("broker_outage_preserves_backlog", "unavailable_publish_cannot_mark_terminal"),
    EXPECTED_PROOFS[5]: (
        "restart_preserves_identity",
        "restart_preserves_semantic_content",
        "notification_is_non_authoritative",
    ),
    EXPECTED_PROOFS[6]: (
        "cleanup_blocks_uncertain_delivery",
        "cleanup_blocks_before_safe_horizon",
        "cleanup_after_safe_horizon_requires_terminal_evidence",
    ),
}
EXPECTED_SOURCE_ASSERTIONS = [
    "business_mutation_and_required_outbox_fact_share_one_atomic_commit_boundary",
    "authoritative_business_state_is_an_immutable_snapshot_not_a_caller_alias",
    "mapping_keys_are_exact_supported_builtin_immutable_scalars_or_rejected_before_commit",
    "outbox_message_identity_and_immutable_semantic_payload_are_fixed_at_commit",
    "claims_carry_monotonic_fence_tokens_and_stale_owners_cannot_dispatch_before_broker_handoff",
    "lease_expiry_is_ambiguity_and_takeover_never_creates_two_current_semantic_owners",
    "broker_handoff_revalidates_current_unexpired_claim_authority_before_cross_authority_effect",
    "post_handoff_claim_loss_is_delivery_ambiguity_not_retroactive_broker_cancellation_or_current_authority",
    "broker_dedup_lookup_conflict_check_and_acceptance_are_one_atomic_operation",
    "broker_acceptance_is_idempotent_for_same_message_identity_and_content_and_conflicts_fail_closed",
    "retry_changes_attempt_metadata_only_and_never_message_identity_or_immutable_fact_content",
    "ack_lost_after_broker_acceptance_is_retried_with_the_exact_same_message_identity_and_semantic_content",
    "terminal_delivery_evidence_requires_current_unexpired_claim_and_acked_receipt_for_same_message_identity_and_content",
    "terminal_delivery_claim_check_and_write_are_one_serialized_conditional_commit_boundary",
    "broker_unavailability_leaves_committed_outbox_backlog_durable_and_dispatchable_after_recovery",
    "dispatcher_restart_rehydrates_claim_state_from_durable_outbox_truth_and_preserves_message_identity_and_content",
    "notification_is_only_a_wakeup_hint_and_polling_or_durable_store_remains_recovery_authority",
    "cleanup_requires_terminal_delivery_evidence_and_safe_horizon_or_stronger_durable_recovery_authority",
    "missing_ack_or_delivery_evidence_is_uncertainty_not_cleanup_permission",
    "candidate_source_evidence_does_not_select_claim_sql_broker_retry_numeric_topology_or_production_mechanics",
]
EXPECTED_NON_AUTHORITY = {
    "d4c_mechanism_selection": "not_selected",
    "d4c_outbox_claim_profile_selection": "not_selected",
    "open_evt_012_ledger_credit": "uncredited",
    "d4c_ledger_credit": "current_4_of_9_unchanged",
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


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateKeyError(f"duplicate JSON member: {key}")
        out[key] = value
    return out


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        manifest = load(root / MANIFEST)
        plan = load(root / PLAN)
        ledger = load(root / LEDGER)
        state = load(root / STATE)
    except Exception as exc:
        return [str(exc)]

    expected_manifest_keys = {
        "schema_version", "gate_id", "track_id", "axis", "source_decision", "evidence_id", "canonical_base",
        "mode", "selection_state", "selection_authority", "current_run_auto_credit", "ledger_credit",
        "candidate_results", "equivalent_reviewed_profile", "required_proofs", "source_assertions", "non_authority",
    }
    if not isinstance(manifest, dict) or set(manifest) != expected_manifest_keys:
        errors.append("source manifest exact key schema drift")
    for key, expected in {
        "schema_version": 1, "gate_id": "D4", "track_id": "D4-C", "axis": AXIS,
        "source_decision": DECISION, "evidence_id": EVIDENCE, "canonical_base": BASE,
        "mode": "candidate_source_evidence_only", "selection_state": "not_selected",
        "selection_authority": "not_granted",
    }.items():
        if manifest.get(key) != expected or type(manifest.get(key)) is not type(expected):
            errors.append(f"source manifest scalar drift: {key}")
    if manifest.get("current_run_auto_credit") is not False or manifest.get("ledger_credit") != []:
        errors.append("source must remain non-promoting")
    if manifest.get("source_assertions") != EXPECTED_SOURCE_ASSERTIONS:
        errors.append("source assertions drift")
    if manifest.get("non_authority") != EXPECTED_NON_AUTHORITY:
        errors.append("source non-authority boundary drift")
    if tuple(PROOFS) != EXPECTED_PROOFS:
        errors.append("evaluator proof inventory drift")
    if PROOF_CHECKS != EXPECTED_PROOF_CHECKS:
        errors.append("evaluator proof-to-check map drift")

    axis = plan.get("axes", {}).get(AXIS) if isinstance(plan, dict) else None
    if not isinstance(axis, dict):
        errors.append("accepted OPEN-EVT-012 axis missing")
    else:
        if axis.get("decision") != DECISION or axis.get("evidence_id") != EVIDENCE:
            errors.append("axis decision/evidence drift")
        expected_candidates = [x for x in axis.get("candidate_classes", []) if x != "equivalent_reviewed_profile"]
        if expected_candidates != list(CANDIDATES):
            errors.append("candidate inventory drift")
        if axis.get("must_prove") != list(EXPECTED_PROOFS):
            errors.append("proof inventory drift")
        if manifest.get("required_proofs") != axis.get("must_prove"):
            errors.append("manifest required proofs must exactly match accepted candidate plan")

    expected_results = {candidate: "eligible_for_evidence_execution" for candidate in CANDIDATES}
    if manifest.get("candidate_results") != expected_results:
        errors.append("manifest candidate results drift")
    if manifest.get("equivalent_reviewed_profile") != "insufficient_evidence":
        errors.append("equivalent profile drift")

    runtime = evaluate_all()
    if runtime.get("candidate_results") != expected_results:
        errors.append("runtime candidate results drift")
    if runtime.get("selection") != "not_selected" or runtime.get("selection_authority") != "not_granted":
        errors.append("runtime selection leakage")
    if runtime.get("ledger_credit") != [] or runtime.get("current_run_auto_credit") is not False:
        errors.append("runtime auto-credit leakage")
    if runtime.get("equivalent_reviewed_profile") != "insufficient_evidence":
        errors.append("runtime equivalent profile drift")

    expected_check_names = {name for names in EXPECTED_PROOF_CHECKS.values() for name in names}
    checks = runtime.get("checks")
    if not isinstance(checks, dict) or set(checks) != set(CANDIDATES):
        errors.append("runtime candidate check inventory drift")
    else:
        for candidate, candidate_checks in checks.items():
            if not isinstance(candidate_checks, dict) or set(candidate_checks) != expected_check_names:
                errors.append(f"runtime exact check inventory drift for {candidate}")
            elif not all(candidate_checks.values()):
                errors.append(f"runtime check failure for {candidate}")

    proofs = runtime.get("proof_results")
    if not isinstance(proofs, dict) or set(proofs) != set(CANDIDATES):
        errors.append("runtime proof inventory drift")
    else:
        for candidate, candidate_proofs in proofs.items():
            if not isinstance(candidate_proofs, dict) or set(candidate_proofs) != set(EXPECTED_PROOFS):
                errors.append(f"runtime exact proof inventory drift for {candidate}")
            elif not all(candidate_proofs.values()):
                errors.append(f"runtime proof failure for {candidate}")

    if ledger.get("ledger_credit_state") != "four_of_nine" or ledger.get("credited_evidence") != CURRENT_CREDITS:
        errors.append("current D4-C ledger drift")
    if EVIDENCE not in ledger.get("remaining_evidence", []) or len(ledger.get("remaining_evidence", [])) != 5:
        errors.append("OPEN-EVT-012 must remain uncredited")

    tracks_raw = state.get("tracks") if isinstance(state, dict) else None
    if not isinstance(tracks_raw, list) or len(tracks_raw) != 4:
        errors.append("global D4 track structure drift")
        return errors
    tracks = {t.get("track_id"): t for t in tracks_raw if isinstance(t, dict)}
    if set(tracks) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
        errors.append("global D4 track identity drift")
        return errors
    d4c = tracks["D4-C"]
    if d4c.get("evidence_completed") != CURRENT_CREDITS or d4c.get("evidence_remaining") != ledger.get("remaining_evidence"):
        errors.append("D4-C current state drift")
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open":
        errors.append("D4-C candidate leakage")
    if tracks["D4-D"].get("evidence_completed") != [] or tracks["D4-D"].get("candidate") is not None:
        errors.append("D4-D leakage")
    if sum(len(t.get("evidence_completed", [])) for t in tracks_raw) != 16:
        errors.append("D4-wide evidence count drift")
    for key, expected in {
        "gate_state": "scoped", "d4_transport_authority": "selected_not_granted",
        "canonical_product_implementation_authority": "not_granted", "wave4_implementation_authority": "not_granted",
        "production_authority": "none", "c3_numeric_topology_authority": "not_selected",
    }.items():
        if state.get(key) != expected:
            errors.append(f"global authority drift: {key}")
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else ROOT
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4C_OPEN_EVT_012_SOURCE_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4c_open_evt_012_source=PASS candidates=3 proofs=7 proof_inventory=exact checks=33 source_auto_credit=false current_d4c=4_of_9 current_d4wide=16_of_26 selection=not_selected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
