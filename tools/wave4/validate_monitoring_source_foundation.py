#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "implementation/wave-4-monitoring-authorization/AUTHORIZATION_MANIFEST.json"
IMPL = ROOT / "implementation/wave-4/IMPLEMENTATION_MANIFEST.json"
STATE = ROOT / "implementation/wave-4/STATE.md"
SOURCE = ROOT / "src/jlmirror_monitoring/source.py"
SQL1 = ROOT / "sql/wave4/001_monitoring_source_foundation.sql"
SQL2 = ROOT / "sql/wave4/002_monitoring_source_audit_evidence.sql"
POSTGRES_CONFORMANCE = ROOT / "tools/wave4/run_monitoring_source_postgres_conformance.sh"
WORKFLOW = ROOT / ".github/workflows/wave4-monitoring-source-foundation.yml"
PRODUCT_MODEL = ROOT / "governance/product-model/organization-provider-commercial/DECISION_MANIFEST.json"
ADR022 = ROOT / "adr/ADR-022-organization-provider-commercial-operating-model.md"
ADR021 = ROOT / "adr/ADR-021-monitoring-source-instance-replacement.md"

EXPECTED_AUTH_COMMIT = "8e2265a4ee2810ea701166228e8f44ad3bc0d894"
EXPECTED_SUCCESSOR_GOVERNANCE_COMMIT = "3c66b5e70e6d12f373315b95e3feefdfbf47e941"
PINNED_POSTGRES_IMAGE = "postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280"
FORBIDDEN_NETWORK_IMPORTS = {"requests", "httpx", "aiohttp", "urllib.request", "socket", "subprocess"}


