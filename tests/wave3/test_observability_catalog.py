import unittest

from jlmirror_observability import (
    EXPECTED_RELIABILITY_PROFILE_IDS,
    ObservationError,
    ProductApplicabilityEvidence,
    RELIABILITY_OBSERVABILITY_JOINS,
    join_for,
)


EXPECTED = {
    "rel.control-plane-placement@1",
    "rel.cell-transactional-store@1",
    "rel.security-session-authority@1",
    "rel.placement-reference-cache@1",
    "rel.performance-cache@1",
    "rel.replay-consume-state@1",
    "rel.secret-key-authority@1",
    "rel.configuration-authority@1",
    "rel.outbox-publication@1",
    "rel.broker-job-transport@1",
    "rel.consumer-inbox-effect@1",
    "rel.external-provider@1",
    "rel.realtime-fanout@1",
    "rel.webhook-delivery@1",
    "rel.telemetry-plane@1",
    "rel.customer-telemetry-acceptance@1",
    "rel.mandatory-audit-plane@1",
    "rel.artifact-storage@1",
    "rel.reporting-derived@1",
    "rel.privileged-operations@1",
}


def product_evidence(selector_id, scope, enabled, **changes):
    values = dict(
        selector_id=selector_id,
        authority_profile="product.scope-authority@1",
        evidence_reference="evidence:product-selector-1",
        scope_binding=scope,
        current=True,
        enabled=enabled,
    )
    values.update(changes)
    return ProductApplicabilityEvidence(**values)


class ObservabilityCatalogTests(unittest.TestCase):
    def test_exact_reliability_profile_set_is_materialized(self):
        self.assertEqual(set(EXPECTED_RELIABILITY_PROFILE_IDS), EXPECTED)
        self.assertEqual(set(RELIABILITY_OBSERVABILITY_JOINS), EXPECTED)

    def test_unknown_reliability_profile_fails_closed(self):
        with self.assertRaises(ObservationError):
            join_for("rel.local-default@1")

    def test_security_authority_direct_sli_is_explicitly_not_applicable(self):
        row = join_for("rel.security-session-authority@1")
        self.assertEqual(row.sli_profile_ids, ())
        self.assertIsNotNone(row.direct_sli_no_applicable_case_reason)
        self.assertEqual(row.impact_sli_profile_ids, ("sli.api.outcome@1",))

    def test_webhook_unproven_product_state_remains_open(self):
        row = join_for("rel.webhook-delivery@1")
        result = row.resolve_product_applicability(None, expected_scope="rel.webhook-delivery@1")
        self.assertEqual(result.state, "open")
        self.assertEqual(result.open_decision_id, "OPEN-OBS-037")

    def test_webhook_disabled_requires_current_scoped_authority_and_is_no_applicable_case(self):
        row = join_for("rel.webhook-delivery@1")
        evidence = product_evidence("webhook_product_state", "rel.webhook-delivery@1", False)
        result = row.resolve_product_applicability(evidence, expected_scope="rel.webhook-delivery@1")
        self.assertEqual(result.state, "no_applicable_case")
        self.assertTrue(result.no_applicable_case_reason)

    def test_webhook_enabled_still_has_open_commitment_decision(self):
        row = join_for("rel.webhook-delivery@1")
        evidence = product_evidence("webhook_product_state", "rel.webhook-delivery@1", True)
        result = row.resolve_product_applicability(evidence, expected_scope="rel.webhook-delivery@1")
        self.assertEqual(result.state, "open")
        self.assertEqual(result.open_decision_id, "OPEN-OBS-035")

    def test_artifact_exposed_delivery_selects_exact_sli(self):
        row = join_for("rel.artifact-storage@1")
        evidence = product_evidence("artifact_delivery_product_state", "rel.artifact-storage@1", True)
        result = row.resolve_product_applicability(evidence, expected_scope="rel.artifact-storage@1")
        self.assertEqual(result.state, "applicable")
        self.assertEqual(result.sli_profile_ids, ("sli.artifact.delivery@1",))

    def test_stale_wrong_scope_or_wrong_selector_evidence_fails_closed(self):
        row = join_for("rel.artifact-storage@1")
        cases = (
            product_evidence("artifact_delivery_product_state", "rel.artifact-storage@1", True, current=False),
            product_evidence("artifact_delivery_product_state", "rel.other@1", True),
            product_evidence("webhook_product_state", "rel.artifact-storage@1", True),
        )
        for evidence in cases:
            with self.subTest(evidence=evidence), self.assertRaises(ObservationError):
                row.resolve_product_applicability(evidence, expected_scope="rel.artifact-storage@1")

    def test_non_product_gated_join_rejects_selector_resolution(self):
        with self.assertRaises(ObservationError):
            join_for("rel.control-plane-placement@1").resolve_product_applicability(
                product_evidence("webhook_product_state", "rel.control-plane-placement@1", False),
                expected_scope="rel.control-plane-placement@1",
            )


if __name__ == "__main__":
    unittest.main()
