#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
from d4d_workload_identity_source import run_probes

MANIFEST=Path("implementation/d4-eventing-async/source-evidence/d4-d-workload-identity/source-evidence-manifest.json")
STATE=Path("implementation/d4-eventing-async/state-manifest.json")
PLAN=Path("implementation/d4-eventing-async/d4-d-candidate-evaluation-plan.json")

EXPECTED_ID="workload_identity_to_broker_credential_adapter_least_privilege"
EXPECTED_DECISION="OPEN-EVT-016"
EXPECTED_MUST={
"canonical_internal_workload_identity_is_authenticated_before_broker_credential_derivation",
"adapter_consumes_ir_d_002_canonical_workload_identity_without_reopening_issuer_or_attestation_authority",
"broker_credential_is_derived_and_replaceable_not_platform_identity_authority",
"credential_scope_is_least_privilege_and_bound_to_service_environment_and_broker_role",
"internal_network_or_broker_presence_alone_never_establishes_trust",
"credential_rotation_or_replacement_does_not_change_canonical_workload_identity",
"stale_or_revoked_workload_identity_cannot_mint_or_retain_current_broker_authority",
"credential_material_is_not_embedded_in_ordinary_messages_logs_or_quarantine_records",
}

def validate(root:Path)->list[str]:
    errors=[]
    m=json.loads((root/MANIFEST).read_text())
    state=json.loads((root/STATE).read_text())
    plan=json.loads((root/PLAN).read_text())
    if m.get("evidence_id")!=EXPECTED_ID or m.get("source_decision")!=EXPECTED_DECISION: errors.append("wrong source evidence identity")
    if set(m.get("must_prove",[]))!=EXPECTED_MUST: errors.append("must_prove drift")
    if m.get("current_run_auto_credit") is not False or m.get("ledger_credit")!=[]: errors.append("source evidence must not auto-credit")
    if m.get("candidate") is not None or m.get("candidate_status")!="not_selected" or m.get("selection_authority")!="not_granted": errors.append("source evidence must not select D4-D")
    if m.get("canonical_identity_authority")!="IR-D-002": errors.append("IR-D-002 authority must remain canonical")
    axis=plan["axes"]["workload_identity_to_broker_credential_adapter"]
    if set(axis["must_prove"])!=EXPECTED_MUST: errors.append("candidate-plan/source must_prove mismatch")
    tracks={t["track_id"]:t for t in state["tracks"]}
    d4d=tracks["D4-D"]
    if d4d["candidate"] is not None or d4d["candidate_status"]!="not_selected" or d4d["evidence_completed"]!=[]: errors.append("D4-D state must remain 0/5 unselected")
    if sum(len(t["evidence_completed"]) for t in state["tracks"])!=21: errors.append("D4-wide must remain 21/26")
    if state["gate_state"]!="scoped" or state["d4_transport_authority"]!="selected_not_granted" or state["canonical_product_implementation_authority"]!="not_granted" or state["wave4_implementation_authority"]!="not_granted" or state["production_authority"]!="none" or state["c3_numeric_topology_authority"]!="not_selected": errors.append("authority leakage")
    checks=run_probes()
    bad=[k for k,v in checks.items() if not v]
    if bad: errors.append("behavior probes failed: "+",".join(bad))
    return errors

if __name__=="__main__":
    root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd()
    errors=validate(root)
    if errors:
        for e in errors: print("D4D_SOURCE_ERROR:",e,file=sys.stderr)
        raise SystemExit(1)
    print("d4d_workload_identity_source=PASS source_auto_credit=false d4d=0_of_5 d4wide=21/26 selection=not_selected authorities=unchanged")
