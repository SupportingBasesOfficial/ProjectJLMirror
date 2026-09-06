#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Callable, Mapping

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
    PROOFS[0]: (
        "atomic_commit_all_or_nothing",
        "business_snapshot_isolated_from_caller_mutation",
        "mutable_mapping_key_rejected",
        "scalar_subclass_mapping_key_rejected",
        "message_identity_fixed_at_commit",
    ),
    PROOFS[1]: (
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
    PROOFS[2]: (
        "coherent_immutable_fact_rewrite_rejected",
        "retry_preserves_identity",
        "retry_preserves_semantic_content",
    ),
    PROOFS[3]: (
        "ack_lost_retry_same_identity",
        "ack_lost_retry_same_content",
        "ambiguous_ack_cannot_mark_terminal",
        "foreign_identity_ack_cannot_mark_terminal",
        "foreign_content_ack_cannot_mark_terminal",
        "broker_conflicting_content_rejected",
    ),
    PROOFS[4]: ("broker_outage_preserves_backlog", "unavailable_publish_cannot_mark_terminal"),
    PROOFS[5]: (
        "restart_preserves_identity",
        "restart_preserves_semantic_content",
        "notification_is_non_authoritative",
    ),
    PROOFS[6]: (
        "cleanup_blocks_uncertain_delivery",
        "cleanup_blocks_before_safe_horizon",
        "cleanup_after_safe_horizon_requires_terminal_evidence",
    ),
}


class ContractViolation(RuntimeError):
    pass


_IMMUTABLE_SCALAR_TYPES = (str, int, float, bool, type(None))


