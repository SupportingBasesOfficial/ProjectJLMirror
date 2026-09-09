#!/usr/bin/env python3
from __future__ import annotations
import json,subprocess,sys,tempfile
from pathlib import Path
import validate_d4d_trace_context_source as v
import validate_d4d_evidence_plan as ledger
ROOT=Path(__file__).resolve().parents[2]
CURRENT_D4B_ADAPTERS=(
    Path('tools/assurance/d4b_catalog_tooling/validate_source_evidence.py'),
    Path('tools/assurance/d4b_contract_version/validate_source_evidence.py'),
    Path('tools/assurance/d4b_wire_schema/validate_source_evidence.py'),
)
D4D_CURRENT_IDS=(
    'workload_identity_to_broker_credential_adapter_least_privilege',
    'tenant_and_contract_scoped_producer_consumer_authorization',
    'message_protection_key_authority_and_historical_verifier_continuity',
    'secret_credential_payload_exclusion_and_erasure_boundary',
    'trace_context_observability_only_validation_and_redaction',
)
def clone(tmp):
    paths=[v.MANIFEST,v.STATE,v.PLAN,ledger.PLAN,ledger.P1,ledger.P2,ledger.P3,ledger.P4,ledger.P5,ledger.S1,ledger.S2,ledger.S3,ledger.S4,ledger.S5,*CURRENT_D4B_ADAPTERS]
    for p in dict.fromkeys(paths):
        dst=tmp/p; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_text((ROOT/p).read_text())
def mutate_json(root,path,fn):
    p=root/path; d=json.loads(p.read_text()); fn(d); p.write_text(json.dumps(d))
def mutate_text(root,path,old,new):
    p=root/path; text=p.read_text(); assert old in text,f'mutation marker missing: {path}: {old}'; p.write_text(text.replace(old,new,1))
def mutate_and_expect_failure(mutator,validator=v.validate):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); clone(root); mutator(root); assert validator(root),'mutation unexpectedly accepted'
def current_projection_adapter_errors(root,execute=False):
    errors=[]
    assurance=root/'tools/assurance'
    discovered={p.relative_to(root) for p in assurance.glob('d4b_*/validate_source_evidence.py') if 'validate_source_evidence_historical_current' in p.read_text()}
    expected=set(CURRENT_D4B_ADAPTERS)
    if discovered!=expected:
        errors.append('D4-B current projection adapter inventory drift: expected='+','.join(map(str,sorted(expected)))+' discovered='+','.join(map(str,sorted(discovered))))
    for rel in CURRENT_D4B_ADAPTERS:
        path=root/rel
        if not path.is_file():
            errors.append(f'missing D4-B current projection adapter: {rel}')
            continue
        text=path.read_text()
        if 'D4D_CREDITS = [' not in text: errors.append(f'{rel}: current D4-D credit set is not explicit')
        for evidence_id in D4D_CURRENT_IDS:
            if evidence_id not in text: errors.append(f'{rel}: missing current D4-D evidence id {evidence_id}')
        if 'd4d.get("evidence_completed") != D4D_CREDITS' not in text or 'd4d.get("evidence_remaining") != []' not in text:
            errors.append(f'{rel}: current D4-D projection is not exact 5/5')
        if '!= 26' not in text or 'D4-wide current state must be 26/26' not in text:
            errors.append(f'{rel}: current D4-wide projection is not exact 26/26')
        if 'current state must be exactly 1/5' in text or 'current state must be 22/26' in text:
            errors.append(f'{rel}: stale current-state projection remains')
        if execute:
            completed=subprocess.run([sys.executable,str(path),str(root)],cwd=root,text=True,capture_output=True,check=False)
            if completed.returncode!=0:
                errors.append(f'{rel}: direct current projection entrypoint failed: '+(completed.stderr.strip() or completed.stdout.strip() or f'exit={completed.returncode}'))
    return errors
