#!/usr/bin/env python3
from __future__ import annotations
import copy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'tools'/'assurance'))
import validate_d4_eventing_async_state as validator
def baseline(): return validator.load_manifest(ROOT)
def must_fail(mutator,fragment):
 state=copy.deepcopy(baseline()); mutator(state); errors=validator.validate_manifest(state)
 if not any(fragment in x for x in errors): raise AssertionError(f'expected failure containing {fragment!r}, got {errors!r}')
def track(state,tid): return next(t for t in state['tracks'] if t['track_id']==tid)
def main():
 state=baseline(); errors=validator.validate_manifest(state)
 if errors: raise AssertionError(f'canonical D4 state failed validation: {errors!r}')
 if validator.EXPECTED_TOTAL_EVIDENCE!=26 or validator.EXPECTED_TOTAL_CREDITED!=26: raise AssertionError('unexpected D4 evidence totals')
 must_fail(lambda s:s.__setitem__('gate_state','separately_accepted'),'must remain scoped')
 must_fail(lambda s:s.__setitem__('d4_transport_authority','granted'),'authority must remain ungranted')
 must_fail(lambda s:s.__setitem__('wave4_implementation_authority','granted'),'must not grant Wave 4')
 must_fail(lambda s:s.__setitem__('production_authority','granted'),'must not grant production')
 must_fail(lambda s:track(s,'D4-A')['evidence_completed'].pop(),'completed evidence drift')
 must_fail(lambda s:track(s,'D4-A').__setitem__('candidate','rabbitmq'),'selected candidate drift')
 must_fail(lambda s:track(s,'D4-B').__setitem__('candidate',None),'selected profile drift')
 def regress_d4c(s):
  d=track(s,'D4-C'); credit=d['evidence_completed'].pop(); d['evidence_remaining'].append(credit)
 must_fail(regress_d4c,'completed evidence drift')
 for credit in validator.EXPECTED_REQUIRED_EVIDENCE['D4-D']:
  def regress(s,c=credit):
   d=track(s,'D4-D'); d['evidence_completed'].remove(c); d['evidence_remaining'].append(c)
  must_fail(regress,'completed evidence drift')
 must_fail(lambda s:track(s,'D4-D')['evidence_completed'].append(validator.EXPECTED_REQUIRED_EVIDENCE['D4-D'][-1]),'completed evidence drift')
 must_fail(lambda s:track(s,'D4-C').__setitem__('candidate','implicit'),'must not silently select')
 must_fail(lambda s:track(s,'D4-D').__setitem__('candidate',None),'selected profile drift')
 must_fail(lambda s:track(s,'D4-D').__setitem__('candidate_status','not_selected'),'selected profile status drift')
 must_fail(lambda s:track(s,'D4-D').__setitem__('state','candidate_selection_open'),'selected state drift')
 def drift_trace(s):
  track(s,'D4-D')['candidate']['trace_context_observability_only_validation_and_redaction']='vendor_neutral_trace_correlation_profile'
 must_fail(drift_trace,'selected profile drift')
 must_fail(lambda s:s['explicit_c3_exclusions'].remove('OPEN-EVT-006'),'C3 exclusion set drift')
 must_fail(lambda s:s['explicit_product_or_later_gate_exclusions'].remove('OPEN-EVT-021'),'Product/later-gate exclusion set drift')
 print('d4_state_falsification=PASS total_required=26 total_credited=26 d4d_selection=bound credit_regressions=blocked authorities=blocked separate_acceptance=preserved')
 return 0
if __name__=='__main__': raise SystemExit(main())
