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
    pythonpath = [str(ROOT / "src"), str(ROOT / "apps/g2-monitoring-source-onboarding")]
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)

    run([
        sys.executable, "-m", "unittest", "discover",
        "-s", str(ROOT / "tests/g2"), "-p", "test_*.py", "-v",
    ], env=env)

    run([
        sys.executable, "-m", "unittest", "discover",
        "-s", str(ROOT / "tests" / "wave4"),
        "-p", "test_zabbix_initial_validation_worker.py", "-v",
    ], env=env)

    shared_tool = ROOT / "tools" / "wave4" / "run_zabbix_initial_validation_postgres_conformance.sh"
    run(["bash", str(shared_tool)], env=env)

    run([sys.executable, "tools/g2/run_g2_browser_e2e.py"], env=env)
    run([sys.executable, "tools/g2/run_g2_container_proof.py"], env=env)

    print(
        "g2_monitoring_source_onboarding_runtime=PASS "
        "unit=PASS current_authority=PASS worker=PASS postgres=PASS browser_e2e=PASS container=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
