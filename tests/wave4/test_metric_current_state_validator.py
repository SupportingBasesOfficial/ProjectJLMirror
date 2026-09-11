from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_metric_current_state_validator_passes() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools/wave4/validate_zabbix_metric_current_state.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "wave4_metric_current_state=PASS" in completed.stdout
