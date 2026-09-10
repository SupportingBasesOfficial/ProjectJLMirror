#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/jlmirror_monitoring/source.py"
SQL4 = ROOT / "sql/wave4/004_monitoring_boundary_hardening.sql"
TEST = ROOT / "tests/wave4/test_monitoring_boundary_hardening.py"
POSTGRES = ROOT / "tools/wave4/run_monitoring_boundary_hardening_postgres_conformance.sh"
WORKFLOW = ROOT / ".github/workflows/wave4-monitoring-source-foundation.yml"

TENANT_TABLES = (
    "monitoring_source",
    "monitoring_source_generation",
    "monitoring_sync_operation",
    "monitoring_source_create_idempotency",
    "monitoring_source_audit_evidence",
    "monitoring_source_validation_evidence",
)


def req(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_source() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    ast.parse(text, filename=str(SOURCE))
    scope_start = text.index("class ConfiguredProviderScope:")
    command_start = text.index("class CreateMonitoringSourceCommand:")
    scope_block = text[scope_start:command_start]
    req("def __post_init__(self)" in scope_block, "scope invariants are not constructor-enforced")
    req("len(self.host_group_refs) > 256" in scope_block, "scope cardinality constructor guard missing")
    req("host_group_refs must not contain duplicates" in scope_block, "scope duplicate constructor guard missing")
    req("return cls(tuple(refs))" in scope_block, "from_refs must delegate to constructor authority")


def validate_sql() -> None:
    text = SQL4.read_text(encoding="utf-8")
    req("CREATE FUNCTION monitoring.wave4_is_canonical_zabbix_base_url" in text, "canonical SQL URL validator missing")
    req("monitoring_source_generation_canonical_base_url" in text, "generation URL CHECK missing")
    req("NEW.configured_provider_scope IS DISTINCT FROM OLD.configured_provider_scope" in text, "scope mutation guard missing")
    req("NEW.scope_revision <= OLD.scope_revision" in text, "strict scope revision advance missing")
    req("current_setting('jlmirror.tenant_id', true)" in text, "transaction-local tenant context missing")
    for table in TENANT_TABLES:
        req(f"ALTER TABLE monitoring.{table} ENABLE ROW LEVEL SECURITY;" in text, f"RLS enable missing: {table}")
        req(f"ALTER TABLE monitoring.{table} FORCE ROW LEVEL SECURITY;" in text, f"RLS force missing: {table}")
    lowered = text.lower()
    for marker in ("http_get", "dblink(", "curl ", "wget "):
        req(marker not in lowered, f"network side effect leaked into canonical persistence validator: {marker}")


def validate_proof() -> None:
    script = POSTGRES.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        "003_zabbix_initial_validation_worker.sql",
        "004_monitoring_boundary_hardening.sql",
        "NOBYPASSRLS",
        "SET LOCAL jlmirror.tenant_id",
        "cross-tenant create unexpectedly succeeded",
        "scope change without revision advance unexpectedly succeeded",
        "noncanonical dot-segment URL unexpectedly persisted",
        "wave4_monitoring_boundary_hardening=PASS",
    ):
        req(marker in script, f"PostgreSQL hardening proof missing marker: {marker}")
    req("python3 tools/wave4/validate_monitoring_boundary_hardening.py" in workflow, "workflow does not validate hardening boundary")
    req("bash tools/wave4/run_monitoring_boundary_hardening_postgres_conformance.sh" in workflow, "workflow does not execute hardening PostgreSQL proof")


def validate() -> None:
    for path in (SOURCE, SQL4, TEST, POSTGRES, WORKFLOW):
        req(path.is_file(), f"missing hardening artifact: {path.relative_to(ROOT)}")
    validate_source()
    validate_sql()
    validate_proof()


def main() -> int:
    try:
        validate()
    except (AssertionError, SyntaxError, ValueError) as exc:
        print(f"wave4_monitoring_boundary_hardening=FAIL reason={exc}", file=sys.stderr)
        return 1
    print("wave4_monitoring_boundary_hardening=PASS scope_ctor=closed rls=fail_closed scope_revision=atomic sql_url=canonical postgres=falsified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
