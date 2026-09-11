#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAIN = ROOT / "src/jlmirror_monitoring/metric_current_state.py"
MIGRATIONS = [ROOT / f"sql/wave4/{name}" for name in (
    "030_zabbix_metric_current_state.sql",
    "031_zabbix_metric_current_state_completion.sql",
    "032_zabbix_metric_current_state_recovery_authority.sql",
    "033_zabbix_metric_current_state_provider_authority.sql",
    "034_zabbix_metric_current_state_recovery_lifecycle.sql",
    "035_zabbix_metric_current_state_claimed_input_liveness.sql",
    "036_zabbix_metric_current_state_completion_totalization.sql",
    "037_zabbix_metric_current_state_supersession.sql",
    "038_zabbix_metric_current_state_least_privilege.sql",
)]
TEST = ROOT / "tests/wave4/test_zabbix_metric_current_state.py"
AUTH = ROOT / "implementation/wave-4-metric-current-state-authorization/AUTHORIZATION_MANIFEST.json"
CONFORMANCE = ROOT / "tools/wave4/run_zabbix_metric_current_state_postgres_conformance.sh"
HARDENING = ROOT / "tools/wave4/run_zabbix_metric_current_state_hardening_postgres_conformance.sh"
RECOVERY_DUMP = ROOT / "tools/wave4/pg_dump_recovery_safe.sh"
WORKFLOW = ROOT / ".github/workflows/wave4-monitoring-source-foundation.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"WAVE4_METRIC_CURRENT_STATE_ERROR: {message}")


def executable_sql(text: str) -> str:
    """Remove SQL line comments before checking forbidden executable surfaces."""
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines())


