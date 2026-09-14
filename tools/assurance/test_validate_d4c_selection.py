#!/usr/bin/env python3
from __future__ import annotations
import copy,shutil,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'tools'/'assurance')); sys.path.insert(0,str(ROOT/'tools'/'project_memory'))
import validate_d4c_selection as validator
import validate_ai_e2e_delivery as delivery_validator
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
def falsify_monitoring_alerting_composed_workflow_dependencies():
 workflow=(ROOT/'.github/workflows/wave4-monitoring-alerting-publication-runtime.yml').read_text(encoding='utf-8')
 assert workflow.count("- 'sql/wave2/001_async_correctness.sql'")==2, 'composed publication gate must observe Wave 2 outbox substrate on PR and push'
 assert workflow.count("- 'sql/wave4/**'")==2, 'composed publication gate must observe all Wave 4 transition substrate changes on PR and push'
 assert workflow.count("- 'tools/assurance/test_validate_d4c_selection.py'")==2, 'publication falsifier source must trigger publication gate on PR and push'
 assert workflow.count("- 'tools/wave4/run_monitoring_alerting_publication_recovery_proxy_postgres_conformance.sh'")==2, 'recovery proxy conformance must trigger publication gate on PR and push'
 assert 'Falsify permanent publication guardrails' in workflow
 assert 'PYTHONPATH=tools/assurance python3 tools/assurance/test_validate_d4c_selection.py' in workflow
 assert 'Prove recovery trigger proxy rejection' in workflow
 assert 'bash tools/wave4/run_monitoring_alerting_publication_recovery_proxy_postgres_conformance.sh' in workflow
 def grant_product(selection,ledger,state,evaluation): selection['canonical_product_implementation_authority']='granted'
 must_fail(grant_product,'Product authority escalation')
