#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "sql/wave4/019_zabbix_host_inventory_work_identity_and_invocation_authority.sql"
FINAL_SCHEMA = ROOT / "tools/wave4/run_zabbix_host_inventory_final_schema_postgres_conformance.sh"
SUPERSEDED_EPOCH = ROOT / "tools/wave4/run_zabbix_host_inventory_superseded_epoch_postgres_conformance.sh"
MANIFEST = ROOT / "implementation/wave-4/IMPLEMENTATION_MANIFEST.json"
WORKFLOW = ROOT / ".github/workflows/wave4-monitoring-source-foundation.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"WAVE4_HOST_INVOCATION_AUTHORITY_ERROR: {message}")


def main() -> None:
    for path in (MIGRATION, FINAL_SCHEMA, SUPERSEDED_EPOCH, MANIFEST, WORKFLOW):
        require(path.is_file(), f"missing required surface: {path.relative_to(ROOT)}")

    migration = MIGRATION.read_text(encoding="utf-8")
    final_schema = FINAL_SCHEMA.read_text(encoding="utf-8")
    superseded = SUPERSEDED_EPOCH.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for marker in (
        "jlmirror_wave4_host_inventory_invoker",
        "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS",
        "Host inventory work identity and source/revision authority are immutable from enqueue",
        "Host inventory operation lifecycle provenance requires guarded executor authority",
        "Host inventory work creation requires guarded executor authority",
        "NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id",
        "NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation",
        "NEW.configuration_revision IS DISTINCT FROM OLD.configuration_revision",
        "NEW.scope_revision IS DISTINCT FROM OLD.scope_revision",
        "NEW.created_at IS DISTINCT FROM OLD.created_at",
        "NEW.started_at IS DISTINCT FROM OLD.started_at",
        "NEW.completed_at IS DISTINCT FROM OLD.completed_at",
        "NEW.last_error_class IS DISTINCT FROM OLD.last_error_class",
        "NEW.attempt_count IS DISTINCT FROM OLD.attempt_count",
        "NEW.started_at IS NOT NULL",
        "NEW.completed_at IS NOT NULL",
        "NEW.attempt_count IS DISTINCT FROM 0",
        "REVOKE EXECUTE ON FUNCTION monitoring.enqueue_zabbix_host_inventory_sync",
        "REVOKE EXECUTE ON FUNCTION monitoring.claim_zabbix_host_inventory",
        "REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_host_inventory",
        "FROM PUBLIC",
        "TO jlmirror_wave4_host_inventory_invoker",
    ):
        require(marker in migration, f"migration 019 authority marker missing: {marker}")

    for marker in (
        "019_zabbix_host_inventory_work_identity_and_invocation_authority.sql",
        "schema=001-019",
        "direct_work_creation=blocked",
        "pending_retarget=blocked",
        "invocation_authority=provider-worker-only",
        "invoker_table_dml=none",
        "poll_authority=single-owner-index",
        "permission denied for function enqueue_zabbix_host_inventory_sync",
        "session_replication_role='replica'",
        "source-final-b",
    ):
        require(marker in final_schema, f"final-schema 019 falsifier missing: {marker}")

    for marker in (
        "019_zabbix_host_inventory_work_identity_and_invocation_authority.sql",
        "schema=001-019",
        "invocation_authority=provider-worker-only",
        "SET LOCAL ROLE jlmirror_wave4_host_inventory_invoker",
    ):
        require(marker in superseded, f"superseded-epoch final-schema marker missing: {marker}")

    require("worker.provider-integration@1" in manifest["runtime_profiles"], "provider-integration specialization not declared")
    require("sql/wave4/019_zabbix_host_inventory_work_identity_and_invocation_authority.sql" in manifest["code_surfaces"], "manifest missing migration 019")
    require("tools/wave4/validate_zabbix_host_inventory_invocation_authority.py" in manifest["assurance_surfaces"], "manifest missing invocation validator")
    for capability in (
        "host_inventory_work_identity_immutable_from_enqueue",
        "host_inventory_provider_worker_invocation_authority",
        "host_inventory_direct_work_creation_rejection",
    ):
        require(capability in manifest["implemented_capability"], f"manifest missing capability: {capability}")

    require("validate_zabbix_host_inventory_invocation_authority.py" in workflow, "workflow does not run invocation-authority validator")

    print("wave4_zabbix_host_inventory_invocation_authority=PASS worker=provider-integration public_execute=revoked direct_work_creation=blocked work_identity=enqueue-frozen lifecycle_provenance=executor-owned final_schema=001-019")


if __name__ == "__main__":
    main()
