#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

CANDIDATES = (
    "canonical_event_history_store_profile",
    "broker_retained_log_plus_authoritative_history_index_profile",
    "hybrid_history_archive_plus_replay_controller_profile",
)

PROOFS = (
    "replay_is_privileged_audited_bounded_and_currently_authorized",
    "replayed_message_preserves_original_identity_and_immutable_semantic_meaning",
    "replay_retains_or_recovers_required_equivalence_and_historical_verifier_authority",
    "unavailable_historical_comparison_authority_blocks_or_reconciles_duplicate_sensitive_effects_instead_of_trusting_identity_alone",
    "irreversible_effects_cannot_be_repeated_by_disabling_dedup",
    "projection_rebuild_uses_isolated_generation_or_target",
    "replay_cannot_exceed_safe_schema_data_dedup_equivalence_and_recovery_evidence",
    "history_storage_product_identity_does_not_become_message_or_contract_identity",
)

class ContractViolation(RuntimeError):
    pass

@dataclass(frozen=True)
class HistoricalMessage:
    tenant_id: str
    contract_id: str
    message_id: str
    semantic_content: str
    schema_version: int
    equivalence_profile: str
    verifier_version: str

@dataclass(frozen=True)
class ReplayRequest:
    actor: str
    authorized: bool
    max_messages: int
    target: str
    replay_generation: str
    disable_dedup: bool = False

class ReplayController:
    def __init__(self, candidate: str) -> None:
        if candidate not in CANDIDATES:
            raise ValueError(candidate)
        self.candidate = candidate
        self.audit: list[dict[str, Any]] = []
        self.completed_irreversible: set[tuple[str, str, str]] = set()

    def replay(self, request: ReplayRequest, messages: list[HistoricalMessage], *,
               verifier_available: bool = True, equivalence_available: bool = True,
               recovery_evidence_available: bool = True, schema_supported: bool = True,
               data_access_allowed: bool = True, duplicate_sensitive: bool = False,
               irreversible: bool = False, storage_identity: str = "history-store-a") -> list[HistoricalMessage]:
        self.audit.append({"actor": request.actor, "target": request.target, "count": len(messages), "authorized": request.authorized})
        if not request.authorized or not request.actor:
            raise ContractViolation("current_privileged_authority_required")
        if request.max_messages <= 0 or len(messages) > request.max_messages:
            raise ContractViolation("replay_bound_exceeded")
        if request.disable_dedup:
            raise ContractViolation("dedup_bypass_forbidden")
        if request.target == "production-current" or not request.replay_generation:
            raise ContractViolation("isolated_replay_target_required")
        if not schema_supported or not data_access_allowed or not recovery_evidence_available:
            raise ContractViolation("safe_replay_evidence_incomplete")
        if duplicate_sensitive and (not verifier_available or not equivalence_available):
            raise ContractViolation("historical_comparison_authority_unavailable")

        emitted: list[HistoricalMessage] = []
        for message in messages:
            if not verifier_available or not equivalence_available:
                if irreversible:
                    raise ContractViolation("effect_safety_authority_unavailable")
            effect_key = (message.tenant_id, message.contract_id, message.message_id)
            if irreversible and effect_key in self.completed_irreversible:
                raise ContractViolation("irreversible_effect_already_completed")
            # Storage identity is deliberately unused as message or contract identity.
            _ = storage_identity
            emitted.append(message)
            if irreversible:
                self.completed_irreversible.add(effect_key)
        return emitted

def blocked(fn: Any, code: str) -> bool:
    try:
        fn()
    except ContractViolation as exc:
        return str(exc) == code
    return False

def sample() -> HistoricalMessage:
    return HistoricalMessage("tenant-a", "orders.v1", "msg-001", '{"order":"42","state":"paid"}', 1, "eq-v1", "reader-v1")

