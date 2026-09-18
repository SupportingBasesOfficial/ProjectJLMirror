from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--self-check",action="store_true")
    args=parser.parse_args()
    if not args.self_check:
        raise SystemExit("G7 runtime proof exposes self-check only")

    contract=json.loads((ROOT/"contracts/g7-alert-policy-lifecycle/policy-v1.json").read_text(encoding="utf-8"))
    if contract.get("source_kinds")!=["monitoring_problem","monitoring_health_projection"]:
        raise SystemExit("G7 contract drift")
    if contract.get("lifecycle")!=["active","resolved"] or contract.get("resolved_terminal") is not True:
        raise SystemExit("G7 lifecycle drift")

    from domain import PolicyVersion, SourceState, evaluate

    policy=PolicyVersion(
        tenant_id="self-check",policy_id="problem",policy_version=1,
        source_kind="monitoring_problem",content_hash="self-check-v1",
        problem_min_severity="warning",
    )
    state=SourceState(
        tenant_id="self-check",source_kind="monitoring_problem",
        source_subject_id="problem-1",monitoring_source_id="source-1",
        monitoring_resource_id="resource-1",
        source_instance_generation="generation-1",
        active_source_instance_generation="generation-1",
        source_evidence_state="current",projection_evidence_state="current",
        projection_revision=1,problem_state="active",severity_class="critical",
    )
    decision=evaluate(policy,state,None,policy_is_effective=True)
    if decision.action!="create" or not decision.alert_id:
        raise SystemExit("G7 evaluation self-check failed")
    print("g7_worker_boot=PASS policy=PASS currentness=PASS lifecycle=PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
