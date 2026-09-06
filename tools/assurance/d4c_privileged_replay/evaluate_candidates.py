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
    authority_epoch: str
    max_messages: int
    target: str
    replay_generation: str
    disable_dedup: bool = False


class ReplayController:
    CURRENT_AUTHORITY_EPOCH = "replay-auth-epoch-2"

    def __init__(self, candidate: str) -> None:
        if candidate not in CANDIDATES:
            raise ValueError(candidate)
        self.candidate = candidate
        self.audit: list[dict[str, Any]] = []
        self.completed_irreversible: set[tuple[str, str, str]] = set()
        self.current_privileged_actors = frozenset({"ops-admin"})

    def replay(
        self,
        request: ReplayRequest,
        messages: list[HistoricalMessage],
        *,
        verifier_available: bool = True,
        equivalence_available: bool = True,
        recovery_evidence_available: bool = True,
        schema_supported: bool = True,
        data_access_allowed: bool = True,
        duplicate_sensitive: bool = False,
        irreversible: bool = False,
        storage_identity: str = "history-store-a",
    ) -> list[HistoricalMessage]:
        self.audit.append(
            {
                "actor": request.actor,
                "authority_epoch": request.authority_epoch,
                "target": request.target,
                "count": len(messages),
            }
        )
        if (
            request.actor not in self.current_privileged_actors
            or request.authority_epoch != self.CURRENT_AUTHORITY_EPOCH
        ):
            raise ContractViolation("current_privileged_authority_required")
        if request.max_messages <= 0 or len(messages) > request.max_messages:
            raise ContractViolation("replay_bound_exceeded")
        if request.disable_dedup:
            raise ContractViolation("dedup_bypass_forbidden")
        if request.target == "production-current" or not request.replay_generation:
            raise ContractViolation("isolated_replay_target_required")
        if not schema_supported or not data_access_allowed or not recovery_evidence_available:
            raise ContractViolation("safe_replay_evidence_incomplete")
        if not verifier_available or not equivalence_available:
            if duplicate_sensitive:
                raise ContractViolation("historical_comparison_authority_unavailable")
            raise ContractViolation("replay_history_authority_unavailable")

        emitted: list[HistoricalMessage] = []
        for message in messages:
            if not message.equivalence_profile or not message.verifier_version:
                raise ContractViolation("historical_verifier_metadata_missing")
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
    return HistoricalMessage(
        "tenant-a",
        "orders.v1",
        "msg-001",
        '{"order":"42","state":"paid"}',
        1,
        "eq-v1",
        "reader-v1",
    )


def request(*, actor: str = "ops-admin", epoch: str = ReplayController.CURRENT_AUTHORITY_EPOCH,
            max_messages: int = 10, target: str = "projection-shadow",
            generation: str = "replay-gen-001", disable_dedup: bool = False) -> ReplayRequest:
    return ReplayRequest(actor, epoch, max_messages, target, generation, disable_dedup)


