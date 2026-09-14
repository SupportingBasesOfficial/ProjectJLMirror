#!/usr/bin/env python3
from __future__ import annotations
import copy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'tools'/'assurance'))
import validate_d4c_selection as validator
def baseline(): return [validator.load(ROOT,p) for p in (validator.SELECTION,validator.LEDGER,validator.STATE,validator.EVALUATION)]
def must_fail(mutator,fragment):
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
 weakened_recovery_proxy_fence=recovery_proxy_fence.replace("AND pg_has_role(r.oid,v_recovery_oid,'USAGE')",'AND false',1)
 try:
  require_recovery_proxy_fence(weakened_recovery_proxy_fence)
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
 print('d4c_selection_falsification=PASS profile_drift=blocked historical_rewrite=blocked evidence_regression=blocked authority_escalation=blocked gate_acceptance_regression=blocked publication_composed_dependencies=bound publication_acl_preflight=recovery-inherited-principal+acl+dependency-proxy+all-privileged-owner+dependency+pre+post-install-attested')
 return 0
if __name__=='__main__':
 main()