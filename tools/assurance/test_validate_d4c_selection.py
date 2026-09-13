#!/usr/bin/env python3
from __future__ import annotations
import copy,shutil,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'tools'/'assurance'))
import validate_d4c_selection as validator
import validate_ai_e2e_delivery as delivery_validator
def baseline(): return [validator.load(ROOT,p) for p in (validator.SELECTION,validator.LEDGER,validator.STATE,validator.EVALUATION)]
def must_fail(mutator,fragment):
 values=[copy.deepcopy(x) for x in baseline()]; mutator(*values); errors=validator.validate_records(*values)
 if not any(fragment in x for x in errors): raise AssertionError(f'expected failure containing {fragment!r}, got {errors!r}')
def falsify_selection_record_product_authority():
 def grant_product(selection,ledger,state,evaluation): selection['canonical_product_implementation_authority']='granted'
 must_fail(grant_product,'Product authority escalation')
def _delivery_clone(root: Path) -> None:
 for rel in (Path('docs/00-foundation/ai-e2e-delivery'),Path('implementation/e2e-delivery')):
  shutil.copytree(ROOT/rel,root/rel)
def _delivery_must_fail(mutator,fragment):
 with tempfile.TemporaryDirectory() as td:
  root=Path(td); _delivery_clone(root); mutator(root)
  try: delivery_validator.validate(root)
  except AssertionError as exc:
   if fragment not in str(exc): raise AssertionError(f'expected delivery failure containing {fragment!r}, got {exc!r}')
  else: raise AssertionError(f'delivery mutation unexpectedly accepted: {fragment}')
def falsify_ai_e2e_delivery_heading_binding():
 def mutate_doc(root,rel,old,new):
  path=root/rel; text=path.read_text(encoding='utf-8'); path.write_text(text.replace(old,new,1),encoding='utf-8')
 def remove_g2(root): mutate_doc(root,Path('docs/00-foundation/ai-e2e-delivery/PRODUCT-EXECUTION-ROADMAP.md'),'### G2 — Monitoring source onboarding golden path','### renamed monitoring source section')
 _delivery_must_fail(remove_g2,'roadmap_heading_missing:G2 — Monitoring source onboarding golden path')
 def demote_g2(root): mutate_doc(root,Path('docs/00-foundation/ai-e2e-delivery/PRODUCT-EXECUTION-ROADMAP.md'),'### G2 — Monitoring source onboarding golden path','#### G2 — Monitoring source onboarding golden path')
 _delivery_must_fail(demote_g2,'roadmap_heading_missing:G2 — Monitoring source onboarding golden path')
 def fence_g2(root): mutate_doc(root,Path('docs/00-foundation/ai-e2e-delivery/PRODUCT-EXECUTION-ROADMAP.md'),'### G2 — Monitoring source onboarding golden path','```text\n### G2 — Monitoring source onboarding golden path\n```')
 _delivery_must_fail(fence_g2,'roadmap_heading_missing:G2 — Monitoring source onboarding golden path')
 def comment_g2(root): mutate_doc(root,Path('docs/00-foundation/ai-e2e-delivery/PRODUCT-EXECUTION-ROADMAP.md'),'### G2 — Monitoring source onboarding golden path','<!--\n### G2 — Monitoring source onboarding golden path\n-->')
 _delivery_must_fail(comment_g2,'roadmap_heading_missing:G2 — Monitoring source onboarding golden path')
 def reorder_gates(root):
  path=root/'docs/00-foundation/ai-e2e-delivery/PRODUCT-EXECUTION-ROADMAP.md'; text=path.read_text(encoding='utf-8'); g1='### G1 — Identity + tenant + shell golden path'; g2='### G2 — Monitoring source onboarding golden path'; text=text.replace(g1,'### __TMP_GATE__',1).replace(g2,g1,1).replace('### __TMP_GATE__',g2,1); path.write_text(text,encoding='utf-8')
 _delivery_must_fail(reorder_gates,'roadmap_heading_order_or_duplicate')
 def duplicate_g2(root): mutate_doc(root,Path('docs/00-foundation/ai-e2e-delivery/PRODUCT-EXECUTION-ROADMAP.md'),'### G2 — Monitoring source onboarding golden path','### G2 — Monitoring source onboarding golden path\n### G2 — Monitoring source onboarding golden path')
 _delivery_must_fail(duplicate_g2,'roadmap_heading_order_or_duplicate')
 def remove_s1(root): mutate_doc(root,Path('docs/00-foundation/ai-e2e-delivery/VERTICAL-SLICE-DELIVERY-MODEL.md'),'### S1 — Contract skeleton','### renamed contract stage')
 _delivery_must_fail(remove_s1,'slice_heading_missing:S1 — Contract skeleton')
 def demote_s1(root): mutate_doc(root,Path('docs/00-foundation/ai-e2e-delivery/VERTICAL-SLICE-DELIVERY-MODEL.md'),'### S1 — Contract skeleton','#### S1 — Contract skeleton')
 _delivery_must_fail(demote_s1,'slice_heading_missing:S1 — Contract skeleton')
 def fence_s1(root): mutate_doc(root,Path('docs/00-foundation/ai-e2e-delivery/VERTICAL-SLICE-DELIVERY-MODEL.md'),'### S1 — Contract skeleton','~~~text\n### S1 — Contract skeleton\n~~~')
 _delivery_must_fail(fence_s1,'slice_heading_missing:S1 — Contract skeleton')
 def comment_s1(root): mutate_doc(root,Path('docs/00-foundation/ai-e2e-delivery/VERTICAL-SLICE-DELIVERY-MODEL.md'),'### S1 — Contract skeleton','<!--\n### S1 — Contract skeleton\n-->')
 _delivery_must_fail(comment_s1,'slice_heading_missing:S1 — Contract skeleton')
 def reorder_slices(root):
  path=root/'docs/00-foundation/ai-e2e-delivery/VERTICAL-SLICE-DELIVERY-MODEL.md'; text=path.read_text(encoding='utf-8'); s0='### S0 — Authority ready'; s1='### S1 — Contract skeleton'; text=text.replace(s0,'### __TMP_SLICE__',1).replace(s1,s0,1).replace('### __TMP_SLICE__',s1,1); path.write_text(text,encoding='utf-8')
 _delivery_must_fail(reorder_slices,'slice_heading_order_or_duplicate')
 def replace_layer(root):
  import json
  path=root/'implementation/e2e-delivery/EXECUTION_MANIFEST.json'; data=json.loads(path.read_text(encoding='utf-8')); data['required_layers'][0]='junk-layer'; path.write_text(json.dumps(data),encoding='utf-8')
 _delivery_must_fail(replace_layer,'manifest_e2e16_exact_layers')
 def remove_dependency(root):
  import json
  path=root/'implementation/e2e-delivery/EXECUTION_MANIFEST.json'; data=json.loads(path.read_text(encoding='utf-8')); data['gates'][7]['depends_on']=[]; path.write_text(json.dumps(data),encoding='utf-8')
 _delivery_must_fail(remove_dependency,'gate_dependencies_exact:G7')
 def corrupt_g7(root):
  import json
  path=root/'implementation/e2e-delivery/EXECUTION_MANIFEST.json'; data=json.loads(path.read_text(encoding='utf-8')); data['gates'][7]['authority_prerequisite']='missing_authority'; path.write_text(json.dumps(data),encoding='utf-8')
 _delivery_must_fail(corrupt_g7,'gate_authority_prerequisite_exact:G7')
 def corrupt_g8(root):
  import json
  path=root/'implementation/e2e-delivery/EXECUTION_MANIFEST.json'; data=json.loads(path.read_text(encoding='utf-8')); data['gates'][8]['authority_prerequisite']='missing_authority'; path.write_text(json.dumps(data),encoding='utf-8')
 _delivery_must_fail(corrupt_g8,'gate_authority_prerequisite_exact:G8')
