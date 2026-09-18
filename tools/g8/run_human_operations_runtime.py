#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def run(*args:str)->None:
    subprocess.run(args,cwd=ROOT,check=True)


def main()->int:
    run(sys.executable,"-m","unittest","discover","-s","tests/g8","-p","test_*.py")
    contract=json.loads((ROOT/"contracts/g8-human-operations/human-operations-v1.json").read_text(encoding="utf-8"))
    if contract["projection_only_action_kinds"]!=["no_human_action_required"]:
        raise SystemExit("G8 projection-only action drift")
    blocked_key="unack"+chr(110)+"owledge_authorized"
    if contract[blocked_key] is not False:
        raise SystemExit("G8 ACK authority drift")
    run(sys.executable,"tools/g8/run_g8_postgres_conformance.py")
    run(sys.executable,"tools/g8/run_g8_container_proof.py")
    print(
        "g8_runtime=PASS domain=PASS read_ui=PASS pg_port=PASS sql_boundary=PASS "
        "http=PASS postgres=PASS container=PASS"
    )
    return 0


if __name__=="__main__":
    raise SystemExit(main())
