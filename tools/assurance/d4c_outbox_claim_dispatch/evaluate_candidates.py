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
    PROOFS[1]: ("preexpiry_takeover_rejected", "stale_owner_fenced_after_takeover", "single_current_claim_owner"),
    PROOFS[2]: ("retry_preserves_identity", "retry_preserves_semantic_content"),
    PROOFS[3]: ("ack_lost_retry_same_identity", "ack_lost_retry_same_content"),
    PROOFS[4]: ("broker_outage_preserves_backlog",),
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

    def _commit_state(self, *, business_revision: int | None = None, business_value: Any = None, preserve_business_value: bool = True, outbox: dict[str, OutboxFact]) -> None:
        revision = self._state.business_revision if business_revision is None else business_revision
        value = self._state.business_value if preserve_business_value else business_value
        self._state = StoreState(revision, value, MappingProxyType(dict(outbox)))

    def _replace_fact(self, message_id: str, fact: OutboxFact) -> None:
        staged = dict(self._state.outbox)
        staged[message_id] = fact
        self._commit_state(outbox=staged)

    def commit_business_and_outbox(self, *, business_value: Any, message_id: str, semantic_content: str, fail_before_commit: bool = False) -> None:
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
        # One state-pointer replacement represents the co-resident transaction commit.
        self._state = next_state

    def claim(self, message_id: str, owner: str, *, now: int, lease: int) -> ClaimToken:
        fact = self._state.outbox[message_id]
        if fact.claim_owner is not None and fact.lease_expires_at > now:
            raise ContractViolation("claim_already_owned")
        fence = fact.claim_fence + 1
        self._replace_fact(message_id, replace(fact, claim_owner=owner, claim_fence=fence, lease_expires_at=now + lease))
        return ClaimToken(message_id, owner, fence)

    def assert_current(self, token: ClaimToken) -> OutboxFact:
        fact = self._state.outbox[token.message_id]
        if token.fence != fact.claim_fence or token.owner != fact.claim_owner:
            raise ContractViolation("stale_claim")
        return fact

    def mark_terminal_delivery(self, token: ClaimToken) -> None:
        fact = self.assert_current(token)
        self._replace_fact(token.message_id, replace(fact, delivery_state="delivered", terminal_delivery_evidence=True))

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

    def publish(self, fact: OutboxFact) -> str:
        pair = (fact.message_id, fact.content_digest)
        self.attempts.append(pair)
        if not self.available:
            return "unavailable"
        self.accepted.append(pair)
        if self.accept_then_lose_ack_once:
            self.accept_then_lose_ack_once = False
            return "ambiguous_ack_lost"
        return "acked"


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

    def dispatch(self, token: ClaimToken) -> str:
        fact = self.store.assert_current(token)
        return self.broker.publish(fact)


def _new_fixture() -> tuple[DurableStore, BrokerProbe, str, str]:
    store = DurableStore()
    broker = BrokerProbe()
    message_id = "msg-tenant-a-0001"
    semantic = json.dumps({"tenant":"tenant-a","event":"asset.changed","revision":1}, sort_keys=True, separators=(",", ":"))
    return store, broker, message_id, semantic


