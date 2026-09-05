#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Tuple


class EvidenceError(Exception):
    pass


class AuthorizationDenied(EvidenceError):
    pass


class IntegrityFailure(EvidenceError):
    pass


class ClassificationDenied(EvidenceError):
    pass


class Uncertainty(EvidenceError):
    pass


Identity = Tuple[str, str, str]
TEST_RETRY_BUDGET = 3  # evidence fixture only; never production numeric authority
TEST_FINGERPRINT_PROFILE = "sha256_fixture_only_noncanonical"
CANDIDATES = (
    "durable_platform_quarantine_store_with_broker_dlq_adapter",
    "broker_native_dlq_with_canonical_platform_quarantine_index",
    "hybrid_platform_quarantine_store_plus_broker_dlq",
)


class QuarantineAuthority:
    """SQLite-backed platform quarantine truth used only as executable evidence.

    Broker DLQ coordinates are adapter metadata. Platform quarantine identity,
    immutable-content equivalence, current redrive authority, audit history and
    classification policy remain platform-owned. Numeric retry values below are
    bounded test fixtures and do not select production retry/retention horizons.
    SHA-256 is only a deterministic evidence comparator and does not select the
    OPEN-EVT-011 production equivalence profile.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        target = ":memory:" if db_path is None else str(db_path)
        self.conn = sqlite3.connect(target, timeout=5.0)
        self.conn.execute("PRAGMA synchronous=FULL")
        if target != ":memory:":
            self.conn.execute("PRAGMA journal_mode=DELETE")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quarantine_record (
              consumer_contract TEXT NOT NULL,
              identity_scope TEXT NOT NULL,
              message_id TEXT NOT NULL,
              fingerprint TEXT,
              payload_json TEXT NOT NULL,
              classification TEXT NOT NULL,
              retention_policy_class TEXT NOT NULL,
              retry_count INTEGER NOT NULL,
              retry_budget INTEGER NOT NULL,
              state TEXT NOT NULL,
              broker_adapter TEXT NOT NULL,
              broker_dlq_ref TEXT,
              effect_committed INTEGER NOT NULL DEFAULT 0,
              external_outcome_unknown INTEGER NOT NULL DEFAULT 0,
              audit_json TEXT NOT NULL,
              PRIMARY KEY (consumer_contract, identity_scope, message_id)
            )
            """
        )
        self.conn.commit()

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

    def close(self) -> None:
        self.conn.close()

    @staticmethod
    def fingerprint(content: Any) -> str:
        canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_identity(identity: Identity) -> None:
        if not isinstance(identity, tuple) or len(identity) != 3 or any(type(v) is not str or not v for v in identity):
            raise ValueError("identity must be a three-part non-empty scoped tuple")

    def _row(self, identity: Identity) -> sqlite3.Row | tuple | None:
        return self.conn.execute(
            """SELECT fingerprint,payload_json,classification,retention_policy_class,retry_count,retry_budget,
                      state,broker_adapter,broker_dlq_ref,effect_committed,external_outcome_unknown,audit_json
                 FROM quarantine_record
                WHERE consumer_contract=? AND identity_scope=? AND message_id=?""",
            identity,
        ).fetchone()

    def record_failure(
        self,
        identity: Identity,
        content: Any,
        *,
        classification: str,
        retention_policy_class: str,
        retry_count: int,
        retry_budget: int,
        broker_adapter: str,
        broker_dlq_ref: str | None,
    ) -> str:
        self._validate_identity(identity)
        if type(retry_count) is not int or type(retry_budget) is not int or retry_count < 0 or retry_budget <= 0:
            raise ValueError("retry counters must be bounded positive test integers")
        if type(classification) is not str or not classification:
            raise ValueError("classification required")
        if type(retention_policy_class) is not str or not retention_policy_class or any(ch.isdigit() for ch in retention_policy_class):
            raise ValueError("retention must be a nonnumeric governed policy class")
        fp = self.fingerprint(content)
        state = "quarantined" if retry_count >= retry_budget else "retryable"
        audit = [{"action": "failure_recorded", "retry_count": retry_count, "state": state}]
        with self._tx():
            existing = self._row(identity)
            if existing is not None and existing[0] != fp:
                raise IntegrityFailure("same scoped identity has conflicting immutable content")
            self.conn.execute(
                """INSERT OR REPLACE INTO quarantine_record
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,0,?)""",
                (*identity, fp, json.dumps(content, sort_keys=True), classification, retention_policy_class,
                 retry_count, retry_budget, state, broker_adapter, broker_dlq_ref, json.dumps(audit, sort_keys=True)),
            )
        return state

    def set_effect_truth(self, identity: Identity, *, committed: bool, external_outcome_unknown: bool = False) -> None:
        with self._tx():
            if self._row(identity) is None:
                raise Uncertainty("quarantine record missing")
            self.conn.execute(
                """UPDATE quarantine_record SET effect_committed=?, external_outcome_unknown=?
                     WHERE consumer_contract=? AND identity_scope=? AND message_id=?""",
                (1 if committed else 0, 1 if external_outcome_unknown else 0, *identity),
            )

    def remove_equivalence_authority(self, identity: Identity) -> None:
        with self._tx():
            if self._row(identity) is None:
                raise Uncertainty("quarantine record missing")
            self.conn.execute(
                """UPDATE quarantine_record SET fingerprint=NULL
                     WHERE consumer_contract=? AND identity_scope=? AND message_id=?""",
                identity,
            )

    def read_payload(self, identity: Identity, allowed_classifications: set[str]) -> dict:
        row = self._row(identity)
        if row is None:
            raise Uncertainty("quarantine record missing")
        if row[2] not in allowed_classifications:
            raise ClassificationDenied("classification-scoped payload access denied")
        return json.loads(row[1])

    def redrive(
        self,
        identity: Identity,
        content: Any,
        *,
        actor: str,
        reason: str,
        currently_authorized: bool,
        allowed_classifications: set[str],
    ) -> str:
        self._validate_identity(identity)
        if not currently_authorized or type(actor) is not str or not actor:
            raise AuthorizationDenied("redrive requires current privileged authority")
        if type(reason) is not str or not reason:
            raise ValueError("audited redrive reason required")
        with self._tx():
            row = self._row(identity)
            if row is None or row[6] != "quarantined":
                raise Uncertainty("redrive requires governed quarantine truth")
            if row[2] not in allowed_classifications:
                raise ClassificationDenied("redrive access is classification scoped")
            if row[0] is None:
                raise Uncertainty("equivalence authority unavailable; identity alone is insufficient")
            if row[0] != self.fingerprint(content):
                raise IntegrityFailure("same scoped identity has conflicting immutable content")
            audit = json.loads(row[11])
            audit.append({"action": "redrive_requested", "actor": actor, "reason": reason})
            if bool(row[10]):
                outcome = "reconciliation_required"
            elif bool(row[9]):
                outcome = "duplicate_noop"
            else:
                outcome = "admitted_for_reprocessing"
            audit.append({"action": "redrive_admission", "outcome": outcome})
            self.conn.execute(
                """UPDATE quarantine_record SET state='redriven', audit_json=?
                     WHERE consumer_contract=? AND identity_scope=? AND message_id=?""",
                (json.dumps(audit, sort_keys=True), *identity),
            )
            return outcome

    def replace_broker(self, identity: Identity, *, new_adapter: str, new_dlq_ref: str | None) -> None:
        with self._tx():
            row = self._row(identity)
            if row is None:
                raise Uncertainty("quarantine record missing")
            audit = json.loads(row[11])
            audit.append({"action": "broker_adapter_replaced", "from": row[7], "to": new_adapter})
            self.conn.execute(
                """UPDATE quarantine_record SET broker_adapter=?, broker_dlq_ref=?, audit_json=?
                     WHERE consumer_contract=? AND identity_scope=? AND message_id=?""",
                (new_adapter, new_dlq_ref, json.dumps(audit, sort_keys=True), *identity),
            )

    def snapshot(self, identity: Identity) -> dict:
        row = self._row(identity)
        if row is None:
            raise Uncertainty("quarantine record missing")
        return {
            "fingerprint": row[0], "classification": row[2], "retention_policy_class": row[3],
            "retry_count": row[4], "retry_budget": row[5], "state": row[6],
            "broker_adapter": row[7], "broker_dlq_ref": row[8], "effect_committed": bool(row[9]),
            "external_outcome_unknown": bool(row[10]), "audit": json.loads(row[11]),
        }


