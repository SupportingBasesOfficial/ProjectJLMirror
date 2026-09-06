#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from evaluate_candidates import CANDIDATES, PROOFS, evaluate

SOURCE = Path('implementation/d4-eventing-async/source-evidence/d4-c-recovery-generation-source.json')
PLAN = Path('implementation/d4-eventing-async/d4-c-evidence-plan.json')
STATE = Path('implementation/d4-eventing-async/state-manifest.json')
CANDIDATE_PLAN = Path('implementation/d4-eventing-async/d4-c-candidate-evaluation-plan.json')
EVIDENCE_ID = 'recovery_generation_rf_inventory_reconciliation_and_activation_gates'
CURRENT_CREDITS = [
    'ack_after_durable_responsibility_and_lease_ambiguity',
    'quarantine_redrive_current_authority_and_dedup_preservation',
    'bounded_message_batch_compression_and_parser_limits',
    'scoped_content_equivalence_confidentiality_and_conflict_rejection',
    'outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity',
    'producer_generation_nonresurrection_across_failover_restore',
    'privileged_bounded_replay_with_original_identity_and_effect_safety',
    'historical_reader_upcaster_semantic_and_equivalence_continuity',
]
CURRENT_REMAINING = [EVIDENCE_ID]
EXPECTED_KEYS = {
    'schema_version','gate_id','track_id','mode','source_decision','evidence_id',
    'candidate_classes','must_prove','candidate_results','selection_state',
    'selection_authority','current_run_auto_credit','ledger_credit','non_authority','source_boundary',
}
EXPECTED_NON_AUTHORITY = {
    'd4c_ledger_credit': 'current_8_of_9_unchanged',
    'open_evt_025_ledger_credit': 'uncredited',
    'd4c_candidate': 'null_not_selected_candidate_selection_open',
    'd4d_ledger_credit': 'zero_of_five',
    'd4_gate': 'scoped',
    'd4_transport_authority': 'selected_not_granted',
    'canonical_product_implementation_authority': 'not_granted',
    'wave4_implementation_authority': 'not_granted',
    'production_authority': 'none',
    'c3_numeric_topology_authority': 'not_selected',
}
EXPECTED_BOUNDARY = {
    'generation_rule': 'restore_and_activation_generations_are_explicit_durable_and_fenced',
    'inventory_rule': 'rf_inventory_reconciles_broker_inbox_outbox_equivalence_external_effect_and_webhook_evidence',
    'uncertainty_rule': 'missing_or_stale_restored_state_is_uncertainty_never_absence_or_safe_duplicate',
    'authority_rule': 'stale_producer_replay_destination_verifier_and_comparison_authority_never_revive',
    'external_effect_rule': 'surviving_external_audit_effect_or_equivalence_evidence_cannot_be_overridden_by_offsets_inbox_or_outbox',
    'activation_rule': 'effectful_async_activation_is_fail_closed_until_generation_scoped_reconciliation_is_complete_and_reproducible',
}

class DuplicateKeyError(ValueError):
    pass

def no_duplicates(pairs):
    out = {}
    for k,v in pairs:
        if k in out:
            raise DuplicateKeyError(f'duplicate JSON member: {k}')
        out[k]=v
    return out

def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=no_duplicates)
def fail(msg: str) -> int:
    print(f'd4c_open_evt_025_source_validation=FAIL reason={msg}', file=sys.stderr)
    return 1

