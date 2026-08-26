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


if __name__ == "__main__":
    unittest.main()
