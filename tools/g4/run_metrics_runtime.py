from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> int:
    env = dict(os.environ)
    pythonpath = [str(ROOT / "src"), str(ROOT / "apps/g4-metrics")]
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)

    run([
        sys.executable, "-m", "unittest", "discover",
        "-s", str(ROOT / "tests/g4"), "-p", "test_*.py", "-v",
    ], env=env)

    run(["bash", "tools/wave4/run_zabbix_metric_definitions_postgres_conformance.sh"], env=env)
    run(["bash", "tools/wave4/run_zabbix_metric_current_state_postgres_conformance.sh"], env=env)
    run(["bash", "tools/wave4/run_zabbix_metric_history_postgres_conformance.sh"], env=env)
    run([sys.executable, "tools/g4/run_g4_browser_e2e.py"], env=env)
    run([sys.executable, "tools/g4/run_g4_container_proof.py"], env=env)

    print(
        "g4_metrics_runtime=PASS unit=PASS authorization=PASS contracts=PASS "
        "definitions_postgres=PASS current_postgres=PASS history_postgres=PASS "
        "browser_e2e=PASS container=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