def check_candidate(candidate: str) -> dict[str, bool]:
    controller = ReplayController(candidate)
    msg = sample()
    req = ReplayRequest("ops-admin", True, 10, "projection-shadow", "replay-gen-001")
    replayed = controller.replay(req, [msg], duplicate_sensitive=True)
    checks = {
        "authorized_replay_audited": replayed == [msg] and len(controller.audit) == 1,
        "unauthorized_replay_rejected": blocked(lambda: controller.replay(ReplayRequest("x", False, 10, "shadow", "g"), [msg]), "current_privileged_authority_required"),
        "bounded_replay_rejected": blocked(lambda: controller.replay(ReplayRequest("x", True, 0, "shadow", "g"), [msg]), "replay_bound_exceeded"),
        "original_identity_preserved": replayed[0].message_id == msg.message_id and replayed[0].contract_id == msg.contract_id and replayed[0].tenant_id == msg.tenant_id,
        "immutable_semantic_meaning_preserved": replayed[0].semantic_content == msg.semantic_content and replayed[0].schema_version == msg.schema_version,
        "equivalence_and_verifier_required": blocked(lambda: controller.replay(req, [msg], verifier_available=False, duplicate_sensitive=True), "historical_comparison_authority_unavailable"),
        "missing_comparison_authority_blocks_duplicate_sensitive_effect": blocked(lambda: controller.replay(req, [msg], equivalence_available=False, duplicate_sensitive=True), "historical_comparison_authority_unavailable"),
        "dedup_bypass_rejected": blocked(lambda: controller.replay(ReplayRequest("x", True, 10, "shadow", "g", True), [msg]), "dedup_bypass_forbidden"),
        "irreversible_effect_not_repeatable": False,
        "projection_target_isolated": blocked(lambda: controller.replay(ReplayRequest("x", True, 10, "production-current", "g"), [msg]), "isolated_replay_target_required"),
        "schema_data_recovery_bounds_enforced": all((
            blocked(lambda: controller.replay(req, [msg], schema_supported=False), "safe_replay_evidence_incomplete"),
            blocked(lambda: controller.replay(req, [msg], data_access_allowed=False), "safe_replay_evidence_incomplete"),
            blocked(lambda: controller.replay(req, [msg], recovery_evidence_available=False), "safe_replay_evidence_incomplete"),
        )),
        "storage_identity_not_message_identity": controller.replay(req, [msg], storage_identity="broker-x")[0].message_id == msg.message_id,
        "storage_identity_not_contract_identity": controller.replay(req, [msg], storage_identity="archive-y")[0].contract_id == msg.contract_id,
    }
    irreversible_controller = ReplayController(candidate)
    irreversible_controller.replay(req, [msg], irreversible=True)
    checks["irreversible_effect_not_repeatable"] = blocked(lambda: irreversible_controller.replay(req, [msg], irreversible=True), "irreversible_effect_already_completed")
    return checks

PROOF_CHECKS = {
    PROOFS[0]: ("authorized_replay_audited", "unauthorized_replay_rejected", "bounded_replay_rejected"),
    PROOFS[1]: ("original_identity_preserved", "immutable_semantic_meaning_preserved"),
    PROOFS[2]: ("equivalence_and_verifier_required",),
    PROOFS[3]: ("missing_comparison_authority_blocks_duplicate_sensitive_effect",),
    PROOFS[4]: ("dedup_bypass_rejected", "irreversible_effect_not_repeatable"),
    PROOFS[5]: ("projection_target_isolated",),
    PROOFS[6]: ("schema_data_recovery_bounds_enforced",),
    PROOFS[7]: ("storage_identity_not_message_identity", "storage_identity_not_contract_identity"),
}

def evaluate() -> dict[str, Any]:
    candidate_checks = {c: check_candidate(c) for c in CANDIDATES}
    proof_results = {c: {p: all(candidate_checks[c][name] for name in names) for p, names in PROOF_CHECKS.items()} for c in CANDIDATES}
    candidate_results = {c: "eligible_for_evidence_execution" if all(candidate_checks[c].values()) and all(proof_results[c].values()) else "insufficient_evidence" for c in CANDIDATES}
    return {"schema_version": 1, "source_decision": "OPEN-EVT-014", "evidence_id": "privileged_bounded_replay_with_original_identity_and_effect_safety", "candidate_results": candidate_results, "proof_results": proof_results, "check_results": candidate_checks, "selection": "not_selected", "selection_authority": "not_granted", "ledger_credit": [], "current_run_auto_credit": False}

if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2, sort_keys=True))
