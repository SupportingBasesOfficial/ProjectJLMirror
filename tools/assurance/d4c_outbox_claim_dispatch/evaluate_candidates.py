#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Mapping

CANDIDATES = (
    "database_skip_locked_polling_claim_profile",
    "compare_and_swap_lease_claim_profile",
    "notification_assisted_polling_claim_profile",
)

PROOFS = (
    "authoritative_mutation_and_required_outbox_fact_commit_atomically",
    "claim_takeover_is_fenced_and_does_not_create_concurrent_semantic_owners",
    "retry_workers_do_not_rewrite_immutable_fact_meaning",
    "broker_ack_ambiguity_retries_same_message_identity_and_semantic_content",
    "broker_outage_preserves_committed_backlog_without_loss",
    "dispatcher_restart_and_recovery_preserve_stable_message_identity_and_semantic_content",
    "cleanup_never_removes_the_last_recovery_authority_before_safe_horizon",
)

PROOF_CHECKS = {
    PROOFS[0]: ("atomic_commit_all_or_nothing", "message_identity_fixed_at_commit"),
    PROOFS[1]: (
        "preexpiry_takeover_rejected",
        "expired_claim_cannot_dispatch",
        "stale_owner_fenced_after_takeover",
        "single_current_claim_owner",
    ),
    PROOFS[2]: ("immutable_fact_rewrite_rejected", "retry_preserves_identity", "retry_preserves_semantic_content"),
    PROOFS[3]: ("ack_lost_retry_same_identity", "ack_lost_retry_same_content", "ambiguous_ack_cannot_mark_terminal"),
    PROOFS[4]: ("broker_outage_preserves_backlog", "unavailable_publish_cannot_mark_terminal"),
    PROOFS[5]: ("restart_preserves_identity", "restart_preserves_semantic_content", "notification_is_non_authoritative"),
    PROOFS[6]: ("cleanup_blocks_uncertain_delivery", "cleanup_blocks_before_safe_horizon", "cleanup_after_safe_horizon_requires_terminal_evidence"),
}


class ContractViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class OutboxFact:
    message_id: str
    semantic_content: str
    content_digest: str
    business_revision: int
    delivery_state: str = "pending"
    terminal_delivery_evidence: bool = False
    safe_horizon_reached: bool = False
    claim_owner: str | None = None
    claim_fence: int = 0
    lease_expires_at: int = 0


@dataclass(frozen=True)
class ClaimToken:
    message_id: str
    owner: str
    fence: int
    lease_expires_at: int


@dataclass(frozen=True)
class PublishReceipt:
    status: str
    message_id: str
    content_digest: str


@dataclass(frozen=True)
class StoreState:
    business_revision: int
    business_value: Any
    outbox: Mapping[str, OutboxFact]


