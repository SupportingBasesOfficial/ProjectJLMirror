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
    run(sys.executable,"-m","unittest","discover","-s","tests/g9","-p","test_*.py")
    contract=json.loads((ROOT/"contracts/g9-notification-delivery/notification-delivery-v1.json").read_text(encoding="utf-8"))
    if contract["channel"]!="whatsapp_business@1":
        raise SystemExit("G9 channel contract drift")
    if contract["max_attempts"]!=3:
        raise SystemExit("G9 retry budget drift")
    if contract["external_read_is_authoritative_native_view"] is not False:
        raise SystemExit("G9 view-authority drift")
    print("g9_runtime=PASS domain=PASS callback=PASS worker=PASS read_ui=PASS pg_port=PASS sql_boundary=PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