def main() -> None:
    for path in (DOMAIN, *MIGRATIONS, TEST, AUTH, CONFORMANCE, HARDENING, RECOVERY_DUMP, WORKFLOW):
        require(path.is_file(), f"missing required surface: {path.relative_to(ROOT)}")

    domain = DOMAIN.read_text(encoding="utf-8")
    domain_lower = domain.lower()
    migration_text = {path.name: path.read_text(encoding="utf-8") for path in MIGRATIONS}
    sql = "\n".join(migration_text.values())
    executable = executable_sql(sql).lower()
    sql030 = migration_text["030_zabbix_metric_current_state.sql"]
    sql031 = migration_text["031_zabbix_metric_current_state_completion.sql"]
    sql032 = migration_text["032_zabbix_metric_current_state_recovery_authority.sql"]
    sql033 = migration_text["033_zabbix_metric_current_state_provider_authority.sql"]
    sql034 = migration_text["034_zabbix_metric_current_state_recovery_lifecycle.sql"]
    sql036 = migration_text["036_zabbix_metric_current_state_completion_totalization.sql"]
    sql037 = migration_text["037_zabbix_metric_current_state_supersession.sql"]
    sql038 = migration_text["038_zabbix_metric_current_state_least_privilege.sql"]
    conformance = CONFORMANCE.read_text(encoding="utf-8")
    hardening = HARDENING.read_text(encoding="utf-8")
    recovery_dump = RECOVERY_DUMP.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for marker in (
        "ZabbixCurrentValueEvidence",
        "MetricCurrentStateClaim",
        "AcceptedCurrentObservation",
        "CredentialResolver",
        "OutboundAdmission",
        "provider_configuration",
        "lastclock must be a positive provider sample timestamp",
        "Decimal(raw)",
    ):
        require(marker in domain, f"domain marker missing: {marker}")
    require("positive object evidence remains admissible" in domain_lower,
            "domain marker missing: positive object evidence remains admissible")

    for marker in (
        "current_state_poll_epoch",
        "current_state_poll_generation",
        "monitoring_metric_current_state_runtime_admission",
        "monitoring_metric_observation_acceptance",
        "history_projection_state",
        "metric_current_state",
        "monitoring_metric_current_state_transition",
        "FORCE ROW LEVEL SECURITY",
        "jlmirror_wave4_metric_current_state_executor",
        "jlmirror_wave4_recovery_authority",
        "enqueue_zabbix_metric_current_state_sync",
        "claim_zabbix_metric_current_state",
        "list_zabbix_metric_current_targets",
        "complete_zabbix_metric_current_state",
        "Exact accepted-observation replay is idempotent",
        "IF v_semantic_change THEN",
    ):
        require(marker in sql, f"sql marker missing: {marker}")

    require("poll generation may advance only one generation at a time" in sql030, "poll generation must be single-step fenced")
    require("polling requires current recovery/placement admission" in sql030, "poll advancement must require admission")
    require("recovery epoch transition must preserve local generation" in sql030, "recovery epoch must preserve generation")
    require("history_projection_state TEXT NOT NULL DEFAULT 'pending'" in sql030, "accepted observations must preserve History obligation")
    require("publication_state" not in sql030, "Monitoring must not duplicate canonical Wave 2 outbox dispatch state")
    require("monitoring_metric_current_state_transition_intent" not in sql, "parallel Current publication-intent table is forbidden")
    require("item_definition_poll_epoch BIGINT NOT NULL DEFAULT" not in sql030, "must not create/reuse Item Definition poll authority")
    require("host_inventory_poll_epoch BIGINT NOT NULL DEFAULT" not in sql030, "must not create/reuse Host Inventory poll authority")

    for forbidden in (
        "create table monitoring.metric_observation",
        "create table monitoring.metric_history",
        "create table monitoring.metric_history_checkpoint",
        "create function monitoring.history_",
        "create or replace function monitoring.history_",
        "create function monitoring.metric_history_",
        "create or replace function monitoring.metric_history_",
        "history.get(",
        "history_get(",
    ):
        require(forbidden not in executable, f"History implementation leaked into Current slice: {forbidden}")

    require("b.provider_operational_state='enabled'" in sql031, "disabled/unsupported binding must not gain fresh Current authority")
    require("d.scope_projection_revision=v_operation.scope_revision" in sql031, "Current target must be proven against claim scope revision")
    require("s.current_state_poll_generation=v_operation.current_state_poll_generation" in sql031, "completion must revalidate current poll fence")
    require("reestablish_metric_current_state_runtime_admission" in sql032, "missing Current recovery readmission")
    require("wave4_terminalize_superseded_metric_current_state_claims" in sql032, "recovery must cross narrow Current terminalization helper")
    require("UPDATE monitoring.monitoring_sync_operation AS o" not in sql032, "recovery function must not directly mutate monitoring_sync_operation")
    require("g.provider_instance_ref,g.provider_base_url,s.credential_binding_ref" in sql033, "Current claim fields must come from owning generation/source records")
    require("Recovery authority may only terminalize superseded Metric Current State claims" in sql034, "operation guard must retain narrow recovery defense")
    require("wave4_current_value_matches_kind" in sql, "database must enforce value-kind/value shape compatibility")
    require("jsonb_typeof(p_observations)<>'array'" in sql036, "claimed-input totalization must validate array shape")
    require("9223372036854775807::NUMERIC" in sql036, "provider clock must be bounded before BIGINT cast")
    require("wave4_current_provider_timestamp_is_valid" in sql036, "provider timestamp conversion must be exception-safe")
    require("WHEN datetime_field_overflow OR numeric_value_out_of_range" in sql036, "provider timestamp overflow must fail closed")
    require("old_o.current_state_poll_generation<v_poll_generation" in sql037, "new Current claim must supersede older in-flight generations")
    require("s.current_state_poll_generation=o.current_state_poll_generation" in sql037, "target listing must revalidate current poll fence")

    require("REVOKE INSERT,UPDATE ON monitoring.monitoring_source" in sql038, "executor source privilege must be narrowed")
    require("GRANT UPDATE (current_state_poll_generation,updated_at)" in sql038, "executor may update only its poll generation bookkeeping")
    require("REVOKE ALL ON monitoring.monitoring_sync_operation" in sql038, "recovery must have no direct operation-table authority")
    require("CREATE OR REPLACE FUNCTION monitoring.wave4_terminalize_superseded_metric_current_state_claims" in sql038, "narrow recovery terminalization helper missing")
    require("AND o.responsibility_kind='metric_current_state_sync'" in sql038, "recovery helper must be responsibility-bound")
    require("AND o.state='running'" in sql038, "recovery helper must be running-state-bound")
    require("AND o.current_state_poll_epoch=p_current_poll_epoch" in sql038, "recovery helper must be old-epoch-bound")
    require("OWNER TO jlmirror_wave4_metric_current_state_executor" in sql038, "recovery helper must execute under Current executor authority")
    require("GRANT EXECUTE ON FUNCTION monitoring.wave4_terminalize_superseded_metric_current_state_claims" in sql038, "recovery helper execute bridge missing")
    require("has_column_privilege" in sql038 and "must not hold direct monitoring_sync_operation UPDATE" in sql038,
            "migration-time negative privilege assurance missing")

    require("--exclude-table-data=monitoring.monitoring_metric_current_state_runtime_admission" in recovery_dump, "recovery dump must exclude Current runtime admission")
    require("run_zabbix_metric_current_state_postgres_conformance.sh" in workflow, "Wave4 workflow must execute Current PostgreSQL conformance")
    require("run_zabbix_metric_current_state_hardening_postgres_conformance.sh" in workflow, "Wave4 workflow must execute Current hardening PostgreSQL conformance")
    require("sql/wave4/038_zabbix_metric_current_state_least_privilege.sql" in conformance, "conformance must execute final Current schema through 038")
    for marker in (
        "exact_replay=idempotent",
        "same_value=no-transition",
        "backward_provider_time=allowed-by-fence",
        "claimed_input=terminalized",
        "supersession=single-winner",
        "recovery=stream-local",
    ):
        require(marker in conformance, f"conformance marker missing: {marker}")

    require("sql/wave4/038_zabbix_metric_current_state_least_privilege.sql" in hardening,
            "hardening conformance must execute final Current schema through 038")
    for marker in (
        "9223372036854775807",
        "provider_timestamp=exception-safe",
        "recovery_operation_dml=none",
        "recovery_bridge=narrow",
        "0:0:0:1",
    ):
        require(marker in hardening, f"hardening PostgreSQL marker missing: {marker}")

    print("wave4_metric_current_state=PASS schema=030-038 current_projection=enabled durable_acceptance=enabled transition=semantic-change-only replay=idempotent trust_boundary=explicit recovery=helper-isolated provider_timestamp=exception-safe history_materialization=blocked")


if __name__ == "__main__":
    main()
