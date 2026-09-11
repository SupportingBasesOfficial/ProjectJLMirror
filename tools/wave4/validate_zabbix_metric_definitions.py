#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAIN = ROOT / "src/jlmirror_monitoring/metric_definitions.py"
M020 = ROOT / "sql/wave4/020_zabbix_metric_definitions.sql"
M021 = ROOT / "sql/wave4/021_zabbix_metric_definitions_authority_hardening.sql"
M022 = ROOT / "sql/wave4/022_zabbix_metric_definitions_atomic_preflight.sql"
M023 = ROOT / "sql/wave4/023_zabbix_metric_definitions_qualified_claim.sql"
M024 = ROOT / "sql/wave4/024_zabbix_metric_definitions_evidence_and_drift_authority.sql"
M025 = ROOT / "sql/wave4/025_zabbix_metric_definitions_drift_visibility.sql"
M026 = ROOT / "sql/wave4/026_zabbix_metric_definitions_provenance_closure.sql"
M027 = ROOT / "sql/wave4/027_zabbix_metric_definitions_completion_authority.sql"
M028 = ROOT / "sql/wave4/028_zabbix_metric_definitions_completion_liveness.sql"
M029 = ROOT / "sql/wave4/029_zabbix_metric_definitions_claimed_input_liveness.sql"
TEST = ROOT / "tests/wave4/test_zabbix_metric_definitions.py"
CONFORMANCE = ROOT / "tools/wave4/run_zabbix_metric_definitions_postgres_conformance.sh"
LIVENESS = ROOT / "tools/wave4/run_zabbix_metric_definitions_liveness_postgres_conformance.sh"
CLAIMED_INPUT_LIVENESS = ROOT / "tools/wave4/run_zabbix_metric_definitions_claimed_input_liveness_postgres_conformance.sh"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"WAVE4_ZABBIX_METRIC_DEFINITIONS_ERROR: {message}")


