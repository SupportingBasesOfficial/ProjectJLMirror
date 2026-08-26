from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class Wave2ContractAlignmentTests(unittest.TestCase):
    def test_manifest_preserves_product_and_next_wave_boundary(self) -> None:
        manifest = json.loads(
            (ROOT / "implementation/wave-2/IMPLEMENTATION_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["product_feature_activation"], "none")
        self.assertFalse(manifest["next_wave_authorized"])
        self.assertEqual(
            manifest["implementation_slices"],
            ["impl.cell-data-runtime@1", "impl.async-core@1"],
        )
        self.assertIn("broker_or_job_transport", manifest["residual_c2_choices_not_selected"])
        self.assertIn(
            "message_equivalence_evidence_mechanism",
            manifest["residual_c2_choices_not_selected"],
        )

    def test_sql_keeps_immutable_message_separate_from_dispatch_state(self) -> None:
        sql = (ROOT / "sql/wave2/001_async_correctness.sql").read_text(encoding="utf-8").lower()
        self.assertIn("system.async_outbox_message", sql)
        self.assertIn("system.async_outbox_dispatch", sql)
        self.assertIn("wave2_outbox_immutable_update_guard", sql)
        self.assertIn("security invoker", sql)
        self.assertNotIn("security definer", sql)

    def test_sql_materializes_atomic_inbox_identity(self) -> None:
        sql = (ROOT / "sql/wave2/001_async_correctness.sql").read_text(encoding="utf-8").lower()
        self.assertIn(
            "primary key (consumer_contract, message_identity_scope, message_id)",
            sql,
        )
        self.assertIn("comparison_evidence bytea not null", sql)
        self.assertIn("reconciliation_required", sql)
        self.assertIn("async_cross_authority_operation", sql)

    def test_sql_does_not_select_runtime_acl_mapping(self) -> None:
        lines = (ROOT / "sql/wave2/001_async_correctness.sql").read_text(encoding="utf-8").splitlines()
        executable_grants = [
            line.strip()
            for line in lines
            if line.strip() and not line.lstrip().startswith("--") and line.strip().upper().startswith("GRANT ")
        ]
        self.assertEqual(executable_grants, [])

    def test_phase10_owners_still_supply_core_invariants(self) -> None:
        publication = (
            ROOT / "docs/10-event-contracts/publication-outbox-and-producer-authority.md"
        ).read_text(encoding="utf-8")
        inbox = (
            ROOT / "docs/10-event-contracts/consumer-inbox-idempotency-and-effects.md"
        ).read_text(encoding="utf-8")
        security = (
            ROOT / "docs/10-event-contracts/security-tenant-context-and-data-classification.md"
        ).read_text(encoding="utf-8")
        self.assertIn("same transaction as the mutation", publication)
        self.assertIn("retrying the same logical `message_id` is preferred", publication)
        self.assertIn("(consumer_contract, message_identity_scope, message_id)", inbox)
        self.assertIn("A read-then-insert race is prohibited", inbox)
        self.assertIn("resolves current placement", security)
        self.assertIn(
            "Human/session/membership authorization from message creation time does not persist automatically",
            security,
        )

    def test_wave2_readme_records_product_clarification_boundary(self) -> None:
        readme = (ROOT / "implementation/wave-2/README.md").read_text(encoding="utf-8")
        self.assertIn("does **not** create Product/domain endpoints", readme)
        self.assertIn("Product/operations clarification", readme)
        self.assertIn("notification/escalation behavior", readme)


if __name__ == "__main__":
    unittest.main()
