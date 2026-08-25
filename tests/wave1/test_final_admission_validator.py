from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.validate_final_admission import (  # noqa: E402
    EXPECTED_MANIFEST,
    _manifest_findings,
    validate_source_contract_text,
)

SOURCE = ROOT / "src" / "jlmirror_authority" / "control_plane.py"


class FinalAdmissionValidatorTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text(encoding="utf-8")

    def test_current_source_contract_passes(self):
        self.assertEqual(validate_source_contract_text(self.source), [])

    def test_missing_final_evidence_type_is_rejected(self):
        mutated = self.source.replace(
            "class FinalAdmissionEvidence:",
            "class RemovedFinalAdmissionEvidence:",
            1,
        )
        findings = validate_source_contract_text(mutated)
        self.assertTrue(any("FinalAdmissionEvidence class is missing" in item for item in findings))

    def test_caller_time_or_keyword_drift_at_finalizer_call_is_rejected(self):
        mutated = self.source.replace(
            "authentication_strength_evidence=strength_evidence,",
            "now=strength_evidence,",
            1,
        )
        findings = validate_source_contract_text(mutated)
        self.assertTrue(any("port call keyword contract drift" in item for item in findings))
        self.assertTrue(any("caller/request now reaches" in item for item in findings))

    def test_returning_serial_authorization_instead_of_final_gate_is_rejected(self):
        mutated = self.source.replace(
            "return _finalize_current_admission(\n",
            "return _evaluate_current_authorization(\n",
            1,
        )
        findings = validate_source_contract_text(mutated)
        self.assertTrue(any("serial authorization evaluation" in item for item in findings))
        self.assertTrue(any("final return bypasses" in item for item in findings))

    def test_manifest_cannot_launder_serial_checks_or_caller_time(self):
        for field in (
            "serial_currentness_is_final_authority",
            "caller_supplied_time_is_final_currentness",
            "fallback_to_serial_checks",
            "final_snapshot_is_durable_effect_authority",
        ):
            manifest = deepcopy(EXPECTED_MANIFEST)
            manifest[field] = True
            with self.subTest(field=field):
                self.assertTrue(_manifest_findings(manifest))


if __name__ == "__main__":
    unittest.main(verbosity=2)