def falsify_monitoring_alerting_privileged_acl_preflight():
 sql=(ROOT/'sql/integration/001_monitoring_alerting_publication.sql').read_text(encoding='utf-8')
 conformance=(ROOT/'tools/wave4/run_monitoring_alerting_publication_acl_preflight_postgres_conformance.sh').read_text(encoding='utf-8')
 recovery_dependency_conformance=(ROOT/'tools/wave4/run_monitoring_alerting_publication_recovery_proxy_postgres_conformance.sh').read_text(encoding='utf-8')
 workflow=(ROOT/'.github/workflows/wave4-monitoring-alerting-publication-runtime.yml').read_text(encoding='utf-8')
 assert 'monitoring.publication_executor_unexpected_owned_object' in sql
 assert 'FROM pg_shdepend d' in sql and "d.deptype='o'" in sql
 assert "d.refclassid='pg_authid'::regclass" in sql
 assert "d.classid='pg_proc'::regclass" in sql
 assert 'monitoring.publication_existing_function_dependency_unsafe' in sql
 assert 'FROM pg_depend d' in sql and "d.refclassid='pg_proc'::regclass" in sql
 privileged_signatures=(
  'monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb)',
  'monitoring.wave4_publish_problem_transition()',
  'monitoring.wave4_publish_health_transition()',
  'monitoring.recover_problem_state_publication(text,text)',
  'monitoring.recover_health_projection_publication(text,text)',
 )
 dependency_fence_start=sql.index('-- CREATE OR REPLACE preserves a function OID.')
 dependency_fence_end=sql.index('-- The Wave 4 recovery authority is intentionally shared',dependency_fence_start)
 dependency_fence=sql[dependency_fence_start:dependency_fence_end]
 for signature in privileged_signatures:
  assert f"('{signature}')" in dependency_fence, f'privileged signature missing from inbound dependency fence: {signature}'
 recovery_proxy_fence_start=sql.index('-- The Wave 4 recovery authority is intentionally shared')
 recovery_proxy_fence_end=sql.index('GRANT USAGE ON SCHEMA monitoring, system',recovery_proxy_fence_start)
 recovery_proxy_fence=sql[recovery_proxy_fence_start:recovery_proxy_fence_end]
 def require_recovery_proxy_fence(text):
  assert 'monitoring.publication_recovery_authority_delegable_membership_unsafe' in text
  assert 'FROM pg_auth_members m' in text
  assert 'm.roleid=v_recovery_oid' in text
  assert 'AND m.admin_option' in text
  assert 'monitoring.publication_recovery_authority_callable_proxy_unsafe' in text
  assert 'monitoring.publication_recovery_authority_dependency_proxy_unsafe' in text
  assert text.count('WITH inheriting_principals AS')==2
  assert text.count("pg_has_role(r.oid,v_recovery_oid,'USAGE')")==2
  assert text.count('JOIN inheriting_principals ip ON ip.principal_oid=p.proowner')==2
  assert text.count('NOT r.rolsuper')==2
  assert "a.privilege_type='EXECUTE'" in text
  assert 'a.grantee<>p.proowner' in text
  assert "aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner)))" in text
  assert "JOIN pg_depend d" in text and "d.refclassid='pg_proc'::regclass" in text and 'd.refobjid=p.oid' in text
 require_recovery_proxy_fence(recovery_proxy_fence)
 weakened_recovery_proxy_fence=recovery_proxy_fence.replace('AND m.admin_option','AND false',1)
 try:
  require_recovery_proxy_fence(weakened_recovery_proxy_fence)
 except AssertionError:
  pass
 else:
  raise AssertionError('delegable recovery membership fence mutation was accepted')
 weakened_inherited_proxy_fence=recovery_proxy_fence.replace("AND pg_has_role(r.oid,v_recovery_oid,'USAGE')",'AND false',1)
 try:
  require_recovery_proxy_fence(weakened_inherited_proxy_fence)
 except AssertionError:
  pass
 else:
  raise AssertionError('inherited recovery principal fence mutation was accepted')
 assert 'monitoring.publication_existing_function_acl_unsafe' in sql
 assert 'monitoring.publication_installed_function_acl_unsafe' in sql
 assert "aclexplode(COALESCE(p.proacl, ARRAY[]::aclitem[]))" in sql
 assert "aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner)))" in sql
 assert "a.privilege_type='EXECUTE'" in sql and 'a.grantee<>p.proowner' in sql
 assert 'a.grantee=0' in sql, 'post-install ACL fence must reject PUBLIC EXECUTE'
 assert 'OR a.is_grantable' in sql, 'recovery authority must never retain EXECUTE WITH GRANT OPTION'
 assert 'jlmirror_recovery_proxy_probe' in conformance and 'recovery_authority_callable_proxy=blocked' in conformance
 assert "EXECUTE 'SELECT monitoring.recover_problem_state_publication($1,$2)'" in conformance
 assert 'proxy_dependency_count' in conformance and 'test "$proxy_dependency_count" = "0"' in conformance
 assert 'monitoring.publication_recovery_authority_callable_proxy_unsafe:routine=monitoring.jlmirror_recovery_proxy_probe(text,text),grantee=PUBLIC' in conformance
 assert 'jlmirror_executor_probe' in conformance and 'executor_owned_routine=blocked' in conformance
 assert 'jlmirror_executor_view_probe' in conformance and 'executor_owned_view=blocked' in conformance
 assert 'SET ROLE jlmirror_view_probe' in conformance and 'permission denied' in conformance
 assert 'jlmirror_retained_trigger_probe' in conformance and 'retained_trigger_dependency=blocked' in conformance
 assert 'monitoring.publication_existing_function_dependency_unsafe:monitoring.wave4_publish_problem_transition():class=pg_trigger' in conformance
 assert 'JOIN pg_trigger t ON t.tgfoid=p.oid' in conformance
 assert 'jlmirror_retained_helper_probe' in conformance and 'retained_helper_expression_dependency=blocked' in conformance
 assert 'CREATE INDEX jlmirror_retained_helper_probe_idx' in conformance
 assert 'monitoring.publication_existing_function_dependency_unsafe:monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb):' in conformance
 assert "JOIN pg_depend d ON d.refclassid='pg_proc'::regclass AND d.refobjid=p.oid" in conformance
 assert 'jlmirror_retained_problem_recovery_probe' in conformance and 'retained_problem_recovery_dependency=blocked' in conformance
 assert 'jlmirror_retained_health_recovery_probe' in conformance and 'retained_health_recovery_dependency=blocked' in conformance
 assert 'monitoring.publication_existing_function_dependency_unsafe:monitoring.recover_problem_state_publication(text,text):' in conformance
 assert 'monitoring.publication_existing_function_dependency_unsafe:monitoring.recover_health_projection_publication(text,text):' in conformance
 assert 'has_table_privilege' in conformance and 'system.async_outbox_message' in conformance
 assert 'jlmirror_acl_probe' in conformance and 'retained_named_execute=blocked' in conformance
 assert 'WITH GRANT OPTION' in conformance and 'recovery_grant_option=blocked' in conformance
 assert 'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA monitoring' in conformance
 assert 'default_execute_grant=blocked' in conformance and 'transactional_acl_fence=proven' in conformance
 assert 'jlmirror_recovery_inheriting_member NOLOGIN INHERIT' in recovery_dependency_conformance
 assert 'GRANT jlmirror_wave4_recovery_authority TO jlmirror_recovery_inheriting_member' in recovery_dependency_conformance
 assert 'jlmirror_recovery_member_callable_proxy' in recovery_dependency_conformance
 assert "pg_has_role('jlmirror_recovery_inheriting_member','jlmirror_wave4_recovery_authority','USAGE')" in recovery_dependency_conformance
 assert 'owner=jlmirror_recovery_inheriting_member' in recovery_dependency_conformance
 assert 'jlmirror_recovery_member_trigger_proxy' in recovery_dependency_conformance
 assert 'CREATE TRIGGER jlmirror_recovery_member_trigger_proxy' in recovery_dependency_conformance
 assert 'REVOKE ALL ON FUNCTION monitoring.jlmirror_recovery_member_trigger_proxy() FROM PUBLIC' in recovery_dependency_conformance
 assert 'monitoring.publication_recovery_authority_dependency_proxy_unsafe:' in recovery_dependency_conformance
 assert "grep -Fq 'class=pg_trigger'" in recovery_dependency_conformance
 assert 'jlmirror_recovery_admin_delegate NOLOGIN NOINHERIT' in recovery_dependency_conformance
 assert 'GRANT jlmirror_wave4_recovery_authority TO jlmirror_recovery_admin_delegate WITH ADMIN OPTION' in recovery_dependency_conformance
 assert 'jlmirror_recovery_admin_delegate_user NOLOGIN NOINHERIT' in recovery_dependency_conformance
 assert "pg_has_role('jlmirror_recovery_admin_delegate_user','jlmirror_recovery_admin_delegate','SET')" in recovery_dependency_conformance
 assert 'monitoring.publication_recovery_authority_delegable_membership_unsafe:' in recovery_dependency_conformance
 assert 'member=jlmirror_recovery_admin_delegate' in recovery_dependency_conformance
 assert 'delegable_admin_membership=blocked' in recovery_dependency_conformance
 assert 'transitive_delegation_root=blocked' in recovery_dependency_conformance
 assert 'jlmirror_recovery_noninheriting_member NOLOGIN NOINHERIT' in recovery_dependency_conformance
 assert "pg_has_role('jlmirror_recovery_noninheriting_member','jlmirror_wave4_recovery_authority','USAGE')" in recovery_dependency_conformance
 assert 'test "$noninherit_usage" = "0"' in recovery_dependency_conformance
 assert 'inherited_callable_proxy=blocked' in recovery_dependency_conformance
 assert 'inherited_trigger_proxy=blocked' in recovery_dependency_conformance
 assert 'noninheriting_membership=preserved' in recovery_dependency_conformance
 assert 'runtime_resolved_recovery_call=no-pg-depend' in recovery_dependency_conformance
 assert 'Prove privileged function ACL preflight' in workflow
 assert 'Prove recovery trigger proxy rejection' in workflow
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
  path=root/rel; text=path.read_text(encoding='utf-8'); assert old in text; path.write_text(text.replace(old,new,1),encoding='utf-8')
 roadmap=Path('docs/00-foundation/ai-e2e-delivery/PRODUCT-EXECUTION-ROADMAP.md')
 slices=Path('docs/00-foundation/ai-e2e-delivery/VERTICAL-SLICE-DELIVERY-MODEL.md')
 constitution=Path('docs/00-foundation/ai-e2e-delivery/AI-E2E-DELIVERY-CONSTITUTION.md')
 def remove_g2(root): mutate_doc(root,roadmap,'### G2 — Monitoring source onboarding golden path','### renamed monitoring source section')
 _delivery_must_fail(remove_g2,'roadmap_heading_missing:G2 — Monitoring source onboarding golden path')
 def demote_g2(root): mutate_doc(root,roadmap,'### G2 — Monitoring source onboarding golden path','#### G2 — Monitoring source onboarding golden path')
 _delivery_must_fail(demote_g2,'roadmap_heading_missing:G2 — Monitoring source onboarding golden path')
 def fence_g2(root): mutate_doc(root,roadmap,'### G2 — Monitoring source onboarding golden path','```text\n### G2 — Monitoring source onboarding golden path\n```')
 _delivery_must_fail(fence_g2,'roadmap_heading_missing:G2 — Monitoring source onboarding golden path')
 def comment_g2(root): mutate_doc(root,roadmap,'### G2 — Monitoring source onboarding golden path','<!--\n### G2 — Monitoring source onboarding golden path\n-->')
 _delivery_must_fail(comment_g2,'roadmap_heading_missing:G2 — Monitoring source onboarding golden path')
 def raw_html_g2(root): mutate_doc(root,roadmap,'### G2 — Monitoring source onboarding golden path','<script>\n### G2 — Monitoring source onboarding golden path\n</script>')
 _delivery_must_fail(raw_html_g2,'roadmap_heading_missing:G2 — Monitoring source onboarding golden path')
 def processing_g2(root): mutate_doc(root,roadmap,'### G2 — Monitoring source onboarding golden path','<?hidden\n### G2 — Monitoring source onboarding golden path\n?>')
 _delivery_must_fail(processing_g2,'roadmap_heading_missing:G2 — Monitoring source onboarding golden path')
 def cdata_g2(root): mutate_doc(root,roadmap,'### G2 — Monitoring source onboarding golden path','<![CDATA[\n### G2 — Monitoring source onboarding golden path\n]]>')
 _delivery_must_fail(cdata_g2,'roadmap_heading_missing:G2 — Monitoring source onboarding golden path')
 def declaration_g2(root): mutate_doc(root,roadmap,'### G2 — Monitoring source onboarding golden path','<!DECLARATION\n### G2 — Monitoring source onboarding golden path\n>')
 _delivery_must_fail(declaration_g2,'roadmap_heading_missing:G2 — Monitoring source onboarding golden path')
 def quoted_raw_html_g2(root): mutate_doc(root,roadmap,'### G2 — Monitoring source onboarding golden path','<x-hidden title=">">\n### G2 — Monitoring source onboarding golden path\n\n')
 _delivery_must_fail(quoted_raw_html_g2,'roadmap_heading_missing:G2 — Monitoring source onboarding golden path')
 def reorder_gates(root):
  path=root/roadmap; text=path.read_text(encoding='utf-8'); g1='### G1 — Identity + tenant + shell golden path'; g2='### G2 — Monitoring source onboarding golden path'; text=text.replace(g1,'### __TMP_GATE__',1).replace(g2,g1,1).replace('### __TMP_GATE__',g2,1); path.write_text(text,encoding='utf-8')
 _delivery_must_fail(reorder_gates,'roadmap_heading_order_or_duplicate')
 def duplicate_g2(root): mutate_doc(root,roadmap,'### G2 — Monitoring source onboarding golden path','### G2 — Monitoring source onboarding golden path\n### G2 — Monitoring source onboarding golden path')
 _delivery_must_fail(duplicate_g2,'roadmap_heading_order_or_duplicate')
 def shadow_g2(root): mutate_doc(root,roadmap,'### G2 — Monitoring source onboarding golden path','### G2 — Shadow replacement gate\n### G2 — Monitoring source onboarding golden path')
 _delivery_must_fail(shadow_g2,'roadmap_heading_order_or_duplicate')
 def remove_s1(root): mutate_doc(root,slices,'### S1 — Contract skeleton','### renamed contract stage')
 _delivery_must_fail(remove_s1,'slice_heading_missing:S1 — Contract skeleton')
 def demote_s1(root): mutate_doc(root,slices,'### S1 — Contract skeleton','#### S1 — Contract skeleton')
 _delivery_must_fail(demote_s1,'slice_heading_missing:S1 — Contract skeleton')
 def fence_s1(root): mutate_doc(root,slices,'### S1 — Contract skeleton','~~~text\n### S1 — Contract skeleton\n~~~')
 _delivery_must_fail(fence_s1,'slice_heading_missing:S1 — Contract skeleton')
 def comment_s1(root): mutate_doc(root,slices,'### S1 — Contract skeleton','<!--\n### S1 — Contract skeleton\n-->')
 _delivery_must_fail(comment_s1,'slice_heading_missing:S1 — Contract skeleton')
 def raw_html_s1(root): mutate_doc(root,slices,'### S1 — Contract skeleton','<pre>\n### S1 — Contract skeleton\n</pre>')
 _delivery_must_fail(raw_html_s1,'slice_heading_missing:S1 — Contract skeleton')
 def reorder_slices(root):
  path=root/slices; text=path.read_text(encoding='utf-8'); s0='### S0 — Authority ready'; s1='### S1 — Contract skeleton'; text=text.replace(s0,'### __TMP_SLICE__',1).replace(s1,s0,1).replace('### __TMP_SLICE__',s1,1); path.write_text(text,encoding='utf-8')
 _delivery_must_fail(reorder_slices,'slice_heading_order_or_duplicate')
 def shadow_s1(root): mutate_doc(root,slices,'### S1 — Contract skeleton','### S1 — Shadow replacement stage\n### S1 — Contract skeleton')
 _delivery_must_fail(shadow_s1,'slice_heading_order_or_duplicate')
 def replace_layer(root):
  import json
  path=root/'implementation/e2e-delivery/EXECUTION_MANIFEST.json'; data=json.loads(path.read_text(encoding='utf-8')); data['required_layers'][0]='junk-layer'; path.write_text(json.dumps(data),encoding='utf-8')
 _delivery_must_fail(replace_layer,'manifest_e2e16_exact_layers')
 def rename_gate(root):
  import json
  path=root/'implementation/e2e-delivery/EXECUTION_MANIFEST.json'; data=json.loads(path.read_text(encoding='utf-8')); data['gates'][2]['name']='Unrelated monitoring gate'; path.write_text(json.dumps(data),encoding='utf-8')
 _delivery_must_fail(rename_gate,'gate_name_exact:G2')
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
 def corrupt_optimization_target(root):
  import json
  path=root/'implementation/e2e-delivery/EXECUTION_MANIFEST.json'; data=json.loads(path.read_text(encoding='utf-8')); data['optimization_target']='maximize_parallel_agent_count'; path.write_text(json.dumps(data),encoding='utf-8')
 _delivery_must_fail(corrupt_optimization_target,'manifest_optimization_target')
 def rewrite_optimization_sentence(root): mutate_doc(root,roadmap,'Optimize for **lead time from accepted requirement to verified executable user outcome**, not lines of code, commit count or number of parallel agents.','Optimize for raw commit throughput.')
 _delivery_must_fail(rewrite_optimization_sentence,'roadmap_optimization_target_missing')
 def hide_optimization_sentence(root): mutate_doc(root,roadmap,'Optimize for **lead time from accepted requirement to verified executable user outcome**, not lines of code, commit count or number of parallel agents.','<!--\nOptimize for **lead time from accepted requirement to verified executable user outcome**, not lines of code, commit count or number of parallel agents.\n-->\nOptimize for raw commit throughput.')
 _delivery_must_fail(hide_optimization_sentence,'roadmap_optimization_target_missing')
 def hide_merge_authority(root): mutate_doc(root,constitution,'READY_FOR_MERGE is not merge authorization','```text\nREADY_FOR_MERGE is not merge authorization\n```\nREADY_FOR_MERGE authorizes merge automatically')
 _delivery_must_fail(hide_merge_authority,'constitution_missing:READY_FOR_MERGE is not merge authorization')
 def boolean_schema(root):
  import json
  path=root/'implementation/e2e-delivery/EXECUTION_MANIFEST.json'; data=json.loads(path.read_text(encoding='utf-8')); data['schema_version']=True; path.write_text(json.dumps(data),encoding='utf-8')
 _delivery_must_fail(boolean_schema,'manifest_schema')
