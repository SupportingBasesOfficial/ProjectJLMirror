#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Tuple


class EvidenceError(Exception):
    pass


class PrematureProgress(EvidenceError):
    pass


class IntegrityFailure(EvidenceError):
    pass


class Uncertainty(EvidenceError):
    pass


class FenceViolation(EvidenceError):
    pass


Identity = Tuple[str, str, str]


@dataclass
class Receipt:
    fingerprint: str | None
    owner: str | None
    epoch: int
    durable_responsibility: bool = True
    effect_committed: bool = False
    acked: bool = False
    checkpointed: bool = False


class DurableConsumerAuthority:
    """Reference state machine for platform consumer responsibility.

    Broker progress is deliberately modeled as subordinate transport state.
    Durable receipt/equivalence/effect state remains platform authority.
    """

    def __init__(self) -> None:
        self.receipts: Dict[Identity, Receipt] = {}
        self.effect_counts: Dict[Identity, int] = {}

    @staticmethod
    def fingerprint(payload: Any) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _get(self, identity: Identity) -> Receipt:
        if identity not in self.receipts:
            raise PrematureProgress("durable consumer responsibility does not exist")
        return self.receipts[identity]

    def claim(self, identity: Identity, payload: Any, owner: str, epoch: int) -> Receipt:
        fp = self.fingerprint(payload)
        receipt = self.receipts.get(identity)
        if receipt is None:
            receipt = Receipt(fingerprint=fp, owner=owner, epoch=epoch)
            self.receipts[identity] = receipt
            return receipt

        if receipt.fingerprint is None:
            raise Uncertainty("scoped identity exists but content-equivalence authority is unavailable")
        if receipt.fingerprint != fp:
            raise IntegrityFailure("same scoped identity has conflicting immutable content")
        if epoch < receipt.epoch:
            raise FenceViolation("stale claim epoch")
        if epoch == receipt.epoch and receipt.owner not in (None, owner):
            raise FenceViolation("concurrent owner at same epoch")
        if epoch > receipt.epoch:
            receipt.epoch = epoch
            receipt.owner = owner
        elif receipt.owner is None:
            receipt.owner = owner
        return receipt

    def expire_lease(self, identity: Identity, owner: str, epoch: int) -> None:
        receipt = self._get(identity)
        self._assert_owner(receipt, owner, epoch)
        receipt.owner = None

    @staticmethod
    def _assert_owner(receipt: Receipt, owner: str, epoch: int) -> None:
        if receipt.owner != owner or receipt.epoch != epoch:
            raise FenceViolation("owner is not current fenced authority")

    def complete_effect(self, identity: Identity, owner: str, epoch: int) -> str:
        receipt = self._get(identity)
        self._assert_owner(receipt, owner, epoch)
        if receipt.fingerprint is None:
            raise Uncertainty("effect admission requires content-equivalence authority")
        if receipt.effect_committed:
            return "duplicate_noop"
        receipt.effect_committed = True
        self.effect_counts[identity] = self.effect_counts.get(identity, 0) + 1
        return "effect_committed"

    def ack(self, identity: Identity, owner: str, epoch: int) -> None:
        receipt = self._get(identity)
        self._assert_owner(receipt, owner, epoch)
        if not receipt.durable_responsibility:
            raise PrematureProgress("ack cannot precede durable responsibility")
        receipt.acked = True

    def checkpoint(self, identity: Identity, owner: str, epoch: int) -> None:
        receipt = self._get(identity)
        self._assert_owner(receipt, owner, epoch)
        if not receipt.durable_responsibility:
            raise PrematureProgress("checkpoint cannot precede durable responsibility")
        receipt.checkpointed = True

    def business_effect_truth(self, identity: Identity) -> bool:
        receipt = self.receipts.get(identity)
        return bool(receipt and receipt.effect_committed)

    def remove_equivalence_authority(self, identity: Identity) -> None:
        self._get(identity).fingerprint = None


CANDIDATES = (
    "durable_inbox_claim_then_broker_ack_profile",
    "broker_visibility_lease_plus_durable_receipt_profile",
    "database_owned_work_claim_plus_broker_checkpoint_profile",
)


def _expect(exc_type, fn) -> bool:
    try:
        fn()
    except exc_type:
        return True
    return False


