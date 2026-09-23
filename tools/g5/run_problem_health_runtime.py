from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]


def run(command:list[str],*,env:dict[str,str]|None=None)->None:
    completed=subprocess.run(command,cwd=ROOT,env=env,check=False)
    if completed.returncode!=0:
        raise SystemExit(completed.returncode)


def main()->int:
    env=dict(os.environ)
    pythonpath=[str(ROOT/"src"),str(ROOT/"apps/g5-problem-health")]
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    env["PYTHONPATH"]=os.pathsep.join(pythonpath)

    run([
        sys.executable,"-m","unittest","discover",
        "-s",str(ROOT/"tests/g5"),"-p","test_*.py","-v",
    ],env=env)

    run(["bash","tools/wave4/run_zabbix_problem_state_postgres_conformance.sh"],env=env)
    run(["bash","tools/wave4/run_health_projection_postgres_conformance.sh"],env=env)
    run([sys.executable,"tools/g5/run_g5_browser_e2e.py"],env=env)
    run([sys.executable,"tools/g5/run_g5_container_proof.py"],env=env)

    print(
        "g5_problem_health_runtime=PASS unit=PASS authorization=PASS contracts=PASS "
        "problem_postgres=PASS health_postgres=PASS browser_e2e=PASS container=PASS"
    )
    return 0


if __name__=="__main__":
    raise SystemExit(main())