def falsify_immutable_identity_envelope():
    for field,bad in [('schema_version',2),('gate_id','D3'),('track_id','D4-C'),('source_decision','OPEN-EVT-017'),('evidence_id','wrong-evidence'),('mode','promotion'),('source_base','0'*40)]:
        mutate_and_expect_failure(lambda r,field=field,bad=bad:mutate_json(r,v.MANIFEST,lambda d,field=field,bad=bad:d.__setitem__(field,bad)))
def falsify_source_time_state_exactness():
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d['source_time_state'].__setitem__('d4d','5_of_5_unselected')))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d['source_time_state'].__setitem__('d4wide','26_of_26')))
    for field,bad in [('d4_transport_authority','granted'),('canonical_product_implementation_authority','granted'),('wave4_implementation_authority','granted'),('production_authority','granted'),('c3_numeric_topology_authority','selected')]:
        mutate_and_expect_failure(lambda r,field=field,bad=bad:mutate_json(r,v.MANIFEST,lambda d,field=field,bad=bad:d['source_time_state'].__setitem__(field,bad)))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d['source_time_state'].__setitem__('unexpected_authority','granted')))
def falsify_promotion_separation_flags():
    for promotion_path,flag in (
        (ledger.P1,'separate_selection_required'),(ledger.P1,'separate_d4_acceptance_required'),
        (ledger.P2,'separate_selection_required'),(ledger.P2,'separate_d4_acceptance_required'),
        (ledger.P3,'separate_selection_required'),(ledger.P3,'separate_d4_acceptance_required'),
        (ledger.P4,'separate_selection_required'),(ledger.P4,'separate_d4_acceptance_required'),
        (ledger.P5,'separate_selection_required'),(ledger.P5,'separate_d4_acceptance_required'),
    ):
        mutate_and_expect_failure(
            lambda r,promotion_path=promotion_path,flag=flag:mutate_json(r,promotion_path,lambda d,flag=flag:d.__setitem__(flag,False)),
            validator=ledger.validate,
        )
def falsify_promotion_identity_envelopes():
    for promotion_path in (ledger.P1,ledger.P2,ledger.P3,ledger.P4,ledger.P5):
        for field,bad in (('schema_version',2),('gate_id','D3'),('track_id','D4-C'),('promotion_id','wrong-promotion')):
            mutate_and_expect_failure(
                lambda r,promotion_path=promotion_path,field=field,bad=bad:mutate_json(r,promotion_path,lambda d,field=field,bad=bad:d.__setitem__(field,bad)),
                validator=ledger.validate,
            )
        mutate_and_expect_failure(
            lambda r,promotion_path=promotion_path:mutate_json(r,promotion_path,lambda d:d['source_review'].__setitem__('review_mode','unbound-review-mode')),
            validator=ledger.validate,
        )
        mutate_and_expect_failure(
            lambda r,promotion_path=promotion_path:mutate_json(r,promotion_path,lambda d:d['source_review'].__setitem__('review_id',-1)),
            validator=ledger.validate,
        )
        mutate_and_expect_failure(
            lambda r,promotion_path=promotion_path:mutate_json(r,promotion_path,lambda d:d['source_workflow'].__setitem__('run_id',-1)),
            validator=ledger.validate,
        )
        mutate_and_expect_failure(
            lambda r,promotion_path=promotion_path:mutate_json(r,promotion_path,lambda d:d['source_manifest'].__setitem__('sha256','0'*64)),
            validator=ledger.validate,
        )