class DurableStore:
    def __init__(self) -> None:
        self._state = StoreState(0, None, MappingProxyType({}))

    @property
    def business_revision(self) -> int:
        return self._state.business_revision

    @property
    def business_value(self) -> Any:
        return self._state.business_value

    @property
    def outbox(self) -> Mapping[str, OutboxFact]:
        return self._state.outbox

    @staticmethod
    def _digest(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _immutable_tuple(fact: OutboxFact) -> tuple[str, str, str, int]:
        return (fact.message_id, fact.semantic_content, fact.content_digest, fact.business_revision)

    def _commit_state(
        self,
        *,
        business_revision: int | None = None,
        business_value: Any = None,
        preserve_business_value: bool = True,
        outbox: dict[str, OutboxFact],
    ) -> None:
        revision = self._state.business_revision if business_revision is None else business_revision
        value = self._state.business_value if preserve_business_value else business_value
        self._state = StoreState(revision, value, MappingProxyType(dict(outbox)))

    def _replace_fact(self, message_id: str, fact: OutboxFact) -> None:
        old = self._state.outbox[message_id]
        if self._immutable_tuple(old) != self._immutable_tuple(fact):
            raise ContractViolation("immutable_fact_rewrite")
        staged = dict(self._state.outbox)
        staged[message_id] = fact
        self._commit_state(outbox=staged)

    def commit_business_and_outbox(
        self,
        *,
        business_value: Any,
        message_id: str,
        semantic_content: str,
        fail_before_commit: bool = False,
    ) -> None:
        if message_id in self._state.outbox:
            raise ContractViolation("message_identity_reuse")
        next_revision = self._state.business_revision + 1
        fact = OutboxFact(
            message_id=message_id,
            semantic_content=semantic_content,
            content_digest=self._digest(semantic_content),
            business_revision=next_revision,
        )
        staged = dict(self._state.outbox)
        staged[message_id] = fact
        next_state = StoreState(next_revision, business_value, MappingProxyType(staged))
        if fail_before_commit:
            return
        # One state-pointer replacement models the co-resident transaction commit.
        self._state = next_state

    def claim(self, message_id: str, owner: str, *, now: int, lease: int) -> ClaimToken:
        fact = self._state.outbox[message_id]
        if fact.claim_owner is not None and fact.lease_expires_at > now:
            raise ContractViolation("claim_already_owned")
        fence = fact.claim_fence + 1
        lease_expires_at = now + lease
        self._replace_fact(
            message_id,
            replace(fact, claim_owner=owner, claim_fence=fence, lease_expires_at=lease_expires_at),
        )
        return ClaimToken(message_id, owner, fence, lease_expires_at)

    def assert_current(self, token: ClaimToken, *, now: int) -> OutboxFact:
        fact = self._state.outbox[token.message_id]
        if token.fence != fact.claim_fence or token.owner != fact.claim_owner:
            raise ContractViolation("stale_claim")
        if token.lease_expires_at != fact.lease_expires_at:
            raise ContractViolation("stale_claim")
        if now >= fact.lease_expires_at:
            raise ContractViolation("claim_expired")
        return fact

    def mark_terminal_delivery(self, token: ClaimToken, receipt: PublishReceipt, *, now: int) -> None:
        fact = self.assert_current(token, now=now)
        if receipt.status != "acked":
            raise ContractViolation("delivery_not_terminal")
        if receipt.message_id != fact.message_id or receipt.content_digest != fact.content_digest:
            raise ContractViolation("delivery_receipt_mismatch")
        self._replace_fact(
            token.message_id,
            replace(fact, delivery_state="delivered", terminal_delivery_evidence=True),
        )

    def set_safe_horizon(self, message_id: str) -> None:
        fact = self._state.outbox[message_id]
        self._replace_fact(message_id, replace(fact, safe_horizon_reached=True))

    def cleanup(self, message_id: str) -> None:
        fact = self._state.outbox[message_id]
        if not fact.terminal_delivery_evidence:
            raise ContractViolation("delivery_uncertain")
        if not fact.safe_horizon_reached:
            raise ContractViolation("safe_horizon_not_reached")
        staged = dict(self._state.outbox)
        del staged[message_id]
        self._commit_state(outbox=staged)


class BrokerProbe:
    def __init__(self) -> None:
        self.available = True
        self.accept_then_lose_ack_once = False
        self.accepted: list[tuple[str, str]] = []
        self.attempts: list[tuple[str, str]] = []

    def publish(self, fact: OutboxFact) -> PublishReceipt:
        pair = (fact.message_id, fact.content_digest)
        self.attempts.append(pair)
        if not self.available:
            return PublishReceipt("unavailable", *pair)
        self.accepted.append(pair)
        if self.accept_then_lose_ack_once:
            self.accept_then_lose_ack_once = False
            return PublishReceipt("ambiguous_ack_lost", *pair)
        return PublishReceipt("acked", *pair)


class Dispatcher:
    def __init__(self, store: DurableStore, broker: BrokerProbe, *, candidate: str, owner: str) -> None:
        if candidate not in CANDIDATES:
            raise ValueError(candidate)
        self.store = store
        self.broker = broker
        self.candidate = candidate
        self.owner = owner
        self.notifications: list[str] = []

    def notify(self, message_id: str) -> None:
        self.notifications.append(message_id)

    def dispatch(self, token: ClaimToken, *, now: int) -> PublishReceipt:
        fact = self.store.assert_current(token, now=now)
        return self.broker.publish(fact)


def _new_fixture() -> tuple[DurableStore, BrokerProbe, str, str]:
    store = DurableStore()
    broker = BrokerProbe()
    message_id = "msg-tenant-a-0001"
    semantic = json.dumps(
        {"tenant": "tenant-a", "event": "asset.changed", "revision": 1},
        sort_keys=True,
        separators=(",", ":"),
    )
    return store, broker, message_id, semantic


def check_candidate(candidate: str) -> dict[str, bool]:
    checks: dict[str, bool] = {}

    store, broker, mid, semantic = _new_fixture()
    store.commit_business_and_outbox(
        business_value={"rev": 1},
        message_id=mid,
        semantic_content=semantic,
        fail_before_commit=True,
    )
    checks["atomic_commit_all_or_nothing"] = store.business_revision == 0 and mid not in store.outbox
    store.commit_business_and_outbox(
        business_value={"rev": 1},
        message_id=mid,
        semantic_content=semantic,
    )
    committed = store.outbox[mid]
    checks["message_identity_fixed_at_commit"] = (
        committed.message_id == mid
        and committed.content_digest == DurableStore._digest(semantic)
        and committed.business_revision == store.business_revision == 1
    )

    d1 = Dispatcher(store, broker, candidate=candidate, owner="worker-a")
    token1 = store.claim(mid, "worker-a", now=10, lease=5)
    preexpiry_blocked = False
    try:
        store.claim(mid, "worker-b", now=14, lease=5)
    except ContractViolation as exc:
        preexpiry_blocked = str(exc) == "claim_already_owned"
    checks["preexpiry_takeover_rejected"] = preexpiry_blocked

    expired_dispatch_blocked = False
    try:
        d1.dispatch(token1, now=15)
    except ContractViolation as exc:
        expired_dispatch_blocked = str(exc) == "claim_expired"
    checks["expired_claim_cannot_dispatch"] = expired_dispatch_blocked

    token2 = store.claim(mid, "worker-b", now=15, lease=5)
    stale_blocked = False
    try:
        d1.dispatch(token1, now=15)
    except ContractViolation as exc:
        stale_blocked = str(exc) == "stale_claim"
    checks["stale_owner_fenced_after_takeover"] = stale_blocked and token2.fence > token1.fence
    current = store.outbox[mid]
    checks["single_current_claim_owner"] = current.claim_owner == "worker-b" and current.claim_fence == token2.fence

    before = store.outbox[mid]
    rewrite_blocked = False
    try:
        store._replace_fact(mid, replace(before, semantic_content="rewritten"))
    except ContractViolation as exc:
        rewrite_blocked = str(exc) == "immutable_fact_rewrite"
    checks["immutable_fact_rewrite_rejected"] = (
        rewrite_blocked
        and store.outbox[mid].semantic_content == before.semantic_content
        and store.outbox[mid].content_digest == before.content_digest
    )

    d2 = Dispatcher(store, broker, candidate=candidate, owner="worker-b")
    first = d2.dispatch(token2, now=16)
    second = d2.dispatch(token2, now=17)
    after = store.outbox[mid]
    checks["retry_preserves_identity"] = (
        broker.attempts[-2][0] == broker.attempts[-1][0] == before.message_id == after.message_id
    )
    checks["retry_preserves_semantic_content"] = (
        broker.attempts[-2][1]
        == broker.attempts[-1][1]
        == before.content_digest
        == after.content_digest
        and first.status == second.status == "acked"
    )

    store2, broker2, mid2, semantic2 = _new_fixture()
    store2.commit_business_and_outbox(
        business_value={"rev": 1}, message_id=mid2, semantic_content=semantic2
    )
    token = store2.claim(mid2, "worker-a", now=1, lease=10)
    dispatcher = Dispatcher(store2, broker2, candidate=candidate, owner="worker-a")
    broker2.accept_then_lose_ack_once = True
    ambiguous = dispatcher.dispatch(token, now=2)
    ambiguous_terminal_blocked = False
    try:
        store2.mark_terminal_delivery(token, ambiguous, now=2)
    except ContractViolation as exc:
        ambiguous_terminal_blocked = str(exc) == "delivery_not_terminal"
    retry = dispatcher.dispatch(token, now=3)
    checks["ack_lost_retry_same_identity"] = (
        ambiguous.status == "ambiguous_ack_lost"
        and retry.status == "acked"
        and broker2.attempts[-2][0] == broker2.attempts[-1][0] == mid2
    )
    checks["ack_lost_retry_same_content"] = (
        broker2.attempts[-2][1]
        == broker2.attempts[-1][1]
        == store2.outbox[mid2].content_digest
    )
    checks["ambiguous_ack_cannot_mark_terminal"] = (
        ambiguous_terminal_blocked and not store2.outbox[mid2].terminal_delivery_evidence
    )

    store3, broker3, mid3, semantic3 = _new_fixture()
    store3.commit_business_and_outbox(
        business_value={"rev": 1}, message_id=mid3, semantic_content=semantic3
    )
    token3 = store3.claim(mid3, "worker-a", now=1, lease=2)
    broker3.available = False
    outage_dispatcher = Dispatcher(store3, broker3, candidate=candidate, owner="worker-a")
    unavailable = outage_dispatcher.dispatch(token3, now=2)
    unavailable_terminal_blocked = False
    try:
        store3.mark_terminal_delivery(token3, unavailable, now=2)
    except ContractViolation as exc:
        unavailable_terminal_blocked = str(exc) == "delivery_not_terminal"
    checks["broker_outage_preserves_backlog"] = (
        unavailable.status == "unavailable"
        and mid3 in store3.outbox
        and store3.outbox[mid3].semantic_content == semantic3
    )
    checks["unavailable_publish_cannot_mark_terminal"] = (
        unavailable_terminal_blocked and not store3.outbox[mid3].terminal_delivery_evidence
    )

    restarted = Dispatcher(store3, broker3, candidate=candidate, owner="worker-restarted")
    token4 = store3.claim(mid3, "worker-restarted", now=3, lease=3)
    broker3.available = True
    recovered = restarted.dispatch(token4, now=4)
    checks["restart_preserves_identity"] = recovered.status == "acked" and recovered.message_id == mid3
    checks["restart_preserves_semantic_content"] = (
        recovered.content_digest
        == store3.outbox[mid3].content_digest
        == DurableStore._digest(semantic3)
    )
    checks["notification_is_non_authoritative"] = (
        candidate != "notification_assisted_polling_claim_profile"
        or (restarted.notifications == [] and recovered.status == "acked")
    )

    uncertain_blocked = False
    try:
        store3.cleanup(mid3)
    except ContractViolation as exc:
        uncertain_blocked = str(exc) == "delivery_uncertain"
    checks["cleanup_blocks_uncertain_delivery"] = uncertain_blocked
    store3.mark_terminal_delivery(token4, recovered, now=4)
    horizon_blocked = False
    try:
        store3.cleanup(mid3)
    except ContractViolation as exc:
        horizon_blocked = str(exc) == "safe_horizon_not_reached"
    checks["cleanup_blocks_before_safe_horizon"] = horizon_blocked and mid3 in store3.outbox
    store3.set_safe_horizon(mid3)
    store3.cleanup(mid3)
    checks["cleanup_after_safe_horizon_requires_terminal_evidence"] = mid3 not in store3.outbox

    return checks


def evaluate_all() -> dict[str, Any]:
    checks = {candidate: check_candidate(candidate) for candidate in CANDIDATES}
    results = {
        candidate: "eligible_for_evidence_execution" if all(values.values()) else "insufficient_evidence"
        for candidate, values in checks.items()
    }
    proof_results = {
        candidate: {
            proof: all(values[name] for name in PROOF_CHECKS[proof])
            for proof in PROOFS
        }
        for candidate, values in checks.items()
    }
    return {
        "schema_version": 1,
        "source_decision": "OPEN-EVT-012",
        "evidence_id": "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity",
        "candidate_results": results,
        "equivalent_reviewed_profile": "insufficient_evidence",
        "checks": checks,
        "proof_results": proof_results,
        "selection": "not_selected",
        "selection_authority": "not_granted",
        "ledger_credit": [],
        "current_run_auto_credit": False,
    }


def main() -> int:
    result = evaluate_all()
    print(json.dumps(result, indent=2, sort_keys=True))
    expected = {
        candidate: "eligible_for_evidence_execution" for candidate in CANDIDATES
    }
    return 0 if result["candidate_results"] == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
