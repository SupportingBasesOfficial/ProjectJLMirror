import unittest

from jlmirror_observability import RELIABILITY_OBSERVABILITY_JOINS
from jlmirror_release.model import ArtifactIdentity, DeploymentIntent, ReleaseError, TargetConfiguration, ValidationScope
from jlmirror_release.verification import (
    EmptyReliabilityFloorJustification,
    RuntimeVerificationEvidence,
    RuntimeVerificationRequirements,
    verify_runtime,
)


def intent(runtime_profiles=("runtime.api@1",), worker_specializations=()):
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
        worker_specialization_set=tuple(worker_specializations),
    )


def empty_floor_justification(i, **changes):
    values = dict(
        reason="worker.reconciliation@1 affected-profile bindings are contextual pre-effect requirements",
        authority_profile="release.empty-reliability-floor-authority@1",
        evidence_reference="evidence:empty-reliability-floor-1",
        scope_binding=f"deployment:{i.target_id}:{i.deployment_operation_id}",
        current=True,
    )
    values.update(changes)
    return EmptyReliabilityFloorJustification(**values)


def requirements(i, reliability_ids, *, justification=None):
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
        requirements_principal_class="principal.release-promote@1",
        empty_floor_justification=justification,
    )


def runtime_evidence(i, worker_specializations):
    return RuntimeVerificationEvidence(
        evidence_reference="evidence:runtime-verification-worker-1",
        evidence_current=True,
        scope_binding=f"deployment:{i.target_id}:{i.deployment_operation_id}",
        release_target_state_version=1,
        observed_artifact_identity=i.artifact.canonical,
        observed_configuration_generation=i.configuration.generation,
        runtime_profile_set=i.runtime_profile_set,
        runtime_admission_evidence_reference="evidence:runtime-admission-worker-1",
        runtime_admission_current=True,
        configuration_currentness_evidence_reference="evidence:configuration-currentness-worker-1",
        configuration_current=True,
        release_policy_profile_and_version=i.release_policy_profile_and_version,
        release_policy_evidence_reference="evidence:runtime-release-policy-worker-1",
        release_policy_current=True,
        verifier_authority_profile_and_version="principal.release-verify@1",
        verifier_authority_evidence_reference="evidence:runtime-verifier-worker-1",
        verifier_authority_current=True,
        health_gates=(),
        worker_specialization_set=tuple(worker_specializations),
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

    def test_worker_runtime_requires_exact_specialization(self):
        with self.assertRaises(ReleaseError):
            intent(("runtime.worker@1",))

    def test_worker_specialization_without_worker_runtime_is_rejected(self):
        with self.assertRaises(ReleaseError):
            intent(("runtime.api@1",), ("worker.outbox-publication@1",))

    def test_unknown_or_duplicate_worker_specialization_is_rejected(self):
        for specializations in (
            ("worker.unknown@1",),
            ("worker.outbox-publication@1", "worker.outbox-publication@1"),
        ):
            with self.subTest(specializations=specializations), self.assertRaises(ReleaseError):
                intent(("runtime.worker@1",), specializations)

    def test_outbox_worker_cannot_omit_broker_transport_reliability(self):
        i = intent(("runtime.worker@1",), ("worker.outbox-publication@1",))
        with self.assertRaises(ReleaseError):
            requirements(i, ("rel.outbox-publication@1",)).validate_for(
                i, expected_release_target_state_version=1
            )

    def test_outbox_worker_complete_minimum_is_accepted(self):
        i = intent(("runtime.worker@1",), ("worker.outbox-publication@1",))
        requirements(i, ("rel.outbox-publication@1", "rel.broker-job-transport@1")).validate_for(
            i, expected_release_target_state_version=1
        )

    def test_reconciliation_worker_uses_exact_pre_effect_affected_reliability(self):
        i = intent(("runtime.worker@1",), ("worker.reconciliation@1",))
        # The affected owner/profile is contextual, so Phase 13 does not define one universal
        # reliability ID for reconciliation workers -- runtime.worker@1 and worker.reconciliation@1
        # both carry an empty non-conditional floor, so the requirements record must present an
        # evidence-backed empty-floor justification. The pre-effect requirements record remains
        # the authority and must still contain a non-empty canonical reliability set.
        requirements(
            i, ("rel.replay-consume-state@1",), justification=empty_floor_justification(i)
        ).validate_for(i, expected_release_target_state_version=1)

    def test_reconciliation_worker_empty_floor_requires_justification(self):
        i = intent(("runtime.worker@1",), ("worker.reconciliation@1",))
        with self.assertRaises(ReleaseError):
            requirements(i, ("rel.replay-consume-state@1",)).validate_for(
                i, expected_release_target_state_version=1
            )

    def test_reconciliation_worker_empty_floor_justification_cannot_be_substituted(self):
        i = intent(("runtime.worker@1",), ("worker.reconciliation@1",))
        for value in ("x", "release.runtime-verification-requirements@1", "attacker-authority@1"):
            with self.subTest(value=value), self.assertRaises(ReleaseError):
                requirements(
                    i, ("rel.replay-consume-state@1",),
                    justification=empty_floor_justification(i, authority_profile=value),
                ).validate_for(i, expected_release_target_state_version=1)

    def test_empty_floor_justification_must_be_the_canonical_evidence_type(self):
        # Regression test: dataclass type hints are not runtime-enforced, so without an explicit
        # isinstance check any duck-typed stand-in exposing a no-op validate_for(expected_scope)
        # would satisfy "is not None" and be delegated to, skipping reason/authority_profile/
        # evidence_reference/current/scope checks entirely.
        class ForgedJustification:
            def validate_for(self, expected_scope):
                return None

        i = intent(("runtime.worker@1",), ("worker.reconciliation@1",))
        with self.assertRaises(ReleaseError):
            requirements(
                i, ("rel.replay-consume-state@1",), justification=ForgedJustification()
            ).validate_for(i, expected_release_target_state_version=1)

    def test_non_empty_floor_cannot_also_claim_empty_floor_justification(self):
        i = intent()
        complete = (
            "rel.cell-transactional-store@1",
            "rel.security-session-authority@1",
            "rel.performance-cache@1",
            "rel.configuration-authority@1",
        )
        with self.assertRaises(ReleaseError):
            requirements(i, complete, justification=empty_floor_justification(i)).validate_for(
                i, expected_release_target_state_version=1
            )

    def test_runtime_evidence_cannot_change_worker_specialization(self):
        i = intent(("runtime.worker@1",), ("worker.outbox-publication@1",))
        req = requirements(i, ("rel.outbox-publication@1", "rel.broker-job-transport@1"))
        with self.assertRaisesRegex(ReleaseError, "worker specialization set differs"):
            verify_runtime(
                i,
                runtime_evidence(i, ("worker.async-consumer@1",)),
                req,
                expected_release_target_state_version=1,
            )


if __name__ == "__main__":
    unittest.main()