def falsify_promotion_unknown_fields():
    for promotion_path,field,bad in (
        (ledger.P1,'acceptance_state','accepted'),(ledger.P1,'implementation_authority','granted'),(ledger.P1,'production_ready',True),(ledger.P1,'candidate_selected',True),
        (ledger.P2,'acceptance_state','accepted'),(ledger.P2,'implementation_authority','granted'),(ledger.P2,'production_ready',True),(ledger.P2,'candidate_selected',True),
        (ledger.P3,'acceptance_state','accepted'),(ledger.P3,'implementation_authority','granted'),(ledger.P3,'production_ready',True),(ledger.P3,'candidate_selected',True),
        (ledger.P4,'acceptance_state','accepted'),(ledger.P4,'implementation_authority','granted'),(ledger.P4,'production_ready',True),(ledger.P4,'candidate_selected',True),
        (ledger.P5,'acceptance_state','accepted'),(ledger.P5,'implementation_authority','granted'),(ledger.P5,'production_ready',True),(ledger.P5,'candidate_selected',True),
    ):
        mutate_and_expect_failure(
            lambda r,promotion_path=promotion_path,field=field,bad=bad:mutate_json(r,promotion_path,lambda d,field=field,bad=bad:d.__setitem__(field,bad)),
            validator=ledger.validate,
        )
def falsify_current_projection_adapters():
    for adapter,old,new in (
        (CURRENT_D4B_ADAPTERS[0],'d4d.get("evidence_completed") != D4D_CREDITS','d4d.get("evidence_completed") != [D4D_CREDITS[0]]'),
        (CURRENT_D4B_ADAPTERS[1],'d4d.get("evidence_completed") != D4D_CREDITS','d4d.get("evidence_completed") != [D4D_CREDITS[0]]'),
        (CURRENT_D4B_ADAPTERS[2],'d4d.get("evidence_completed") != D4D_CREDITS','d4d.get("evidence_completed") != [D4D_CREDITS[0]]'),
        (CURRENT_D4B_ADAPTERS[0],'!= 26','!= 22'),
        (CURRENT_D4B_ADAPTERS[1],'!= 26','!= 22'),
        (CURRENT_D4B_ADAPTERS[2],'!= 26','!= 22'),
    ):
        mutate_and_expect_failure(
            lambda r,adapter=adapter,old=old,new=new:mutate_text(r,adapter,old,new),
            validator=lambda root:current_projection_adapter_errors(root,execute=False),
        )
def main():
    assert not v.validate(ROOT)
    assert not current_projection_adapter_errors(ROOT,execute=True)
    falsify_immutable_identity_envelope()
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('current_run_auto_credit',True)))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('ledger_credit',[v.EXPECTED_ID])))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('trace_context_authority','tenant_authority')))
    falsify_source_time_state_exactness()
    mutate_and_expect_failure(lambda r:mutate_json(r,v.PLAN,lambda d:d['axes'][v.EXPECTED_ID]['must_prove'].pop()))
    def regress_fifth(r):
        def fn(d):
            t=next(t for t in d['tracks'] if t['track_id']=='D4-D'); t['evidence_completed'].remove(v.EXPECTED_ID); t['evidence_remaining']=[v.EXPECTED_ID]
        mutate_json(r,v.STATE,fn)
    mutate_and_expect_failure(regress_fifth)
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:(d.__setitem__('candidate',{'kind':'trace_profile'}),d.__setitem__('candidate_status','selected'))))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('selection_authority','granted')))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.STATE,lambda d:d.__setitem__('canonical_product_implementation_authority','granted')))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.STATE,lambda d:d.__setitem__('production_authority','granted')))
    falsify_promotion_separation_flags()
    falsify_promotion_identity_envelopes()
    falsify_promotion_unknown_fields()
    falsify_current_projection_adapters()
    print('d4d_trace_context_source_falsification=PASS source_identity=exact source_snapshot=4_of_5_25_of_26_exact current_state=5_of_5_26_of_26 authorities_exact promotion_separation=bound promotion_identity=P1-P5-closed-complete-envelope-bound unknown_promotion_fields=blocked current_projection_adapters=inventory+direct-execution+regression-blocked auto_credit=blocked selection=blocked authority_leakage=blocked')
if __name__=='__main__': main()
