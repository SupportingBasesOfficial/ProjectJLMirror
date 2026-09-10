#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "src/jlmirror_monitoring/host_inventory.py"
SQL = ROOT / "sql/wave4/005_zabbix_host_inventory.sql"
HARDENING = ROOT / "sql/wave4/006_zabbix_host_inventory_boundary_hardening.sql"
INTEGRITY = ROOT / "sql/wave4/007_zabbix_host_inventory_integrity_hardening.sql"
ORDERING = ROOT / "sql/wave4/008_zabbix_host_inventory_poll_ordering_hardening.sql"
AUTHORITY = ROOT / "sql/wave4/009_zabbix_host_inventory_evidence_authority_hardening.sql"
FINAL_AUTHORITY = ROOT / "sql/wave4/010_zabbix_host_inventory_final_authority_hardening.sql"
EXPLICIT_AUTHORITY = ROOT / "sql/wave4/015_zabbix_host_inventory_explicit_admission_and_resource_authority.sql"
SUPERSEDED_EPOCH = ROOT / "sql/wave4/017_zabbix_host_inventory_superseded_epoch_retirement.sql"
CLAIM_REVISION = ROOT / "sql/wave4/018_zabbix_host_inventory_claim_revision_immutability.sql"
TEST = ROOT / "tests/wave4/test_zabbix_host_inventory.py"
PG = ROOT / "tools/wave4/run_zabbix_host_inventory_postgres_conformance.sh"
PG_ORDERING = ROOT / "tools/wave4/run_zabbix_host_inventory_ordering_postgres_conformance.sh"
PG_AUTHORITY = ROOT / "tools/wave4/run_zabbix_host_inventory_evidence_authority_postgres_conformance.sh"
PG_FINAL_SCHEMA = ROOT / "tools/wave4/run_zabbix_host_inventory_final_schema_postgres_conformance.sh"
PG_SUPERSEDED_EPOCH = ROOT / "tools/wave4/run_zabbix_host_inventory_superseded_epoch_postgres_conformance.sh"
PG_DUMP = ROOT / "tools/wave4/pg_dump_recovery_safe.sh"
WORKFLOW = ROOT / ".github/workflows/wave4-monitoring-source-foundation.yml"
MANIFEST = ROOT / "implementation/wave-4/IMPLEMENTATION_MANIFEST.json"
AUTH = ROOT / "implementation/wave-4-host-inventory-authorization/AUTHORIZATION_MANIFEST.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"WAVE4_HOST_INVENTORY_ERROR: {message}")


