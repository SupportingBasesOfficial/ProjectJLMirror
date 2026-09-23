#!/usr/bin/env python3
from __future__ import annotations
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def run(*args): subprocess.run(args,cwd=ROOT,check=True)
def main():
    run(sys.executable,"-m","unittest","discover","-s","tests/g10","-p","test_*.py")
    c=json.loads((ROOT/"contracts/g10-itsm/incident-v1.json").read_text())
    if c["object_type"]!="incident": raise SystemExit("object drift")
    if c["provider_adapter_contract"]!="itsm_provider_neutral@1": raise SystemExit("adapter drift")
    run(sys.executable,"tools/g10/run_g10_postgres_conformance.py")
    run(sys.executable,"tools/g10/run_g10_container_proof.py")
    print(
        "g10_runtime=PASS domain=PASS worker=PASS read_ui=PASS sql_boundary=PASS "
        "http=PASS postgres=PASS container=PASS"
    )
    return 0
if __name__=="__main__": raise SystemExit(main())
