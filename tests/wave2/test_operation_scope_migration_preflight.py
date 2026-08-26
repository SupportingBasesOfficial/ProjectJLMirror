from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class OperationScopeMigrationPreflightTests(unittest.TestCase):
    def test_existing_bindings_are_fenced_and_validated_before_trigger_publication(self) -> None:
        sql = (ROOT / "sql/wave2/006_operation_scope_binding_hardening.sql").read_text(
            encoding="utf-8"
        ).lower()

        inbox_lock = "lock table system.async_consumer_inbox in share row exclusive mode"
        operation_lock = "lock table system.async_cross_authority_operation in share mode"
        preflight = "preexisting inbox binding lacks exact tenant/owner authority scope"
        trigger = "create trigger wave2_inbox_operation_scope_guard"

        self.assertIn(inbox_lock, sql)
        self.assertIn(operation_lock, sql)
        self.assertIn("left join system.async_cross_authority_operation", sql)
        self.assertIn("operation.operation_id is null", sql)
        self.assertIn("operation.tenant_id is distinct from inbox.tenant_id", sql)
        self.assertIn(
            "operation.owner_contract is distinct from inbox.consumer_contract",
            sql,
        )
        self.assertIn(preflight, sql)

        self.assertLess(sql.index(inbox_lock), sql.index(preflight))
        self.assertLess(sql.index(operation_lock), sql.index(preflight))
        self.assertLess(sql.index(preflight), sql.index(trigger))


if __name__ == "__main__":
    unittest.main()
