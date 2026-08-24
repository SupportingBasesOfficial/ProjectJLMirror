from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.control_plane import (  # noqa: E402
    PlacementEvidence,
    RuntimeLifecycle,
    construct_tenant_context,
)
from jlmirror_authority.model import (  # noqa: E402
    AdmissionDenied,
    EnvironmentClass,
    Principal,
    PrincipalKind,
)
from jlmirror_authority.runtime_profiles import API_AUTH_BOUNDARY  # noqa: E402

NOW = datetime(2026, 8, 24, 11, 45, tzinfo=timezone.utc)


class PlacementAuthority:
    def __init__(self, evidence):
        self.evidence = evidence

    def resolve_current(self, tenant_id):
        return self.evidence if tenant_id == self.evidence.tenant_id else None

    def context_is_current(self, context):
        return True


def placement(environment: EnvironmentClass) -> PlacementEvidence:
    return PlacementEvidence(
        tenant_id="tenant-acme",
        cell_id="cell-a",
        placement_version="pv-1",
        runtime_generation="runtime-g1",
        configuration_generation="cfg-g1",
        workload_credential_generation="wc-g1",
        network_policy_generation="np-g1",
        environment_class=environment,
        isolation_class="pooled",
        runtime_lifecycle=RuntimeLifecycle.ACTIVE,
        placement_current=True,
        operation_eligible=True,
        cell_admission_current=True,
        fence_scope_id="tenant:acme",
        fence_epoch=1,
    )


def construct(evidence, **overrides):
    values = dict(
        principal=Principal(
            "user-1", PrincipalKind.HUMAN_BROWSER_SESSION, "session-g1"
        ),
        placement_authority=PlacementAuthority(evidence),
        tenant_id=evidence.tenant_id,
        destination_cell_id=evidence.cell_id,
        destination_runtime_generation=evidence.runtime_generation,
        destination_configuration_generation=evidence.configuration_generation,
        destination_workload_credential_generation=evidence.workload_credential_generation,
        destination_network_policy_generation=evidence.network_policy_generation,
        required_environment=evidence.environment_class,
        now=NOW,
    )
    values.update(overrides)
    return construct_tenant_context(**values)


class TenantRuntimeBindingTests(unittest.TestCase):
    def test_default_api_boundary_rejects_recovery_environment_even_when_placement_matches(self):
        with self.assertRaises(AdmissionDenied):
            construct(placement(EnvironmentClass.RECOVERY))

    def test_destination_environment_must_match_current_placement_evidence(self):
        evidence = placement(EnvironmentClass.PRODUCTION)
        with self.assertRaises(AdmissionDenied):
            construct(evidence, required_environment=EnvironmentClass.VALIDATION)

    def test_altered_runtime_binding_cannot_be_substituted_for_accepted_profile(self):
        evidence = placement(EnvironmentClass.PRODUCTION)
        altered = replace(
            API_AUTH_BOUNDARY,
            allowed_environment_classes=frozenset(
                {
                    EnvironmentClass.DEVELOPMENT,
                    EnvironmentClass.VALIDATION,
                    EnvironmentClass.PRODUCTION,
                    EnvironmentClass.RECOVERY,
                }
            ),
        )
        with self.assertRaises(AdmissionDenied):
            construct(evidence, runtime_binding=altered)

    def test_exact_api_runtime_binding_accepts_current_production_placement(self):
        evidence = placement(EnvironmentClass.PRODUCTION)
        context = construct(evidence, runtime_binding=API_AUTH_BOUNDARY)
        self.assertEqual(context.environment_class, EnvironmentClass.PRODUCTION)
        self.assertEqual(context.runtime_generation, "runtime-g1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
