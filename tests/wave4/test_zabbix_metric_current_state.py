from __future__ import annotations

from dataclasses import replace

import pytest

from jlmirror_monitoring.metric_current_state import (
    CurrentMetricTarget,
    CurrentStateFailureClass,
    MetricCurrentStateClaim,
    ZabbixCurrentValueEvidence,
    collect_metric_current_state,
    parse_canonical_value,
)
from jlmirror_monitoring.metric_definitions import MetricValueKind
from jlmirror_monitoring.source import OperationalEvidenceState, SyncOperationState


class Reader:
    def __init__(self, rows):
        self.rows = tuple(rows)

    def read_current_values(self, itemids, *, max_items):
        assert max_items == 200_000
        return self.rows


def claim(*targets: CurrentMetricTarget) -> MetricCurrentStateClaim:
    return MetricCurrentStateClaim(
        claim_token="claim-1",
        tenant_id="tenant-1",
        monitoring_sync_operation_id="op-1",
        monitoring_source_id="source-1",
        source_instance_generation="gen-1",
        configuration_revision=1,
        scope_revision=1,
        current_state_poll_epoch=1,
        current_state_poll_generation=1,
        targets=tuple(targets),
    )


def target(itemid: str = "100", kind: MetricValueKind = MetricValueKind.INTEGER) -> CurrentMetricTarget:
    return CurrentMetricTarget("metric-1", "resource-1", itemid, kind)


def test_provider_sample_time_must_be_valid() -> None:
    with pytest.raises(ValueError):
        ZabbixCurrentValueEvidence("100", "1", 0, 0)
    with pytest.raises(ValueError):
        ZabbixCurrentValueEvidence("100", "1", 1, 1_000_000_000)


def test_positive_object_evidence_does_not_require_global_completion() -> None:
    c = claim(target("100"), replace(target("200"), metric_definition_id="metric-2"))
    result = collect_metric_current_state(
        c,
        reader=Reader([ZabbixCurrentValueEvidence("100", "42", 1_700_000_000, 123)]),
    )
    assert result.operation_state is SyncOperationState.SUCCEEDED
    assert result.operational_evidence_state is OperationalEvidenceState.CURRENT
    assert len(result.accepted_observations) == 1
    assert result.accepted_observations[0].canonical_value == 42


def test_unknown_provider_item_fails_closed() -> None:
    result = collect_metric_current_state(
        claim(target("100")),
        reader=Reader([ZabbixCurrentValueEvidence("999", "42", 1_700_000_000, 0)]),
    )
    assert result.operation_state is SyncOperationState.RECONCILIATION_REQUIRED
    assert result.failure_class is CurrentStateFailureClass.PROVIDER_PROTOCOL_INVALID
    assert result.accepted_observations == ()


def test_duplicate_provider_item_fails_closed() -> None:
    row = ZabbixCurrentValueEvidence("100", "42", 1_700_000_000, 0)
    result = collect_metric_current_state(claim(target()), reader=Reader([row, row]))
    assert result.operation_state is SyncOperationState.RECONCILIATION_REQUIRED
    assert result.accepted_observations == ()


def test_integer_parser_is_canonical_and_does_not_infer_boolean() -> None:
    assert parse_canonical_value(MetricValueKind.INTEGER, "1") == 1
    with pytest.raises(ValueError):
        parse_canonical_value(MetricValueKind.INTEGER, " 1")
    assert parse_canonical_value(MetricValueKind.BOOLEAN, "1") is True
    assert parse_canonical_value(MetricValueKind.BOOLEAN, "0") is False
    with pytest.raises(ValueError):
        parse_canonical_value(MetricValueKind.BOOLEAN, "2")


def test_non_finite_number_is_rejected() -> None:
    for raw in ("nan", "inf", "-inf"):
        with pytest.raises(ValueError):
            parse_canonical_value(MetricValueKind.NUMBER, raw)


def test_parse_failure_does_not_partially_accept_batch() -> None:
    c = claim(
        target("100", MetricValueKind.INTEGER),
        CurrentMetricTarget("metric-2", "resource-1", "200", MetricValueKind.INTEGER),
    )
    result = collect_metric_current_state(
        c,
        reader=Reader(
            [
                ZabbixCurrentValueEvidence("100", "42", 1_700_000_000, 1),
                ZabbixCurrentValueEvidence("200", "not-an-int", 1_700_000_001, 2),
            ]
        ),
    )
    assert result.operation_state is SyncOperationState.RECONCILIATION_REQUIRED
    assert result.failure_class is CurrentStateFailureClass.VALUE_PARSE_INVALID
    assert result.accepted_observations == ()
