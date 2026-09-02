from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class DurableResponsibilityReceipt:
    consumer_contract: str
    message_identity_scope: str
    message_id: str
    receipt_id: str
    payload_digest: str
    effect_key: str


class EffectProtectionGuard:
    """Marker contract for executable inbox/effect protection implementations."""

    profile = "abstract"
    contract_id = "abstract"


class SQLiteAtomicInboxEffectGuard(EffectProtectionGuard):
    """Executable atomic-local evidence guard backed by durable SQLite state."""

    profile = "atomic_local"
    contract_id = "sqlite_atomic_inbox_effect_v1"

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS inbox (
                    consumer_contract TEXT NOT NULL,
                    message_identity_scope TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    PRIMARY KEY (consumer_contract, message_identity_scope, message_id)
                );
                CREATE TABLE IF NOT EXISTS business_effect (
                    effect_key TEXT PRIMARY KEY,
                    consumer_contract TEXT NOT NULL,
                    message_identity_scope TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    apply_count INTEGER NOT NULL CHECK (apply_count = 1)
                );
                CREATE TABLE IF NOT EXISTS durable_receipt (
                    receipt_id TEXT PRIMARY KEY,
                    consumer_contract TEXT NOT NULL,
                    message_identity_scope TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    effect_key TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _digest(payload: str) -> str:
        return sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _receipt_id(consumer_contract: str, message_identity_scope: str, message_id: str, payload_digest: str) -> str:
        material = f"{consumer_contract}|{message_identity_scope}|{message_id}|{payload_digest}|d4a-responsibility-v1"
        return sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _effect_key(consumer_contract: str, message_identity_scope: str, message_id: str) -> str:
        material = f"{consumer_contract}|{message_identity_scope}|{message_id}|d4a-effect-v1"
        return sha256(material.encode("utf-8")).hexdigest()

    def record_and_apply(
        self,
        *,
        consumer_contract: str,
        message_identity_scope: str,
        message_id: str,
        payload: str,
    ) -> DurableResponsibilityReceipt:
        if not message_identity_scope:
            raise ValueError("trusted message identity scope is required")
        payload_digest = self._digest(payload)
        effect_key = self._effect_key(consumer_contract, message_identity_scope, message_id)
        receipt_id = self._receipt_id(consumer_contract, message_identity_scope, message_id, payload_digest)

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT payload_digest FROM inbox WHERE consumer_contract=? AND message_identity_scope=? AND message_id=?",
                (consumer_contract, message_identity_scope, message_id),
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO inbox(consumer_contract,message_identity_scope,message_id,payload_digest) VALUES(?,?,?,?)",
                    (consumer_contract, message_identity_scope, message_id, payload_digest),
                )
                connection.execute(
                    "INSERT INTO business_effect(effect_key,consumer_contract,message_identity_scope,message_id,payload,apply_count) VALUES(?,?,?,?,?,1)",
                    (effect_key, consumer_contract, message_identity_scope, message_id, payload),
                )
            elif existing[0] != payload_digest:
                raise ValueError("replayed scoped message identity has conflicting payload")

            connection.execute(
                "INSERT OR IGNORE INTO durable_receipt(receipt_id,consumer_contract,message_identity_scope,message_id,payload_digest,effect_key) VALUES(?,?,?,?,?,?)",
                (receipt_id, consumer_contract, message_identity_scope, message_id, payload_digest, effect_key),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        receipt = DurableResponsibilityReceipt(
            consumer_contract=consumer_contract,
            message_identity_scope=message_identity_scope,
            message_id=message_id,
            receipt_id=receipt_id,
            payload_digest=payload_digest,
            effect_key=effect_key,
        )
        self.assert_durable(receipt)
        return receipt

    def assert_durable(self, receipt: DurableResponsibilityReceipt) -> None:
        if not isinstance(receipt, DurableResponsibilityReceipt):
            raise TypeError("acknowledgement requires a durable responsibility receipt")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT r.payload_digest, i.payload_digest, e.payload, e.apply_count,
                       e.consumer_contract, e.message_identity_scope, e.message_id
                FROM durable_receipt r
                JOIN inbox i
                  ON i.consumer_contract=r.consumer_contract
                 AND i.message_identity_scope=r.message_identity_scope
                 AND i.message_id=r.message_id
                JOIN business_effect e ON e.effect_key=r.effect_key
                WHERE r.receipt_id=?
                  AND r.consumer_contract=?
                  AND r.message_identity_scope=?
                  AND r.message_id=?
                  AND r.effect_key=?
                """,
                (
                    receipt.receipt_id,
                    receipt.consumer_contract,
                    receipt.message_identity_scope,
                    receipt.message_id,
                    receipt.effect_key,
                ),
            ).fetchone()
        if row is None:
            raise PermissionError("durable responsibility receipt is not backed by committed scoped state")
        receipt_digest, inbox_digest, payload, apply_count, effect_consumer, effect_scope, effect_message_id = row
        if receipt_digest != receipt.payload_digest or inbox_digest != receipt.payload_digest:
            raise PermissionError("durable responsibility digest mismatch")
        if (effect_consumer, effect_scope, effect_message_id) != (
            receipt.consumer_contract,
            receipt.message_identity_scope,
            receipt.message_id,
        ):
            raise PermissionError("protected business effect scoped identity mismatch")
        if self._digest(payload) != receipt.payload_digest or apply_count != 1:
            raise PermissionError("protected business effect is not durably consistent")

    def observe_effect(self, effect_key: str) -> dict[str, object]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT consumer_contract,message_identity_scope,message_id,payload,apply_count FROM business_effect WHERE effect_key=?",
                (effect_key,),
            ).fetchone()
        if row is None:
            raise LookupError("protected business effect missing")
        return {
            "consumer_contract": row[0],
            "message_identity_scope": row[1],
            "message_id": row[2],
            "payload": row[3],
            "apply_count": row[4],
            "payload_digest": self._digest(row[3]),
        }

    @classmethod
    def binding_descriptor(cls) -> dict[str, str]:
        return {"profile": cls.profile, "implementation": cls.__name__, "contract": cls.contract_id}