def falsify_project_memory_review_guardrails():
 human=(ROOT/'docs/00-foundation/project-memory/HUMAN-OPERATIONS-MODEL.md').read_text(encoding='utf-8')
 must_fail(lambda: project_memory.validate_human_operations(human.replace('authoritative visibility','verified awareness',1)),'project_memory_human_model_missing:authoritative visibility')
 workflow=project_memory.WORKFLOW.read_text(encoding='utf-8')
 must_fail(lambda: project_memory.validate_project_memory_workflow(workflow.replace('run: python3 tools/assurance/validate_repository.py','# run: python3 tools/assurance/validate_repository.py',1)),'project_memory_workflow_missing_executable_step:Validate repository structure and workflow safety')
 must_fail(lambda: project_memory.validate_project_memory_workflow(workflow.replace('allow-unsafe-pr-checkout: false','# allow-unsafe-pr-checkout: false',1)),'project_memory_workflow_checkout_binding_invalid')
 must_fail(lambda: project_memory.validate_project_memory_workflow(workflow.replace('run: PYTHONPATH=tools/assurance:tools/project_memory python3 tools/assurance/test_validate_d4c_selection.py','# run: PYTHONPATH=tools/assurance:tools/project_memory python3 tools/assurance/test_validate_d4c_selection.py',1)),'project_memory_workflow_missing_executable_step:Falsify canonical project-memory guardrails')
 disabled=workflow.replace('      - name: Falsify canonical project-memory guardrails\n','      - name: Falsify canonical project-memory guardrails\n        if: ${{ false }}\n',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(disabled),'project_memory_workflow_condition_not_allowed')
 quoted_disabled=workflow.replace('      - name: Falsify canonical project-memory guardrails\n','      - name: Falsify canonical project-memory guardrails\n        "if": ${{ false }}\n',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(quoted_disabled),'project_memory_workflow_condition_not_allowed')
 explicit_disabled=workflow.replace('      - name: Falsify canonical project-memory guardrails\n','      - name: Falsify canonical project-memory guardrails\n        ? if\n        : ${{ false }}\n',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(explicit_disabled),'project_memory_workflow_step_explicit_key_not_allowed')
 folded_step_key=workflow.replace('      - name: Falsify canonical project-memory guardrails\n','      - name: Falsify canonical project-memory guardrails\n        ? >-\n          if\n        : ${{ false }}\n',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(folded_step_key),'project_memory_workflow_step_explicit_key_not_allowed')
 job_disabled=workflow.replace('  project-memory:\n','  project-memory:\n    if: ${{ false }}\n',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(job_disabled),'project_memory_workflow_job_condition_not_allowed')
 folded_job_key=workflow.replace('  project-memory:\n','  project-memory:\n    ? >-\n      if\n    : ${{ false }}\n',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(folded_job_key),'project_memory_workflow_job_explicit_key_not_allowed')
 wrong_pr_head=workflow.replace('${{ github.event.pull_request.head.sha }}','${{ github.event.pull_request.base.sha }}',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(wrong_pr_head),'project_memory_workflow_job_env_binding_invalid')
 wrong_prior=workflow.replace('PR_BASE_SHA: ${{ github.event.pull_request.base.sha }}','PR_BASE_SHA: ${{ github.event.pull_request.head.sha }}',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(wrong_prior),'project_memory_workflow_job_env_binding_invalid')
 resolve_comment_decoy=workflow.replace('            resolved_sha="$PR_HEAD_SHA"\n','            resolved_sha="$EVENT_SHA"\n            # resolved_sha="$PR_HEAD_SHA"\n',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(resolve_comment_decoy),'project_memory_workflow_resolve_head_binding_invalid')
 continue_on_error=workflow.replace('      - name: Falsify canonical project-memory guardrails\n','      - name: Falsify canonical project-memory guardrails\n        continue-on-error: ${{ true }}\n',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(continue_on_error),'project_memory_workflow_continue_on_error_not_allowed')
 required='run: PYTHONPATH=tools/assurance:tools/project_memory python3 tools/assurance/test_validate_d4c_selection.py'
 env_decoy=workflow.replace('      - name: Falsify canonical project-memory guardrails\n        '+required+'\n',"      - name: Falsify canonical project-memory guardrails\n        run: 'true'\n        env:\n          "+required+'\n',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(env_decoy),'project_memory_workflow_missing_executable_step:Falsify canonical project-memory guardrails')
 checkout_decoy=workflow.replace('          ref: ${{ steps.target.outputs.sha }}\n','          ref: main\n',1).replace('      - name: Validate canonical project memory\n','      - name: Validate canonical project memory\n        env:\n          ref: ${{ steps.target.outputs.sha }}\n',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(checkout_decoy),'project_memory_workflow_checkout_binding_invalid')
 verify_decoy=workflow.replace('          test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"\n','          true\n',1).replace('      - name: Validate canonical project memory\n','      - name: Validate canonical project memory\n        env:\n          DECOY: test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"\n',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(verify_decoy),'project_memory_workflow_verify_head_binding_invalid')
 second_checkout=workflow.replace('      - name: Validate canonical project memory\n','      - name: Checkout accepted main after verification\n        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1\n        with:\n          ref: main\n          persist-credentials: false\n          fetch-depth: 0\n          allow-unsafe-pr-checkout: false\n\n      - name: Validate canonical project memory\n',1)
 must_fail(lambda: project_memory.validate_project_memory_workflow(second_checkout),'project_memory_workflow_step_order_invalid')
 rows=[f'| {decision_id} | {meaning} | current | accepted |' for decision_id,meaning in project_memory.BASELINE_DECISION_MEANINGS.items()]
 hidden='<!--\n'+'\n'.join(rows)+'\n-->'
 must_fail(lambda: project_memory.validate_decision_register(hidden),'project_memory_missing_baseline_decision:JLM-DEC-001')
 fenced='```markdown\n    ```\n'+'\n'.join(rows)+'\n```'
 must_fail(lambda: project_memory.validate_decision_register(fenced),'project_memory_missing_baseline_decision:JLM-DEC-001')
 raw_html='<script type="text/plain">\n'+'\n'.join(rows)+'\n</script>'
 must_fail(lambda: project_memory.validate_decision_register(raw_html),'project_memory_missing_baseline_decision:JLM-DEC-001')
 for hidden_html in ('<?hidden\n'+'\n'.join(rows)+'\n?>','<![CDATA[\n'+'\n'.join(rows)+'\n]]>','<!DECLARATION\n'+'\n'.join(rows)+'\n>','<custom hidden>\n'+'\n'.join(rows)+'\n\n','<custom hidden data=">">\n'+'\n'.join(rows)+'\n\n'):
  must_fail(lambda sample=hidden_html: project_memory.validate_decision_register(sample),'project_memory_missing_baseline_decision:JLM-DEC-001')
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
 backward=list(rows); backward[16]='| JLM-DEC-017 | Repository truth outranks assistant/chat memory | superseded by JLM-DEC-001 | accepted |'
 must_fail(lambda: project_memory.validate_decision_register('\n'.join(backward)),'project_memory_supersession_target_not_newer:JLM-DEC-017->JLM-DEC-001')
 duplicate=list(rows); duplicate.append('| JLM-DEC-017 | Repository truth outranks assistant/chat memory | current | accepted |')
 must_fail(lambda: project_memory.validate_decision_register('\n'.join(duplicate)),'project_memory_duplicate_decision_definition_id')
 truncated=list(rows); truncated.append('| JLM-DEC-018 |')
 must_fail(lambda: project_memory.validate_decision_register('\n'.join(truncated)),'project_memory_decision_row_invalid:JLM-DEC-018')
 prior=list(rows); prior.append('| JLM-DEC-018 | accepted appended decision | current | accepted-source |')
 must_fail(lambda: project_memory.validate_decision_history('\n'.join(rows),'\n'.join(prior)),'project_memory_prior_decision_missing:JLM-DEC-018')
 changed=list(prior); changed[-1]='| JLM-DEC-018 | rewritten appended decision | current | accepted-source |'
 must_fail(lambda: project_memory.validate_decision_history('\n'.join(changed),'\n'.join(prior)),'project_memory_prior_decision_meaning_changed:JLM-DEC-018')
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
 falsify_monitoring_alerting_composed_workflow_dependencies()
 falsify_monitoring_alerting_privileged_acl_preflight()
 falsify_ai_e2e_delivery_heading_binding()
 falsify_project_memory_review_guardrails()
 print('d4c_selection_falsification=PASS profile_drift=blocked historical_rewrite=blocked evidence_regression=blocked authority_escalation=blocked gate_acceptance_regression=blocked publication_composed_dependencies=bound publication_acl_preflight=recovery-admin-delegation+recovery-inherited-principal+acl+dependency-proxy+all-privileged-owner+dependency+pre+post-install-attested ai_e2e_governance=preserved project_memory_review_guardrails=prior-history+exact-step-chain+complete-decision-rows')
 return 0
if __name__=='__main__': main()
