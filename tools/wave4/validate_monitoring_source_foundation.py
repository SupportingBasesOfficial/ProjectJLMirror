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
SQL1 = ROOT / "sql/wave4/001_monitoring_source_foundation.sql"
SQL2 = ROOT / "sql/wave4/002_monitoring_source_audit_evidence.sql"
POSTGRES_CONFORMANCE = ROOT / "tools/wave4/run_monitoring_source_postgres_conformance.sh"
WORKFLOW = ROOT / ".github/workflows/wave4-monitoring-source-foundation.yml"

EXPECTED_AUTH_COMMIT = "8e2265a4ee2810ea701166228e8f44ad3bc0d894"
PINNED_POSTGRES_IMAGE = "postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280"
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
    implemented = set(data.get("implemented_capability", []))
    for marker in (
        "atomic_create_or_observe_monitoring_source_transaction",
        "atomic_append_only_privileged_source_creation_audit_evidence",
        "executable_postgresql_source_creation_conformance",
    ):
        req(marker in implemented, f"implemented capability missing: {marker}")
    forbidden = set(data.get("explicitly_not_implemented", []))
    for marker in (
        "zabbix_network_client", "http_route_adapter", "browser_frontend",
        "provider_write_back", "browser_realtime", "production_deployment",
        "c3_production_numerics", "central_compliance_audit_projection_or_external_delivery",
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
    req("audit_evidence_id_factory" in text, "source creation plan does not bind audit evidence identity")
    req('if "\\\\" in raw:' in text, "canonical URL backslash rejection missing")
    req('raw.encode("ascii")' in text, "canonical URL ASCII representation guard missing")
    req('segment in (".", "..")' in text, "canonical URL dot-segment rejection missing")


def validate_sql() -> None:
    foundation = SQL1.read_text(encoding="utf-8")
    audit = SQL2.read_text(encoding="utf-8")
    combined = foundation + "\n" + audit
    for table in (
        "monitoring.monitoring_source",
        "monitoring.monitoring_source_generation",
        "monitoring.monitoring_sync_operation",
        "monitoring.monitoring_source_create_idempotency",
    ):
        req(f"CREATE TABLE {table}" in foundation, f"missing table: {table}")
    req("CREATE TABLE monitoring.monitoring_source_audit_evidence" in audit, "privileged audit evidence table missing")
    req("PRIMARY KEY (tenant_id, monitoring_source_id)" in foundation, "source tenant isolation key missing")
    req("PRIMARY KEY (tenant_id, monitoring_source_id, source_instance_generation)" in foundation, "generation tenant/source identity missing")
    req("Monitoring source generation records are immutable" in foundation, "generation immutability guard missing")
    req("PRIMARY KEY (tenant_id, idempotency_key)" in foundation, "create idempotency scope missing")
    req("DROP FUNCTION monitoring.create_zabbix_source(" in audit, "non-audited create function is not removed")
    req("p_audit_evidence_id TEXT" in audit, "final create function lacks audit evidence identity")
    req("p_actor_principal_id TEXT" in audit, "final create function lacks actor principal")
    req("p_actor_credential_generation TEXT" in audit, "final create function lacks actor generation")
    req("p_authorization_decision_ref TEXT" in audit, "final create function lacks authorization decision reference")
    req("p_request_correlation_id TEXT" in audit, "final create function lacks request correlation")
    req("ON CONFLICT (tenant_id, idempotency_key) DO NOTHING" in audit, "atomic idempotency claim missing")
    req("RAISE EXCEPTION 'idempotency.key_reused'" in audit, "fingerprint mismatch rejection missing")
    req("RETURN QUERY SELECT existing_source_id, existing_operation_id, existing_state, TRUE" in audit, "same-key replay path missing")
    req("'reconciliation_required', p_monitoring_sync_operation_id" in audit, "local create must start with non-current evidence")
    req("'validation_and_initial_sync', 'pending'" in audit, "durable initial sync operation missing")
    req("INSERT INTO monitoring.monitoring_source_audit_evidence(" in audit, "audit evidence is not atomically inserted")
    req("'monitoring.source.manage', 'privileged'" in audit, "privileged audit classification drift")
    req("Monitoring source audit evidence is immutable" in audit, "audit evidence immutability guard missing")
    req("safe_summary = '{\"mutation\":\"create\",\"provider_profile\":\"zabbix\"}'::jsonb" in audit, "audit safe summary drift")
    audit_table = audit[
        audit.index("CREATE TABLE monitoring.monitoring_source_audit_evidence ("):
        audit.index("COMMENT ON TABLE monitoring.monitoring_source_audit_evidence")
    ]
    for forbidden in ("credential_binding_ref", "provider_base_url", "configured_provider_scope"):
        req(forbidden not in audit_table, f"sensitive/source configuration leaked into audit evidence schema: {forbidden}")
    source_start = foundation.index("CREATE TABLE monitoring.monitoring_source (")
    generation_start = foundation.index("CREATE TABLE monitoring.monitoring_source_generation (")
    sync_start = foundation.index("CREATE TABLE monitoring.monitoring_sync_operation (")
    source_block = foundation[source_start:generation_start]
    generation_block = foundation[generation_start:sync_start]
    req("credential_binding_ref TEXT NOT NULL" in source_block, "mutable credential binding must live on logical source")
    req("configured_provider_scope JSONB NOT NULL" in source_block, "mutable scope must live on logical source")
    req("credential_binding_ref" not in generation_block, "credential binding leaked into immutable generation")
    req("configured_provider_scope" not in generation_block, "scope leaked into immutable generation")
    req("provider_base_url TEXT NOT NULL" in generation_block, "provider endpoint must be generation-bound")
    lowered = combined.lower()
    for marker in ("http_get", "curl ", "wget ", "dblink("):
        req(marker not in lowered, f"network/external side effect leaked into local migration: {marker}")


def validate_postgres_proof() -> None:
    script = POSTGRES_CONFORMANCE.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        PINNED_POSTGRES_IMAGE,
        "002_monitoring_source_audit_evidence.sql",
        "wave4_monitoring_postgres_conformance=PASS",
        "idempotency.key_reused",
        "Monitoring source generation records are immutable",
        "Monitoring source audit evidence is immutable",
        "Monitoring source revisions cannot regress",
        "duplicate configured scope unexpectedly succeeded",
        "replay_audit_count",
    ):
        req(marker in script, f"PostgreSQL conformance proof missing marker: {marker}")
    req("bash tools/wave4/run_monitoring_source_postgres_conformance.sh" in workflow, "dedicated CI does not execute PostgreSQL conformance proof")
    req(PINNED_POSTGRES_IMAGE in workflow, "dedicated CI PostgreSQL image is not digest-pinned")
    req("allow-unsafe-pr-checkout: false" in workflow, "dedicated CI unsafe PR checkout guard missing")


def validate() -> None:
    for path in (AUTH, IMPL, SOURCE, SQL1, SQL2, POSTGRES_CONFORMANCE, WORKFLOW):
        req(path.is_file(), f"missing governed artifact: {path.relative_to(ROOT)}")
    validate_authority()
    validate_manifest()
    validate_source_has_no_network_side_effects()
    validate_sql()
    validate_postgres_proof()


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"wave4_monitoring_source_foundation=FAIL reason={exc}", file=sys.stderr)
        return 1
    print("wave4_monitoring_source_foundation=PASS source_identity=logical generation=opaque+historical-safe create=idempotent+atomic audit=privileged+append-only postgres=executed initial_sync=durable network_in_create=none production=none frontend=deferred")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
