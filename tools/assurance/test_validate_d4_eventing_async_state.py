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
 if validator.EXPECTED_TOTAL_EVIDENCE!=26 or validator.EXPECTED_TOTAL_CREDITED!=24: raise AssertionError('unexpected D4 evidence totals')
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
 first,second,third,fourth=validator.EXPECTED_REQUIRED_EVIDENCE['D4-D'][:4]
 def regress_credit(s,credit):
  d=track(s,'D4-D'); d['evidence_completed'].remove(credit); d['evidence_remaining'].insert(0,credit)
 for credit in (first,second,third): must_fail(lambda s,c=credit:regress_credit(s,c),'completed evidence drift')
 must_fail(lambda s:track(s,'D4-D')['evidence_completed'].append(first),'completed evidence drift')
 def grant_fourth(s):
  d=track(s,'D4-D'); d['evidence_remaining'].remove(fourth); d['evidence_completed'].append(fourth)
 must_fail(grant_fourth,'completed evidence drift')
 must_fail(lambda s:track(s,'D4-C').__setitem__('candidate','implicit'),'must not silently select')
 must_fail(lambda s:track(s,'D4-D').__setitem__('candidate','implicit'),'must not silently select')
 must_fail(lambda s:s['explicit_c3_exclusions'].remove('OPEN-EVT-006'),'C3 exclusion set drift')
 must_fail(lambda s:s['explicit_product_or_later_gate_exclusions'].remove('OPEN-EVT-021'),'Product/later-gate exclusion set drift')
 print('d4_state_falsification=PASS total_required=26 total_credited=24 d4d_first_second_third_regression=blocked duplicate=blocked fourth_credit_without_promotion=blocked selection=blocked authorities=blocked')
 return 0
if __name__=='__main__': raise SystemExit(main())
