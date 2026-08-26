import unittest

from jlmirror_observability import (
    HealthAssessment,
    HealthState,
    ObservationError,
    ObservabilityBinding,
    SignalFamily,
    SignalRecord,
    missing_health,
    require_product_applicability,
)


class ObservabilityTests(unittest.TestCase):
    def test_signal_record_accepts_bounded_dimensions(self):
        rec = SignalRecord(
            profile_id="obs.request.outcome@1",
            family=SignalFamily.METRIC,
            operation_class="api.read",
            classification="internal",
            tenant_scope_class="tenant_scoped_bounded",
            metric_dimensions={"outcome_class": "success", "operation_class": "api.read"},
            diagnostic_fields={"request_id": "r-1"},
        )
        self.assertEqual(rec.metric_dimensions["outcome_class"], "success")

    def test_request_id_cannot_be_metric_dimension(self):
        with self.assertRaises(ObservationError):
            SignalRecord(
                profile_id="obs.request.outcome@1",
                family=SignalFamily.METRIC,
                operation_class="api.read",
                classification="internal",
                tenant_scope_class="tenant_scoped_bounded",
                metric_dimensions={"request_id": "r-1"},
            )

    def test_secret_bearing_field_is_rejected(self):
        with self.assertRaises(ObservationError):
            SignalRecord(
                profile_id="obs.request.outcome@1",
                family=SignalFamily.LOG,
                operation_class="api.read",
                classification="internal",
                tenant_scope_class="tenant_scoped_bounded",
                diagnostic_fields={"refresh_token": "never"},
            )

    def test_unknown_signal_profile_fails_closed(self):
        with self.assertRaises(ObservationError):
            SignalRecord(
                profile_id="obs.local-made-up@1",
                family=SignalFamily.EVENT,
                operation_class="x",
                classification="internal",
                tenant_scope_class="none",
            )

    def test_missing_health_is_unknown(self):
        health = missing_health("health.observability-pipeline@1")
        self.assertEqual(health.state, HealthState.UNKNOWN)
        self.assertFalse(health.evidence_complete)
        self.assertFalse(health.grants_authority)

    def test_incomplete_health_cannot_be_green(self):
        with self.assertRaises(ObservationError):
            HealthAssessment(
                profile_id="health.cell@1",
                state=HealthState.HEALTHY,
                reason_class="missing_dependency_data",
                evidence_complete=False,
            )

    def test_health_never_grants_authority(self):
        health = HealthAssessment(
            profile_id="health.cell@1",
            state=HealthState.HEALTHY,
            reason_class="evidence_complete",
            evidence_complete=True,
        )
        self.assertFalse(health.grants_authority)

    def test_no_applicable_case_requires_reason(self):
        with self.assertRaises(ObservationError):
            ObservabilityBinding(
                health_profile_id="health.security-authority@1",
                sli_profile_ids=("sli.api.outcome@1",),
                alert_profile_ids=("alert.security-trust@1",),
                direct_sli_applicable=False,
            )

    def test_unknown_product_applicability_fails_closed(self):
        with self.assertRaises(ObservationError):
            require_product_applicability(product_state_proven=False, enabled=False)

    def test_proven_disabled_product_stays_disabled(self):
        self.assertFalse(require_product_applicability(product_state_proven=True, enabled=False))


if __name__ == "__main__":
    unittest.main()