def run_profile(profile: str) -> Dict[str, bool]:
    if profile not in CANDIDATES:
        raise ValueError(profile)

    identity = ("consumer.orders.v1", "tenant:t1/order:o1", "msg-001")
    payload = {"event": "order.updated", "order_id": "o1", "revision": 7}

    premature = DurableConsumerAuthority()
    premature_ack = _expect(PrematureProgress, lambda: premature.ack(identity, "w1", 1))
    premature_checkpoint = _expect(PrematureProgress, lambda: premature.checkpoint(identity, "w1", 1))

    progress_only = DurableConsumerAuthority()
    progress_only.claim(identity, payload, "w1", 1)
    if profile == "database_owned_work_claim_plus_broker_checkpoint_profile":
        progress_only.checkpoint(identity, "w1", 1)
    else:
        progress_only.ack(identity, "w1", 1)
    broker_progress_not_effect_truth = not progress_only.business_effect_truth(identity)

    ambiguous = DurableConsumerAuthority()
    ambiguous.claim(identity, payload, "w1", 1)
    ambiguous.complete_effect(identity, "w1", 1)
    ambiguous.expire_lease(identity, "w1", 1)
    ambiguous.claim(identity, payload, "w2", 2)
    duplicate_result = ambiguous.complete_effect(identity, "w2", 2)
    lease_expiry_ambiguous_safe = duplicate_result == "duplicate_noop" and ambiguous.effect_counts[identity] == 1

    conflicting = DurableConsumerAuthority()
    conflicting.claim(identity, payload, "w1", 1)
    conflicting_content_fails_closed = _expect(
        IntegrityFailure,
        lambda: conflicting.claim(identity, {**payload, "revision": 8}, "w2", 2),
    )

    rewind = DurableConsumerAuthority()
    rewind.claim(identity, payload, "w1", 1)
    rewind.remove_equivalence_authority(identity)
    rewind_requires_equivalence = _expect(Uncertainty, lambda: rewind.claim(identity, payload, "w2", 2))

    fenced = DurableConsumerAuthority()
    fenced.claim(identity, payload, "w1", 1)
    fenced.expire_lease(identity, "w1", 1)
    fenced.claim(identity, payload, "w2", 2)
    stale_owner_fenced = _expect(FenceViolation, lambda: fenced.complete_effect(identity, "w1", 1))

    crash_before_effect = DurableConsumerAuthority()
    crash_before_effect.claim(identity, payload, "w1", 1)
    crash_before_effect.expire_lease(identity, "w1", 1)
    crash_before_effect.claim(identity, payload, "w2", 2)
    crash_before_effect.complete_effect(identity, "w2", 2)
    if profile == "database_owned_work_claim_plus_broker_checkpoint_profile":
        crash_before_effect.checkpoint(identity, "w2", 2)
    else:
        crash_before_effect.ack(identity, "w2", 2)
    responsibility_crash_recovers = crash_before_effect.effect_counts[identity] == 1

    crash_after_effect = DurableConsumerAuthority()
    crash_after_effect.claim(identity, payload, "w1", 1)
    crash_after_effect.complete_effect(identity, "w1", 1)
    crash_after_effect.expire_lease(identity, "w1", 1)
    crash_after_effect.claim(identity, payload, "w2", 2)
    second = crash_after_effect.complete_effect(identity, "w2", 2)
    if profile == "database_owned_work_claim_plus_broker_checkpoint_profile":
        crash_after_effect.checkpoint(identity, "w2", 2)
    else:
        crash_after_effect.ack(identity, "w2", 2)
    effect_to_progress_crash_safe = second == "duplicate_noop" and crash_after_effect.effect_counts[identity] == 1

    return {
        "premature_ack_rejected": premature_ack,
        "premature_checkpoint_rejected": premature_checkpoint,
        "broker_progress_not_effect_truth": broker_progress_not_effect_truth,
        "lease_expiry_is_ambiguity_with_idempotent_redelivery": lease_expiry_ambiguous_safe,
        "rewind_requires_content_equivalence_authority": rewind_requires_equivalence,
        "conflicting_same_identity_fails_closed": conflicting_content_fails_closed,
        "stale_owner_is_fenced": stale_owner_fenced,
        "crash_after_responsibility_before_effect_or_progress_recovers": responsibility_crash_recovers,
        "crash_after_effect_before_progress_does_not_repeat_effect": effect_to_progress_crash_safe,
    }


def evaluate_all() -> Dict[str, str]:
    results: Dict[str, str] = {}
    for candidate in CANDIDATES:
        checks = run_profile(candidate)
        results[candidate] = "eligible_for_evidence_execution" if all(checks.values()) else "ineligible_by_contract"
    return results


def main() -> int:
    detailed = {candidate: run_profile(candidate) for candidate in CANDIDATES}
    output = {
        "candidate_results": evaluate_all(),
        "equivalent_reviewed_profile": "insufficient_evidence",
        "checks": detailed,
        "selection": "not_selected",
        "ledger_credit": [],
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    if not all(v == "eligible_for_evidence_execution" for v in output["candidate_results"].values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
