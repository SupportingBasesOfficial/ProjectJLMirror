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
 if errors: raise AssertionError(f'canonical D4 accepted state failed validation: {errors!r}')
 if validator.EXPECTED_TOTAL_EVIDENCE!=26 or validator.EXPECTED_TOTAL_CREDITED!=26: raise AssertionError('unexpected D4 evidence totals')
 must_fail(lambda s:s.__setitem__('gate_state','scoped'),'must remain separately accepted')
 must_fail(lambda s:s.__setitem__('d4_transport_authority','granted'),'implementation authority must remain ungranted')
 must_fail(lambda s:s.__setitem__('canonical_product_implementation_authority','granted'),'must not grant canonical Product')
 must_fail(lambda s:s.__setitem__('wave4_implementation_authority','granted'),'must not grant Wave 4')
 must_fail(lambda s:s.__setitem__('production_authority','granted'),'must not grant production')
 must_fail(lambda s:s.__setitem__('c3_numeric_topology_authority','selected'),'must not select C3')
 for tid in ['D4-A','D4-B','D4-C','D4-D']:
  must_fail(lambda s,t=tid:track(s,t).__setitem__('state','selected_candidate'),tid+' accepted state drift')
  must_fail(lambda s,t=tid:track(s,t)['evidence_completed'].pop(),tid+' completed evidence drift')
 must_fail(lambda s:track(s,'D4-A').__setitem__('candidate','rabbitmq'),'D4-A accepted candidate drift')
 must_fail(lambda s:track(s,'D4-B').__setitem__('candidate',None),'D4-B accepted profile drift')
 must_fail(lambda s:track(s,'D4-C').__setitem__('candidate',None),'D4-C accepted profile drift')
 must_fail(lambda s:track(s,'D4-D').__setitem__('candidate',None),'D4-D accepted profile drift')
 must_fail(lambda s:s['explicit_c3_exclusions'].remove('OPEN-EVT-006'),'C3 exclusion set drift')
 must_fail(lambda s:s['explicit_product_or_later_gate_exclusions'].remove('OPEN-EVT-021'),'Product/later-gate exclusion set drift')
 print('d4_acceptance_falsification=PASS evidence=26_of_26 tracks=4_accepted transport_implementation_authority=blocked product_wave4=blocked production=blocked c3=blocked')
 return 0
if __name__=='__main__': raise SystemExit(main())
