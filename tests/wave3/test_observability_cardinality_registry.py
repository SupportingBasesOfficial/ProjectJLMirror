import unittest

from jlmirror_observability import ObservationError, SignalFamily, SignalRecord


class ObservabilityCardinalityRegistryTests(unittest.TestCase):
    def test_namespaced_tenant_identifier_cannot_launder_into_operation_class(self):
        with self.assertRaisesRegex(ObservationError, "reviewed finite Wave 3 registry"):
            SignalRecord(
                "obs.request.outcome@1",
                SignalFamily.LOG,
                "tenant.customer123",
                "internal",
                "bounded",
            )

    def test_known_metric_key_does_not_make_runtime_value_a_safe_dimension(self):
        cases = (
            (
                "obs.provider.operation@1",
                "api.read",
                {"provider_class": "tenant-12345"},
            ),
            (
                "obs.operation.state@1",
                "api.read",
                {"state_class": "resource-550e8400"},
            ),
            (
                "obs.async.progress@1",
                "api.read",
                {"workload_class": "customer-acme"},
            ),
            (
                "obs.observability.pipeline@1",
                "api.read",
                {"saturation_class": "tenant-42"},
            ),
        )
        for profile_id, operation_class, dimensions in cases:
            with self.subTest(profile_id=profile_id, dimensions=dimensions):
                with self.assertRaisesRegex(ObservationError, "reviewed finite semantic registry"):
                    SignalRecord(
                        profile_id,
                        SignalFamily.METRIC,
                        operation_class,
                        "internal",
                        "bounded",
                        metric_dimensions=dimensions,
                    )

    def test_phase11_failure_and_degradation_taxonomies_are_finite(self):
        record = SignalRecord(
            "obs.message-equivalence.admission@1",
            SignalFamily.METRIC,
            "message.equivalence",
            "protected",
            "bounded",
            metric_dimensions={
                "comparison_outcome_class": "verifier_temporarily_unavailable",
                "reliability_failure_class": "unavailable",
                "reliability_degradation_mode": "fail_closed",
            },
        )
        self.assertEqual(record.metric_dimensions["reliability_failure_class"], "unavailable")

        for key, value in (
            ("reliability_failure_class", "tenant-12345"),
            ("reliability_degradation_mode", "retry_forever"),
        ):
            dimensions = {
                "comparison_outcome_class": "verifier_temporarily_unavailable",
                "reliability_failure_class": "unavailable",
                "reliability_degradation_mode": "fail_closed",
                key: value,
            }
            with self.subTest(key=key, value=value), self.assertRaises(ObservationError):
                SignalRecord(
                    "obs.message-equivalence.admission@1",
                    SignalFamily.METRIC,
                    "message.equivalence",
                    "protected",
                    "bounded",
                    metric_dimensions=dimensions,
                )


if __name__ == "__main__":
    unittest.main()
