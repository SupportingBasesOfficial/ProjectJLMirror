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
REQUIRED=[
EXPECTED_ID,
"tenant_and_contract_scoped_producer_consumer_authorization",
"message_protection_key_authority_and_historical_verifier_continuity",
"secret_credential_payload_exclusion_and_erasure_boundary",
"trace_context_observability_only_validation_and_redaction",
]

def validate(root:Path)->list[str]:
    errors=[]
    m=json.loads((root/MANIFEST).read_text())
    state=json.loads((root/STATE).read_text())
    plan=json.loads((root/PLAN).read_text())
    if m.get("evidence_id")!=EXPECTED_ID or m.get("source_decision")!=EXPECTED_DECISION: errors.append("wrong source evidence identity")
    if set(m.get("must_prove",[]))!=EXPECTED_MUST: errors.append("must_prove drift")
    if m.get("current_run_auto_credit") is not False or m.get("ledger_credit")!=[]: errors.append("source evidence must remain non-promoting at source time")
    if m.get("candidate") is not None or m.get("candidate_status")!="not_selected" or m.get("selection_authority")!="not_granted": errors.append("source evidence must not select D4-D")
    if m.get("canonical_identity_authority")!="IR-D-002": errors.append("IR-D-002 authority must remain canonical")
    source_time=m.get("source_time_state",{})
    if source_time.get("d4d")!="0_of_5_unselected" or source_time.get("d4wide")!="21_of_26": errors.append("source-time snapshot must remain 0/5 and 21/26")
    axis=plan["axes"]["workload_identity_to_broker_credential_adapter"]
    if set(axis["must_prove"])!=EXPECTED_MUST: errors.append("candidate-plan/source must_prove mismatch")
    tracks={t["track_id"]:t for t in state["tracks"]}
    d4d=tracks["D4-D"]
    if d4d["candidate"] is not None or d4d["candidate_status"]!="not_selected" or d4d.get("state")!="candidate_selection_open": errors.append("D4-D state must remain open/unselected")
    if d4d.get("required_evidence")!=REQUIRED or d4d.get("evidence_completed")!=[EXPECTED_ID] or d4d.get("evidence_remaining")!=REQUIRED[1:]: errors.append("current D4-D state must reflect exactly the separate first promotion")
    if sum(len(t["evidence_completed"]) for t in state["tracks"])!=22: errors.append("D4-wide current state must be 22/26")
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
    print("d4d_workload_identity_source=PASS source_snapshot=0_of_5 source_auto_credit=false current_d4d=1_of_5 d4wide=22/26 selection=not_selected authorities=unchanged")
