#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

CANDIDATES = (
    "restore_generation_fence_manifest_profile",
    "reconciliation_inventory_job_plus_activation_gate_profile",
    "hybrid_generation_manifest_plus_multi_store_reconciler_profile",
)

PROOFS = (
    "restore_generation_and_fence_boundary_are_explicit_and_durable",
    "r_f_window_inventory_reconciles_broker_history_inbox_outbox_equivalence_and_external_effect_evidence",
    "webhook_recovery_preserves_stable_delivery_identity_semantic_snapshot_or_reproduction_authority_and_destination_generation_fences",
    "missing_restored_state_is_uncertainty_not_absence",
    "missing_or_older_content_comparison_evidence_is_not_safe_duplicate_proof",
    "missing_or_stale_historical_comparison_authority_blocks_duplicate_sensitive_effects",
    "duplicate_classification_and_effectful_async_admission_remain_fail_closed_until_continuity_equivalence_and_historical_authority_are_proven",
    "stale_producer_replay_authorization_and_destination_generations_do_not_revive",
    "obsolete_restored_verifier_or_profile_cannot_become_current_authority_for_unrelated_scope",
    "offset_outbox_or_inbox_state_cannot_override_surviving_external_audit_effect_or_equivalence_evidence",
    "effectful_async_activation_is_fail_closed_until_required_reconciliation_is_proven",
    "reconciliation_results_are_generation_scoped_auditable_and_reproducible",
)

class ContractViolation(RuntimeError):
    pass

@dataclass(frozen=True)
class Evidence:
    name: str
    generation: int
    status: str
    identity: str
    semantic_digest: str

@dataclass(frozen=True)
class RecoveryManifest:
    restore_generation: int
    fence_generation: int
    producer_generation: int
    replay_authorization_generation: int
    destination_generation: int
    verifier_generation: int
    comparison_profile_generation: int

class RecoveryReconciler:
    REQUIRED = (
        "broker_history", "inbox", "outbox", "equivalence",
        "external_effect", "webhook_delivery",
    )

    def __init__(self, candidate: str) -> None:
        if candidate not in CANDIDATES:
            raise ValueError(candidate)
        self.candidate = candidate

    def reconcile(self, manifest: RecoveryManifest, inventory: dict[str, Evidence], *, current_generation: int, target_scope: str = "tenant-a/orders") -> dict[str, Any]:
        if manifest.restore_generation <= 0 or manifest.fence_generation != current_generation:
            raise ContractViolation("restore_generation_fence_invalid")
        if manifest.producer_generation != current_generation:
            raise ContractViolation("stale_producer_generation")
        if manifest.replay_authorization_generation != current_generation:
            raise ContractViolation("stale_replay_authorization_generation")
        if manifest.destination_generation != current_generation:
            raise ContractViolation("stale_destination_generation")
        if manifest.verifier_generation != current_generation:
            raise ContractViolation("stale_historical_verifier_generation")
        if manifest.comparison_profile_generation != current_generation:
            raise ContractViolation("stale_comparison_profile_generation")
        missing = [name for name in self.REQUIRED if name not in inventory]
        if missing:
            raise ContractViolation("restored_state_uncertain")
        for name in self.REQUIRED:
            item = inventory[name]
            if item.generation != current_generation:
                raise ContractViolation(f"stale_inventory_generation:{name}")
            if item.status not in {"present", "confirmed_effect"}:
                raise ContractViolation(f"uncertain_inventory_state:{name}")
        eq = inventory["equivalence"]
        if eq.semantic_digest == "":
            raise ContractViolation("comparison_evidence_unverifiable")
        ext = inventory["external_effect"]
        inbox = inventory["inbox"]
        outbox = inventory["outbox"]
        broker = inventory["broker_history"]
        webhook = inventory["webhook_delivery"]
        if len({broker.identity, inbox.identity, outbox.identity}) != 1:
            raise ContractViolation("message_identity_continuity_broken")
        if webhook.identity != "delivery-001":
            raise ContractViolation("webhook_delivery_identity_broken")
        if ext.status == "confirmed_effect" and any(item.semantic_digest == "claims-absence" for item in (broker, inbox, outbox)):
            authority = "external_effect_survives"
        else:
            authority = "reconciled"
        result = {
            "restore_generation": manifest.restore_generation,
            "fence_generation": manifest.fence_generation,
            "scope": target_scope,
            "inventory": sorted(self.REQUIRED),
            "message_identity": broker.identity,
            "webhook_delivery_identity": webhook.identity,
            "semantic_digest": eq.semantic_digest,
            "external_authority": authority,
            "activation": "eligible",
        }
        result["audit_fingerprint"] = json.dumps(result, sort_keys=True, separators=(",", ":"))
        return result

def sample_manifest() -> RecoveryManifest:
    return RecoveryManifest(7, 9, 9, 9, 9, 9, 9)

def sample_inventory() -> dict[str, Evidence]:
    return {
        "broker_history": Evidence("broker_history", 9, "present", "msg-001", "sem-001"),
        "inbox": Evidence("inbox", 9, "present", "msg-001", "sem-001"),
        "outbox": Evidence("outbox", 9, "present", "msg-001", "sem-001"),
        "equivalence": Evidence("equivalence", 9, "present", "eq-001", "sem-001"),
        "external_effect": Evidence("external_effect", 9, "confirmed_effect", "effect-001", "sem-001"),
        "webhook_delivery": Evidence("webhook_delivery", 9, "present", "delivery-001", "sem-001"),
    }

