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
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS redrive_grant (
              actor TEXT NOT NULL,
              classification TEXT NOT NULL,
              active INTEGER NOT NULL CHECK (active IN (0,1)),
              PRIMARY KEY (actor, classification)
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

    @staticmethod
    def _validate_actor(actor: str) -> None:
        if type(actor) is not str or not actor:
            raise ValueError("actor must be a non-empty string")

    def _row(self, identity: Identity) -> tuple | None:
        return self.conn.execute(
            """SELECT fingerprint,payload_json,classification,retention_policy_class,retry_count,retry_budget,
                      state,broker_adapter,broker_dlq_ref,effect_committed,external_outcome_unknown,audit_json
                 FROM quarantine_record
                WHERE consumer_contract=? AND identity_scope=? AND message_id=?""",
            identity,
        ).fetchone()

    def _append_audit(self, identity: Identity, event: dict) -> None:
        with self._tx():
            row = self._row(identity)
            if row is None:
                raise Uncertainty("quarantine record missing")
            audit = json.loads(row[11])
            audit.append(event)
            self.conn.execute(
                """UPDATE quarantine_record SET audit_json=?
                     WHERE consumer_contract=? AND identity_scope=? AND message_id=?""",
                (json.dumps(audit, sort_keys=True), *identity),
            )

    def grant_redrive(self, actor: str, classifications: set[str]) -> None:
        self._validate_actor(actor)
        if not classifications or any(type(v) is not str or not v for v in classifications):
            raise ValueError("at least one non-empty classification is required")
        with self._tx():
            for classification in classifications:
                self.conn.execute(
                    """INSERT INTO redrive_grant(actor,classification,active) VALUES(?,?,1)
                       ON CONFLICT(actor,classification) DO UPDATE SET active=1""",
                    (actor, classification),
                )

    def revoke_redrive(self, actor: str) -> None:
        self._validate_actor(actor)
        with self._tx():
            self.conn.execute("UPDATE redrive_grant SET active=0 WHERE actor=?", (actor,))

    def _has_any_active_grant(self, actor: str) -> bool:
        return self.conn.execute("SELECT 1 FROM redrive_grant WHERE actor=? AND active=1 LIMIT 1", (actor,)).fetchone() is not None

    def _has_current_grant(self, actor: str, classification: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM redrive_grant WHERE actor=? AND classification=? AND active=1",
            (actor, classification),
        ).fetchone() is not None

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
        if type(broker_adapter) is not str or not broker_adapter:
            raise ValueError("broker adapter metadata required")
        fp = self.fingerprint(content)
        with self._tx():
            existing = self._row(identity)
            if existing is None:
                state = "quarantined" if retry_count >= retry_budget else "retryable"
                audit = [{"action": "failure_recorded", "retry_count": retry_count, "state": state}]
                self.conn.execute(
                    """INSERT INTO quarantine_record
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,0,?)""",
                    (*identity, fp, json.dumps(content, sort_keys=True), classification, retention_policy_class,
                     retry_count, retry_budget, state, broker_adapter, broker_dlq_ref, json.dumps(audit, sort_keys=True)),
                )
            else:
                if existing[0] != fp:
                    raise IntegrityFailure("same scoped identity has conflicting immutable content")
                if existing[2] != classification or existing[3] != retention_policy_class:
                    raise IntegrityFailure("classification or retention policy cannot be silently rebound")
                if existing[5] != retry_budget:
                    raise IntegrityFailure("retry budget cannot be silently rebound for the same scoped identity")
                if retry_count < existing[4]:
                    raise IntegrityFailure("retry count cannot regress for the same scoped identity")
                state = "quarantined" if existing[6].startswith("quarantined") or retry_count >= retry_budget else "retryable"
                audit = json.loads(existing[11])
                audit.append({"action": "failure_recorded", "retry_count": retry_count, "state": state})
                self.conn.execute(
                    """UPDATE quarantine_record
                          SET retry_count=?, state=?, broker_adapter=?, broker_dlq_ref=?, audit_json=?
                        WHERE consumer_contract=? AND identity_scope=? AND message_id=?""",
                    (retry_count, state, broker_adapter, broker_dlq_ref, json.dumps(audit, sort_keys=True), *identity),
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

    def read_payload(self, identity: Identity, actor: str) -> dict:
        self._validate_actor(actor)
        row = self._row(identity)
        if row is None:
            raise Uncertainty("quarantine record missing")
        if not self._has_current_grant(actor, row[2]):
            raise ClassificationDenied("classification-scoped payload access denied")
        return json.loads(row[1])

    def redrive(self, identity: Identity, content: Any, *, actor: str, reason: str) -> str:
        self._validate_identity(identity)
        self._validate_actor(actor)
        if type(reason) is not str or not reason:
            raise ValueError("audited redrive reason required")
        initial = self._row(identity)
        if initial is None or initial[6] != "quarantined":
            raise Uncertainty("redrive requires governed quarantine truth")

        self._append_audit(identity, {"action": "redrive_attempt", "actor": actor, "reason": reason})
        row = self._row(identity)
        assert row is not None
        if not self._has_current_grant(actor, row[2]):
            denial = "classification_denied" if self._has_any_active_grant(actor) else "authority_denied"
            self._append_audit(identity, {"action": "redrive_denied", "actor": actor, "reason": denial})
            if denial == "classification_denied":
                raise ClassificationDenied("current grant does not cover quarantine classification")
            raise AuthorizationDenied("redrive requires current privileged authority")
        if row[0] is None:
            self._append_audit(identity, {"action": "redrive_blocked", "actor": actor, "reason": "equivalence_unavailable"})
            raise Uncertainty("equivalence authority unavailable; identity alone is insufficient")
        if row[0] != self.fingerprint(content):
            self._append_audit(identity, {"action": "redrive_blocked", "actor": actor, "reason": "content_conflict"})
            raise IntegrityFailure("same scoped identity has conflicting immutable content")

        if bool(row[10]):
            outcome = "reconciliation_required"
            next_state = "quarantined_reconciliation"
        elif bool(row[9]):
            outcome = "duplicate_noop"
            next_state = "resolved_duplicate"
        else:
            outcome = "admitted_for_reprocessing"
            next_state = "redrive_admitted"
        self._append_audit(identity, {"action": "redrive_admission", "actor": actor, "outcome": outcome})
        with self._tx():
            self.conn.execute(
                """UPDATE quarantine_record SET state=?
                     WHERE consumer_contract=? AND identity_scope=? AND message_id=?""",
                (next_state, *identity),
            )
        return outcome

    def replace_broker(self, identity: Identity, *, new_adapter: str, new_dlq_ref: str | None) -> None:
        if type(new_adapter) is not str or not new_adapter:
            raise ValueError("replacement adapter required")
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
    q.set_effect_truth(identity, committed=False, external_outcome_unknown=False)
    quarantined = q.record_failure(identity, content, classification="confidential", retention_policy_class="regulated_event_policy", retry_count=TEST_RETRY_BUDGET, retry_budget=TEST_RETRY_BUDGET, broker_adapter=profile, broker_dlq_ref=broker_ref)
    after_retry_update = q.snapshot(identity)
    bounded_retry_to_quarantine = retryable == "retryable" and quarantined == "quarantined" and len(after_retry_update["audit"]) == 2 and after_retry_update["effect_committed"] is False
    retry_count_regression_rejected = _expect(IntegrityFailure, lambda: q.record_failure(identity, content, classification="confidential", retention_policy_class="regulated_event_policy", retry_count=TEST_RETRY_BUDGET - 1, retry_budget=TEST_RETRY_BUDGET, broker_adapter=profile, broker_dlq_ref=broker_ref))
    retry_budget_rebind_rejected = _expect(IntegrityFailure, lambda: q.record_failure(identity, content, classification="confidential", retention_policy_class="regulated_event_policy", retry_count=TEST_RETRY_BUDGET + 1, retry_budget=TEST_RETRY_BUDGET + 1, broker_adapter=profile, broker_dlq_ref=broker_ref))
    quarantine_nonregression = q.snapshot(identity)["state"] == "quarantined"

    before = q.snapshot(identity)
    platform_identity_independent_of_dlq = before["fingerprint"] == q.fingerprint(content) and before["state"] == "quarantined"

    q.grant_redrive("historical-admin", {"confidential"})
    q.revoke_redrive("historical-admin")
    historical_grant_revoked = _expect(AuthorizationDenied, lambda: q.redrive(identity, content, actor="historical-admin", reason="revoked actor retry"))
    denied_audited = any(e.get("action") == "redrive_denied" and e.get("actor") == "historical-admin" for e in q.snapshot(identity)["audit"])

    q.grant_redrive("public-operator", {"public"})
    classification_scope_enforced = _expect(ClassificationDenied, lambda: q.read_payload(identity, "public-operator")) and _expect(ClassificationDenied, lambda: q.redrive(identity, content, actor="public-operator", reason="wrong classification"))

    q.grant_redrive("admin", {"confidential"})
    conflicting_content_rejected = _expect(IntegrityFailure, lambda: q.redrive(identity, {**content, "payload": {"order_id": "o1", "revision": 10}}, actor="admin", reason="conflicting replay"))

    q.set_effect_truth(identity, committed=True)
    duplicate_outcome = q.redrive(identity, content, actor="admin", reason="authorized replay")
    audit = q.snapshot(identity)["audit"]
    redrive_audited_and_dedup_safe = duplicate_outcome == "duplicate_noop" and any(e.get("action") == "redrive_attempt" and e.get("actor") == "admin" for e in audit) and q.snapshot(identity)["state"] == "resolved_duplicate"
    q.close()

    uncertain = QuarantineAuthority()
    uncertain.record_failure(identity, content, classification="confidential", retention_policy_class="regulated_event_policy", retry_count=TEST_RETRY_BUDGET, retry_budget=TEST_RETRY_BUDGET, broker_adapter=profile, broker_dlq_ref=broker_ref)
    uncertain.grant_redrive("admin", {"confidential"})
    uncertain.set_effect_truth(identity, committed=False, external_outcome_unknown=True)
    reconciliation_required = uncertain.redrive(identity, content, actor="admin", reason="recover ambiguous external effect") == "reconciliation_required" and uncertain.snapshot(identity)["state"] == "quarantined_reconciliation"
    uncertain.close()

    missing_equivalence = QuarantineAuthority()
    missing_equivalence.record_failure(identity, content, classification="confidential", retention_policy_class="regulated_event_policy", retry_count=TEST_RETRY_BUDGET, retry_budget=TEST_RETRY_BUDGET, broker_adapter=profile, broker_dlq_ref=broker_ref)
    missing_equivalence.grant_redrive("admin", {"confidential"})
    missing_equivalence.remove_equivalence_authority(identity)
    identity_only_rejected = _expect(Uncertainty, lambda: missing_equivalence.redrive(identity, content, actor="admin", reason="missing equivalence"))
    missing_equivalence.close()

    with tempfile.TemporaryDirectory(prefix="d4c-quarantine-") as td:
        db = Path(td) / "quarantine.sqlite3"
        persisted = QuarantineAuthority(db)
        persisted.record_failure(identity, content, classification="confidential", retention_policy_class="regulated_event_policy", retry_count=TEST_RETRY_BUDGET, retry_budget=TEST_RETRY_BUDGET, broker_adapter=profile, broker_dlq_ref=broker_ref)
        persisted.grant_redrive("admin", {"confidential"})
        original = persisted.snapshot(identity)
        persisted.replace_broker(identity, new_adapter="replacement_broker_adapter", new_dlq_ref="replacement:opaque-ref")
        replaced = persisted.snapshot(identity)
        persisted.close()
        reopened = QuarantineAuthority(db)
        after_restart = reopened.snapshot(identity)
        current_authority_survives_restart = reopened.read_payload(identity, "admin") == content
        broker_replacement_preserves_truth = original["fingerprint"] == replaced["fingerprint"] == after_restart["fingerprint"] and after_restart["classification"] == "confidential" and after_restart["retention_policy_class"] == "regulated_event_policy" and after_restart["broker_adapter"] == "replacement_broker_adapter" and any(e.get("action") == "broker_adapter_replaced" for e in after_restart["audit"])
        reopened.close()

    retention_policy_nonnumeric = before["retention_policy_class"] == "regulated_event_policy" and not any(ch.isdigit() for ch in before["retention_policy_class"])
    fingerprint_fixture_noncanonical = TEST_FINGERPRINT_PROFILE == "sha256_fixture_only_noncanonical"

    return {
        "platform_quarantine_truth_independent_of_broker_dlq": platform_identity_independent_of_dlq,
        "bounded_retry_exhaustion_reaches_quarantine_without_truth_reset": bounded_retry_to_quarantine,
        "retry_count_regression_is_rejected": retry_count_regression_rejected,
        "retry_budget_rebind_is_rejected": retry_budget_rebind_rejected,
        "quarantine_state_cannot_regress_via_failure_redelivery": quarantine_nonregression,
        "historical_privilege_revocation_blocks_redrive": historical_grant_revoked,
        "denied_redrive_attempt_is_audited": denied_audited,
        "redrive_is_audited_and_dedup_safe": redrive_audited_and_dedup_safe,
        "ambiguous_external_effect_requires_reconciliation": reconciliation_required,
        "same_identity_conflicting_content_rejected": conflicting_content_rejected,
        "identity_without_equivalence_authority_rejected": identity_only_rejected,
        "classification_scoped_access_enforced": classification_scope_enforced,
        "retention_policy_is_nonnumeric_governed_class": retention_policy_nonnumeric,
        "broker_replacement_preserves_platform_truth": broker_replacement_preserves_truth,
        "current_authority_state_survives_process_restart": current_authority_survives_restart,
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
