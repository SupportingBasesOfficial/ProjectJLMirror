from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class MetricHistoryAuthorizationTests(unittest.TestCase):
    def test_metric_history_authorization_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools/wave4/validate_metric_history_authorization.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("wave4_metric_history_authorization=PASS", completed.stdout)


if __name__ == "__main__":
    unittest.main()
