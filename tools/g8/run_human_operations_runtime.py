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
    if contract["unacknowledge_authorized"] is not False:
        raise SystemExit("G8 ACK authority drift")
    print("g8_runtime=PASS domain=PASS read_ui=PASS pg_port=PASS sql_boundary=PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