def _freeze(value: Any) -> Any:
    if type(value) in _IMMUTABLE_SCALAR_TYPES:
        return value
    if isinstance(value, Mapping):
        frozen: dict[Any, Any] = {}
        for key, item in value.items():
            if type(key) not in _IMMUTABLE_SCALAR_TYPES:
                raise ContractViolation("unsupported_mutable_business_key")
            frozen[key] = _freeze(item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    raise ContractViolation("unsupported_mutable_business_value")


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
        self._state_lock = threading.RLock()
        self.terminal_pause_after_read = False

    @property
    def business_revision(self) -> int:
        with self._state_lock:
            return self._state.business_revision

    @property
    def business_value(self) -> Any:
        with self._state_lock:
            return self._state.business_value

    @property
    def outbox(self) -> Mapping[str, OutboxFact]:
        with self._state_lock:
            return self._state.outbox

    @staticmethod
    def _digest(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _immutable_tuple(fact: OutboxFact) -> tuple[str, str, str, int]:
        return (fact.message_id, fact.semantic_content, fact.content_digest, fact.business_revision)

    @staticmethod
    def _assert_token_matches(fact: OutboxFact, token: ClaimToken, *, now: int) -> None:
        if token.fence != fact.claim_fence or token.owner != fact.claim_owner:
            raise ContractViolation("stale_claim")
        if token.lease_expires_at != fact.lease_expires_at:
            raise ContractViolation("stale_claim")
        if now >= fact.lease_expires_at:
            raise ContractViolation("claim_expired")

    def _commit_outbox_locked(self, outbox: dict[str, OutboxFact]) -> None:
        self._state = StoreState(
            self._state.business_revision,
            self._state.business_value,
            MappingProxyType(dict(outbox)),
        )

    def _replace_fact(self, message_id: str, fact: OutboxFact) -> None:
        with self._state_lock:
            old = self._state.outbox[message_id]
            if self._immutable_tuple(old) != self._immutable_tuple(fact):
                raise ContractViolation("immutable_fact_rewrite")
            staged = dict(self._state.outbox)
            staged[message_id] = fact
            self._commit_outbox_locked(staged)

    def _replace_fact_if_current_claim(
        self,
        token: ClaimToken,
        *,
        now: int,
        transform: Callable[[OutboxFact], OutboxFact],
    ) -> None:
        with self._state_lock:
            current = self._state.outbox[token.message_id]
            self._assert_token_matches(current, token, now=now)
            if self.terminal_pause_after_read:
                time.sleep(0.01)
            replacement = transform(current)
            if self._immutable_tuple(current) != self._immutable_tuple(replacement):
                raise ContractViolation("immutable_fact_rewrite")
            latest = self._state.outbox[token.message_id]
            self._assert_token_matches(latest, token, now=now)
            if latest != current:
                raise ContractViolation("claim_state_changed")
            staged = dict(self._state.outbox)
            staged[token.message_id] = replacement
            self._commit_outbox_locked(staged)

    def commit_business_and_outbox(
        self,
        *,
        business_value: Any,
        message_id: str,
        semantic_content: str,
        fail_before_commit: bool = False,
    ) -> None:
        frozen_business = _freeze(business_value)
        with self._state_lock:
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
            next_state = StoreState(next_revision, frozen_business, MappingProxyType(staged))
            if fail_before_commit:
                return
            self._state = next_state

    def claim(self, message_id: str, owner: str, *, now: int, lease: int) -> ClaimToken:
        with self._state_lock:
            fact = self._state.outbox[message_id]
            if fact.claim_owner is not None and fact.lease_expires_at > now:
                raise ContractViolation("claim_already_owned")
            fence = fact.claim_fence + 1
            expires = now + lease
            replacement = replace(fact, claim_owner=owner, claim_fence=fence, lease_expires_at=expires)
            staged = dict(self._state.outbox)
            staged[message_id] = replacement
            self._commit_outbox_locked(staged)
            return ClaimToken(message_id, owner, fence, expires)

    def assert_current(self, token: ClaimToken, *, now: int) -> OutboxFact:
        with self._state_lock:
            fact = self._state.outbox[token.message_id]
            self._assert_token_matches(fact, token, now=now)
            return fact

    def mark_terminal_delivery(
        self,
        token: ClaimToken,
        receipt: PublishReceipt,
        *,
        now: int,
        commit_now: int | None = None,
        before_commit: Callable[[], None] | None = None,
    ) -> None:
        fact = self.assert_current(token, now=now)
        if receipt.status != "acked":
            raise ContractViolation("delivery_not_terminal")
        if receipt.message_id != fact.message_id or receipt.content_digest != fact.content_digest:
            raise ContractViolation("delivery_receipt_mismatch")
        if before_commit is not None:
            before_commit()
        boundary_now = now if commit_now is None else commit_now
        self._replace_fact_if_current_claim(
            token,
            now=boundary_now,
            transform=lambda current: replace(
                current,
                delivery_state="delivered",
                terminal_delivery_evidence=True,
            ),
        )

    def set_safe_horizon(self, message_id: str) -> None:
        with self._state_lock:
            fact = self._state.outbox[message_id]
            staged = dict(self._state.outbox)
            staged[message_id] = replace(fact, safe_horizon_reached=True)
            self._commit_outbox_locked(staged)

    def cleanup(self, message_id: str) -> None:
        with self._state_lock:
            fact = self._state.outbox[message_id]
            if not fact.terminal_delivery_evidence:
                raise ContractViolation("delivery_uncertain")
            if not fact.safe_horizon_reached:
                raise ContractViolation("safe_horizon_not_reached")
            staged = dict(self._state.outbox)
            del staged[message_id]
            self._commit_outbox_locked(staged)


class BrokerProbe:
    def __init__(self) -> None:
        self.available = True
        self.accept_then_lose_ack_once = False
        self.accepted: list[tuple[str, str]] = []
        self.attempts: list[tuple[str, str]] = []
        self._accepted_by_message_id: dict[str, str] = {}
        self._accept_lock = threading.Lock()
        self.accept_pause_after_lookup = False

    def _accept_idempotently(self, pair: tuple[str, str]) -> None:
        message_id, content_digest = pair
        with self._accept_lock:
            existing = self._accepted_by_message_id.get(message_id)
            if self.accept_pause_after_lookup:
                time.sleep(0.01)
            if existing is None:
                self._accepted_by_message_id[message_id] = content_digest
                self.accepted.append(pair)
            elif existing != content_digest:
                raise ContractViolation("broker_message_identity_conflict")

    def publish(
        self,
        fact: OutboxFact,
        *,
        authorize_handoff: Callable[[], None],
        before_handoff: Callable[[], None] | None = None,
        after_handoff: Callable[[], None] | None = None,
    ) -> PublishReceipt:
        pair = (fact.message_id, fact.content_digest)
        self.attempts.append(pair)
        if not self.available:
            return PublishReceipt("unavailable", *pair)
        if before_handoff is not None:
            before_handoff()
        authorize_handoff()
        if after_handoff is not None:
            after_handoff()
        # Once the cross-authority broker call is in flight, later claim loss cannot
        # retroactively cancel it. Completion is ambiguity contained by stable ID/content.
        self._accept_idempotently(pair)
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

    def dispatch(
        self,
        token: ClaimToken,
        *,
        now: int,
        handoff_now: int | None = None,
        before_handoff: Callable[[], None] | None = None,
        after_handoff: Callable[[], None] | None = None,
    ) -> PublishReceipt:
        fact = self.store.assert_current(token, now=now)
        boundary_now = now if handoff_now is None else handoff_now
        return self.broker.publish(
            fact,
            authorize_handoff=lambda: self.store.assert_current(token, now=boundary_now),
            before_handoff=before_handoff,
            after_handoff=after_handoff,
        )


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


def _blocked(fn: Callable[[], Any], code: str) -> bool:
    try:
        fn()
    except ContractViolation as exc:
        return str(exc) == code
    return False


def check_candidate(candidate: str) -> dict[str, bool]:
    checks: dict[str, bool] = {}

    store, broker, mid, semantic = _new_fixture()
    store.commit_business_and_outbox(
        business_value={"rev": 1}, message_id=mid, semantic_content=semantic, fail_before_commit=True
    )
    checks["atomic_commit_all_or_nothing"] = store.business_revision == 0 and mid not in store.outbox

    caller_business = {"rev": 1, "nested": {"status": "committed"}}
    store.commit_business_and_outbox(
        business_value=caller_business, message_id=mid, semantic_content=semantic
    )
    caller_business["rev"] = 2
    caller_business["nested"]["status"] = "mutated"
    snapshot = store.business_value
    checks["business_snapshot_isolated_from_caller_mutation"] = (
        snapshot["rev"] == 1 and snapshot["nested"]["status"] == "committed"
    )

    class MutableKey:
        def __init__(self) -> None:
            self.value = "before"
        def __hash__(self) -> int:
            return 7

    mutable_key = MutableKey()
    key_store = DurableStore()
    checks["mutable_mapping_key_rejected"] = _blocked(
        lambda: key_store.commit_business_and_outbox(
            business_value={mutable_key: "value"}, message_id="key-msg", semantic_content="{}"
        ),
        "unsupported_mutable_business_key",
    ) and key_store.business_revision == 0 and "key-msg" not in key_store.outbox

    class MutableStr(str):
        pass

    scalar_key = MutableStr("key")
    scalar_key.mutable_state = "before"
    scalar_key_store = DurableStore()
    checks["scalar_subclass_mapping_key_rejected"] = _blocked(
        lambda: scalar_key_store.commit_business_and_outbox(
            business_value={scalar_key: "value"}, message_id="scalar-key-msg", semantic_content="{}"
        ),
        "unsupported_mutable_business_key",
    ) and scalar_key_store.business_revision == 0 and "scalar-key-msg" not in scalar_key_store.outbox

    committed = store.outbox[mid]
    checks["message_identity_fixed_at_commit"] = (
        committed.message_id == mid
        and committed.content_digest == DurableStore._digest(semantic)
        and committed.business_revision == store.business_revision == 1
    )

    d1 = Dispatcher(store, broker, candidate=candidate, owner="worker-a")
    token1 = store.claim(mid, "worker-a", now=10, lease=5)
    checks["preexpiry_takeover_rejected"] = _blocked(
        lambda: store.claim(mid, "worker-b", now=14, lease=5), "claim_already_owned"
    )
    checks["expired_claim_cannot_dispatch"] = _blocked(
        lambda: d1.dispatch(token1, now=15), "claim_expired"
    )

    broker.accepted.clear()
    token2_box: list[ClaimToken] = []

    def takeover_before_handoff() -> None:
        token2_box.append(store.claim(mid, "worker-b", now=15, lease=5))

    inflight_blocked = _blocked(
        lambda: d1.dispatch(
            token1,
            now=14,
            handoff_now=15,
            before_handoff=takeover_before_handoff,
        ),
        "stale_claim",
    )
    token2 = token2_box[0]
    checks["inflight_takeover_fenced_before_broker_handoff"] = inflight_blocked and broker.accepted == []

    ambiguity_broker = BrokerProbe()
    ambiguity_store = DurableStore()
    ambiguity_store.commit_business_and_outbox(
        business_value={"rev": 1}, message_id="ambiguity-msg", semantic_content=semantic
    )
    ambiguity_a = ambiguity_store.claim("ambiguity-msg", "worker-a", now=10, lease=5)
    ambiguity_dispatcher_a = Dispatcher(
        ambiguity_store, ambiguity_broker, candidate=candidate, owner="worker-a"
    )
    ambiguity_b_box: list[ClaimToken] = []

    def takeover_after_handoff() -> None:
        ambiguity_b_box.append(ambiguity_store.claim("ambiguity-msg", "worker-b", now=15, lease=5))

    stale_completion = ambiguity_dispatcher_a.dispatch(
        ambiguity_a,
        now=14,
        handoff_now=14,
        after_handoff=takeover_after_handoff,
    )
    ambiguity_b = ambiguity_b_box[0]
    current_retry = Dispatcher(
        ambiguity_store, ambiguity_broker, candidate=candidate, owner="worker-b"
    ).dispatch(ambiguity_b, now=15)
    stale_terminal_blocked = _blocked(
        lambda: ambiguity_store.mark_terminal_delivery(ambiguity_a, stale_completion, now=15),
        "stale_claim",
    )
    checks["post_handoff_takeover_completion_is_ambiguous_and_deduplicated"] = (
        stale_completion.status == "acked"
        and current_retry.status == "acked"
        and len(ambiguity_broker.attempts) == 2
        and ambiguity_broker.accepted == [("ambiguity-msg", DurableStore._digest(semantic))]
        and stale_terminal_blocked
        and not ambiguity_store.outbox["ambiguity-msg"].terminal_delivery_evidence
    )

    concurrent_broker = BrokerProbe()
    concurrent_broker.accept_pause_after_lookup = True
    concurrent_fact = OutboxFact("concurrent-msg", semantic, DurableStore._digest(semantic), 1)
    start = threading.Barrier(8)
    failures: list[Exception] = []

    def concurrent_publish() -> None:
        try:
            start.wait()
            concurrent_broker.publish(concurrent_fact, authorize_handoff=lambda: None)
        except Exception as exc:
            failures.append(exc)

    threads = [threading.Thread(target=concurrent_publish) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    checks["broker_acceptance_atomic_under_concurrency"] = (
        failures == []
        and len(concurrent_broker.attempts) == 8
        and concurrent_broker.accepted == [("concurrent-msg", DurableStore._digest(semantic))]
    )

    checks["stale_owner_fenced_after_takeover"] = _blocked(
        lambda: d1.dispatch(token1, now=15), "stale_claim"
    ) and token2.fence > token1.fence
    current = store.outbox[mid]
    checks["single_current_claim_owner"] = current.claim_owner == "worker-b" and current.claim_fence == token2.fence

    before = store.outbox[mid]
    rewritten = '{"tenant":"tenant-a","event":"asset.changed","revision":2}'
    coherent_rewrite = replace(
        before,
        semantic_content=rewritten,
        content_digest=DurableStore._digest(rewritten),
    )
    checks["coherent_immutable_fact_rewrite_rejected"] = _blocked(
        lambda: store._replace_fact(mid, coherent_rewrite), "immutable_fact_rewrite"
    ) and DurableStore._immutable_tuple(store.outbox[mid]) == DurableStore._immutable_tuple(before)

    d2 = Dispatcher(store, broker, candidate=candidate, owner="worker-b")
    first = d2.dispatch(token2, now=16)
    second = d2.dispatch(token2, now=17)
    after = store.outbox[mid]
    checks["retry_preserves_identity"] = (
        broker.attempts[-2][0] == broker.attempts[-1][0] == before.message_id == after.message_id
    )
    checks["retry_preserves_semantic_content"] = (
        broker.attempts[-2][1] == broker.attempts[-1][1] == before.content_digest == after.content_digest
        and first.status == second.status == "acked"
    )

    terminal_store, terminal_broker, terminal_mid, terminal_semantic = _new_fixture()
    terminal_store.commit_business_and_outbox(
        business_value={"rev": 1}, message_id=terminal_mid, semantic_content=terminal_semantic
    )
    terminal_a = terminal_store.claim(terminal_mid, "worker-a", now=0, lease=2)
    terminal_dispatcher = Dispatcher(terminal_store, terminal_broker, candidate=candidate, owner="worker-a")
    terminal_ack = terminal_dispatcher.dispatch(terminal_a, now=1)
    checks["expired_claim_cannot_mark_terminal"] = _blocked(
        lambda: terminal_store.mark_terminal_delivery(terminal_a, terminal_ack, now=2),
        "claim_expired",
    ) and not terminal_store.outbox[terminal_mid].terminal_delivery_evidence
    terminal_b = terminal_store.claim(terminal_mid, "worker-b", now=2, lease=2)
    checks["superseded_claim_cannot_mark_terminal"] = _blocked(
        lambda: terminal_store.mark_terminal_delivery(terminal_a, terminal_ack, now=2),
        "stale_claim",
    ) and not terminal_store.outbox[terminal_mid].terminal_delivery_evidence and terminal_b.fence > terminal_a.fence

    cas_store, cas_broker, cas_mid, cas_semantic = _new_fixture()
    cas_store.commit_business_and_outbox(
        business_value={"rev": 1}, message_id=cas_mid, semantic_content=cas_semantic
    )
    cas_a = cas_store.claim(cas_mid, "worker-a", now=0, lease=2)
    cas_ack = Dispatcher(cas_store, cas_broker, candidate=candidate, owner="worker-a").dispatch(cas_a, now=1)
    cas_b_box: list[ClaimToken] = []

    def terminal_takeover() -> None:
        cas_b_box.append(cas_store.claim(cas_mid, "worker-b", now=2, lease=2))

    cas_blocked = _blocked(
        lambda: cas_store.mark_terminal_delivery(
            cas_a,
            cas_ack,
            now=1,
            commit_now=2,
            before_commit=terminal_takeover,
        ),
        "stale_claim",
    )
    cas_current = cas_store.outbox[cas_mid]
    checks["inflight_terminal_takeover_cas_rejected"] = (
        cas_blocked
        and len(cas_b_box) == 1
        and cas_current.claim_owner == "worker-b"
        and cas_current.claim_fence == cas_b_box[0].fence
        and not cas_current.terminal_delivery_evidence
    )

    concurrent_store, concurrent_terminal_broker, concurrent_mid, concurrent_semantic = _new_fixture()
    concurrent_store.commit_business_and_outbox(
        business_value={"rev": 1}, message_id=concurrent_mid, semantic_content=concurrent_semantic
    )
    concurrent_a = concurrent_store.claim(concurrent_mid, "worker-a", now=0, lease=2)
    concurrent_ack = Dispatcher(
        concurrent_store, concurrent_terminal_broker, candidate=candidate, owner="worker-a"
    ).dispatch(concurrent_a, now=1)
    concurrent_store.terminal_pause_after_read = True
    terminal_errors: list[Exception] = []

    def terminal_writer() -> None:
        try:
            concurrent_store.mark_terminal_delivery(concurrent_a, concurrent_ack, now=1)
        except Exception as exc:
            terminal_errors.append(exc)

    writer = threading.Thread(target=terminal_writer)
    writer.start()
    time.sleep(0.002)
    concurrent_b = concurrent_store.claim(concurrent_mid, "worker-b", now=2, lease=2)
    writer.join()
    concurrent_current = concurrent_store.outbox[concurrent_mid]
    checks["terminal_claim_write_atomic_under_concurrency"] = (
        terminal_errors == []
        and concurrent_current.claim_owner == "worker-b"
        and concurrent_current.claim_fence == concurrent_b.fence
        and concurrent_current.terminal_delivery_evidence
    )

    store2, broker2, mid2, semantic2 = _new_fixture()
    store2.commit_business_and_outbox(
        business_value={"rev": 1}, message_id=mid2, semantic_content=semantic2
    )
    token = store2.claim(mid2, "worker-a", now=1, lease=10)
    dispatcher = Dispatcher(store2, broker2, candidate=candidate, owner="worker-a")
    broker2.accept_then_lose_ack_once = True
    ambiguous = dispatcher.dispatch(token, now=2)
    checks["ambiguous_ack_cannot_mark_terminal"] = _blocked(
        lambda: store2.mark_terminal_delivery(token, ambiguous, now=2), "delivery_not_terminal"
    ) and not store2.outbox[mid2].terminal_delivery_evidence
    retry = dispatcher.dispatch(token, now=3)
    checks["ack_lost_retry_same_identity"] = (
        ambiguous.status == "ambiguous_ack_lost"
        and retry.status == "acked"
        and broker2.attempts[-2][0] == broker2.attempts[-1][0] == mid2
    )
    checks["ack_lost_retry_same_content"] = (
        broker2.attempts[-2][1] == broker2.attempts[-1][1] == store2.outbox[mid2].content_digest
    )
    foreign_identity = PublishReceipt("acked", "other-message", retry.content_digest)
    checks["foreign_identity_ack_cannot_mark_terminal"] = _blocked(
        lambda: store2.mark_terminal_delivery(token, foreign_identity, now=3), "delivery_receipt_mismatch"
    ) and not store2.outbox[mid2].terminal_delivery_evidence
    foreign_content = PublishReceipt("acked", mid2, DurableStore._digest("other-content"))
    checks["foreign_content_ack_cannot_mark_terminal"] = _blocked(
        lambda: store2.mark_terminal_delivery(token, foreign_content, now=3), "delivery_receipt_mismatch"
    ) and not store2.outbox[mid2].terminal_delivery_evidence

    conflict_broker = BrokerProbe()
    original = OutboxFact("conflict-msg", "one", DurableStore._digest("one"), 1)
    conflict = OutboxFact("conflict-msg", "two", DurableStore._digest("two"), 1)
    conflict_broker.publish(original, authorize_handoff=lambda: None)
    checks["broker_conflicting_content_rejected"] = _blocked(
        lambda: conflict_broker.publish(conflict, authorize_handoff=lambda: None),
        "broker_message_identity_conflict",
    ) and conflict_broker.accepted == [("conflict-msg", DurableStore._digest("one"))]

    store3, broker3, mid3, semantic3 = _new_fixture()
    store3.commit_business_and_outbox(
        business_value={"rev": 1}, message_id=mid3, semantic_content=semantic3
    )
    token3 = store3.claim(mid3, "worker-a", now=1, lease=2)
    broker3.available = False
    outage_dispatcher = Dispatcher(store3, broker3, candidate=candidate, owner="worker-a")
    unavailable = outage_dispatcher.dispatch(token3, now=2)
    checks["unavailable_publish_cannot_mark_terminal"] = _blocked(
        lambda: store3.mark_terminal_delivery(token3, unavailable, now=2), "delivery_not_terminal"
    ) and not store3.outbox[mid3].terminal_delivery_evidence
    checks["broker_outage_preserves_backlog"] = (
        unavailable.status == "unavailable"
        and mid3 in store3.outbox
        and store3.outbox[mid3].semantic_content == semantic3
    )

    restarted = Dispatcher(store3, broker3, candidate=candidate, owner="worker-restarted")
    token4 = store3.claim(mid3, "worker-restarted", now=3, lease=3)
    broker3.available = True
    recovered = restarted.dispatch(token4, now=4)
    checks["restart_preserves_identity"] = recovered.status == "acked" and recovered.message_id == mid3
    checks["restart_preserves_semantic_content"] = (
        recovered.content_digest == store3.outbox[mid3].content_digest == DurableStore._digest(semantic3)
    )
    checks["notification_is_non_authoritative"] = (
        candidate != "notification_assisted_polling_claim_profile"
        or (restarted.notifications == [] and recovered.status == "acked")
    )

    checks["cleanup_blocks_uncertain_delivery"] = _blocked(
        lambda: store3.cleanup(mid3), "delivery_uncertain"
    )
    store3.mark_terminal_delivery(token4, recovered, now=4)
    checks["cleanup_blocks_before_safe_horizon"] = _blocked(
        lambda: store3.cleanup(mid3), "safe_horizon_not_reached"
    ) and mid3 in store3.outbox
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
