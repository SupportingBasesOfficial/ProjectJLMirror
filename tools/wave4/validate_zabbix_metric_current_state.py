#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAIN = ROOT / "src/jlmirror_monitoring/metric_current_state.py"
M030 = ROOT / "sql/wave4/030_zabbix_metric_current_state.sql"
TEST = ROOT / "tests/wave4/test_zabbix_metric_current_state.py"
AUTH = ROOT / "implementation/wave-4-metric-current-state-authorization/AUTHORIZATION_MANIFEST.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"WAVE4_METRIC_CURRENT_STATE_ERROR: {message}")


def main() -> None:
    for path in (DOMAIN, M030, TEST, AUTH):
        require(path.is_file(), f"missing required surface: {path.relative_to(ROOT)}")

    domain = DOMAIN.read_text(encoding="utf-8")
    sql = M030.read_text(encoding="utf-8")

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
    ):
        require(marker in sql, f"sql marker missing: {marker}")

    require("publication_state" not in sql, "Monitoring must not duplicate canonical Wave 2 outbox dispatch state")
    require("monitoring_metric_current_state_transition_intent" not in sql, "parallel Current publication-intent table is forbidden")
    require("item_definition_poll_epoch BIGINT NOT NULL DEFAULT" not in sql, "must not create/reuse Item Definition poll authority")
    require("host_inventory_poll_epoch BIGINT NOT NULL DEFAULT" not in sql, "must not create/reuse Host Inventory poll authority")
    require("history_projection_state TEXT NOT NULL DEFAULT 'pending'" in sql, "accepted observations must preserve History obligation")
    require("metric_observation" not in sql.replace("monitoring_metric_observation_acceptance", ""), "history materialization leaked into current slice")
    require("history.get" not in sql.lower(), "history.get leaked into current slice")

    print("wave4_metric_current_state=PASS migration=030 current_projection=enabled durable_acceptance=enabled transition=owner-domain-immutable history_materialization=blocked poll_stream=independent")


if __name__ == "__main__":
    main()
