from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]


def run(command:list[str],*,env:dict[str,str]|None=None)->None:
    cp=subprocess.run(command,cwd=ROOT,env=env,check=False)
    if cp.returncode!=0:
        raise SystemExit(cp.returncode)


def main()->int:
    env=dict(os.environ)
    parts=[str(ROOT/"src"),str(ROOT/"apps/g6-monitoring-alerting-transport")]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"]=os.pathsep.join(parts)

    run([
        sys.executable,"-m","unittest","discover",
        "-s",str(ROOT/"tests/g6"),"-p","test_*.py","-v",
    ],env=env)
    run([sys.executable,"tools/async_core/validate_wave2.py"],env=env)
    run(["bash","tools/wave4/run_monitoring_alerting_publication_postgres_conformance.sh"],env=env)
    run([sys.executable,"tools/g6/run_g6_postgres_conformance.py"],env=env)
    run([sys.executable,"tools/g6/run_g6_container_proof.py"],env=env)

    print(
        "g6_monitoring_alerting_transport_runtime=PASS unit=PASS wave2=PASS "
        "publication=PASS consumer_postgres=PASS container=PASS"
    )
    return 0


if __name__=="__main__":
    raise SystemExit(main())