def main() -> None:
    required = (DOMAIN, M020, M021, M022, M023, M024, M025, M026, M027, M028, M029, TEST, CONFORMANCE, LIVENESS, CLAIMED_INPUT_LIVENESS)
    for path in required:
        require(path.is_file(), f"missing required surface: {path.relative_to(ROOT)}")

    domain = DOMAIN.read_text(encoding="utf-8")
    migration_paths = (M020, M021, M022, M023, M024, M025, M026, M027, M028, M029)
    migrations = {path.name: path.read_text(encoding="utf-8") for path in migration_paths}
    m020, m021, m022, m023, m024, m025, m026, m027, m028, m029 = (migrations[path.name] for path in migration_paths)
    conformance = CONFORMANCE.read_text(encoding="utf-8")
    liveness = LIVENESS.read_text(encoding="utf-8")
    claimed_input_liveness = CLAIMED_INPUT_LIVENESS.read_text(encoding="utf-8")

    for marker in (
        'class MetricValueKind', 'class ZabbixNativeValueType', 'class ZabbixItemOperationalState',
        'MAX_ITEMS_PER_SNAPSHOT = 200_000', 'MetricValueKind.INTEGER', 'MetricValueKind.STRING',
        'MetricDefinitionWorker', 'complete_metric_definitions must return authoritative persisted MetricDefinitionResult',
    ):
        require(marker in domain, f"domain invariant missing: {marker}")
    require('BOOLEAN = "boolean"' not in domain, "generic Zabbix integer must not become boolean")
    require('lastvalue' not in domain and 'history_get' not in domain, "current/history ingestion leaked into bounded slice")

    for marker in (
        'item_definition_poll_epoch', 'item_definition_poll_generation', 'monitoring_metric_definition_runtime_admission',
        'CREATE TABLE monitoring.metric_definition (', 'CREATE TABLE monitoring.metric_definition_provider_binding (',
        "provider_object_kind TEXT NOT NULL CHECK (provider_object_kind='zabbix_item')",
        'provider_external_ref TEXT NOT NULL', 'jlmirror_wave4_metric_definition_executor',
        'jlmirror_wave4_metric_definition_invoker', 'metric_definition_sync',
        'REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_definitions',
    ):
        require(marker in m020, f"migration 020 invariant missing: {marker}")

    for marker in (
        'DEFERRABLE INITIALLY DEFERRED', 'reestablish_metric_definition_runtime_admission',
        'monitoring.metric_definition_recovery_epoch_must_advance', 'wave4_retire_missing_metric_definitions',
        "r.presence_state='present'", "r.presence_evidence_state='current'", "r.scope_evidence_state='current'",
    ):
        require(marker in m021, f"migration 021 hardening missing: {marker}")

    for marker in ('PRECHECK:', 'provider.value_kind_drift', 'No definition/binding/provider-evidence mutation from this snapshot is accepted.',
                   'PERFORM monitoring.wave4_retire_missing_metric_definitions', "r.presence_evidence_state='current'"):
        require(marker in m022, f"migration 022 atomicity invariant missing: {marker}")

    for marker in (
        'RETURNS TABLE (', 'UPDATE monitoring.monitoring_source AS s',
        'UPDATE monitoring.monitoring_sync_operation AS o', 'attempt_count=o.attempt_count+1',
        'g.provider_instance_ref', 'g.provider_base_url',
        's.credential_binding_ref', 's.configured_provider_scope',
    ):
        require(marker in m023, f"migration 023 claim qualification/field authority missing: {marker}")
    for forbidden in ('s.provider_base_url', 'g.credential_binding_ref', 'g.configured_provider_scope'):
        require(forbidden not in m023, f"metric claim field read from wrong authority record: {forbidden}")

    for marker in ('wave4_guard_metric_definition_evidence_insert',
                   'Metric definition evidence creation requires guarded executor authority',
                   'wave4_mark_metric_value_kind_drift', "definition_evidence_state='reconciliation_required'",
                   "evidence_state='reconciliation_required'"):
        require(marker in m024, f"migration 024 evidence/drift authority missing: {marker}")

    for marker in ('v_drift_itemid', 'PERFORM monitoring.wave4_mark_metric_value_kind_drift',
                   "p_failure_class := 'provider.value_kind_drift'", "IF p_operation_state='succeeded' THEN"):
        require(marker in m025, f"migration 025 drift visibility missing: {marker}")

    for marker in (
        'metric_definition_owner_tuple_unique', 'metric_definition_binding_owner_fk',
        'metric_definition_provider_evidence_owner_fk', 'metric_definition_poll_authority_single_owner',
        'wave4_mark_metric_binding_reconciliation', 'wave4_verify_metric_snapshot_closure',
        'wave4_verify_metric_provider_evidence_closure', 'Metric provider evidence fingerprint mismatch',
        'Metric provider evidence membership does not match normalized evidence',
    ):
        require(marker in m026, f"migration 026 provenance closure missing: {marker}")

    for marker in (
        'execution.stale_metric_definition_authority', 'provider.host_association_drift',
        'v_current_generation IS DISTINCT FROM v_generation',
        'v_current_configuration_revision IS DISTINCT FROM v_configuration_revision',
        'v_current_scope_revision IS DISTINCT FROM v_scope_revision',
        'monitoring.monitoring_metric_definition_runtime_admission AS a',
        'v_existing_host_ref IS DISTINCT FROM v_hostid', 'v_existing_resource_id IS DISTINCT FROM v_resource_id',
        'PERFORM monitoring.wave4_mark_metric_binding_reconciliation',
    ):
        require(marker in m027, f"migration 027 completion authority missing: {marker}")

    for marker in (
        "p_failure_class := 'provider.protocol_invalid'", "p_failure_class := 'provider.host_association_invalid'",
        "p_operation_state := 'reconciliation_required'", "p_snapshot_complete := FALSE",
        "UPDATE monitoring.monitoring_sync_operation AS o", "claim_token=NULL",
        "No canonical definition/binding mutation",
    ):
        require(marker in m028, f"migration 028 completion liveness missing: {marker}")

    for marker in (
        'complete_zabbix_metric_definitions_v028',
        "p_items IS NULL OR jsonb_typeof(p_items) IS DISTINCT FROM 'array'",
        'v_item_count > 200000', 'v_item_count := 0',
        "v_input_failure := 'execution.invalid_completion_shape'",
        "metric-reconciliation-", 'claim_token=NULL',
        'FROM PUBLIC,jlmirror_wave4_metric_definition_invoker',
    ):
        require(marker in m029, f"migration 029 claimed-input liveness missing: {marker}")

    for migration in (
        'sql/wave4/023_zabbix_metric_definitions_qualified_claim.sql',
        'sql/wave4/024_zabbix_metric_definitions_evidence_and_drift_authority.sql',
        'sql/wave4/025_zabbix_metric_definitions_drift_visibility.sql',
        'sql/wave4/026_zabbix_metric_definitions_provenance_closure.sql',
        'sql/wave4/027_zabbix_metric_definitions_completion_authority.sql',
    ):
        require(migration in conformance, f"broad composed conformance missing {migration}")

    require('sql/wave4/028_zabbix_metric_definitions_completion_liveness.sql' in liveness,
            'final-schema liveness conformance does not apply migration 028')
    require('sql/wave4/029_zabbix_metric_definitions_claimed_input_liveness.sql' in claimed_input_liveness,
            'claimed-input liveness conformance does not apply migration 029')

    combined = '\n'.join(migrations.values())
    for marker in ('metric_current_state', 'metric_observation', 'history.get', 'problem_state', 'health_projection'):
        require(marker not in combined, f"unauthorized surface leaked into SQL: {marker}")

    for marker in (
        'schema=001-027', 'canonical_binding=owner-bound', 'evidence=closed+fingerprint-verified',
        'drift=host+value-visible+atomic', 'poll_stream=independent', 'recovery=stale-fenced+admission-volatile',
    ):
        require(marker in conformance, f"broad PostgreSQL conformance marker missing: {marker}")

    for marker in (
        'schema=001-028', 'malformed=terminal-reconciliation', 'duplicate=terminal-reconciliation',
        'missing_host=terminal-reconciliation', 'partial_mutation=none', 'claim=retired',
    ):
        require(marker in liveness, f"liveness PostgreSQL conformance marker missing: {marker}")

    for marker in (
        'schema=001-029', 'null=terminal', 'nonarray=terminal', 'overbound=terminal',
        'invalid_shape=terminal', 'missing_snapshot=fallback-id', 'helper=executor-only',
        'partial_mutation=none', 'claim=retired',
    ):
        require(marker in claimed_input_liveness, f"claimed-input PostgreSQL conformance marker missing: {marker}")

    print('wave4_zabbix_metric_definitions=PASS schema=020-029 broad=001-027 item_liveness=001-028 claimed_input_liveness=001-029 scope=item-get-metadata-only authority=item-stream-independent atomic_preflight=required claim=qualified+split-field-authority evidence=owner-bound+closed+fingerprint-verified drift=host+value-visible recovery=stale-fenced liveness=terminal-reconciliation+claimed-input-total')


if __name__ == '__main__':
    main()
