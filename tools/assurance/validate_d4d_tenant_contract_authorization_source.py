#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
from d4d_tenant_contract_authorization_source import run_probes
MANIFEST=Path('implementation/d4-eventing-async/source-evidence/d4-d-tenant-contract-authorization/source-evidence-manifest.json'); STATE=Path('implementation/d4-eventing-async/state-manifest.json'); PLAN=Path('implementation/d4-eventing-async/d4-d-candidate-evaluation-plan.json')
EXPECTED_ID='tenant_and_contract_scoped_producer_consumer_authorization'; THIRD='message_protection_key_authority_and_historical_verifier_continuity'; EXPECTED_DECISION='OPEN-EVT-016'; EXPECTED_AXIS=EXPECTED_ID; FIRST='workload_identity_to_broker_credential_adapter_least_privilege'
EXPECTED_MUST={'producer_authorization_is_contract_scoped_and_least_privilege','consumer_authorization_is_service_domain_and_tenant_constrained','broker_acl_or_policy_identity_does_not_replace_platform_tenant_authority','cross_tenant_produce_and_consume_attempts_fail_closed','authorization_revocation_or_generation_change_blocks_stale_broker_access','wildcard_or_broad_broker_permissions_cannot_bypass_contract_scope','authorization_projection_is_reconcilable_from_current_platform_authority'}
REQUIRED=[FIRST,EXPECTED_ID,THIRD,'secret_credential_payload_exclusion_and_erasure_boundary','trace_context_observability_only_validation_and_redaction']
def validate(root):
 e=[]; m=json.loads((root/MANIFEST).read_text()); state=json.loads((root/STATE).read_text()); plan=json.loads((root/PLAN).read_text())
 if m.get('evidence_id')!=EXPECTED_ID or m.get('source_decision')!=EXPECTED_DECISION:e.append('wrong source evidence identity')
 if set(m.get('must_prove',[]))!=EXPECTED_MUST:e.append('must_prove drift')
 if m.get('broker_authorization_authority')!='projection_of_current_platform_authority':e.append('broker authorization must remain a projection of current platform authority')
 if m.get('current_run_auto_credit') is not False or m.get('ledger_credit')!=[]:e.append('source evidence must remain non-promoting at source time')
 if m.get('candidate') is not None or m.get('candidate_status')!='not_selected' or m.get('selection_authority')!='not_granted':e.append('source evidence must not select D4-D')
 st=m.get('source_time_state',{})
 if st.get('d4d')!='1_of_5_unselected' or st.get('d4wide')!='22_of_26':e.append('source-time snapshot must remain 1/5 and 22/26')
 axis=plan['axes'][EXPECTED_AXIS]
 if axis.get('decision')!=EXPECTED_DECISION or set(axis.get('must_prove',[]))!=EXPECTED_MUST:e.append('candidate-plan/source must_prove mismatch')
 tracks={t['track_id']:t for t in state['tracks']}; d=tracks['D4-D']
 if d.get('candidate') is not None or d.get('candidate_status')!='not_selected' or d.get('state')!='candidate_selection_open':e.append('D4-D state must remain open/unselected')
 if d.get('required_evidence')!=REQUIRED or d.get('evidence_completed')!=[FIRST,EXPECTED_ID,THIRD] or d.get('evidence_remaining')!=REQUIRED[3:]:e.append('current D4-D state must reflect exactly the separate third promotion')
 if sum(len(t['evidence_completed']) for t in state['tracks'])!=24:e.append('D4-wide current state must be 24/26')
 if state.get('gate_state')!='scoped' or state.get('d4_transport_authority')!='selected_not_granted' or state.get('canonical_product_implementation_authority')!='not_granted' or state.get('wave4_implementation_authority')!='not_granted' or state.get('production_authority')!='none' or state.get('c3_numeric_topology_authority')!='not_selected':e.append('authority leakage')
 bad=[k for k,v in run_probes().items() if not v]
 if bad:e.append('behavior probes failed: '+','.join(bad))
 return e
if __name__=='__main__':
 root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd(); errors=validate(root); [print('D4D_AUTH_SOURCE_ERROR:',x,file=sys.stderr) for x in errors]
 if errors:raise SystemExit(1)
 print('d4d_tenant_contract_authorization_source=PASS source_snapshot=1_of_5 source_auto_credit=false current_d4d=3_of_5 d4wide=24/26 selection=not_selected authorities=unchanged')