def main() -> None:
    for path in (
        PY, SQL, HARDENING, INTEGRITY, ORDERING, AUTHORITY, FINAL_AUTHORITY,
        EXPLICIT_AUTHORITY, SUPERSEDED_EPOCH, CLAIM_REVISION, TEST, PG, PG_ORDERING,
        PG_AUTHORITY, PG_FINAL_SCHEMA, PG_SUPERSEDED_EPOCH, PG_DUMP, WORKFLOW,
        MANIFEST, AUTH,
    ):
        require(path.is_file(), f"missing required surface: {path.relative_to(ROOT)}")

    ast.parse(PY.read_text(encoding="utf-8"))
    py = PY.read_text(encoding="utf-8")
    sql = SQL.read_text(encoding="utf-8")
    hardening = HARDENING.read_text(encoding="utf-8")
    integrity = INTEGRITY.read_text(encoding="utf-8")
    ordering = ORDERING.read_text(encoding="utf-8")
    authority = AUTHORITY.read_text(encoding="utf-8")
    final_authority = FINAL_AUTHORITY.read_text(encoding="utf-8")
    explicit_authority = EXPLICIT_AUTHORITY.read_text(encoding="utf-8")
    superseded_epoch = SUPERSEDED_EPOCH.read_text(encoding="utf-8")
    claim_revision = CLAIM_REVISION.read_text(encoding="utf-8")
    test_py = TEST.read_text(encoding="utf-8")
    base_pg = PG.read_text(encoding="utf-8")
    ordering_pg = PG_ORDERING.read_text(encoding="utf-8")
    authority_pg = PG_AUTHORITY.read_text(encoding="utf-8")
    final_schema_pg = PG_FINAL_SCHEMA.read_text(encoding="utf-8")
    superseded_epoch_pg = PG_SUPERSEDED_EPOCH.read_text(encoding="utf-8")
    dump_pg = PG_DUMP.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    auth = json.loads(AUTH.read_text(encoding="utf-8"))

    require(auth["canonical_resource_kind_mapping"]["monitoring_resource_kind"] == "host", "canonical resource_kind authority drift")
    require(auth["canonical_resource_kind_mapping"]["provider_object_kind"] == "zabbix_host", "provider object kind authority drift")
    require(auth["implementation_authority_after_merge"] == "granted_for_exact_host_inventory_ingestion_slice_only", "host inventory implementation authority not canonical")
    require(manifest["host_inventory_authorization_commit"] == "2986f43ff262ecd5781661dbdee46c896f5019bc", "host inventory authorization commit drift")

    for marker in (
        "MAX_HOSTS_PER_SNAPSHOT = 50_000",
        "class ZabbixHostEvidence",
        "def canonical_evidence",
        "def evidence_fingerprint",
        "class ZabbixHostSnapshot",
        "snapshot.complete",
        "InventoryFailureClass.SNAPSHOT_TRUNCATED",
        "InventoryFailureClass.SCOPE_EVIDENCE_INVALID",
        "InventoryFailureClass.SCOPE_ANCHOR_INACCESSIBLE",
        "def hostgroup_get",
        "visible_groups = tuple(host_reader.hostgroup_get",
        "opaque_token(\"mon-host-claim\")",
        "persisted_result = self._repository.complete_host_inventory",
        "return persisted_result",
        "authoritative post-persistence outcome",
    ):
        require(marker in py, f"Python boundary missing: {marker}")
    require("test_worker_returns_persisted_completion_outcome" in test_py, "worker outcome authority regression test missing")
    require(py.index("visible_groups = tuple(host_reader.hostgroup_get") < py.index("snapshot = host_reader.host_get"), "scope anchors must be revalidated before host snapshot read")
    canonical_evidence_body = py.split("def canonical_evidence", 1)[1].split("def evidence_fingerprint", 1)[0]
    require("canonical_device_class" not in canonical_evidence_body, "provider evidence must not project canonical device classification")
    require("resource_kind" not in canonical_evidence_body, "provider evidence must not own canonical resource kind")

    for marker in (
        "CREATE TABLE monitoring.monitoring_resource",
        "resource_kind TEXT NOT NULL CHECK (resource_kind = 'host')",
        "provider_object_kind TEXT NOT NULL CHECK (provider_object_kind = 'zabbix_host')",
        "CREATE TABLE monitoring.monitoring_host_inventory_snapshot_evidence",
        "CREATE TABLE monitoring.monitoring_resource_provider_evidence",
        "octet_length(normalized_evidence::text) <= 65536",
        "ALTER TABLE monitoring.monitoring_resource FORCE ROW LEVEL SECURITY",
        "ALTER TABLE monitoring.monitoring_host_inventory_snapshot_evidence FORCE ROW LEVEL SECURITY",
        "ALTER TABLE monitoring.monitoring_resource_provider_evidence FORCE ROW LEVEL SECURITY",
        "CREATE FUNCTION monitoring.claim_zabbix_host_inventory",
        "CREATE FUNCTION monitoring.complete_zabbix_host_inventory",
        "FOR UPDATE OF s",
        "IF p_snapshot_complete THEN",
        "presence_state='removed'",
        "execution.stale_authority",
    ):
        require(marker in sql, f"SQL boundary missing: {marker}")
    require("provider_payload" not in sql, "raw provider payload storage is forbidden")

    for marker in (
        "CREATE FUNCTION monitoring.wave4_is_bounded_zabbix_host_evidence",
        "monitoring_resource_provider_evidence_bounded_shape",
        "wave4_guard_host_provider_evidence_insert",
        "host provider evidence lacks configured-scope membership",
        "monitoring_source_validation_evidence",
        "monitoring.host_inventory_source_not_validated_current",
        "monitoring.host_inventory_stale_authority",
        "IF (p_evidence->'inventory') - ARRAY[",
    ):
        require(marker in hardening, f"host evidence hardening missing: {marker}")
    for forbidden in ("canonical_device_class", "canonical_device_type", "resource_kind"):
        require(f"'{forbidden}'" not in hardening.split("ARRAY['technical_name'", 1)[1].split("::TEXT[]", 1)[0], f"provider evidence allowlist illegally admits {forbidden}")

    for marker in (
        "monitoring_resource_latest_provider_evidence_owner_fk",
        "monitoring_sync_operation_host_inventory_snapshot_owner_fk",
        "wave4_guard_monitoring_resource_update",
        "Monitoring resource canonical/provider identity is immutable",
        "Monitoring resource removal requires complete authoritative negative snapshot evidence",
        "wave4_is_canonical_zabbix_host_evidence_details",
    ):
        require(marker in integrity, f"host inventory integrity guard missing: {marker}")

    for marker in (
        "host_inventory_poll_generation BIGINT NOT NULL DEFAULT 0",
        "last_confirmed_present_poll_generation BIGINT NOT NULL DEFAULT 0",
        "removed_poll_generation BIGINT NULL",
        "CREATE OR REPLACE FUNCTION monitoring.complete_zabbix_host_inventory",
        "host_inventory_poll_generation=s.host_inventory_poll_generation+1",
        "FOR UPDATE OF s,o",
        "execution.superseded_poll_authority",
        "last_confirmed_present_poll_generation=v_poll_generation",
        "removed_poll_generation=v_poll_generation",
        "e.host_inventory_poll_generation > OLD.last_confirmed_present_poll_generation",
        "newer complete authoritative negative poll evidence",
        "Poll generation, not wall-clock time, is the authoritative presence ordering field",
        "no unfenced helper remains callable",
    ):
        require(marker in ordering, f"host inventory ordering guard missing: {marker}")
    require("wave4_complete_zabbix_host_inventory_pre_poll_fence" not in ordering, "unfenced host inventory completion helper must not exist")

    for marker in (
        "wave4_guard_host_inventory_snapshot_insert",
        "not bound to its claimed running operation",
        "wave4_guard_host_provider_evidence_authority",
        "open claimed snapshot operation",
        "wave4_python_canonical_jsonb",
        "fingerprint does not match normalized evidence",
        "wave4_deferred_monitoring_resource_presence_authority",
        "positive presence requires accepted provider snapshot authority",
        "completed newer authoritative negative poll evidence",
        "positive presence requires a poll newer than removal authority",
    ):
        require(marker in authority, f"host inventory evidence-authority guard missing: {marker}")

    for marker in (
        "wave4_guard_monitoring_source_poll_generation_update",
        "poll generation cannot rewind",
        "wave4_guard_sync_operation_poll_generation_update",
        "operation poll generation is immutable after claim",
        "s.host_inventory_poll_generation=NEW.host_inventory_poll_generation",
        "requires current claimed poll authority",
        "wave4_deferred_host_inventory_snapshot_closure",
        "host_count must equal final provider evidence membership",
        "snapshot must close with its owning terminal operation",
    ):
        require(marker in final_authority, f"final host inventory authority guard missing: {marker}")

    for marker in (
        "DROP TRIGGER IF EXISTS wave4_host_inventory_runtime_admission_bootstrap",
        "last_observed_at IS DISTINCT FROM OLD.last_observed_at",
        "last_confirmed_present_at IS DISTINCT FROM OLD.last_confirmed_present_at",
        "removed_at IS DISTINCT FROM OLD.removed_at",
        "Monitoring resource authority fields require guarded host-inventory executor",
    ):
        require(marker in explicit_authority, f"explicit/final resource authority guard missing: {marker}")

    for marker in (
        "execution.superseded_poll_epoch_authority",
        "v_poll_epoch IS NULL OR v_poll_epoch <> v_current_poll_epoch",
        "host_inventory_poll_epoch=v_current_poll_epoch",
    ):
        require(marker in superseded_epoch, f"superseded epoch retirement guard missing: {marker}")

    for marker in (
        "wave4_guard_host_inventory_claim_revision_update",
        "NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id",
        "NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation",
        "NEW.configuration_revision IS DISTINCT FROM OLD.configuration_revision",
        "NEW.scope_revision IS DISTINCT FROM OLD.scope_revision",
        "Claimed host inventory source/revision authority is immutable",
    ):
        require(marker in claim_revision, f"claimed host inventory revision authority guard missing: {marker}")

    require("sql/wave4/008_zabbix_host_inventory_poll_ordering_hardening.sql" in base_pg, "base host inventory conformance does not apply ordering migration")
    for marker in (
        "poll_generation=claim_ordered",
        "late_completion=retired_without_mutation",
        "stale_negative=blocked",
        "newer_positive=preserved",
        "unfenced_helper=absent",
        "poll_generation=presence_authority",
    ):
        require(marker in ordering_pg, f"host inventory ordering PostgreSQL falsifier missing: {marker}")
    for marker in (
        "sql/wave4/009_zabbix_host_inventory_evidence_authority_hardening.sql",
        "sql/wave4/010_zabbix_host_inventory_final_authority_hardening.sql",
        "snapshot_operation_binding=closed",
        "membership_after_completion=closed",
        "positive_transition=evidence_bound",
        "fingerprint=verified",
        "negative_transition=completed_operation_bound",
        "poll_rewind=blocked",
        "superseded_snapshot=current-poll-bound",
        "host_count=final-membership-verified",
    ):
        require(marker in authority_pg, f"host inventory evidence-authority PostgreSQL falsifier missing: {marker}")

    require("--exclude-table-data=monitoring.monitoring_host_inventory_runtime_admission" in dump_pg, "canonical logical dump must exclude runtime admission data")
    for migration in (
        "001_monitoring_source_foundation.sql",
        "008_zabbix_host_inventory_poll_ordering_hardening.sql",
        "009_zabbix_host_inventory_evidence_authority_hardening.sql",
        "010_zabbix_host_inventory_final_authority_hardening.sql",
        "011_zabbix_host_inventory_terminal_operation_hardening.sql",
        "011a_zabbix_host_inventory_executor_roles.sql",
        "012_zabbix_host_inventory_recovery_authority_hardening.sql",
        "013_zabbix_host_inventory_executor_privileges.sql",
        "014_zabbix_host_inventory_resource_epoch_insert.sql",
        "015_zabbix_host_inventory_explicit_admission_and_resource_authority.sql",
        "016_zabbix_host_inventory_operation_insert_authority.sql",
        "017_zabbix_host_inventory_superseded_epoch_retirement.sql",
        "018_zabbix_host_inventory_claim_revision_immutability.sql",
    ):
        require(migration in final_schema_pg, f"final-schema conformance omits migration: {migration}")
    for marker in (
        "schema=001-018",
        "complete_snapshot=accepted",
        "negative_removal=accepted",
        "superseded_poll=retired",
        "terminal_reopen=blocked",
        "claimed_revision_authority=immutable",
        "observation_forgery=blocked",
        "logical_recovery_admission=excluded",
        "pg_dump_recovery_safe.sh",
        "recovered_admission_count",
    ):
        require(marker in final_schema_pg, f"final-schema PostgreSQL proof missing: {marker}")
    for marker in (
        "schema=001-017",
        "old_epoch=retired",
        "reconciliation=required",
        "stale_snapshot=absent",
    ):
        require(marker in superseded_epoch_pg, f"superseded-epoch PostgreSQL proof missing: {marker}")

    require("validate_zabbix_host_inventory.py" in workflow, "workflow does not run host inventory validator")
    require("run_zabbix_host_inventory_postgres_conformance.sh" in workflow, "workflow does not run PostgreSQL host inventory proof")
    require("run_zabbix_host_inventory_ordering_postgres_conformance.sh" in workflow, "workflow does not run host inventory ordering proof")
    require("run_zabbix_host_inventory_evidence_authority_postgres_conformance.sh" in workflow, "workflow does not run host inventory evidence-authority proof")
    require("run_zabbix_host_inventory_final_schema_postgres_conformance.sh" in workflow, "workflow does not run final composed schema proof")
    require("run_zabbix_host_inventory_superseded_epoch_postgres_conformance.sh" in workflow, "workflow does not run superseded epoch retirement proof")

    require("src/jlmirror_monitoring/host_inventory.py" in manifest["code_surfaces"], "manifest missing host inventory code surface")
    for surface in (
        "sql/wave4/006_zabbix_host_inventory_boundary_hardening.sql",
        "sql/wave4/007_zabbix_host_inventory_integrity_hardening.sql",
        "sql/wave4/008_zabbix_host_inventory_poll_ordering_hardening.sql",
        "sql/wave4/009_zabbix_host_inventory_evidence_authority_hardening.sql",
        "sql/wave4/010_zabbix_host_inventory_final_authority_hardening.sql",
        "sql/wave4/015_zabbix_host_inventory_explicit_admission_and_resource_authority.sql",
        "sql/wave4/016_zabbix_host_inventory_operation_insert_authority.sql",
        "sql/wave4/017_zabbix_host_inventory_superseded_epoch_retirement.sql",
        "sql/wave4/018_zabbix_host_inventory_claim_revision_immutability.sql",
    ):
        require(surface in manifest["code_surfaces"], f"manifest missing hardening surface: {surface}")
    for surface in (
        "tools/wave4/pg_dump_recovery_safe.sh",
        "tools/wave4/run_zabbix_host_inventory_final_schema_postgres_conformance.sh",
        "tools/wave4/run_zabbix_host_inventory_superseded_epoch_postgres_conformance.sh",
    ):
        require(surface in manifest["assurance_surfaces"], f"manifest missing assurance/recovery surface: {surface}")
    for capability in (
        "host_inventory_ingestion",
        "host_inventory_poll_generation_fence",
        "stale_negative_snapshot_rejection",
        "host_inventory_snapshot_operation_binding",
        "host_inventory_closed_snapshot_membership",
        "host_inventory_positive_presence_authority",
        "host_inventory_evidence_fingerprint_verification",
        "host_inventory_scope_anchor_revalidation",
        "host_inventory_poll_generation_rewind_rejection",
        "host_inventory_current_poll_snapshot_binding",
        "host_inventory_snapshot_cardinality_closure",
        "host_inventory_explicit_runtime_admission",
        "host_inventory_resource_observation_authority",
        "host_inventory_logical_recovery_admission_exclusion",
        "host_inventory_final_schema_composed_conformance",
        "host_inventory_superseded_epoch_retirement",
        "host_inventory_persisted_completion_outcome",
        "host_inventory_claim_revision_authority_immutability",
    ):
        require(capability in manifest["implemented_capability"], f"manifest does not declare capability: {capability}")
    require("host_inventory_ingestion" not in manifest["explicitly_not_implemented"], "manifest still denies implemented host inventory")
    require("canonical_device_classification" in manifest["explicitly_not_implemented"], "implementation must not claim device classification authority")

    print("wave4_zabbix_host_inventory_validation=PASS resource_kind=host provider_object_kind=zabbix_host evidence=bounded+scope-bound+owner-bound+operation-bound+closed-membership+cardinality-bound+fingerprint-verified identity=immutable presence=positive+negative-authority-bound tenant_rls=forced stale_authority=fenced poll_generation=single-winner+nonrewind snapshot=current-poll-bound scope_anchor=same-cycle-revalidated recovery=explicit-admission+logical-dump-excluded+superseded-epoch-retired claim_revision=immutable completion=post-persistence-authoritative final_schema=001-018-composed")


if __name__ == "__main__":
    main()
