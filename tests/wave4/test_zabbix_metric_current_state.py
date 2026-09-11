from __future__ import annotations

import unittest
from dataclasses import replace

from jlmirror_monitoring.metric_current_state import (
    CurrentMetricTarget,
    CurrentStateFailureClass,
    MetricCurrentStateClaim,
    ZabbixCurrentValueEvidence,
    collect_metric_current_state,
    parse_canonical_value,
)
from jlmirror_monitoring.metric_definitions import MetricValueKind
from jlmirror_monitoring.source import OperationalEvidenceState, SyncOperationState, ZabbixProviderConfiguration
from jlmirror_monitoring.validation_worker import (
    AdmittedProviderEndpoint,
    CredentialResolutionError,
    EgressAdmissionError,
    ResolvedZabbixCredential,
)


class Reader:
    def __init__(self, rows):
        self.rows = tuple(rows)

    def read_current_values(self, endpoint, credential, itemids, *, max_items):
        assert isinstance(endpoint, AdmittedProviderEndpoint)
        assert isinstance(credential, ResolvedZabbixCredential)
        assert max_items == 200_000
        return self.rows


class Resolver:
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    def resolve_zabbix_api_token(self, credential_binding_ref):
        if self.fail:
            raise CredentialResolutionError("missing")
        assert credential_binding_ref == "credential-binding:current"
        return ResolvedZabbixCredential("secret-token", "credential-generation:current")


class Admission:
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    def admit_zabbix_api(self, provider_configuration):
        if self.fail:
            raise EgressAdmissionError("blocked")
        assert provider_configuration.base_url == "https://zabbix.example.test/zabbix"
        return AdmittedProviderEndpoint(
            "https://zabbix.example.test/zabbix/api_jsonrpc.php",
            "egress-decision:current",
        )


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
        provider_instance_ref="provider-instance:current",
        provider_configuration=ZabbixProviderConfiguration("https://zabbix.example.test/zabbix"),
        credential_binding_ref="credential-binding:current",
        targets=tuple(targets),
    )


def collect(c, rows):
    return collect_metric_current_state(
        c,
        credential_resolver=Resolver(),
        outbound_admission=Admission(),
        reader=Reader(rows),
    )


def target(itemid: str = "100", kind: MetricValueKind = MetricValueKind.INTEGER) -> CurrentMetricTarget:
    return CurrentMetricTarget("metric-1", "resource-1", itemid, kind)


class MetricCurrentStateTests(unittest.TestCase):
    def test_provider_sample_time_must_be_valid(self) -> None:
        with self.assertRaises(ValueError):
            ZabbixCurrentValueEvidence("100", "1", 0, 0)
        with self.assertRaises(ValueError):
            ZabbixCurrentValueEvidence("100", "1", 1, 1_000_000_000)

    def test_positive_object_evidence_does_not_require_global_completion(self) -> None:
        c = claim(target("100"), replace(target("200"), metric_definition_id="metric-2"))
        result = collect(c, [ZabbixCurrentValueEvidence("100", "42", 1_700_000_000, 123)])
        self.assertIs(result.operation_state, SyncOperationState.SUCCEEDED)
        self.assertIs(result.operational_evidence_state, OperationalEvidenceState.CURRENT)
        self.assertEqual(len(result.accepted_observations), 1)
        self.assertEqual(result.accepted_observations[0].canonical_value, 42)
        self.assertEqual(result.egress_decision_ref, "egress-decision:current")
        self.assertEqual(result.credential_generation_ref, "credential-generation:current")

    def test_credential_and_egress_authority_fail_closed(self) -> None:
        c = claim(target())
        credential_failure = collect_metric_current_state(
            c,
            credential_resolver=Resolver(fail=True),
            outbound_admission=Admission(),
            reader=Reader([]),
        )
        self.assertIs(credential_failure.failure_class, CurrentStateFailureClass.CREDENTIAL_UNAVAILABLE)
        egress_failure = collect_metric_current_state(
            c,
            credential_resolver=Resolver(),
            outbound_admission=Admission(fail=True),
            reader=Reader([]),
        )
        self.assertIs(egress_failure.failure_class, CurrentStateFailureClass.EGRESS_NOT_ADMITTED)

    def test_unknown_provider_item_fails_closed(self) -> None:
        result = collect(claim(target("100")), [ZabbixCurrentValueEvidence("999", "42", 1_700_000_000, 0)])
        self.assertIs(result.operation_state, SyncOperationState.RECONCILIATION_REQUIRED)
        self.assertIs(result.failure_class, CurrentStateFailureClass.PROVIDER_PROTOCOL_INVALID)
        self.assertEqual(result.accepted_observations, ())

    def test_duplicate_provider_item_fails_closed(self) -> None:
        row = ZabbixCurrentValueEvidence("100", "42", 1_700_000_000, 0)
        result = collect(claim(target()), [row, row])
        self.assertIs(result.operation_state, SyncOperationState.RECONCILIATION_REQUIRED)
        self.assertEqual(result.accepted_observations, ())

    def test_integer_parser_is_canonical_and_does_not_infer_boolean(self) -> None:
        self.assertEqual(parse_canonical_value(MetricValueKind.INTEGER, "1"), 1)
        with self.assertRaises(ValueError):
            parse_canonical_value(MetricValueKind.INTEGER, " 1")
        self.assertIs(parse_canonical_value(MetricValueKind.BOOLEAN, "1"), True)
        self.assertIs(parse_canonical_value(MetricValueKind.BOOLEAN, "0"), False)
        with self.assertRaises(ValueError):
            parse_canonical_value(MetricValueKind.BOOLEAN, "2")

    def test_non_finite_number_is_rejected(self) -> None:
        for raw in ("nan", "inf", "-inf"):
            with self.assertRaises(ValueError):
                parse_canonical_value(MetricValueKind.NUMBER, raw)

    def test_parse_failure_does_not_partially_accept_batch(self) -> None:
        c = claim(
            target("100", MetricValueKind.INTEGER),
            CurrentMetricTarget("metric-2", "resource-1", "200", MetricValueKind.INTEGER),
        )
        result = collect(
            c,
            [
                ZabbixCurrentValueEvidence("100", "42", 1_700_000_000, 1),
                ZabbixCurrentValueEvidence("200", "not-an-int", 1_700_000_001, 2),
            ],
        )
        self.assertIs(result.operation_state, SyncOperationState.RECONCILIATION_REQUIRED)
        self.assertIs(result.failure_class, CurrentStateFailureClass.VALUE_PARSE_INVALID)
        self.assertEqual(result.accepted_observations, ())


if __name__ == "__main__":
    unittest.main()
