import unittest

from jlmirror_observability import RELIABILITY_OBSERVABILITY_JOINS
from jlmirror_release.model import ArtifactIdentity, DeploymentIntent, ReleaseError, TargetConfiguration, ValidationScope
from jlmirror_release.verification import RuntimeVerificationRequirements


def intent(runtime_profiles=("runtime.api@1",)):
    return DeploymentIntent(
        deployment_operation_id="op-runtime-profile",
        target_id="validation-cell-a",
        expected_release_target_state_version=0,
        artifact=ArtifactIdentity("sha256", "a" * 64),
        configuration=TargetConfiguration("cfg", "g1", "config.release@1"),
        target_environment_class="environment.validation@1",
        runtime_profile_set=tuple(runtime_profiles),
        promotion_id="promotion-runtime-profile",
        release_policy_profile_and_version="release-policy@1",
        validation_scope=ValidationScope.GENERAL,
        rollout_scope="validation-cell-a",
        schema_state="compatible",
        api_compatibility_family="api.v1",
        event_compatibility_set=("event.v1",),
    )


def requirements(i, reliability_ids):
    health_ids = tuple(sorted({
        health_id
        for reliability_id in reliability_ids
        for health_id in RELIABILITY_OBSERVABILITY_JOINS[reliability_id].health_profile_ids
    }))
    return RuntimeVerificationRequirements(
        authority_profile_and_version="release.runtime-verification-requirements@1",
        evidence_reference="evidence:runtime-profile-requirements-1",
        scope_binding=f"deployment:{i.target_id}:{i.deployment_operation_id}",
        release_target_state_version=1,
        release_policy_profile_and_version=i.release_policy_profile_and_version,
        release_policy_evidence_reference="evidence:release-policy-1",
        required_reliability_profile_ids=tuple(reliability_ids),
        required_health_profile_ids=health_ids,
        current=True,
    )


class RuntimeProfileReliabilityTests(unittest.TestCase):
    def test_runtime_api_cannot_omit_configuration_reliability(self):
        i = intent()
        incomplete = (
            "rel.cell-transactional-store@1",
            "rel.security-session-authority@1",
            "rel.performance-cache@1",
        )
        with self.assertRaises(ReleaseError):
            requirements(i, incomplete).validate_for(i, expected_release_target_state_version=1)

    def test_runtime_api_complete_minimum_is_accepted(self):
        i = intent()
        complete = (
            "rel.cell-transactional-store@1",
            "rel.security-session-authority@1",
            "rel.performance-cache@1",
            "rel.configuration-authority@1",
        )
        requirements(i, complete).validate_for(i, expected_release_target_state_version=1)

    def test_control_plane_cannot_omit_placement_cache_reliability(self):
        i = intent(("runtime.control-plane@1",))
        incomplete = (
            "rel.control-plane-placement@1",
            "rel.configuration-authority@1",
        )
        with self.assertRaises(ReleaseError):
            requirements(i, incomplete).validate_for(i, expected_release_target_state_version=1)

    def test_web_bff_does_not_make_conditional_performance_cache_mandatory(self):
        i = intent(("runtime.web-bff@1",))
        requirements(i, ("rel.security-session-authority@1",)).validate_for(
            i, expected_release_target_state_version=1
        )

    def test_unknown_runtime_profile_is_rejected(self):
        with self.assertRaises(ReleaseError):
            intent(("runtime.unknown@1",))

    def test_duplicate_runtime_profile_is_rejected(self):
        with self.assertRaises(ReleaseError):
            intent(("runtime.api@1", "runtime.api@1"))


if __name__ == "__main__":
    unittest.main()