def main():
 values=baseline(); errors=validator.validate_records(*values)
 if errors: raise AssertionError(f'canonical D4-C selection failed validation: {errors!r}')
 def drift_axis(selection,ledger,state,evaluation): selection['profile']['quarantine_and_redrive']['mechanism_class']='broker_native_dlq_with_canonical_platform_quarantine_index'
 must_fail(drift_axis,'quarantine_and_redrive mechanism selection drift')
 def drift_ledger(selection,ledger,state,evaluation): ledger['candidate']['outbox_claim_dispatch_and_ack_ambiguity']='database_skip_locked_polling_claim_profile'
 must_fail(drift_ledger,'current ledger selected profile drift')
 def drift_state(selection,ledger,state,evaluation): next(t for t in state['tracks'] if t['track_id']=='D4-C')['candidate']['recovery_generation_reconciliation_and_activation']='restore_generation_fence_manifest_profile'
 must_fail(drift_state,'state selected profile drift')
 def rewrite_history(selection,ledger,state,evaluation): evaluation['selection_state']='selected'; evaluation['selection_authority']='selection_record'; evaluation['separate_selection_required']=False
 must_fail(rewrite_history,'historical evaluation plan must remain not_selected')
 def regress_credit(selection,ledger,state,evaluation): ledger['credited_evidence'].pop(); ledger['remaining_evidence']=[validator.EXPECTED_EVIDENCE[-1]]
 must_fail(regress_credit,'current ledger evidence drift')
 def grant_transport(selection,ledger,state,evaluation): state['d4_transport_authority']='granted'
 must_fail(grant_transport,'transport authority escalation')
 def regress_d4_acceptance(selection,ledger,state,evaluation): state['gate_state']='scoped'
 must_fail(regress_d4_acceptance,'state D4 gate authority drift')
 falsify_selection_record_product_authority()
 falsify_ai_e2e_delivery_heading_binding()
 print('d4c_selection_falsification=PASS profile_drift=blocked historical_rewrite=blocked evidence_regression=blocked authority_escalation=blocked gate_acceptance_regression=blocked ai_e2e_governance=negative-mutated')
 return 0
if __name__=='__main__': main()