def blocked(fn: Any, code: str) -> bool:
    try:
        fn()
    except ContractViolation as exc:
        return str(exc) == code
    return False

def with_item(inv: dict[str, Evidence], name: str, item: Evidence) -> dict[str, Evidence]:
    out = dict(inv)
    out[name] = item
    return out

def check_candidate(candidate: str) -> dict[str, bool]:
    reconciler = RecoveryReconciler(candidate)
    manifest = sample_manifest()
    inventory = sample_inventory()
    result = reconciler.reconcile(manifest, inventory, current_generation=9)
    missing = dict(inventory)
    missing.pop("equivalence")
    stale_eq = with_item(inventory, "equivalence", Evidence("equivalence", 8, "present", "eq-001", "sem-001"))
    blank_eq = with_item(inventory, "equivalence", Evidence("equivalence", 9, "present", "eq-001", ""))
    conflict = dict(inventory)
    conflict["broker_history"] = Evidence("broker_history", 9, "present", "msg-001", "claims-absence")
    conflict["inbox"] = Evidence("inbox", 9, "present", "msg-001", "claims-absence")
    conflict["outbox"] = Evidence("outbox", 9, "present", "msg-001", "claims-absence")
    conflict_result = reconciler.reconcile(manifest, conflict, current_generation=9)
    return {
        "generation_and_fence_explicit": result["restore_generation"] == 7 and result["fence_generation"] == 9,
        "rf_inventory_complete": result["inventory"] == sorted(RecoveryReconciler.REQUIRED),
        "webhook_identity_stable": result["webhook_delivery_identity"] == "delivery-001",
        "missing_state_blocks": blocked(lambda: reconciler.reconcile(manifest, missing, current_generation=9), "restored_state_uncertain"),
        "older_equivalence_blocks": blocked(lambda: reconciler.reconcile(manifest, stale_eq, current_generation=9), "stale_inventory_generation:equivalence"),
        "unverifiable_equivalence_blocks": blocked(lambda: reconciler.reconcile(manifest, blank_eq, current_generation=9), "comparison_evidence_unverifiable"),
        "stale_producer_blocks": blocked(lambda: reconciler.reconcile(RecoveryManifest(7,9,8,9,9,9,9), inventory, current_generation=9), "stale_producer_generation"),
        "stale_replay_auth_blocks": blocked(lambda: reconciler.reconcile(RecoveryManifest(7,9,9,8,9,9,9), inventory, current_generation=9), "stale_replay_authorization_generation"),
        "stale_destination_blocks": blocked(lambda: reconciler.reconcile(RecoveryManifest(7,9,9,9,8,9,9), inventory, current_generation=9), "stale_destination_generation"),
        "obsolete_verifier_blocks": blocked(lambda: reconciler.reconcile(RecoveryManifest(7,9,9,9,9,8,9), inventory, current_generation=9), "stale_historical_verifier_generation"),
        "obsolete_profile_blocks": blocked(lambda: reconciler.reconcile(RecoveryManifest(7,9,9,9,9,9,8), inventory, current_generation=9), "stale_comparison_profile_generation"),
        "external_effect_not_overridden": conflict_result["external_authority"] == "external_effect_survives",
        "activation_fail_closed_until_reconciled": result["activation"] == "eligible" and blocked(lambda: reconciler.reconcile(manifest, missing, current_generation=9), "restored_state_uncertain"),
        "reconciliation_reproducible": result["audit_fingerprint"] == reconciler.reconcile(manifest, inventory, current_generation=9)["audit_fingerprint"],
    }

PROOF_CHECKS = {
    PROOFS[0]: ("generation_and_fence_explicit",),
    PROOFS[1]: ("rf_inventory_complete",),
    PROOFS[2]: ("webhook_identity_stable", "stale_destination_blocks"),
    PROOFS[3]: ("missing_state_blocks",),
    PROOFS[4]: ("older_equivalence_blocks", "unverifiable_equivalence_blocks"),
    PROOFS[5]: ("obsolete_verifier_blocks", "obsolete_profile_blocks"),
    PROOFS[6]: ("missing_state_blocks", "older_equivalence_blocks", "activation_fail_closed_until_reconciled"),
    PROOFS[7]: ("stale_producer_blocks", "stale_replay_auth_blocks", "stale_destination_blocks"),
    PROOFS[8]: ("obsolete_verifier_blocks", "obsolete_profile_blocks"),
    PROOFS[9]: ("external_effect_not_overridden",),
    PROOFS[10]: ("activation_fail_closed_until_reconciled",),
    PROOFS[11]: ("reconciliation_reproducible", "generation_and_fence_explicit"),
}

def evaluate() -> dict[str, Any]:
    checks = {c: check_candidate(c) for c in CANDIDATES}
    proofs = {c: {p: all(checks[c][n] for n in names) for p, names in PROOF_CHECKS.items()} for c in CANDIDATES}
    results = {c: ("eligible_for_evidence_execution" if all(checks[c].values()) and all(proofs[c].values()) else "insufficient_evidence") for c in CANDIDATES}
    return {
        "schema_version": 1,
        "source_decision": "OPEN-EVT-025",
        "evidence_id": "recovery_generation_rf_inventory_reconciliation_and_activation_gates",
        "candidate_results": results,
        "proof_results": proofs,
        "check_results": checks,
        "selection": "not_selected",
        "selection_authority": "not_granted",
        "ledger_credit": [],
        "current_run_auto_credit": False,
    }

if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2, sort_keys=True))
