#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "src/jlmirror_monitoring/host_inventory.py"
SQL = ROOT / "sql/wave4/005_zabbix_host_inventory.sql"
TEST = ROOT / "tests/wave4/test_zabbix_host_inventory.py"
PG = ROOT / "tools/wave4/run_zabbix_host_inventory_postgres_conformance.sh"
WORKFLOW = ROOT / ".github/workflows/wave4-monitoring-source-foundation.yml"
MANIFEST = ROOT / "implementation/wave-4/IMPLEMENTATION_MANIFEST.json"
AUTH = ROOT / "implementation/wave-4-host-inventory-authorization/AUTHORIZATION_MANIFEST.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"WAVE4_HOST_INVENTORY_ERROR: {message}")


def main() -> None:
    for path in (PY, SQL, TEST, PG, WORKFLOW, MANIFEST, AUTH):
        require(path.is_file(), f"missing required surface: {path.relative_to(ROOT)}")

    ast.parse(PY.read_text(encoding="utf-8"))
    py = PY.read_text(encoding="utf-8")
    sql = SQL.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    auth = json.loads(AUTH.read_text(encoding="utf-8"))

    require(auth["canonical_resource_kind_mapping"]["monitoring_resource_kind"] == "host", "canonical resource_kind authority drift")
    require(auth["canonical_resource_kind_mapping"]["provider_object_kind"] == "zabbix_host", "provider object kind authority drift")
    require(auth["implementation_authority_after_merge"] == "granted_for_exact_host_inventory_ingestion_slice_only", "host inventory implementation authority not canonical")

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
    require("canonical_device_class" not in py.split("def canonical_evidence", 1)[1].split("def evidence_fingerprint", 1)[0], "provider evidence must not project canonical device classification")

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

    require("validate_zabbix_host_inventory.py" in workflow, "workflow does not run host inventory validator")
    require("run_zabbix_host_inventory_postgres_conformance.sh" in workflow, "workflow does not run PostgreSQL host inventory proof")
    require("src/jlmirror_monitoring/host_inventory.py" in manifest["code_surfaces"], "manifest missing host inventory code surface")
    require("host_inventory_ingestion" in manifest["implemented_capability"], "manifest does not declare host inventory capability")
    require("host_inventory_ingestion" not in manifest["explicitly_not_implemented"], "manifest still denies implemented host inventory")

    print("wave4_zabbix_host_inventory_validation=PASS resource_kind=host provider_object_kind=zabbix_host evidence=bounded removal=authoritative-only tenant_rls=forced stale_authority=fenced")


if __name__ == "__main__":
    main()
