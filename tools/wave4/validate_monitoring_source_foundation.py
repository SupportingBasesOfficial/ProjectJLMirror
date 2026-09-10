#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "implementation/wave-4-monitoring-authorization/AUTHORIZATION_MANIFEST.json"
IMPL = ROOT / "implementation/wave-4/IMPLEMENTATION_MANIFEST.json"
SOURCE = ROOT / "src/jlmirror_monitoring/source.py"
SQL = ROOT / "sql/wave4/001_monitoring_source_foundation.sql"

EXPECTED_AUTH_COMMIT = "8e2265a4ee2810ea701166228e8f44ad3bc0d894"
FORBIDDEN_NETWORK_IMPORTS = {
    "requests", "httpx", "aiohttp", "urllib.request", "socket", "subprocess"
}


def req(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_authority() -> None:
    auth = load(AUTH)
    req(auth.get("authorization_id") == "wave4.monitoring-zabbix.vertical@1", "authorization id drift")
    req(auth.get("canonical_effect_after_merge") == "authorized_to_implement_exact_scoped_monitoring_vertical_only", "authorization is not canonical implementation authority")
    req(auth.get("production_authority") == "none", "production authority must remain none")
    req(auth.get("frontend_authority") == "not_granted_by_this_gate", "frontend authority drift")
    slices = {(row["slice_id"], row["scope"]) for row in auth.get("authorized_slices", [])}
    req(("impl.customer-telemetry@1", "accepted_d2_track_b_profile_only") in slices, "customer telemetry slice missing")
    req(("impl.provider-integration@1", "accepted_monitoring_zabbix_subprofile_only") in slices, "Zabbix provider slice missing")


def validate_manifest() -> None:
    data = load(IMPL)
    req(data.get("wave") == 4, "wave drift")
    req(data.get("canonical_authorization_commit") == EXPECTED_AUTH_COMMIT, "authorization commit drift")
    req(data.get("authorization_id") == "wave4.monitoring-zabbix.vertical@1", "implementation authorization id drift")
    req(data.get("product_feature_activation") == "monitoring_source_foundation_only", "feature activation widened")
    forbidden = set(data.get("explicitly_not_implemented", []))
    for marker in (
        "zabbix_network_client", "http_route_adapter", "browser_frontend",
        "provider_write_back", "browser_realtime", "production_deployment",
        "c3_production_numerics",
    ):
        req(marker in forbidden, f"missing explicit non-implementation boundary: {marker}")
    req(data.get("frontend_rule") == "backend_entities_tables_endpoints_and_use_cases_do_not_imply_frontend_routes", "frontend route boundary drift")


def validate_source_has_no_network_side_effects() -> None:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    bad = sorted(name for name in imports if any(name == f or name.startswith(f + ".") for f in FORBIDDEN_NETWORK_IMPORTS))
    req(not bad, "local source creation imported network/process side effects: " + ",".join(bad))
    text = SOURCE.read_text(encoding="utf-8")
    req("OperationalEvidenceState.RECONCILIATION_REQUIRED" in text, "creation must not fabricate current provider evidence")
    req('responsibility_kind="validation_and_initial_sync"' in text, "initial durable sync responsibility missing")


def validate_sql() -> None:
    text = SQL.read_text(encoding="utf-8")
    for table in (
        "monitoring.monitoring_source",
        "monitoring.monitoring_source_generation",
        "monitoring.monitoring_sync_operation",
        "monitoring.monitoring_source_create_idempotency",
    ):
        req(f"CREATE TABLE {table}" in text, f"missing table: {table}")
    req("PRIMARY KEY (tenant_id, monitoring_source_id)" in text, "source tenant isolation key missing")
    req("PRIMARY KEY (tenant_id, monitoring_source_id, source_instance_generation)" in text, "generation tenant/source identity missing")
    req("Monitoring source generation records are immutable" in text, "generation immutability guard missing")
    req("PRIMARY KEY (tenant_id, idempotency_key)" in text, "create idempotency scope missing")
    lowered = text.lower()
    for marker in ("http_get", "curl ", "wget ", "dblink("):
        req(marker not in lowered, f"network/external side effect leaked into local migration: {marker}")


def validate() -> None:
    for path in (AUTH, IMPL, SOURCE, SQL):
        req(path.is_file(), f"missing governed artifact: {path.relative_to(ROOT)}")
    validate_authority()
    validate_manifest()
    validate_source_has_no_network_side_effects()
    validate_sql()


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"wave4_monitoring_source_foundation=FAIL reason={exc}", file=sys.stderr)
        return 1
    print("wave4_monitoring_source_foundation=PASS source_identity=logical generation=opaque+historical-safe initial_sync=durable network_in_create=none production=none frontend=deferred")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
