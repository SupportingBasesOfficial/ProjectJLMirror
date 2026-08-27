import unittest

from jlmirror_release import ReleaseError, verify_runtime
from test_release import intent, runtime_evidence, runtime_requirements


class RuntimeVerifierAuthorityTests(unittest.TestCase):
    def test_deploy_principal_cannot_substitute_for_release_verifier(self):
        i = intent()
        evidence = runtime_evidence(verifier_authority_profile_and_version="principal.release-deploy@1")
        with self.assertRaisesRegex(ReleaseError, "canonical release verifier principal"):
            verify_runtime(
                i,
                evidence,
                runtime_requirements(i),
                expected_release_target_state_version=5,
            )

    def test_arbitrary_profile_cannot_substitute_for_release_verifier(self):
        i = intent()
        evidence = runtime_evidence(verifier_authority_profile_and_version="release.verifier-current@1")
        with self.assertRaisesRegex(ReleaseError, "canonical release verifier principal"):
            verify_runtime(
                i,
                evidence,
                runtime_requirements(i),
                expected_release_target_state_version=5,
            )

    def test_current_health_policy_evidence_may_rotate_without_repinning_pre_effect_gate_set(self):
        i = intent()
        good = runtime_evidence()
        gate = good.health_gates[0]
        rotated_gate = type(gate)(**{
            **gate.__dict__,
            "policy_evidence_reference": "evidence:health-admission-policy-2",
            "policy_current": True,
        })
        evidence = runtime_evidence(health_gates=(rotated_gate,) + good.health_gates[1:])
        verify_runtime(
            i,
            evidence,
            runtime_requirements(i),
            expected_release_target_state_version=5,
        )

    def test_stale_health_policy_evidence_still_fails_closed(self):
        i = intent()
        good = runtime_evidence()
        gate = good.health_gates[0]
        stale_gate = type(gate)(**{**gate.__dict__, "policy_current": False})
        evidence = runtime_evidence(health_gates=(stale_gate,) + good.health_gates[1:])
        with self.assertRaisesRegex(ReleaseError, "owning Phase 12 policy"):
            verify_runtime(
                i,
                evidence,
                runtime_requirements(i),
                expected_release_target_state_version=5,
            )


if __name__ == "__main__":
    unittest.main()
