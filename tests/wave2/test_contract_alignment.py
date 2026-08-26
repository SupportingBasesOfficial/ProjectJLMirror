from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class Wave2ContractAlignmentTests(unittest.TestCase):
    def test_manifest_preserves_product_next_wave_and_execution_boundaries(self) -> None:
        manifest = json.loads(
            (ROOT / "implementation/wave-2/IMPLEMENTATION_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["product_feature_activation"], "none")
        self.assertFalse(manifest["next_wave_authorized"])
        self.assertEqual(
            manifest["implementation_slices"],
            ["impl.cell-data-runtime@1", "impl.async-core@1"],
        )
        self.assertEqual(
            manifest["fixed_execution_admission"],
            "revision_bound_current_authority_before_each_protected_effect_attempt",
        )
        self.assertEqual(
            manifest["fixed_lease_loss_semantics"],
            "lease_expiry_never_proves_effect_absence",
        )
        self.assertIn("broker_or_job_transport", manifest["residual_c2_choices_not_selected"])
        self.assertIn(
            "message_equivalence_evidence_mechanism",
            manifest["residual_c2_choices_not_selected"],
        )
        for forbidden in (
            "dispatch_time_for_authoritative_event_occurrence",
            "job_command_without_durable_operation_identity",
            "lease_expiry_for_effect_absence",
            "stale_or_missing_current_execution_admission_for_effect_authority",
            "preexisting_same_name_correctness_table_for_schema_conformance",
            "same_canonical_inbox_key_with_conflicting_trusted_tenant_binding_for_benign_duplicate",
        ):
            self.assertIn(forbidden, manifest["forbidden_correctness_substitutions"])

    def test_sql_keeps_immutable_message_separate_from_dispatch_state(self) -> None:
        sql = (ROOT / "sql/wave2/001_async_correctness.sql").read_text(encoding="utf-8").lower()
        self.assertIn("system.async_outbox_message", sql)
        self.assertIn("system.async_outbox_dispatch", sql)
        self.assertIn("wave2_outbox_immutable_update_guard", sql)
        self.assertIn("security invoker", sql)
        self.assertNotIn("security definer", sql)

    def test_sql_critical_correctness_tables_fail_closed_on_preexisting_names(self) -> None:
        sql = (ROOT / "sql/wave2/001_async_correctness.sql").read_text(encoding="utf-8").lower()
        critical = (
            "system.async_outbox_message",
            "system.async_outbox_dispatch",
            "system.async_consumer_inbox",
            "system.async_cross_authority_operation",
        )
        for table in critical:
            self.assertIn(f"create table {table}", sql)
            self.assertNotIn(f"create table if not exists {table}", sql)

    def test_sql_outbox_insert_atomically_initializes_dispatch_bookkeeping(self) -> None:
        sql = (ROOT / "sql/wave2/001_async_correctness.sql").read_text(encoding="utf-8").lower()
        self.assertIn("create function system.wave2_initialize_outbox_dispatch()", sql)
        self.assertIn("after insert on system.async_outbox_message", sql)
        self.assertIn("insert into system.async_outbox_dispatch(outbox_record_id)", sql)

    def test_sql_materializes_atomic_inbox_identity(self) -> None:
        sql = (ROOT / "sql/wave2/001_async_correctness.sql").read_text(encoding="utf-8").lower()
        self.assertIn(
            "primary key (consumer_contract, message_identity_scope, message_id)",
            sql,
        )
        self.assertIn("comparison_evidence bytea not null", sql)
        self.assertIn("reconciliation_required", sql)
        self.assertIn("async_cross_authority_operation", sql)

    def test_sql_materializes_lease_and_current_execution_evidence(self) -> None:
        sql = (ROOT / "sql/wave2/001_async_correctness.sql").read_text(encoding="utf-8").lower()
        for anchor in (
            "claim_expires_at timestamptz null",
            "attempt_expires_at timestamptz null",
            "execution_admission_revision text null",
            "execution_authorization_revision text null",
            "execution_principal_credential_generation text null",
            "execution_runtime_profile_id text null",
            "execution_runtime_generation text null",
            "execution_environment_class text null",
            "execution_placement_version text null",
            "execution_fence_scope_id text null",
            "execution_fence_epoch bigint null",
        ):
            self.assertIn(anchor, sql)
        self.assertIn("state = 'processing'", sql)
        self.assertIn("state = 'attempting'", sql)
        self.assertIn("claim_expires_at is not null", sql)
        self.assertIn("attempt_expires_at is not null", sql)

    def test_sql_materializes_message_class_time_semantics(self) -> None:
        sql = (ROOT / "sql/wave2/001_async_correctness.sql").read_text(encoding="utf-8").lower()
        self.assertIn("occurred_at timestamptz null", sql)
        self.assertIn("created_at timestamptz null", sql)
        self.assertIn("message_class in ('domain_event', 'integration_event', 'realtime_projection')", sql)
        self.assertIn("message_class in ('job_command', 'process_signal', 'outbound_webhook_delivery')", sql)
        self.assertIn("message_class <> 'job_command' or operation_id is not null", sql)

    def test_sql_does_not_select_runtime_acl_mapping(self) -> None:
        lines = (ROOT / "sql/wave2/001_async_correctness.sql").read_text(encoding="utf-8").splitlines()
        executable_grants = [
            line.strip()
            for line in lines
            if line.strip() and not line.lstrip().startswith("--") and line.strip().upper().startswith("GRANT ")
        ]
        self.assertEqual(executable_grants, [])

    def test_phase10_owners_still_supply_core_invariants(self) -> None:
        envelope = (ROOT / "docs/10-event-contracts/message-envelope-and-classes.md").read_text(encoding="utf-8")
        publication = (
            ROOT / "docs/10-event-contracts/publication-outbox-and-producer-authority.md"
        ).read_text(encoding="utf-8")
        delivery = (
            ROOT / "docs/10-event-contracts/delivery-ack-retry-and-quarantine.md"
        ).read_text(encoding="utf-8")
        inbox = (
            ROOT / "docs/10-event-contracts/consumer-inbox-idempotency-and-effects.md"
        ).read_text(encoding="utf-8")
        security = (
            ROOT / "docs/10-event-contracts/security-tenant-context-and-data-classification.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Events use `occurred_at`", envelope)
        self.assertIn("Jobs use `created_at`", envelope)
        self.assertIn("durable operation identity", envelope)
        self.assertIn("same transaction as the mutation", publication)
        self.assertIn("retrying the same logical `message_id` is preferred", publication)
        self.assertIn("claim/lease/locking semantics", publication)
        self.assertIn("lease timeout while original executor may still be active", delivery)
        self.assertIn("worker lease expiry is not effect absence proof", delivery)
        self.assertIn("(consumer_contract, message_identity_scope, message_id)", inbox)
        self.assertIn("A read-then-insert race is prohibited", inbox)
        self.assertIn("resolves current placement", security)
        self.assertIn(
            "Human/session/membership authorization from message creation time does not persist automatically",
            security,
        )

    def test_wave1_scope_compatibility_does_not_legalize_wave2_as_wave1(self) -> None:
        scope = (ROOT / "tools/authority/wave1_scope.py").read_text(encoding="utf-8")
        test = (ROOT / "tests/wave1/test_wave1_scope_guard.py").read_text(encoding="utf-8")
        self.assertIn(
            'ACCEPTED_WAVE1_SHA = "ff932cec10e3b7dcc13b050bb09d4a7efd634598"',
            scope,
        )
        self.assertIn("implementation/wave-2/README.md", test)
        self.assertIn("escapes authorized path set", test)

    def test_wave2_readme_records_product_clarification_and_fail_closed_boundaries(self) -> None:
        readme = (ROOT / "implementation/wave-2/README.md").read_text(encoding="utf-8")
        self.assertIn("does **not** create Product/domain endpoints", readme)
        self.assertIn("Product/operations clarification", readme)
        self.assertIn("notification/escalation behavior", readme)
        self.assertIn("LEASE EXPIRY != EFFECT ABSENCE", readme)
        self.assertIn("PREEXISTING TABLE NAME != CORRECTNESS SCHEMA CONFORMANCE", readme)
        self.assertIn("CurrentAsyncExecutionAuthorityPort", readme)


if __name__ == "__main__":
    unittest.main()
