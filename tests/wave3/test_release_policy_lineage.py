import unittest

from jlmirror_release import (
    DeploymentAuthority,
    DeploymentObservation,
    ReleaseError,
    ReleaseTargetState,
    verify_runtime,
)
from test_release import DIGEST_A, admission, intent, runtime_evidence, runtime_requirements


class ReleasePolicyLineageTests(unittest.TestCase):
    def test_runtime_verification_cannot_rotate_release_policy_lineage_after_gate_set_authorized(self):
        i = intent()
        with self.assertRaisesRegex(ReleaseError, "pre-effect requirements policy lineage"):
            verify_runtime(
                i,
                runtime_evidence(release_policy_evidence_reference="evidence:rotated-release-policy"),
                runtime_requirements(i),
                expected_release_target_state_version=5,
            )

    def test_effectful_deployment_cannot_complete_with_different_runtime_release_policy_lineage(self):
        i = intent()
        authority = DeploymentAuthority(ReleaseTargetState(i.target_id, 4))
        authority.create_or_observe(i, admission(i))
        authority.observe_effect(
            i.deployment_operation_id,
            DeploymentObservation.EFFECT_CONFIRMED,
            observed_artifact_identity=f"sha256:{DIGEST_A}",
            observed_configuration_generation="cfg-7",
            durable_target_evidence_reference="evidence:target-1",
        )
        with self.assertRaisesRegex(ReleaseError, "pre-effect requirements policy lineage"):
            authority.complete_runtime_verification(
                i.deployment_operation_id,
                runtime_evidence(release_policy_evidence_reference="evidence:rotated-release-policy"),
            )


if __name__ == "__main__":
    unittest.main()
