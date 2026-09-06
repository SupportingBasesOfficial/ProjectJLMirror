#!/usr/bin/env python3
from __future__ import annotations

from evaluate_candidates import (
    CANDIDATES, PROOFS, Evidence, RecoveryManifest,
    RecoveryReconciler, blocked, evaluate, sample_inventory, sample_manifest,
)

def main() -> int:
    result = evaluate()
    assert result['selection'] == 'not_selected'
    assert result['selection_authority'] == 'not_granted'
    assert result['ledger_credit'] == []
    assert result['current_run_auto_credit'] is False
    assert set(result['candidate_results']) == set(CANDIDATES)
    assert all(v == 'eligible_for_evidence_execution' for v in result['candidate_results'].values())
    assert all(set(result['proof_results'][c]) == set(PROOFS) for c in CANDIDATES)
    assert all(all(v.values()) for v in result['proof_results'].values())

    for candidate in CANDIDATES:
        r = RecoveryReconciler(candidate)
        manifest = sample_manifest()
        inv = sample_inventory()
        ok = r.reconcile(manifest, inv, current_generation=9)
        assert ok['activation'] == 'eligible'
        assert ok['message_identity'] == 'msg-001'
        assert ok['webhook_delivery_identity'] == 'delivery-001'
        missing = dict(inv); missing.pop('inbox')
        assert blocked(lambda: r.reconcile(manifest, missing, current_generation=9), 'restored_state_uncertain')
        assert blocked(lambda: r.reconcile(RecoveryManifest(7,9,8,9,9,9,9), inv, current_generation=9), 'stale_producer_generation')
        assert blocked(lambda: r.reconcile(RecoveryManifest(7,9,9,8,9,9,9), inv, current_generation=9), 'stale_replay_authorization_generation')
        assert blocked(lambda: r.reconcile(RecoveryManifest(7,9,9,9,8,9,9), inv, current_generation=9), 'stale_destination_generation')
        assert blocked(lambda: r.reconcile(RecoveryManifest(7,9,9,9,9,8,9), inv, current_generation=9), 'stale_historical_verifier_generation')
        assert blocked(lambda: r.reconcile(RecoveryManifest(7,9,9,9,9,9,8), inv, current_generation=9), 'stale_comparison_profile_generation')
        stale = dict(inv); stale['equivalence'] = Evidence('equivalence',8,'present','eq-001','sem-001')
        assert blocked(lambda: r.reconcile(manifest, stale, current_generation=9), 'stale_inventory_generation:equivalence')
        blank = dict(inv); blank['equivalence'] = Evidence('equivalence',9,'present','eq-001','')
        assert blocked(lambda: r.reconcile(manifest, blank, current_generation=9), 'comparison_evidence_unverifiable')

    print('d4c_open_evt_025_falsification=PASS candidates=3 proofs=12 generation_fencing=true rf_inventory=true uncertainty_fail_closed=true stale_authority_blocked=true activation_gated=true')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