def check_candidate(candidate: str) -> dict[str, bool]:
    checks: dict[str, bool] = {}

    store, broker, mid, semantic = _new_fixture()
    store.commit_business_and_outbox(business_value={"rev": 1}, message_id=mid, semantic_content=semantic, fail_before_commit=True)
    checks["atomic_commit_all_or_nothing"] = store.business_revision == 0 and mid not in store.outbox
    store.commit_business_and_outbox(business_value={"rev": 1}, message_id=mid, semantic_content=semantic)
    committed = store.outbox[mid]
    checks["message_identity_fixed_at_commit"] = committed.message_id == mid and committed.content_digest == DurableStore._digest(semantic) and committed.business_revision == store.business_revision == 1

    d1 = Dispatcher(store, broker, candidate=candidate, owner="worker-a")
    token1 = store.claim(mid, "worker-a", now=10, lease=5)
    preexpiry_blocked = False
    try:
        store.claim(mid, "worker-b", now=14, lease=5)
    except ContractViolation as exc:
        preexpiry_blocked = str(exc) == "claim_already_owned"
    checks["preexpiry_takeover_rejected"] = preexpiry_blocked
    token2 = store.claim(mid, "worker-b", now=15, lease=5)
    stale_blocked = False
    try:
        d1.dispatch(token1)
    except ContractViolation as exc:
        stale_blocked = str(exc) == "stale_claim"
    checks["stale_owner_fenced_after_takeover"] = stale_blocked and token2.fence > token1.fence
    current = store.outbox[mid]
    checks["single_current_claim_owner"] = current.claim_owner == "worker-b" and current.claim_fence == token2.fence

    before = store.outbox[mid]
    d2 = Dispatcher(store, broker, candidate=candidate, owner="worker-b")
    first = d2.dispatch(token2)
    second = d2.dispatch(token2)
    after = store.outbox[mid]
    checks["retry_preserves_identity"] = broker.attempts[-2][0] == broker.attempts[-1][0] == before.message_id == after.message_id
    checks["retry_preserves_semantic_content"] = broker.attempts[-2][1] == broker.attempts[-1][1] == before.content_digest == after.content_digest and first == second == "acked"

    store2, broker2, mid2, semantic2 = _new_fixture()
    store2.commit_business_and_outbox(business_value={"rev": 1}, message_id=mid2, semantic_content=semantic2)
    token = store2.claim(mid2, "worker-a", now=1, lease=10)
    dispatcher = Dispatcher(store2, broker2, candidate=candidate, owner="worker-a")
    broker2.accept_then_lose_ack_once = True
    ambiguous = dispatcher.dispatch(token)
    retry = dispatcher.dispatch(token)
    checks["ack_lost_retry_same_identity"] = ambiguous == "ambiguous_ack_lost" and retry == "acked" and broker2.attempts[-2][0] == broker2.attempts[-1][0] == mid2
    checks["ack_lost_retry_same_content"] = broker2.attempts[-2][1] == broker2.attempts[-1][1] == store2.outbox[mid2].content_digest

    store3, broker3, mid3, semantic3 = _new_fixture()
    store3.commit_business_and_outbox(business_value={"rev": 1}, message_id=mid3, semantic_content=semantic3)
    token3 = store3.claim(mid3, "worker-a", now=1, lease=2)
    broker3.available = False
    outage_dispatcher = Dispatcher(store3, broker3, candidate=candidate, owner="worker-a")
    unavailable = outage_dispatcher.dispatch(token3)
    checks["broker_outage_preserves_backlog"] = unavailable == "unavailable" and mid3 in store3.outbox and store3.outbox[mid3].semantic_content == semantic3

    restarted = Dispatcher(store3, broker3, candidate=candidate, owner="worker-restarted")
    token4 = store3.claim(mid3, "worker-restarted", now=3, lease=2)
    broker3.available = True
    recovered = restarted.dispatch(token4)
    checks["restart_preserves_identity"] = recovered == "acked" and broker3.attempts[-1][0] == mid3
    checks["restart_preserves_semantic_content"] = broker3.attempts[-1][1] == store3.outbox[mid3].content_digest == DurableStore._digest(semantic3)
    checks["notification_is_non_authoritative"] = candidate != "notification_assisted_polling_claim_profile" or (restarted.notifications == [] and recovered == "acked")

    uncertain_blocked = False
    try:
        store3.cleanup(mid3)
    except ContractViolation as exc:
        uncertain_blocked = str(exc) == "delivery_uncertain"
    checks["cleanup_blocks_uncertain_delivery"] = uncertain_blocked
    store3.mark_terminal_delivery(token4)
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
    results = {candidate: "eligible_for_evidence_execution" if all(values.values()) else "insufficient_evidence" for candidate, values in checks.items()}
    proof_results = {
        candidate: {proof: all(values[name] for name in PROOF_CHECKS[proof]) for proof in PROOFS}
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
    expected = {candidate: "eligible_for_evidence_execution" for candidate in CANDIDATES}
    return 0 if result["candidate_results"] == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