def req(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_authority() -> None:
    auth = load(AUTH)
    req(auth.get("authorization_id") == "wave4.monitoring-zabbix.vertical@1", "authorization id drift")
    req(
        auth.get("canonical_effect_after_merge") == "authorized_to_implement_exact_scoped_monitoring_vertical_only",
        "authorization is not canonical implementation authority",
    )
    req(auth.get("production_authority") == "none", "production authority must remain none")
    req(auth.get("frontend_authority") == "not_granted_by_this_gate", "frontend authority drift")
    slices = {(row["slice_id"], row["scope"]) for row in auth.get("authorized_slices", [])}
    req(("impl.customer-telemetry@1", "accepted_d2_track_b_profile_only") in slices, "customer telemetry slice missing")
    req(("impl.provider-integration@1", "accepted_monitoring_zabbix_subprofile_only") in slices, "Zabbix provider slice missing")


def validate_successor_product_model() -> None:
    model = load(PRODUCT_MODEL)
    adr022 = ADR022.read_text(encoding="utf-8")
    adr021 = ADR021.read_text(encoding="utf-8")
    req(model.get("decision_id") == "organization-provider-commercial-model@1", "successor product model id drift")
    req(model.get("status") == "separately_accepted", "successor product model is not accepted")
    req(model.get("runtime_implementation_authority") == "not_granted_by_this_gate", "product-model gate unexpectedly grants runtime")
    req(model.get("production_authority") == "none", "product-model gate unexpectedly grants production")
    decisions = model.get("decisions", {})
    req(decisions.get("provider_instance_model") == "one_physical_provider_instance_may_serve_many_tenants", "shared provider model drift")
    req(decisions.get("provider_visibility_vs_platform_authority") == "independent_layers", "provider visibility conflated with platform authority")
    req(decisions.get("ownership_ambiguity") == "fail_closed_reconciliation_required", "ownership ambiguity no longer fails closed")
    req("# ADR-022 — Organization, Provider and Commercial Operating Model" in adr022, "ADR-022 missing")
    req("# ADR-021 — Monitoring Source-Instance Replacement" in adr021, "Monitoring ADR-021 missing")


def validate_manifest() -> None:
    data = load(IMPL)
    req(data.get("wave") == 4, "wave drift")
    req(data.get("implementation_id") == "wave4.monitoring-source-foundation@2", "implementation identity drift")
    req(data.get("canonical_authorization_commit") == EXPECTED_AUTH_COMMIT, "authorization commit drift")
    req(data.get("canonical_successor_governance_commit") == EXPECTED_SUCCESSOR_GOVERNANCE_COMMIT, "successor governance commit drift")
    req(data.get("successor_product_model_decision") == "organization-provider-commercial-model@1", "successor model binding drift")
    req(data.get("successor_architecture_decision") == "ADR-022", "successor ADR binding drift")
    req(data.get("product_feature_activation") == "monitoring_source_foundation_only", "feature activation widened")
    implemented = set(data.get("implemented_capability", []))
    for marker in (
        "explicit_provider_instance_lineage_reference",
        "explicit_provider_scope_tenant_binding_identity",
        "shared_provider_instance_across_isolated_tenants_without_identity_collapse",
        "atomic_create_or_observe_monitoring_source_transaction",
        "atomic_append_only_privileged_source_creation_audit_evidence",
        "executable_postgresql_source_creation_conformance",
    ):
        req(marker in implemented, f"implemented capability missing: {marker}")
    forbidden = set(data.get("explicitly_not_implemented", []))
    for marker in (
        "provider_instance_registry_runtime",
        "organization_runtime",
        "commercial_runtime",
        "provider_operator_resolution_runtime",
        "delegated_msp_authority_runtime",
        "zabbix_network_client",
        "resource_ingestion",
        "http_route_adapter",
        "browser_frontend",
        "provider_write_back",
        "production_deployment",
        "c3_production_numerics",
    ):
        req(marker in forbidden, f"missing explicit non-implementation boundary: {marker}")


def validate_source() -> None:
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
    for marker in (
        "provider_instance_ref",
        "provider_scope_tenant_binding_id",
        "MonitoringSourceGeneration",
        "OperationalEvidenceState.RECONCILIATION_REQUIRED",
        'responsibility_kind="validation_and_initial_sync"',
        "scope_tenant_binding_id_factory",
    ):
        req(marker in text, f"source lineage marker missing: {marker}")
    req('if "\\\\" in raw:' in text, "canonical URL backslash rejection missing")
    req('raw.encode("ascii")' in text, "canonical URL ASCII guard missing")


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
    req("CREATE TABLE monitoring.monitoring_source_audit_evidence" in audit, "audit table missing")
    req("provider_scope_tenant_binding_id TEXT NOT NULL" in foundation, "explicit tenant binding identity missing")
    req("UNIQUE (tenant_id, provider_scope_tenant_binding_id)" in foundation, "tenant binding uniqueness missing")
    req("provider_instance_ref TEXT NOT NULL" in foundation, "provider instance lineage missing")
    req("may be shared by independent tenant-scoped Monitoring sources" in foundation, "shared-provider semantics missing")
    req("PRIMARY KEY (tenant_id, monitoring_source_id)" in foundation, "tenant/source primary key missing")
    req("PRIMARY KEY (tenant_id, monitoring_source_id, source_instance_generation)" in foundation, "generation scope missing")
    req("Monitoring source generation records are immutable" in foundation, "generation immutability guard missing")
    req("tenant/logical/binding identity/provider profile is immutable" in foundation, "binding immutability guard missing")
    req("p_provider_instance_ref TEXT" in audit, "final create function lacks provider lineage")
    req("p_provider_scope_tenant_binding_id TEXT" in audit, "final create function lacks tenant binding identity")
    req("ON CONFLICT (tenant_id, idempotency_key) DO NOTHING" in audit, "atomic idempotency claim missing")
    req("RAISE EXCEPTION 'idempotency.key_reused'" in audit, "fingerprint mismatch rejection missing")
    req("Monitoring source audit evidence is immutable" in audit, "audit immutability missing")
    audit_table = audit[
        audit.index("CREATE TABLE monitoring.monitoring_source_audit_evidence ("):
        audit.index("COMMENT ON TABLE monitoring.monitoring_source_audit_evidence")
    ]
    for forbidden in ("credential_binding_ref", "provider_base_url", "configured_provider_scope", "provider_instance_ref"):
        req(forbidden not in audit_table, f"provider/source configuration leaked into audit evidence schema: {forbidden}")
    lowered = combined.lower()
    for marker in ("http_get", "curl ", "wget ", "dblink("):
        req(marker not in lowered, f"network/external side effect leaked into local migration: {marker}")


def validate_state_and_proof() -> None:
    state = STATE.read_text(encoding="utf-8")
    script = POSTGRES_CONFORMANCE.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        "provider_instance_ref",
        "provider_scope_tenant_binding_id",
        "multiple tenants may reference the same physical/logical provider instance",
        "provider-instance registry runtime",
    ):
        req(marker in state, f"STATE boundary missing: {marker}")
    for marker in (
        PINNED_POSTGRES_IMAGE,
        "shared_provider_instance",
        "provider_scope_tenant_binding_id",
        "idempotency.key_reused",
        "Monitoring source generation records are immutable",
        "Monitoring source audit evidence is immutable",
        "wave4_monitoring_postgres_conformance=PASS",
    ):
        req(marker in script, f"PostgreSQL conformance proof missing marker: {marker}")
    req("bash tools/wave4/run_monitoring_source_postgres_conformance.sh" in workflow, "CI does not execute PostgreSQL conformance")
    req(PINNED_POSTGRES_IMAGE in workflow, "CI PostgreSQL image is not digest-pinned")
    req("allow-unsafe-pr-checkout: false" in workflow, "unsafe PR checkout guard missing")


def validate() -> None:
    for path in (AUTH, IMPL, STATE, SOURCE, SQL1, SQL2, POSTGRES_CONFORMANCE, WORKFLOW, PRODUCT_MODEL, ADR022, ADR021):
        req(path.is_file(), f"missing governed artifact: {path.relative_to(ROOT)}")
    validate_authority()
    validate_successor_product_model()
    validate_manifest()
    validate_source()
    validate_sql()
    validate_state_and_proof()


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"wave4_monitoring_source_foundation=FAIL reason={exc}", file=sys.stderr)
        return 1
    print(
        "wave4_monitoring_source_foundation=PASS version=2 "
        "provider_instance=explicit+shareable tenant_binding=explicit+isolated "
        "generation=opaque+historical-safe create=idempotent+atomic "
        "audit=privileged+append-only network_in_create=none production=none frontend=deferred"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
