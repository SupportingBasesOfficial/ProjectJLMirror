#!/usr/bin/env python3
from __future__ import annotations
import copy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'tools'/'assurance')); sys.path.insert(0,str(ROOT/'tools'/'project_memory'))
import validate_d4c_selection as validator
import validate_project_memory as project_memory
def baseline(): return [validator.load(ROOT,p) for p in (validator.SELECTION,validator.LEDGER,validator.STATE,validator.EVALUATION)]
def must_fail(mutator,fragment):
 if fragment.startswith('project_memory_'):
  try: mutator()
  except AssertionError as exc:
   if fragment not in str(exc): raise AssertionError(f'expected project-memory failure containing {fragment!r}, got {exc!r}')
   return
  raise AssertionError(f'expected project-memory failure containing {fragment!r}, but mutation was accepted')
 values=[copy.deepcopy(x) for x in baseline()]; mutator(*values); errors=validator.validate_records(*values)
 if not any(fragment in x for x in errors): raise AssertionError(f'expected failure containing {fragment!r}, got {errors!r}')
def falsify_selection_record_product_authority():
 def grant_product(selection,ledger,state,evaluation): selection['canonical_product_implementation_authority']='granted'
 must_fail(grant_product,'Product authority escalation')
def falsify_project_memory_review_guardrails():
 human=(ROOT/'docs/00-foundation/project-memory/HUMAN-OPERATIONS-MODEL.md').read_text(encoding='utf-8')
 must_fail(lambda: project_memory.validate_human_operations(human.replace('authoritative visibility','verified awareness',1)),'project_memory_human_model_missing:authoritative visibility')
 workflow=project_memory.WORKFLOW.read_text(encoding='utf-8')
 must_fail(lambda: project_memory.validate_project_memory_workflow(workflow.replace('run: python3 tools/assurance/validate_repository.py','# run: python3 tools/assurance/validate_repository.py',1)),'project_memory_workflow_missing_active_line')
 must_fail(lambda: project_memory.validate_project_memory_workflow(workflow.replace('allow-unsafe-pr-checkout: false','# allow-unsafe-pr-checkout: false',1)),'project_memory_workflow_missing_active_line')
 must_fail(lambda: project_memory.validate_project_memory_workflow(workflow.replace('run: PYTHONPATH=tools/assurance:tools/project_memory python3 tools/assurance/test_validate_d4c_selection.py','# run: PYTHONPATH=tools/assurance:tools/project_memory python3 tools/assurance/test_validate_d4c_selection.py',1)),'project_memory_workflow_missing_active_line')
 disabled=workflow.replace('      - name: Falsify canonical project-memory guardrails\n','      - name: Falsify canonical project-memory guardrails\n        if: ${{ false }}\n',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(disabled),'project_memory_workflow_condition_not_allowed')
 quoted_disabled=workflow.replace('      - name: Falsify canonical project-memory guardrails\n','      - name: Falsify canonical project-memory guardrails\n        "if": ${{ false }}\n',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(quoted_disabled),'project_memory_workflow_condition_not_allowed')
 rows=[f'| {decision_id} | {meaning} | current | accepted |' for decision_id,meaning in project_memory.BASELINE_DECISION_MEANINGS.items()]
 hidden='<!--\n'+'\n'.join(rows)+'\n-->'
 must_fail(lambda: project_memory.validate_decision_register(hidden),'project_memory_missing_baseline_decision:JLM-DEC-001')
 fenced='```markdown\n    ```\n'+'\n'.join(rows)+'\n```'
 must_fail(lambda: project_memory.validate_decision_register(fenced),'project_memory_missing_baseline_decision:JLM-DEC-001')
 unescaped=list(rows); unescaped[11]=unescaped[11].replace('\\|','|',1)
 must_fail(lambda: project_memory.validate_decision_register('\n'.join(unescaped)),'project_memory_baseline_decision_meaning_changed:JLM-DEC-012')
 missing=list(rows); missing.pop(16)
 must_fail(lambda: project_memory.validate_decision_register('\n'.join(missing)),'project_memory_missing_baseline_decision:JLM-DEC-017')
 rewritten=list(rows); rewritten[16]='| JLM-DEC-017 | Chat memory outranks repository truth | current | accepted |'
 must_fail(lambda: project_memory.validate_decision_register('\n'.join(rewritten)),'project_memory_baseline_decision_meaning_changed:JLM-DEC-017')
 dangling=list(rows); dangling[0]='| JLM-DEC-001 | JLMirror is provider-neutral, not a Zabbix UI | superseded by JLM-DEC-999 | accepted |'
 must_fail(lambda: project_memory.validate_decision_register('\n'.join(dangling)),'project_memory_missing_supersession_target:JLM-DEC-999')
 malformed=list(rows); malformed[0]='| JLM-DEC-001 | JLMirror is provider-neutral, not a Zabbix UI | superseded by JLM-DEC-99 | accepted |'
 must_fail(lambda: project_memory.validate_decision_register('\n'.join(malformed)),'project_memory_malformed_supersession:JLM-DEC-001')
 cyclic=list(rows); cyclic[0]='| JLM-DEC-001 | JLMirror is provider-neutral, not a Zabbix UI | superseded by JLM-DEC-002 | accepted |'; cyclic[1]='| JLM-DEC-002 | Tenant isolation is foundational | superseded by JLM-DEC-001 | accepted |'
 must_fail(lambda: project_memory.validate_decision_register('\n'.join(cyclic)),'project_memory_supersession_cycle')
 duplicate=list(rows); duplicate.append('| JLM-DEC-017 | Repository truth outranks assistant/chat memory | current | accepted |')
 must_fail(lambda: project_memory.validate_decision_register('\n'.join(duplicate)),'project_memory_duplicate_decision_definition_id')
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
 must_fail(grant_transport,'state transport authority escalation')
 def regress_d4_acceptance(selection,ledger,state,evaluation): state['gate_state']='scoped'
 must_fail(regress_d4_acceptance,'state D4 gate authority drift')
 falsify_selection_record_product_authority()
 falsify_project_memory_review_guardrails()
 print('d4c_selection_falsification=PASS profile_drift=blocked historical_rewrite=blocked evidence_regression=blocked authority_escalation=blocked gate_acceptance_regression=blocked project_memory_review_guardrails=rendering+workflow-negative-tested')
 return 0
if __name__=='__main__':
 main()