def check_candidate(candidate: str) -> dict[str, bool]:
    controller = ReplayController(candidate)
    msg = sample()
    req = request()
    replayed = controller.replay(req, [msg], duplicate_sensitive=True)
    checks = {
        "authorized_replay_audited": replayed == [msg] and len(controller.audit) == 1,
        "unauthorized_actor_rejected": blocked(
            lambda: controller.replay(request(actor="unknown-actor"), [msg]),
            "current_privileged_authority_required",
        ),
        "stale_authority_epoch_rejected": blocked(
            lambda: controller.replay(request(epoch="replay-auth-epoch-1"), [msg]),
            "current_privileged_authority_required",
        ),
        "bounded_replay_rejected": blocked(
            lambda: controller.replay(request(max_messages=0), [msg]),
            "replay_bound_exceeded",
        ),
        "original_identity_preserved": (
            replayed[0].message_id == msg.message_id
            and replayed[0].contract_id == msg.contract_id
            and replayed[0].tenant_id == msg.tenant_id
        ),
        "immutable_semantic_meaning_preserved": (
            replayed[0].semantic_content == msg.semantic_content
            and replayed[0].schema_version == msg.schema_version
        ),
        "historical_authority_metadata_preserved": (
            replayed[0].equivalence_profile == msg.equivalence_profile
            and replayed[0].verifier_version == msg.verifier_version
        ),
        "missing_verifier_blocks_all_replay": blocked(
            lambda: controller.replay(req, [msg], verifier_available=False),
            "replay_history_authority_unavailable",
        ),
        "missing_equivalence_blocks_all_replay": blocked(
            lambda: controller.replay(req, [msg], equivalence_available=False),
            "replay_history_authority_unavailable",
        ),
        "missing_comparison_authority_blocks_duplicate_sensitive_effect": blocked(
            lambda: controller.replay(
                req,
                [msg],
                equivalence_available=False,
                duplicate_sensitive=True,
            ),
            "historical_comparison_authority_unavailable",
        ),
        "missing_historical_metadata_rejected": blocked(
            lambda: controller.replay(
                req,
                [HistoricalMessage(
                    msg.tenant_id,
                    msg.contract_id,
                    msg.message_id,
                    msg.semantic_content,
                    msg.schema_version,
                    "",
                    msg.verifier_version,
                )],
            ),
            "historical_verifier_metadata_missing",
        ),
        "dedup_bypass_rejected": blocked(
            lambda: controller.replay(request(disable_dedup=True), [msg]),
            "dedup_bypass_forbidden",
        ),
        "irreversible_effect_not_repeatable": False,
        "projection_target_isolated": blocked(
            lambda: controller.replay(request(target="production-current"), [msg]),
            "isolated_replay_target_required",
        ),
        "replay_generation_required": blocked(
            lambda: controller.replay(request(generation=""), [msg]),
            "isolated_replay_target_required",
        ),
        "schema_data_recovery_bounds_enforced": all((
            blocked(
                lambda: controller.replay(req, [msg], schema_supported=False),
                "safe_replay_evidence_incomplete",
            ),
            blocked(
                lambda: controller.replay(req, [msg], data_access_allowed=False),
                "safe_replay_evidence_incomplete",
            ),
            blocked(
                lambda: controller.replay(req, [msg], recovery_evidence_available=False),
                "safe_replay_evidence_incomplete",
            ),
        )),
        "storage_identity_not_message_identity": (
            controller.replay(req, [msg], storage_identity="broker-x")[0].message_id
            == msg.message_id
        ),
        "storage_identity_not_contract_identity": (
            controller.replay(req, [msg], storage_identity="archive-y")[0].contract_id
            == msg.contract_id
        ),
    }
    irreversible_controller = ReplayController(candidate)
    irreversible_controller.replay(req, [msg], irreversible=True)
    checks["irreversible_effect_not_repeatable"] = blocked(
        lambda: irreversible_controller.replay(req, [msg], irreversible=True),
        "irreversible_effect_already_completed",
    )
    return checks


PROOF_CHECKS = {
    PROOFS[0]: (
        "authorized_replay_audited",
        "unauthorized_actor_rejected",
        "stale_authority_epoch_rejected",
        "bounded_replay_rejected",
    ),
    PROOFS[1]: ("original_identity_preserved", "immutable_semantic_meaning_preserved"),
    PROOFS[2]: (
        "historical_authority_metadata_preserved",
        "missing_verifier_blocks_all_replay",
        "missing_equivalence_blocks_all_replay",
        "missing_historical_metadata_rejected",
    ),
    PROOFS[3]: ("missing_comparison_authority_blocks_duplicate_sensitive_effect",),
    PROOFS[4]: ("dedup_bypass_rejected", "irreversible_effect_not_repeatable"),
    PROOFS[5]: ("projection_target_isolated", "replay_generation_required"),
    PROOFS[6]: (
        "schema_data_recovery_bounds_enforced",
        "missing_verifier_blocks_all_replay",
        "missing_equivalence_blocks_all_replay",
        "dedup_bypass_rejected",
    ),
    PROOFS[7]: ("storage_identity_not_message_identity", "storage_identity_not_contract_identity"),
}


def evaluate() -> dict[str, Any]:
    candidate_checks = {c: check_candidate(c) for c in CANDIDATES}
    proof_results = {
        c: {p: all(candidate_checks[c][name] for name in names) for p, names in PROOF_CHECKS.items()}
        for c in CANDIDATES
    }
    candidate_results = {
        c: (
            "eligible_for_evidence_execution"
            if all(candidate_checks[c].values()) and all(proof_results[c].values())
            else "insufficient_evidence"
        )
        for c in CANDIDATES
    }
    return {
        "schema_version": 1,
        "source_decision": "OPEN-EVT-014",
        "evidence_id": "privileged_bounded_replay_with_original_identity_and_effect_safety",
        "candidate_results": candidate_results,
        "proof_results": proof_results,
        "check_results": candidate_checks,
        "selection": "not_selected",
        "selection_authority": "not_granted",
        "ledger_credit": [],
        "current_run_auto_credit": False,
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2, sort_keys=True))