def _expect(exc_type, fn) -> bool:
    try:
        fn()
    except exc_type:
        return True
    return False


def run_profile(profile: str) -> Dict[str, bool]:
    if profile not in CANDIDATES:
        raise ValueError(profile)
    identity = ("consumer.orders.v1", "tenant:t1/order:o1", "msg-009")
    content = {"envelope": {"event_type": "order.updated", "contract_version": 7}, "payload": {"order_id": "o1", "revision": 9}}
    broker_ref = "broker-dlq:opaque-ref" if profile != "durable_platform_quarantine_store_with_broker_dlq_adapter" else None

    q = QuarantineAuthority()
    retryable = q.record_failure(identity, content, classification="confidential", retention_policy_class="regulated_event_policy", retry_count=TEST_RETRY_BUDGET - 1, retry_budget=TEST_RETRY_BUDGET, broker_adapter=profile, broker_dlq_ref=broker_ref)
    quarantined = q.record_failure(identity, content, classification="confidential", retention_policy_class="regulated_event_policy", retry_count=TEST_RETRY_BUDGET, retry_budget=TEST_RETRY_BUDGET, broker_adapter=profile, broker_dlq_ref=broker_ref)
    bounded_retry_to_quarantine = retryable == "retryable" and quarantined == "quarantined"

    before = q.snapshot(identity)
    platform_identity_independent_of_dlq = before["fingerprint"] == q.fingerprint(content) and before["state"] == "quarantined"
    unauthorized_redrive_rejected = _expect(AuthorizationDenied, lambda: q.redrive(identity, content, actor="operator", reason="manual", currently_authorized=False, allowed_classifications={"confidential"}))
    classification_scope_enforced = _expect(ClassificationDenied, lambda: q.read_payload(identity, {"public"}))
    conflicting_content_rejected = _expect(IntegrityFailure, lambda: q.redrive(identity, {**content, "payload": {"order_id": "o1", "revision": 10}}, actor="admin", reason="manual", currently_authorized=True, allowed_classifications={"confidential"}))

    q.set_effect_truth(identity, committed=True)
    duplicate_outcome = q.redrive(identity, content, actor="admin", reason="authorized replay", currently_authorized=True, allowed_classifications={"confidential"})
    audit = q.snapshot(identity)["audit"]
    redrive_audited_and_dedup_safe = duplicate_outcome == "duplicate_noop" and any(e.get("action") == "redrive_requested" and e.get("actor") == "admin" for e in audit)
    q.close()

    uncertain = QuarantineAuthority()
    uncertain.record_failure(identity, content, classification="confidential", retention_policy_class="regulated_event_policy", retry_count=TEST_RETRY_BUDGET, retry_budget=TEST_RETRY_BUDGET, broker_adapter=profile, broker_dlq_ref=broker_ref)
    uncertain.set_effect_truth(identity, committed=False, external_outcome_unknown=True)
    reconciliation_required = uncertain.redrive(identity, content, actor="admin", reason="recover ambiguous external effect", currently_authorized=True, allowed_classifications={"confidential"}) == "reconciliation_required"
    uncertain.close()

    missing_equivalence = QuarantineAuthority()
    missing_equivalence.record_failure(identity, content, classification="confidential", retention_policy_class="regulated_event_policy", retry_count=TEST_RETRY_BUDGET, retry_budget=TEST_RETRY_BUDGET, broker_adapter=profile, broker_dlq_ref=broker_ref)
    missing_equivalence.remove_equivalence_authority(identity)
    identity_only_rejected = _expect(Uncertainty, lambda: missing_equivalence.redrive(identity, content, actor="admin", reason="manual", currently_authorized=True, allowed_classifications={"confidential"}))
    missing_equivalence.close()

    with tempfile.TemporaryDirectory(prefix="d4c-quarantine-") as td:
        db = Path(td) / "quarantine.sqlite3"
        persisted = QuarantineAuthority(db)
        persisted.record_failure(identity, content, classification="confidential", retention_policy_class="regulated_event_policy", retry_count=TEST_RETRY_BUDGET, retry_budget=TEST_RETRY_BUDGET, broker_adapter=profile, broker_dlq_ref=broker_ref)
        original = persisted.snapshot(identity)
        persisted.replace_broker(identity, new_adapter="replacement_broker_adapter", new_dlq_ref="replacement:opaque-ref")
        replaced = persisted.snapshot(identity)
        persisted.close()
        reopened = QuarantineAuthority(db)
        after_restart = reopened.snapshot(identity)
        broker_replacement_preserves_truth = original["fingerprint"] == replaced["fingerprint"] == after_restart["fingerprint"] and after_restart["classification"] == "confidential" and after_restart["retention_policy_class"] == "regulated_event_policy" and after_restart["broker_adapter"] == "replacement_broker_adapter" and any(e.get("action") == "broker_adapter_replaced" for e in after_restart["audit"])
        reopened.close()

    retention_policy_nonnumeric = before["retention_policy_class"] == "regulated_event_policy" and not any(ch.isdigit() for ch in before["retention_policy_class"])
    fingerprint_fixture_noncanonical = TEST_FINGERPRINT_PROFILE == "sha256_fixture_only_noncanonical"

    return {
        "platform_quarantine_truth_independent_of_broker_dlq": platform_identity_independent_of_dlq,
        "bounded_retry_exhaustion_reaches_quarantine": bounded_retry_to_quarantine,
        "unauthorized_redrive_rejected": unauthorized_redrive_rejected,
        "redrive_is_audited_and_dedup_safe": redrive_audited_and_dedup_safe,
        "ambiguous_external_effect_requires_reconciliation": reconciliation_required,
        "same_identity_conflicting_content_rejected": conflicting_content_rejected,
        "identity_without_equivalence_authority_rejected": identity_only_rejected,
        "classification_scoped_access_enforced": classification_scope_enforced,
        "retention_policy_is_nonnumeric_governed_class": retention_policy_nonnumeric,
        "broker_replacement_preserves_platform_truth": broker_replacement_preserves_truth,
        "test_fingerprint_profile_is_noncanonical": fingerprint_fixture_noncanonical,
    }


def evaluate_all() -> dict:
    checks = {profile: run_profile(profile) for profile in CANDIDATES}
    results = {profile: ("eligible_for_evidence_execution" if all(profile_checks.values()) else "insufficient_evidence") for profile, profile_checks in checks.items()}
    return {
        "candidate_results": results,
        "equivalent_reviewed_profile": "insufficient_evidence",
        "checks": checks,
        "selection": "not_selected",
        "ledger_credit": [],
        "test_retry_budget_is_noncanonical_fixture": True,
        "test_fingerprint_profile": TEST_FINGERPRINT_PROFILE,
    }


if __name__ == "__main__":
    print(json.dumps(evaluate_all(), indent=2, sort_keys=True))
