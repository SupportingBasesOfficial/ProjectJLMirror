#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
from d4d_workload_identity_source import run_probes
MANIFEST=Path('implementation/d4-eventing-async/source-evidence/d4-d-workload-identity/source-evidence-manifest.json'); STATE=Path('implementation/d4-eventing-async/state-manifest.json'); PLAN=Path('implementation/d4-eventing-async/d4-d-candidate-evaluation-plan.json')
EXPECTED_ID='workload_identity_to_broker_credential_adapter_least_privilege'; SECOND='tenant_and_contract_scoped_producer_consumer_authorization'; THIRD='message_protection_key_authority_and_historical_verifier_continuity'; FOURTH='secret_credential_payload_exclusion_and_erasure_boundary'; EXPECTED_DECISION='OPEN-EVT-016'
EXPECTED_MUST={'canonical_internal_workload_identity_is_authenticated_before_broker_credential_derivation','adapter_consumes_ir_d_002_canonical_workload_identity_without_reopening_issuer_or_attestation_authority','broker_credential_is_derived_and_replaceable_not_platform_identity_authority','credential_scope_is_least_privilege_and_bound_to_service_environment_and_broker_role','internal_network_or_broker_presence_alone_never_establishes_trust','credential_rotation_or_replacement_does_not_change_canonical_workload_identity','stale_or_revoked_workload_identity_cannot_mint_or_retain_current_broker_authority','credential_material_is_not_embedded_in_ordinary_messages_logs_or_quarantine_records'}
REQUIRED=[EXPECTED_ID,SECOND,THIRD,FOURTH,'trace_context_observability_only_validation_and_redaction']; CURRENT_CREDITS=list(REQUIRED)
def validate(root):
 e=[]; m=json.loads((root/MANIFEST).read_text()); state=json.loads((root/STATE).read_text()); plan=json.loads((root/PLAN).read_text())
 if m.get('evidence_id')!=EXPECTED_ID or m.get('source_decision')!=EXPECTED_DECISION:e.append('wrong source evidence identity')
 if set(m.get('must_prove',[]))!=EXPECTED_MUST:e.append('must_prove drift')
 if m.get('current_run_auto_credit') is not False or m.get('ledger_credit')!=[]:e.append('source evidence must remain non-promoting at source time')
 if m.get('candidate') is not None or m.get('candidate_status')!='not_selected' or m.get('selection_authority')!='not_granted':e.append('source evidence must not select D4-D')
 if m.get('canonical_identity_authority')!='IR-D-002':e.append('IR-D-002 authority must remain canonical')
 st=m.get('source_time_state',{})
 if st.get('d4d')!='0_of_5_unselected' or st.get('d4wide')!='21_of_26':e.append('source-time snapshot must remain 0/5 and 21/26')
 if set(plan['axes']['workload_identity_to_broker_credential_adapter']['must_prove'])!=EXPECTED_MUST:e.append('candidate-plan/source must_prove mismatch')
 tracks={t['track_id']:t for t in state['tracks']}; d=tracks['D4-D']
 if d.get('candidate') is not None or d.get('candidate_status')!='not_selected' or d.get('state')!='candidate_selection_open':e.append('D4-D state must remain open/unselected')
 if d.get('required_evidence')!=REQUIRED or d.get('evidence_completed')!=CURRENT_CREDITS or d.get('evidence_remaining')!=[]:e.append('current D4-D state must reflect exactly five separate promotions')
 if sum(len(t['evidence_completed']) for t in state['tracks'])!=26:e.append('D4-wide current state must be 26/26')
 if state.get('gate_state')!='scoped' or state.get('d4_transport_authority')!='selected_not_granted' or state.get('canonical_product_implementation_authority')!='not_granted' or state.get('wave4_implementation_authority')!='not_granted' or state.get('production_authority')!='none' or state.get('c3_numeric_topology_authority')!='not_selected':e.append('authority leakage')
 bad=[k for k,v in run_probes().items() if not v]
 if bad:e.append('behavior probes failed: '+','.join(bad))
 return e
if __name__=='__main__':
 root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd(); errors=validate(root); [print('D4D_SOURCE_ERROR:',x,file=sys.stderr) for x in errors]
 if errors:raise SystemExit(1)
 print('d4d_workload_identity_source=PASS source_snapshot=0_of_5 current_d4d=5_of_5 d4wide=26/26 selection=not_selected authorities=unchanged')
