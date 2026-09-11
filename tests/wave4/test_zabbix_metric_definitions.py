from __future__ import annotations

import unittest

from jlmirror_monitoring.metric_definitions import (
    MAX_ITEMS_PER_SNAPSHOT,
    MetricValueKind,
    ZabbixItemEvidence,
    ZabbixItemOperationalState,
    ZabbixItemSnapshot,
    ZabbixNativeValueType,
    canonical_value_kind,
)


class ZabbixMetricDefinitionTests(unittest.TestCase):
    def test_native_value_types_map_without_boolean_inference(self) -> None:
        self.assertEqual(canonical_value_kind(ZabbixNativeValueType.FLOAT), MetricValueKind.NUMBER)
        self.assertEqual(canonical_value_kind(ZabbixNativeValueType.UNSIGNED), MetricValueKind.INTEGER)
        self.assertEqual(canonical_value_kind(ZabbixNativeValueType.CHARACTER), MetricValueKind.STRING)
        self.assertEqual(canonical_value_kind(ZabbixNativeValueType.TEXT), MetricValueKind.TEXT)
        self.assertEqual(canonical_value_kind(ZabbixNativeValueType.LOG), MetricValueKind.LOG)
        self.assertNotIn(MetricValueKind.BOOLEAN if hasattr(MetricValueKind, "BOOLEAN") else "boolean", set(MetricValueKind))

    def test_provider_disabled_and_unsupported_are_valid_presence_evidence(self) -> None:
        for state in (ZabbixItemOperationalState.DISABLED, ZabbixItemOperationalState.UNSUPPORTED):
            item = ZabbixItemEvidence(
                itemid="10001",
                hostid="20001",
                name="CPU state",
                key="system.cpu.util",
                unit="%",
                native_value_type=ZabbixNativeValueType.FLOAT,
                operational_state=state,
            )
            self.assertEqual(item.value_kind, MetricValueKind.NUMBER)
            self.assertEqual(item.operational_state, state)

    def test_duplicate_itemid_is_rejected(self) -> None:
        item = ZabbixItemEvidence(
            itemid="10001",
            hostid="20001",
            name="CPU",
            key="system.cpu.util",
            unit="%",
            native_value_type=ZabbixNativeValueType.FLOAT,
            operational_state=ZabbixItemOperationalState.ENABLED,
        )
        with self.assertRaisesRegex(ValueError, "duplicate itemid"):
            ZabbixItemSnapshot(items=(item, item), complete=True)

    def test_snapshot_cardinality_is_hard_bounded(self) -> None:
        item = ZabbixItemEvidence(
            itemid="1",
            hostid="2",
            name="n",
            key="k",
            unit="",
            native_value_type=ZabbixNativeValueType.UNSIGNED,
            operational_state=ZabbixItemOperationalState.ENABLED,
        )
        oversized = tuple(item for _ in range(MAX_ITEMS_PER_SNAPSHOT + 1))
        with self.assertRaisesRegex(ValueError, "bounded tuple"):
            ZabbixItemSnapshot(items=oversized, complete=False)

    def test_provider_strings_are_bounded(self) -> None:
        with self.assertRaises(ValueError):
            ZabbixItemEvidence(
                itemid="1",
                hostid="2",
                name="x" * 1025,
                key="k",
                unit="",
                native_value_type=ZabbixNativeValueType.TEXT,
                operational_state=ZabbixItemOperationalState.ENABLED,
            )


if __name__ == "__main__":
    unittest.main()
