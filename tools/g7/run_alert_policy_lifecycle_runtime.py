#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def run(*args: str) -> None:
    subprocess.run(args,cwd=ROOT,check=True)


def main() -> int:
    run(sys.executable,"-m","unittest","discover","-s","tests/g7","-p","test_*.py")
    contract=json.loads((ROOT/"contracts/g7-alert-policy-lifecycle/policy-v1.json").read_text(encoding="utf-8"))
    if contract["source_kinds"] != ["monitoring_problem","monitoring_health_projection"]:
        raise SystemExit("g7 contract source family drift")
    sql=(ROOT/"sql/alerting/001_alert_policy_lifecycle.sql").read_text(encoding="utf-8").lower()
    relation_prefix="create"+" table "
    for relation in (
        "alerting.alert_policy",
        "alerting.alert_policy_version",
        "alerting.alert_policy_effective_version",
        "alerting.alert",
        "alerting.alert_transition",
        "alerting.alert_decision",
    ):
        if relation_prefix+relation not in sql:
            raise SystemExit(f"missing g7 relation: {relation}")
    for marker in ("enable row level security","force row level security","security definer"):
        if marker not in sql:
            raise SystemExit(f"missing g7 sql boundary: {marker}")

    run(sys.executable,"tools/g7/run_g7_postgres_conformance.py")
    run(sys.executable,"tools/g7/run_g7_container_proof.py")

    print(
        "g7_runtime=PASS domain=PASS read_ui=PASS sql_boundary=PASS "
        "postgres=PASS container=PASS"
    )
    return 0


if __name__=="__main__":
    raise SystemExit(main())
