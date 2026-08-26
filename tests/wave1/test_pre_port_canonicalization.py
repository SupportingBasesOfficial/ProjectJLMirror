from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.control_plane import construct_tenant_context  # noqa: E402
from jlmirror_authority.model import (  # noqa: E402
    AdmissionDenied,
    EnvironmentClass,
    Principal,
    PrincipalKind,
)

NOW = datetime(2026, 8, 24, 14, 30, tzinfo=timezone.utc)


class PrincipalAuthority:
    def is_current(self, **kwargs):
        return True


class ExplodingPlacementAuthority:
    def __init__(self) -> None:
        self.called = False

    def resolve_current(self, tenant_id):
        self.called = True
        raise AssertionError("malformed lookup input must fail before placement authority")

    def context_is_current(self, context):
        raise AssertionError("not reached")


class PrePortCanonicalizationTests(unittest.TestCase):
    def _call(self, authority, **overrides):
        values = dict(
            principal=Principal(
                "user-1", PrincipalKind.HUMAN_BROWSER_SESSION, "session-g1"
            ),
            principal_authority=PrincipalAuthority(),
            placement_authority=authority,
            tenant_id="tenant-acme",
            destination_cell_id="cell-a",
            destination_runtime_generation="runtime-g1",
            destination_configuration_generation="cfg-g1",
            destination_workload_credential_generation="wc-g1",
            destination_network_policy_generation="np-g1",
            required_environment=EnvironmentClass.PRODUCTION,
            now=NOW,
        )
        values.update(overrides)
        return construct_tenant_context(**values)

    def test_malformed_logical_lookup_inputs_fail_before_c2_adapter(self):
        cases = {
            "tenant_id": " tenant-acme",
            "destination_cell_id": "cell a",
            "destination_runtime_generation": "runtime\ng1",
            "destination_configuration_generation": "cfg g1",
            "destination_workload_credential_generation": "wc\tg1",
            "destination_network_policy_generation": "np g1",
        }
        for field, value in cases.items():
            authority = ExplodingPlacementAuthority()
            with self.subTest(field=field), self.assertRaises(AdmissionDenied):
                self._call(authority, **{field: value})
            self.assertFalse(authority.called)

    def test_oversized_tenant_identifier_fails_before_c2_adapter(self):
        authority = ExplodingPlacementAuthority()
        with self.assertRaises(AdmissionDenied):
            self._call(authority, tenant_id="t" * 257)
        self.assertFalse(authority.called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
