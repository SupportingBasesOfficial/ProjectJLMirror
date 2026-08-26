import unittest

from jlmirror_observability import HealthState, ObservabilityPipelineEvidence


class ObservabilityPipelineTests(unittest.TestCase):
    def test_complete_current_pipeline_can_be_healthy_evidence(self):
        assessment = ObservabilityPipelineEvidence(True, True, True, True, True).assess()
        self.assertEqual(assessment.state, HealthState.HEALTHY)
        self.assertTrue(assessment.evidence_complete)
        self.assertFalse(assessment.grants_authority)

    def test_missing_pipeline_evidence_is_unknown_not_green(self):
        assessment = ObservabilityPipelineEvidence(None, True, True, True, True).assess()
        self.assertEqual(assessment.state, HealthState.UNKNOWN)
        self.assertFalse(assessment.evidence_complete)

    def test_missing_self_observation_confidence_is_unknown(self):
        assessment = ObservabilityPipelineEvidence(True, True, True, False, True).assess()
        self.assertEqual(assessment.state, HealthState.UNKNOWN)

    def test_known_component_failure_is_degraded(self):
        assessment = ObservabilityPipelineEvidence(True, False, True, True, True).assess()
        self.assertEqual(assessment.state, HealthState.DEGRADED)
        self.assertTrue(assessment.evidence_complete)


if __name__ == "__main__":
    unittest.main()
