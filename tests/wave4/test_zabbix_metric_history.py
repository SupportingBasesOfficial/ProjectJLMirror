from __future__ import annotations

import unittest
from pathlib import Path

from jlmirror_monitoring.metric_definitions import MetricValueKind
from jlmirror_monitoring.metric_history import (
    HistoryCoverageState,
    HistoryMetricTarget,
    MAX_HISTORY_ITEMS_PER_REQUEST,
    MAX_HISTORY_ROWS_PER_REQUEST,
    MetricHistoryFailureClass,
    MetricHistoryWindow,
    ZabbixHistoryEvidence,
)

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "sql/wave4/040_zabbix_metric_history.sql"


class MetricHistoryDomainTests(unittest.TestCase):
    def test_window_is_bounded_and_inclusive(self) -> None:
        window = MetricHistoryWindow(1_000, 1_100)
        self.assertEqual(window.time_from, 1_000)
        self.assertEqual(window.time_till, 1_100)
        with self.assertRaises(ValueError):
            MetricHistoryWindow(1_100, 1_000)

    def test_target_binds_item_and_value_type(self) -> None:
        target = HistoryMetricTarget(
            metric_definition_id="metric-1",
            monitoring_resource_id="resource-1",
            provider_external_ref="42",
            value_kind=MetricValueKind.NUMBER,
            history_value_type=0,
        )
        self.assertEqual(target.provider_external_ref, "42")
        with self.assertRaises(ValueError):
            HistoryMetricTarget("metric-1", "resource-1", "42", MetricValueKind.NUMBER, 9)

    def test_same_second_rows_remain_distinct_by_ns(self) -> None:
        first = ZabbixHistoryEvidence("42", 1_700_000_000, 1, "1")
        second = ZabbixHistoryEvidence("42", 1_700_000_000, 2, "1")
        self.assertNotEqual((first.clock, first.ns), (second.clock, second.ns))

    def test_implementation_limits_are_finite(self) -> None:
        self.assertGreater(MAX_HISTORY_ITEMS_PER_REQUEST, 0)
        self.assertGreater(MAX_HISTORY_ROWS_PER_REQUEST, 0)
        self.assertEqual(HistoryCoverageState.GAP.value, "gap")
        self.assertEqual(MetricHistoryFailureClass.PAGE_TRUNCATED.value, "monitoring.history_page_truncated")


class MetricHistoryPersistenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = SQL.read_text(encoding="utf-8")
        cls.lower = cls.sql.lower()

    def test_materializes_history_without_current_mutation(self) -> None:
        self.assertIn("create table monitoring.metric_observation", self.lower)
        self.assertIn("create table monitoring.metric_history_stream_state", self.lower)
        self.assertNotIn("update monitoring.metric_current_state", self.lower)
        self.assertNotIn("insert into monitoring.metric_current_state", self.lower)
        self.assertNotIn("delete from monitoring.metric_current_state", self.lower)

    def test_history_reuses_durable_acceptance_identity(self) -> None:
        self.assertIn(
            "references monitoring.monitoring_metric_observation_acceptance(tenant_id, observation_id)",
            self.lower,
        )
        self.assertIn("history projection cannot be acknowledged before compatible durable projection exists", self.lower)
        self.assertIn("history projection state permits only pending to projected", self.lower)

    def test_checkpoint_is_independent_per_logical_stream(self) -> None:
        for marker in (
            "monitoring_source_id text not null",
            "source_instance_generation text not null",
            "provider_external_ref text not null",
            "history_value_type integer not null",
            "provisional_clock bigint",
            "safe_clock bigint",
            "finalized_through_clock bigint",
            "coverage_state text not null",
        ):
            self.assertIn(marker, self.lower)
        self.assertIn("metric history safe checkpoint cannot rewind", self.lower)

    def test_gap_evidence_is_explicit_and_immutable(self) -> None:
        self.assertIn("create table monitoring.metric_history_gap_evidence", self.lower)
        self.assertIn("provider_retention_loss", self.lower)
        self.assertIn("truncated_window", self.lower)
        self.assertIn("metric_history_gap_evidence_immutable_guard", self.lower)

    def test_history_tables_force_rls(self) -> None:
        for table in (
            "monitoring.metric_observation",
            "monitoring.metric_history_stream_state",
            "monitoring.metric_history_gap_evidence",
        ):
            self.assertIn(f"alter table {table} enable row level security", self.lower)
            self.assertIn(f"alter table {table} force row level security", self.lower)


if __name__ == "__main__":
    unittest.main()
