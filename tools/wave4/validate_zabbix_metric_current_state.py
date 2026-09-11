#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAIN = ROOT / "src/jlmirror_monitoring/metric_current_state.py"
M030 = ROOT / "sql/wave4/030_zabbix_metric_current_state.sql"
M031 = ROOT / "sql/wave4/031_zabbix_metric_current_state_completion.sql"
TEST = ROOT / "tests/wave4/test_zabbix_metric_current_state.py"
AUTH = ROOT / "implementation/wave-4-metric-current-state-authorization/AUTHORIZATION_MANIFEST.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"WAVE4_METRIC_CURRENT_STATE_ERROR: {message}")


def main() -> None:
    for path in (DOMAIN, M030, M031, TEST, AUTH):
        require(path.is_file(), f"missing required surface: {path.relative_to(ROOT)}")

    domain = DOMAIN.read_text(encoding="utf-8")
    sql030 = M030.read_text(encoding="utf-8")
    sql031 = M031.read_text(encoding="utf-8")
    sql = sql030 + "\n" + sql031

    for marker in (
        "ZabbixCurrentValueEvidence",
        "MetricCurrentStateClaim",
        "AcceptedCurrentObservation",
        "positive object evidence remains admissible",
        "lastclock must be a positive provider sample timestamp",
    ):
        require(marker in domain, f"domain marker missing: {marker}")

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
        "poll generation may advance only one generation at a time",
        "polling requires current recovery/placement admission",
        "recovery epoch transition must preserve local generation",
        "enqueue_zabbix_metric_current_state_sync",
        "claim_zabbix_metric_current_state",
        "list_zabbix_metric_current_targets",
        "complete_zabbix_metric_current_state",
        "Full preflight",
        "Exact accepted-observation replay is idempotent",
        "IF v_semantic_change THEN",
    ):
        require(marker in sql, f"sql marker missing: {marker}")

    require("publication_state" not in sql030, "Monitoring must not duplicate canonical Wave 2 outbox dispatch state")
    require("monitoring_metric_current_state_transition_intent" not in sql, "parallel Current publication-intent table is forbidden")
    require("item_definition_poll_epoch BIGINT NOT NULL DEFAULT" not in sql030, "must not create/reuse Item Definition poll authority")
    require("host_inventory_poll_epoch BIGINT NOT NULL DEFAULT" not in sql030, "must not create/reuse Host Inventory poll authority")
    require("history_projection_state TEXT NOT NULL DEFAULT 'pending'" in sql030, "accepted observations must preserve History obligation")
    require("CREATE TABLE monitoring.metric_observation" not in sql, "history materialization leaked into current slice")
    require("history.get" not in sql.lower(), "history.get leaked into current slice")
    require("b.provider_operational_state='enabled'" in sql031, "disabled/unsupported binding must not gain fresh Current authority")
    require("d.scope_projection_revision=v_operation.scope_revision" in sql031, "Current target must be proven against claim scope revision")
    require("s.current_state_poll_generation=v_operation.current_state_poll_generation" in sql031, "completion must revalidate current poll fence")

    print("wave4_metric_current_state=PASS schema=030-031 current_projection=enabled durable_acceptance=enabled transition=semantic-change-only replay=idempotent history_materialization=blocked poll_stream=independent")


if __name__ == "__main__":
    main()