def main() -> int:
    try:
        source, plan, state, candidate_plan = map(load, (SOURCE, PLAN, STATE, CANDIDATE_PLAN))
    except Exception as exc:
        return fail(str(exc))
    if not isinstance(source, dict) or set(source) != EXPECTED_KEYS:
        return fail('source exact key schema drift')
    if type(source.get('schema_version')) is not int or source['schema_version'] != 1:
        return fail('schema_version must be integer 1')
    if source.get('gate_id') != 'D4' or source.get('track_id') != 'D4-C' or source.get('mode') != 'candidate_source_evidence_only':
        return fail('gate track or mode drift')
    if source.get('source_decision') != 'OPEN-EVT-025' or source.get('evidence_id') != EVIDENCE_ID:
        return fail('source identity drift')
    if tuple(source.get('candidate_classes', [])) != CANDIDATES or tuple(source.get('must_prove', [])) != PROOFS:
        return fail('candidate or proof inventory drift')
    if source.get('candidate_results') != {c:'eligible_for_evidence_execution' for c in CANDIDATES}:
        return fail('candidate result drift')
    if source.get('selection_state') != 'not_selected' or source.get('selection_authority') != 'not_granted':
        return fail('selection leakage')
    if source.get('current_run_auto_credit') is not False or source.get('ledger_credit') != []:
        return fail('source credit leakage')
    if source.get('non_authority') != EXPECTED_NON_AUTHORITY or source.get('source_boundary') != EXPECTED_BOUNDARY:
        return fail('boundary drift')
    axis = candidate_plan.get('axes',{}).get('recovery_generation_reconciliation_and_activation',{})
    if axis.get('decision') != 'OPEN-EVT-025' or axis.get('evidence_id') != EVIDENCE_ID:
        return fail('candidate-plan axis identity drift')
    if tuple(c for c in axis.get('candidate_classes',[]) if c != 'equivalent_reviewed_profile') != CANDIDATES:
        return fail('candidate-plan classes drift')
    if tuple(axis.get('must_prove',[])) != PROOFS:
        return fail('candidate-plan proof drift')
    runtime = evaluate()
    if runtime['candidate_results'] != source['candidate_results']:
        return fail('runtime candidate result drift')
    for c in CANDIDATES:
        if set(runtime['proof_results'].get(c,{})) != set(PROOFS) or not all(runtime['proof_results'][c].values()) or not all(runtime['check_results'][c].values()):
            return fail(f'runtime proof/check failure for {c}')
    if runtime['selection'] != 'not_selected' or runtime['ledger_credit'] != [] or runtime['current_run_auto_credit'] is not False:
        return fail('runtime authority leakage')
    if plan.get('ledger_credit_state') != 'eight_of_nine' or plan.get('credited_evidence') != CURRENT_CREDITS or plan.get('remaining_evidence') != CURRENT_REMAINING:
        return fail('D4-C ledger drift')
    if EVIDENCE_ID in plan.get('credited_evidence',[]) or EVIDENCE_ID not in plan.get('remaining_evidence',[]):
        return fail('OPEN-EVT-025 must remain uncredited at source stage')
    if plan.get('candidate') is not None or plan.get('candidate_status') != 'not_selected':
        return fail('D4-C candidate selection leakage')
    tracks = {t['track_id']:t for t in state.get('tracks',[])}
    if set(tracks) != {'D4-A','D4-B','D4-C','D4-D'}:
        return fail('D4 track inventory drift')
    d4c=tracks['D4-C']
    if d4c.get('evidence_completed') != CURRENT_CREDITS or d4c.get('evidence_remaining') != CURRENT_REMAINING:
        return fail('D4-C global projection drift')
    if d4c.get('candidate') is not None or d4c.get('candidate_status') != 'not_selected' or d4c.get('state') != 'candidate_selection_open':
        return fail('D4-C selection leakage')
    if tracks['D4-D'].get('evidence_completed') != [] or tracks['D4-D'].get('candidate') is not None:
        return fail('D4-D leakage')
    if sum(len(t.get('evidence_completed',[])) for t in tracks.values()) != 20:
        return fail('D4-wide credit count must remain 20/26')
    expected = {
        'gate_state':'scoped','d4_transport_authority':'selected_not_granted',
        'canonical_product_implementation_authority':'not_granted',
        'wave4_implementation_authority':'not_granted','production_authority':'none',
        'c3_numeric_topology_authority':'not_selected',
    }
    for k,v in expected.items():
        if state.get(k) != v:
            return fail(f'authority drift: {k}')
    print('d4c_open_evt_025_source_validation=PASS candidates=3 proofs=12 source_snapshot=8/9_uncredited current_d4c=8/9 current_d4wide=20/26 selection=none authorities=unchanged')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
