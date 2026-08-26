import unittest

from jlmirror_observability import (
    EvidencePlane, HealthAssessment, HealthState, ObservationError, ObservabilityBinding,
    SignalFamily, SignalRecord, missing_health, require_product_applicability,
)


class ObservabilityTests(unittest.TestCase):
    def test_signal_record_accepts_profile_declared_bounded_dimensions(self):
        rec = SignalRecord(
            profile_id="obs.request.outcome@1", family=SignalFamily.METRIC,
            operation_class="api.read", classification="internal",
            tenant_scope_class="tenant_scoped_bounded",
            metric_dimensions={"outcome_class": "success", "operation_class": "api.read"},
            diagnostic_fields={"request_id": "r-1"},
        )
        self.assertEqual(rec.metric_dimensions["outcome_class"], "success")
        self.assertEqual(rec.evidence_plane, EvidencePlane.OPERATIONAL_OBSERVABILITY)
        self.assertFalse(rec.grants_authority)

    def test_request_id_alias_cannot_be_metric_dimension(self):
        for key in ("request_id", "requestId", "req-id", "local_dynamic_label"):
            with self.subTest(key=key):
                with self.assertRaises(ObservationError):
                    SignalRecord("obs.request.outcome@1", SignalFamily.METRIC, "api.read", "internal", "bounded", {key: "r-1"})

    def test_untrusted_dynamic_diagnostic_field_name_fails_closed(self):
        with self.assertRaises(ObservationError):
            SignalRecord("obs.request.outcome@1", SignalFamily.LOG, "api.read", "internal", "bounded", diagnostic_fields={"user_supplied_index_name": "value"})

    def test_diagnostic_identifier_rejects_payload_shape(self):
        with self.assertRaises(ObservationError):
            SignalRecord("obs.request.outcome@1", SignalFamily.LOG, "api.read", "internal", "bounded", diagnostic_fields={"request_id": "Bearer secret-token"})

    def test_secret_bearing_field_name_is_rejected(self):
        with self.assertRaises(ObservationError):
            SignalRecord("obs.request.outcome@1", SignalFamily.LOG, "api.read", "internal", "bounded", diagnostic_fields={"refresh_token": "never"})

    def test_metric_value_must_be_bounded_semantic_token(self):
        with self.assertRaises(ObservationError):
            SignalRecord("obs.request.outcome@1", SignalFamily.METRIC, "api.read", "internal", "bounded", metric_dimensions={"outcome_class": "arbitrary value with spaces " * 30})

    def test_outcome_class_is_exact_phase12_taxonomy_not_arbitrary_token(self):
        with self.assertRaises(ObservationError):
            SignalRecord("obs.request.outcome@1", SignalFamily.METRIC, "api.read", "internal", "bounded", metric_dimensions={"outcome_class": "tenant-12345"})

    def test_metric_operation_class_cannot_disagree_with_record_class(self):
        with self.assertRaises(ObservationError):
            SignalRecord("obs.request.outcome@1", SignalFamily.METRIC, "api.read", "internal", "bounded", metric_dimensions={"operation_class": "api.write"})

    def test_operation_class_requires_stable_namespaced_semantic_shape(self):
        for value in ("tenant-12345", "550e8400-e29b-41d4-a716-446655440000", "single"):
            with self.subTest(value=value), self.assertRaises(ObservationError):
                SignalRecord("obs.request.outcome@1", SignalFamily.LOG, value, "internal", "bounded")

    def test_tenant_scope_class_cannot_be_raw_tenant_identifier(self):
        for value in ("tenant-12345", "550e8400-e29b-41d4-a716-446655440000", "customer-acme"):
            with self.subTest(value=value), self.assertRaises(ObservationError):
                SignalRecord("obs.request.outcome@1", SignalFamily.LOG, "api.read", "internal", value)

    def test_classification_is_reviewed_bounded_mapping(self):
        with self.assertRaises(ObservationError):
            SignalRecord("obs.request.outcome@1", SignalFamily.LOG, "api.read", "tenant-12345", "bounded")

    def test_unknown_signal_profile_fails_closed(self):
        with self.assertRaises(ObservationError):
            SignalRecord("obs.local-made-up@1", SignalFamily.EVENT, "x", "internal", "none")

    def test_wrong_signal_family_fails_closed(self):
        with self.assertRaises(ObservationError):
            SignalRecord("obs.security.authority-freshness@1", SignalFamily.TRACE, "security.currentness", "protected", "bounded")

    def test_customer_acceptance_plane_is_not_operational_observability(self):
        rec = SignalRecord("obs.telemetry.acceptance@1", SignalFamily.EVENT, "monitoring.accept", "internal", "tenant_scoped_bounded")
        self.assertEqual(rec.evidence_plane, EvidencePlane.CUSTOMER_MONITORING)

    def test_audit_responsibility_plane_is_distinct(self):
        rec = SignalRecord("obs.audit.responsibility-health@1", SignalFamily.HEALTH, "audit.responsibility", "protected", "bounded")
        self.assertEqual(rec.evidence_plane, EvidencePlane.AUDIT_RESPONSIBILITY)

    def test_missing_health_is_unknown(self):
        health = missing_health("health.observability-pipeline@1")
        self.assertEqual(health.state, HealthState.UNKNOWN)
        self.assertFalse(health.evidence_complete)
        self.assertFalse(health.grants_authority)

    def test_incomplete_health_cannot_be_green(self):
        with self.assertRaises(ObservationError):
            HealthAssessment("health.cell@1", HealthState.HEALTHY, "missing_dependency_data", False)

    def test_health_never_grants_authority(self):
        health = HealthAssessment("health.cell@1", HealthState.HEALTHY, "evidence_complete", True)
        self.assertFalse(health.grants_authority)

    def test_no_applicable_case_requires_reason(self):
        with self.assertRaises(ObservationError):
            ObservabilityBinding("health.security-authority@1", ("sli.api.outcome@1",), ("alert.security-trust@1",), False)

    def test_unknown_product_applicability_fails_closed(self):
        with self.assertRaises(ObservationError):
            require_product_applicability(product_state_proven=False, enabled=False)

    def test_proven_disabled_product_stays_disabled(self):
        self.assertFalse(require_product_applicability(product_state_proven=True, enabled=False))


if __name__ == "__main__":
    unittest.main()
