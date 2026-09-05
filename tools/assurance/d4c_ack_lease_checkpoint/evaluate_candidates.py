#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, Tuple


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


@dataclass(frozen=True)
class Receipt:
    fingerprint: str | None
    owner: str | None
    epoch: int
    lease_expired: bool
    durable_responsibility: bool
    effect_committed: bool
    effect_count: int
    acked: bool
    checkpointed: bool


class DurableConsumerAuthority:
    """SQLite-backed reference authority for consumer responsibility.

    The durable receipt/equivalence/effect record is platform authority. Broker
    ack/checkpoint state is intentionally subordinate transport progress. File-
    backed instances are closed and reopened in crash scenarios so restart
    continuity is not accidentally proved by reusing an in-memory object.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        target = ":memory:" if db_path is None else str(db_path)
        self.conn = sqlite3.connect(target, timeout=5.0)
        self.conn.execute("PRAGMA synchronous=FULL")
        if target != ":memory:":
            self.conn.execute("PRAGMA journal_mode=DELETE")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS consumer_receipt (
              consumer_contract TEXT NOT NULL,
              identity_scope TEXT NOT NULL,
              message_id TEXT NOT NULL,
              fingerprint TEXT,
              owner TEXT,
              epoch INTEGER NOT NULL,
              lease_expired INTEGER NOT NULL CHECK (lease_expired IN (0,1)),
              durable_responsibility INTEGER NOT NULL CHECK (durable_responsibility IN (0,1)),
              effect_committed INTEGER NOT NULL CHECK (effect_committed IN (0,1)),
              effect_count INTEGER NOT NULL CHECK (effect_count >= 0),
              acked INTEGER NOT NULL CHECK (acked IN (0,1)),
              checkpointed INTEGER NOT NULL CHECK (checkpointed IN (0,1)),
              PRIMARY KEY (consumer_contract, identity_scope, message_id)
            )
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def _tx(self) -> Iterator[None]:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self.conn.rollback()
            raise
        else:
            self.conn.commit()

    @staticmethod
    def fingerprint(payload: Any) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_identity(identity: Identity) -> None:
        if not isinstance(identity, tuple) or len(identity) != 3:
            raise ValueError("identity must be a three-part scoped tuple")
        if any(type(part) is not str or not part for part in identity):
            raise ValueError("identity components must be non-empty strings")

    @staticmethod
    def _validate_owner_epoch(owner: str, epoch: int) -> None:
        if type(owner) is not str or not owner:
            raise ValueError("owner must be a non-empty string")
        if type(epoch) is not int or epoch <= 0:
            raise ValueError("epoch must be a positive integer")

    def _row(self, identity: Identity) -> tuple | None:
        return self.conn.execute(
            """
            SELECT fingerprint, owner, epoch, lease_expired, durable_responsibility,
                   effect_committed, effect_count, acked, checkpointed
              FROM consumer_receipt
             WHERE consumer_contract=? AND identity_scope=? AND message_id=?
            """,
            identity,
        ).fetchone()

    @staticmethod
    def _receipt(row: tuple) -> Receipt:
        return Receipt(
            fingerprint=row[0],
            owner=row[1],
            epoch=int(row[2]),
            lease_expired=bool(row[3]),
            durable_responsibility=bool(row[4]),
            effect_committed=bool(row[5]),
            effect_count=int(row[6]),
            acked=bool(row[7]),
            checkpointed=bool(row[8]),
        )

    def _get(self, identity: Identity) -> Receipt:
        row = self._row(identity)
        if row is None:
            raise PrematureProgress("durable consumer responsibility does not exist")
        return self._receipt(row)

    @staticmethod
    def _assert_owner(receipt: Receipt, owner: str, epoch: int) -> None:
        if receipt.owner != owner or receipt.epoch != epoch or receipt.lease_expired:
            raise FenceViolation("owner is not current fenced authority")

    def claim(self, identity: Identity, payload: Any, owner: str, epoch: int) -> Receipt:
        self._validate_identity(identity)
        self._validate_owner_epoch(owner, epoch)
        fp = self.fingerprint(payload)
        with self._tx():
            row = self._row(identity)
            if row is None:
                self.conn.execute(
                    """
                    INSERT INTO consumer_receipt
                    VALUES (?, ?, ?, ?, ?, ?, 0, 1, 0, 0, 0, 0)
                    """,
                    (*identity, fp, owner, epoch),
                )
                return self._get(identity)

            receipt = self._receipt(row)
            if receipt.fingerprint is None:
                raise Uncertainty("scoped identity exists but content-equivalence authority is unavailable")
            if receipt.fingerprint != fp:
                raise IntegrityFailure("same scoped identity has conflicting immutable content")

            if receipt.owner is not None:
                if epoch < receipt.epoch:
                    raise FenceViolation("stale claim epoch")
                if epoch == receipt.epoch and receipt.owner != owner:
                    raise FenceViolation("concurrent owner at same epoch")
                if epoch > receipt.epoch:
                    raise FenceViolation("takeover cannot bypass explicit lease expiry")
                return receipt

            if not receipt.lease_expired:
                raise FenceViolation("ownerless claim without explicit expiry is invalid")
            if epoch <= receipt.epoch:
                raise FenceViolation("takeover requires a strictly newer fence epoch")

            self.conn.execute(
                """
                UPDATE consumer_receipt
                   SET owner=?, epoch=?, lease_expired=0
                 WHERE consumer_contract=? AND identity_scope=? AND message_id=?
                """,
                (owner, epoch, *identity),
            )
            return self._get(identity)

    def expire_lease(self, identity: Identity, owner: str, epoch: int) -> None:
        self._validate_identity(identity)
        self._validate_owner_epoch(owner, epoch)
        with self._tx():
            receipt = self._get(identity)
            self._assert_owner(receipt, owner, epoch)
            self.conn.execute(
                """
                UPDATE consumer_receipt
                   SET owner=NULL, lease_expired=1
                 WHERE consumer_contract=? AND identity_scope=? AND message_id=?
                """,
                identity,
            )

    def complete_effect(self, identity: Identity, owner: str, epoch: int) -> str:
        self._validate_owner_epoch(owner, epoch)
        with self._tx():
            receipt = self._get(identity)
            self._assert_owner(receipt, owner, epoch)
            if receipt.fingerprint is None:
                raise Uncertainty("effect admission requires content-equivalence authority")
            if receipt.effect_committed:
                return "duplicate_noop"
            self.conn.execute(
                """
                UPDATE consumer_receipt
                   SET effect_committed=1, effect_count=effect_count+1
                 WHERE consumer_contract=? AND identity_scope=? AND message_id=?
                """,
                identity,
            )
            return "effect_committed"

    def ack(self, identity: Identity, owner: str, epoch: int) -> None:
        self._validate_owner_epoch(owner, epoch)
        with self._tx():
            receipt = self._get(identity)
            self._assert_owner(receipt, owner, epoch)
            if not receipt.durable_responsibility:
                raise PrematureProgress("ack cannot precede durable responsibility")
            self.conn.execute(
                """
                UPDATE consumer_receipt SET acked=1
                 WHERE consumer_contract=? AND identity_scope=? AND message_id=?
                """,
                identity,
            )

    def checkpoint(self, identity: Identity, owner: str, epoch: int) -> None:
        self._validate_owner_epoch(owner, epoch)
        with self._tx():
            receipt = self._get(identity)
            self._assert_owner(receipt, owner, epoch)
            if not receipt.durable_responsibility:
                raise PrematureProgress("checkpoint cannot precede durable responsibility")
            self.conn.execute(
                """
                UPDATE consumer_receipt SET checkpointed=1
                 WHERE consumer_contract=? AND identity_scope=? AND message_id=?
                """,
                identity,
            )

    def business_effect_truth(self, identity: Identity) -> bool:
        row = self._row(identity)
        return bool(row and self._receipt(row).effect_committed)

    def effect_count(self, identity: Identity) -> int:
        return self._get(identity).effect_count

    def remove_equivalence_authority(self, identity: Identity) -> None:
        with self._tx():
            self._get(identity)
            self.conn.execute(
                """
                UPDATE consumer_receipt SET fingerprint=NULL
                 WHERE consumer_contract=? AND identity_scope=? AND message_id=?
                """,
                identity,
            )


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


def _advance_progress(store: DurableConsumerAuthority, profile: str, identity: Identity, owner: str, epoch: int) -> None:
    if profile == "database_owned_work_claim_plus_broker_checkpoint_profile":
        store.checkpoint(identity, owner, epoch)
    else:
        store.ack(identity, owner, epoch)


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
    _advance_progress(progress_only, profile, identity, "w1", 1)
    broker_progress_not_effect_truth = not progress_only.business_effect_truth(identity)

    ambiguous = DurableConsumerAuthority()
    ambiguous.claim(identity, payload, "w1", 1)
    ambiguous.complete_effect(identity, "w1", 1)
    ambiguous.expire_lease(identity, "w1", 1)
    same_epoch_takeover_rejected = _expect(FenceViolation, lambda: ambiguous.claim(identity, payload, "w2", 1))
    ambiguous.claim(identity, payload, "w2", 2)
    duplicate_result = ambiguous.complete_effect(identity, "w2", 2)
    lease_expiry_ambiguous_safe = duplicate_result == "duplicate_noop" and ambiguous.effect_count(identity) == 1

    conflicting = DurableConsumerAuthority()
    conflicting.claim(identity, payload, "w1", 1)
    conflicting_content_fails_closed = _expect(
        IntegrityFailure,
        lambda: conflicting.claim(identity, {**payload, "revision": 8}, "w2", 2),
    )

    rewind = DurableConsumerAuthority()
    rewind.claim(identity, payload, "w1", 1)
    rewind.remove_equivalence_authority(identity)
    rewind_requires_equivalence = _expect(Uncertainty, lambda: rewind.claim(identity, payload, "w1", 1))

    fenced = DurableConsumerAuthority()
    fenced.claim(identity, payload, "w1", 1)
    fenced.expire_lease(identity, "w1", 1)
    fenced.claim(identity, payload, "w2", 2)
    stale_owner_fenced = _expect(FenceViolation, lambda: fenced.complete_effect(identity, "w1", 1))

    with tempfile.TemporaryDirectory(prefix="d4c-ack-before-") as td:
        db = Path(td) / "authority.sqlite3"
        first = DurableConsumerAuthority(db)
        first.claim(identity, payload, "w1", 1)
        first.close()
        restarted = DurableConsumerAuthority(db)
        restart_preserved_receipt = not restarted.business_effect_truth(identity) and restarted._get(identity).fingerprint is not None
        restarted.expire_lease(identity, "w1", 1)
        restarted.claim(identity, payload, "w2", 2)
        restarted.complete_effect(identity, "w2", 2)
        _advance_progress(restarted, profile, identity, "w2", 2)
        responsibility_crash_recovers = restarted.effect_count(identity) == 1
        restarted.close()

    with tempfile.TemporaryDirectory(prefix="d4c-ack-after-") as td:
        db = Path(td) / "authority.sqlite3"
        first = DurableConsumerAuthority(db)
        first.claim(identity, payload, "w1", 1)
        first.complete_effect(identity, "w1", 1)
        first.close()
        restarted = DurableConsumerAuthority(db)
        restart_preserved_effect_truth = restarted.business_effect_truth(identity) and restarted.effect_count(identity) == 1
        restarted.expire_lease(identity, "w1", 1)
        restarted.claim(identity, payload, "w2", 2)
        second = restarted.complete_effect(identity, "w2", 2)
        _advance_progress(restarted, profile, identity, "w2", 2)
        effect_to_progress_crash_safe = second == "duplicate_noop" and restarted.effect_count(identity) == 1
        restarted.close()

    return {
        "premature_ack_rejected": premature_ack,
        "premature_checkpoint_rejected": premature_checkpoint,
        "broker_progress_not_effect_truth": broker_progress_not_effect_truth,
        "lease_expiry_requires_new_fence_epoch": same_epoch_takeover_rejected,
        "lease_expiry_is_ambiguity_with_idempotent_redelivery": lease_expiry_ambiguous_safe,
        "rewind_requires_content_equivalence_authority": rewind_requires_equivalence,
        "conflicting_same_identity_fails_closed": conflicting_content_fails_closed,
        "stale_owner_is_fenced": stale_owner_fenced,
        "restart_preserves_durable_receipt_and_equivalence_authority": restart_preserved_receipt,
        "crash_after_responsibility_before_effect_or_progress_recovers": responsibility_crash_recovers,
        "restart_preserves_effect_truth": restart_preserved_effect_truth,
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
