from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.runtime_profiles import (  # noqa: E402
    API_AUTH_BOUNDARY,
    CONTROL_PLANE,
    WEB_BFF,
)
from tools.authority.validate_wave1 import _runtime_semantic_binding_findings  # noqa: E402


class RuntimeSemanticJoinTests(unittest.TestCase):
    def test_exact_accepted_wave1_runtime_joins_pass(self):
        self.assertEqual(
            _runtime_semantic_binding_findings(
                (WEB_BFF, API_AUTH_BOUNDARY, CONTROL_PLANE)
            ),
            [],
        )

    def test_existing_but_wrong_principal_profile_fails(self):
        altered = replace(WEB_BFF, principal_class="principal.control-plane@1")
        findings = _runtime_semantic_binding_findings(
            (altered, API_AUTH_BOUNDARY, CONTROL_PLANE)
        )
        self.assertTrue(any("runtime.web-bff@1" in finding for finding in findings))

    def test_existing_but_wrong_ingress_profile_fails(self):
        altered = replace(
            CONTROL_PLANE,
            ingress_profile="ingress.authenticated-api@1",
        )
        findings = _runtime_semantic_binding_findings(
            (WEB_BFF, API_AUTH_BOUNDARY, altered)
        )
        self.assertTrue(any("runtime.control-plane@1" in finding for finding in findings))

    def test_secret_reference_union_laundering_fails(self):
        altered = replace(
            API_AUTH_BOUNDARY,
            secret_reference_classes=frozenset(
                {
                    "secretref.state-port@1",
                    "secretref.service-communication@1",
                    "secretref.migration-admin@1",
                }
            ),
        )
        findings = _runtime_semantic_binding_findings(
            (WEB_BFF, altered, CONTROL_PLANE)
        )
        self.assertTrue(any("runtime.api@1" in finding for finding in findings))

    def test_missing_or_extra_runtime_binding_fails(self):
        self.assertTrue(
            _runtime_semantic_binding_findings((WEB_BFF, API_AUTH_BOUNDARY))
        )
        duplicated = (WEB_BFF, API_AUTH_BOUNDARY, CONTROL_PLANE, WEB_BFF)
        self.assertTrue(_runtime_semantic_binding_findings(duplicated))


if __name__ == "__main__":
    unittest.main(verbosity=2)
