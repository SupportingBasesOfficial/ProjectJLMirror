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
EXPECTED_FOUNDATION_SQUASH = "d642a7f456e042dd02de2c04533c39c748f88aa9"
EXPECTED_HOST_INVENTORY_AUTH = "2986f43ff262ecd5781661dbdee46c896f5019bc"
EXPECTED_HOST_INVENTORY_SQUASH = "18581e18b90f1c387d2b175ec4f4dac0fbf677d2"
EXPECTED_METRIC_DEFINITION_AUTH = "4debb413aad4b1b449fd6e0dcd05f101021d81e3"
PINNED_POSTGRES_IMAGE = "postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280"
FORBIDDEN_NETWORK_IMPORTS = {"requests", "httpx", "aiohttp", "urllib.request", "socket", "subprocess"}


def req(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate() -> None:
    for path in (AUTH, IMPL, STATE, SOURCE, SQL1, SQL2, POSTGRES_CONFORMANCE, WORKFLOW, PRODUCT_MODEL, ADR022, ADR021):
        req(path.is_file(), f"missing governed artifact: {path.relative_to(ROOT)}")

    auth = load(AUTH)
    req(auth.get("authorization_id") == "wave4.monitoring-zabbix.vertical@1", "authorization id drift")
    req(auth.get("canonical_effect_after_merge") == "authorized_to_implement_exact_scoped_monitoring_vertical_only", "implementation authority drift")
    req(auth.get("production_authority") == "none", "production authority widened")
    req(auth.get("frontend_authority") == "not_granted_by_this_gate", "frontend authority widened")

    model = load(PRODUCT_MODEL)
    req(model.get("decision_id") == "organization-provider-commercial-model@1", "product model drift")
    req(model.get("status") == "separately_accepted", "product model not accepted")
    req(model.get("decisions", {}).get("provider_instance_model") == "one_physical_provider_instance_may_serve_many_tenants", "shared provider model drift")
    req("# ADR-022 — Organization, Provider and Commercial Operating Model" in ADR022.read_text(encoding="utf-8"), "ADR-022 missing")
    req("# ADR-021 — Monitoring Source-Instance Replacement" in ADR021.read_text(encoding="utf-8"), "Monitoring ADR-021 missing")

    impl = load(IMPL)
    req(impl.get("wave") == 4, "wave drift")
    req(impl.get("canonical_authorization_commit") == EXPECTED_AUTH_COMMIT, "authorization commit drift")
    impl_id = impl.get("implementation_id")
    req(
        impl_id in {
            "wave4.monitoring-source-foundation@2",
            "wave4.zabbix-initial-validation-worker@1",
            "wave4.zabbix-host-inventory@1",
            "wave4.zabbix-metric-definitions@1",
        },
        "implementation identity drift",
    )

    if impl_id == "wave4.monitoring-source-foundation@2":
        req(impl.get("product_feature_activation") == "monitoring_source_foundation_only", "foundation activation widened")
    elif impl_id == "wave4.zabbix-initial-validation-worker@1":
        req(impl.get("canonical_predecessor_commit") == EXPECTED_FOUNDATION_SQUASH, "initial-validation successor lost source-foundation provenance")
        req(impl.get("product_feature_activation") == "monitoring_source_validation_hostgroup_only", "initial-validation activation widened")
    elif impl_id == "wave4.zabbix-host-inventory@1":
        req(impl.get("canonical_predecessor_commit") == EXPECTED_FOUNDATION_SQUASH, "host inventory successor lost source-foundation provenance")
        req(impl.get("host_inventory_authorization_commit") == EXPECTED_HOST_INVENTORY_AUTH, "host inventory successor lost product authority")
        req(impl.get("host_inventory_authorization_id") == "wave4.monitoring-host-inventory@1", "host inventory authorization id drift")
        req(impl.get("product_feature_activation") == "monitoring_source_validation_and_bounded_host_inventory", "host inventory activation drift")
        req("host_inventory_ingestion" in impl.get("implemented_capability", []), "host inventory successor missing bounded capability")
        for forbidden in ("metric_ingestion", "problem_ingestion", "history_ingestion", "canonical_device_classification", "browser_frontend", "provider_write_back", "production_deployment"):
            req(forbidden in impl.get("explicitly_not_implemented", []), f"host inventory successor widened into deferred capability: {forbidden}")
    else:
        req(impl.get("canonical_predecessor_commit") == EXPECTED_HOST_INVENTORY_SQUASH, "metric definition successor lost host-inventory provenance")
        req(impl.get("host_inventory_authorization_commit") == EXPECTED_HOST_INVENTORY_AUTH, "metric definition successor lost host inventory authority")
        req(impl.get("host_inventory_authorization_id") == "wave4.monitoring-host-inventory@1", "metric definition successor host inventory authorization id drift")
        req(impl.get("metric_definition_authorization_commit") == EXPECTED_METRIC_DEFINITION_AUTH, "metric definition successor lost product authority")
        req(impl.get("metric_definition_authorization_id") == "wave4.monitoring-metric-definitions@1", "metric definition authorization id drift")
        req(impl.get("product_feature_activation") == "monitoring_source_validation_host_inventory_and_bounded_metric_definitions", "metric definition activation drift")
        capabilities = set(impl.get("implemented_capability", []))
        for capability in (
            "host_inventory_ingestion",
            "zabbix_item_get_bounded_metric_definition_domain",
            "zabbix_item_binding_separate_from_metric_definition",
            "metric_definition_independent_poll_epoch_generation_admission",
            "metric_definition_atomic_snapshot_preflight",
        ):
            req(capability in capabilities, f"metric definition successor missing bounded capability: {capability}")
        deferred = set(impl.get("explicitly_not_implemented", []))
        for forbidden in (
            "metric_current_state_ingestion",
            "metric_history_ingestion",
            "problem_ingestion",
            "health_projection",
            "browser_frontend",
            "provider_write_back",
            "production_deployment",
        ):
            req(forbidden in deferred, f"metric definition successor widened into deferred capability: {forbidden}")

    source_text = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(SOURCE))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    bad = sorted(name for name in imports if any(name == f or name.startswith(f + ".") for f in FORBIDDEN_NETWORK_IMPORTS))
    req(not bad, "local source creation imported network/process side effects: " + ",".join(bad))
    for marker in ("provider_instance_ref", "provider_scope_tenant_binding_id", "MonitoringSourceGeneration", "OperationalEvidenceState.RECONCILIATION_REQUIRED", 'responsibility_kind="validation_and_initial_sync"'):
        req(marker in source_text, f"source foundation marker missing: {marker}")

    foundation = SQL1.read_text(encoding="utf-8")
    audit = SQL2.read_text(encoding="utf-8")
    for marker in (
        "CREATE TABLE monitoring.monitoring_source (",
        "CREATE TABLE monitoring.monitoring_source_generation (",
        "CREATE TABLE monitoring.monitoring_sync_operation (",
        "CREATE TABLE monitoring.monitoring_source_create_idempotency (",
        "provider_scope_tenant_binding_id TEXT NOT NULL",
        "provider_instance_ref TEXT NOT NULL",
        "UNIQUE (tenant_id, provider_scope_tenant_binding_id)",
        "Monitoring source generation records are immutable",
        "tenant/logical/binding identity/provider profile is immutable",
    ):
        req(marker in foundation, f"foundation SQL invariant missing: {marker}")
    for marker in (
        "CREATE TABLE monitoring.monitoring_source_audit_evidence",
        "ON CONFLICT (tenant_id, idempotency_key) DO NOTHING",
        "RAISE EXCEPTION 'idempotency.key_reused'",
        "Monitoring source audit evidence is immutable",
    ):
        req(marker in audit, f"audit/create invariant missing: {marker}")

    audit_table = audit[audit.index("CREATE TABLE monitoring.monitoring_source_audit_evidence ("):audit.index("COMMENT ON TABLE monitoring.monitoring_source_audit_evidence")]
    for forbidden in ("credential_binding_ref", "provider_base_url", "configured_provider_scope", "provider_instance_ref"):
        req(forbidden not in audit_table, f"configuration leaked into audit evidence: {forbidden}")

    script = POSTGRES_CONFORMANCE.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for marker in (PINNED_POSTGRES_IMAGE, "shared_provider_instance", "provider_scope_tenant_binding_id", "idempotency.key_reused", "wave4_monitoring_postgres_conformance=PASS"):
        req(marker in script, f"foundation conformance marker missing: {marker}")
    req("bash tools/wave4/run_monitoring_source_postgres_conformance.sh" in workflow, "foundation PostgreSQL proof not wired")
    req(PINNED_POSTGRES_IMAGE in workflow, "CI PostgreSQL image not digest-pinned")
    req("allow-unsafe-pr-checkout: false" in workflow, "unsafe checkout guard missing")


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"wave4_monitoring_source_foundation=FAIL reason={exc}", file=sys.stderr)
        return 1
    print("wave4_monitoring_source_foundation=PASS predecessor=preserved successor=bounded shared_provider=isolated create=atomic audit=append-only production=none frontend=deferred")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
