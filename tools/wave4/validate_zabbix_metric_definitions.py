#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAIN = ROOT / "src/jlmirror_monitoring/metric_definitions.py"
M020 = ROOT / "sql/wave4/020_zabbix_metric_definitions.sql"
M021 = ROOT / "sql/wave4/021_zabbix_metric_definitions_authority_hardening.sql"
M022 = ROOT / "sql/wave4/022_zabbix_metric_definitions_atomic_preflight.sql"
M023 = ROOT / "sql/wave4/023_zabbix_metric_definitions_qualified_claim.sql"
TEST = ROOT / "tests/wave4/test_zabbix_metric_definitions.py"
CONFORMANCE = ROOT / "tools/wave4/run_zabbix_metric_definitions_postgres_conformance.sh"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"WAVE4_ZABBIX_METRIC_DEFINITIONS_ERROR: {message}")


def main() -> None:
    for path in (DOMAIN, M020, M021, M022, M023, TEST, CONFORMANCE):
        require(path.is_file(), f"missing required surface: {path.relative_to(ROOT)}")

    domain = DOMAIN.read_text(encoding="utf-8")
    m020 = M020.read_text(encoding="utf-8")
    m021 = M021.read_text(encoding="utf-8")
    m022 = M022.read_text(encoding="utf-8")
    m023 = M023.read_text(encoding="utf-8")
    conformance = CONFORMANCE.read_text(encoding="utf-8")

    for marker in (
        'class MetricValueKind',
        'class ZabbixNativeValueType',
        'class ZabbixItemOperationalState',
        'MAX_ITEMS_PER_SNAPSHOT = 200_000',
        'MetricValueKind.INTEGER',
        'MetricValueKind.STRING',
        'MetricDefinitionWorker',
        'complete_metric_definitions must return authoritative persisted MetricDefinitionResult',
    ):
        require(marker in domain, f"domain invariant missing: {marker}")
    require('BOOLEAN = "boolean"' not in domain, "generic Zabbix integer must not become boolean")
    require('lastvalue' not in domain and 'history_get' not in domain, "current/history ingestion leaked into bounded slice")

    for marker in (
        'item_definition_poll_epoch',
        'item_definition_poll_generation',
        'monitoring_metric_definition_runtime_admission',
        'CREATE TABLE monitoring.metric_definition (',
        'CREATE TABLE monitoring.metric_definition_provider_binding (',
        "provider_object_kind TEXT NOT NULL CHECK (provider_object_kind='zabbix_item')",
        'provider_external_ref TEXT NOT NULL',
        'jlmirror_wave4_metric_definition_executor',
        'jlmirror_wave4_metric_definition_invoker',
        'metric_definition_sync',
        'REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_definitions',
    ):
        require(marker in m020, f"migration 020 invariant missing: {marker}")

    for marker in (
        'DEFERRABLE INITIALLY DEFERRED',
        'reestablish_metric_definition_runtime_admission',
        'monitoring.metric_definition_recovery_epoch_must_advance',
        'wave4_retire_missing_metric_definitions',
        "r.presence_state='present'",
        "r.presence_evidence_state='current'",
        "r.scope_evidence_state='current'",
    ):
        require(marker in m021, f"migration 021 hardening missing: {marker}")

    for marker in (
        'PRECHECK:',
        'provider.value_kind_drift',
        'No definition/binding/provider-evidence mutation from this snapshot is accepted.',
        'PERFORM monitoring.wave4_retire_missing_metric_definitions',
        "r.presence_evidence_state='current'",
    ):
        require(marker in m022, f"migration 022 atomicity invariant missing: {marker}")

    for marker in (
        'RETURNS TABLE (',
        'UPDATE monitoring.monitoring_source AS s',
        'UPDATE monitoring.monitoring_sync_operation AS o',
        'attempt_count=o.attempt_count+1',
        'sql/wave4/023_zabbix_metric_definitions_qualified_claim.sql',
    ):
        source = m023 if marker != 'sql/wave4/023_zabbix_metric_definitions_qualified_claim.sql' else conformance
        require(marker in source, f"migration 023/composed-schema invariant missing: {marker}")

    forbidden_sql = ('metric_current_state', 'metric_observation', 'history.get', 'problem_state', 'health_projection')
    combined = '\n'.join((m020, m021, m022, m023))
    for marker in forbidden_sql:
        require(marker not in combined, f"unauthorized surface leaked into SQL: {marker}")

    require('schema=001-023' in conformance, "PostgreSQL conformance is not pinned to final schema 001-023")
    print('wave4_zabbix_metric_definitions=PASS schema=020-023 composed=001-023 scope=item-get-metadata-only authority=item-stream-independent atomic_preflight=required claim=qualified')


if __name__ == '__main__':
    main()
