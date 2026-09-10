#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "src/jlmirror_monitoring/host_inventory.py"
SQL = ROOT / "sql/wave4/005_zabbix_host_inventory.sql"
HARDENING = ROOT / "sql/wave4/006_zabbix_host_inventory_boundary_hardening.sql"
TEST = ROOT / "tests/wave4/test_zabbix_host_inventory.py"
PG = ROOT / "tools/wave4/run_zabbix_host_inventory_postgres_conformance.sh"
WORKFLOW = ROOT / ".github/workflows/wave4-monitoring-source-foundation.yml"
MANIFEST = ROOT / "implementation/wave-4/IMPLEMENTATION_MANIFEST.json"
AUTH = ROOT / "implementation/wave-4-host-inventory-authorization/AUTHORIZATION_MANIFEST.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"WAVE4_HOST_INVENTORY_ERROR: {message}")


def main() -> None:
    for path in (PY, SQL, HARDENING, TEST, PG, WORKFLOW, MANIFEST, AUTH):
        require(path.is_file(), f"missing required surface: {path.relative_to(ROOT)}")

    ast.parse(PY.read_text(encoding="utf-8"))
    py = PY.read_text(encoding="utf-8")
    sql = SQL.read_text(encoding="utf-8")
    hardening = HARDENING.read_text(encoding="utf-8")
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
        "opaque_token(\"mon-host-claim\")",
    ):
        require(marker in py, f"Python boundary missing: {marker}")
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
    ):
        require(marker in hardening, f"host evidence hardening missing: {marker}")
    for forbidden in ("canonical_device_class", "canonical_device_type", "resource_kind"):
        require(f"'{forbidden}'" not in hardening.split("ARRAY['technical_name'", 1)[1].split("::TEXT[]", 1)[0], f"provider evidence allowlist illegally admits {forbidden}")

    require("validate_zabbix_host_inventory.py" in workflow, "workflow does not run host inventory validator")
    require("run_zabbix_host_inventory_postgres_conformance.sh" in workflow, "workflow does not run PostgreSQL host inventory proof")
    require("src/jlmirror_monitoring/host_inventory.py" in manifest["code_surfaces"], "manifest missing host inventory code surface")
    require("sql/wave4/006_zabbix_host_inventory_boundary_hardening.sql" in manifest["code_surfaces"], "manifest missing host evidence hardening surface")
    require("host_inventory_ingestion" in manifest["implemented_capability"], "manifest does not declare host inventory capability")
    require("host_inventory_ingestion" not in manifest["explicitly_not_implemented"], "manifest still denies implemented host inventory")
    require("canonical_device_classification" in manifest["explicitly_not_implemented"], "implementation must not claim device classification authority")

    print("wave4_zabbix_host_inventory_validation=PASS resource_kind=host provider_object_kind=zabbix_host evidence=bounded+scope-bound removal=authoritative-only tenant_rls=forced stale_authority=fenced recovery=validation-authority")


if __name__ == "__main__":
    main()
