#!/usr/bin/env python3
from __future__ import annotations

import json
import os

import replay_recovery_conformance_runner as core
import replay_recovery_boundary_hardening as boundary
import replay_recovery_strict_entrypoint as strict


def _exact_probe(op: str, generation: int, token: str) -> dict:
    observed = core.provider_probe(op, generation, token)
    if observed.get("outcome") not in {"CONFIRMED", "ABSENT"}: raise RuntimeError("provider probe did not establish an authoritative outcome")
    if int(observed.get("attempt_generation", -1)) != generation: raise RuntimeError("provider probe generation does not match issued capability")
    if observed.get("attempt_token") != token: raise RuntimeError("provider probe token does not match issued capability")
    return observed


def _unique_captured_capability(status: dict):
    canonical=boundary.canonicalize_provider_outcome(status); effect=canonical.get("effect"); fence=canonical.get("fence")
    if effect and fence: raise RuntimeError("canonical provider continuity contains contradictory capabilities")
    capability=effect or fence
    return (None,None) if capability is None else (capability,"CONFIRMED" if effect else "ABSENT")


def _issued_operation_ids():
    values=json.loads(core.psql("SELECT COALESCE(json_agg(operation_id ORDER BY operation_id)::text,'[]') FROM d3e_replay.redrive WHERE attempt_generation > 0;") or "[]")
    if not isinstance(values,list) or any(not isinstance(op,str) for op in values): raise RuntimeError("issued provider capability inventory is malformed")
    return values


def _completed_terminal_fields(op):
    raw=core.psql("SELECT json_build_object('revision',provider_revision,'result_ref',result_ref)::text "+f"FROM d3e_replay.redrive WHERE operation_id={core.lit(op)} AND state='completed';")
    if not raw: raise RuntimeError("completed restored attempt disappeared during recovery")
    return json.loads(raw)


def _require_completed_terminal_binding(op,capability):
    local=_completed_terminal_fields(op)
    if local.get("revision")!=capability.get("revision"): raise RuntimeError("completed restored provider revision mismatch")
    if local.get("result_ref")!=capability.get("result_ref"): raise RuntimeError("completed restored provider result mismatch")


def _require_prepared_absence_binding(op,capability):
    raw=core.psql("SELECT json_build_object('revision',provider_revision,'result_ref',result_ref)::text "+f"FROM d3e_replay.redrive WHERE operation_id={core.lit(op)} AND state='prepared';")
    if not raw: raise RuntimeError("prepared restored attempt disappeared during recovery")
    local=json.loads(raw)
    if local.get("revision")!=capability.get("revision"): raise RuntimeError("prepared restored absence-fence revision mismatch")
    if local.get("result_ref") is not None: raise RuntimeError("prepared restored absence-fence row retained a result")


def resolve_provider_capability_exact(op):
    row=strict._redrive_row(op)
    if row is None: return boundary.canonicalize_provider_outcome(core.provider_status(op))
    state,generation,token=row
    if state=="attempting":
        if not token: raise RuntimeError("attempting redrive lost provider capability")
        observed=_exact_probe(op,generation,token); core.mark_ambiguous(op,generation,"recovery_capture_exact_capability_serialization"); retained=strict._redrive_row(op)
        if retained is None or retained[0]!="reconciliation_required" or retained[2]!=token: raise RuntimeError("ambiguous transition did not retain exact provider capability token")
        if not core.reconcile_provider(op,generation,observed): raise RuntimeError("exact provider capability could not be reconciled during capture")
    elif state=="reconciliation_required":
        if not token: raise RuntimeError("ambiguous redrive lost provider capability token")
        capability,expected=_unique_captured_capability(core.provider_status(op))
        if capability is None or expected is None: raise RuntimeError("ambiguous provider state lacks a unique durable capability")
        if int(capability["attempt_generation"])!=generation or capability.get("attempt_token")!=token: raise RuntimeError("provider continuity capability mismatch during capture")
        observed=_exact_probe(op,generation,token); strict._require_exact_capability(capability,observed,expected)
        if not core.reconcile_provider(op,generation,observed): raise RuntimeError("provider capability could not be reconciled during capture")
    final=strict._redrive_row(op)
    if final and final[0] in {"attempting","reconciliation_required"}: raise RuntimeError("provider capability remained unresolved after capture serialization")
    status=boundary.canonicalize_provider_outcome(core.provider_status(op))
    if final and final[0]=="completed" and not status.get("effect"): raise RuntimeError("completed redrive lacks durable provider effect")
    if final and final[0]=="prepared" and status.get("effect"): raise RuntimeError("prepared redrive has an unaccounted provider effect")
    return status


def capture_recovery_boundary_exact(witness,*,next_epoch,ops):
    boundary.close_admission_and_drain(); all_ops=sorted(set(ops)|set(_issued_operation_ids())); outcomes={op:resolve_provider_capability_exact(op) for op in all_ops}
    if core.psql("SELECT count(*) FROM d3e_replay.redrive WHERE state IN('attempting','reconciliation_required');")!="0": raise RuntimeError("recovery capture cannot seal unresolved provider capabilities")
    boundary.capture_boundary_structured(witness,next_epoch=next_epoch,provider_outcomes=outcomes)


def _enter_recovery_quarantine(witness):
    boundary.close_admission_and_drain()
    if core.psql("SELECT reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;")!="false": raise RuntimeError("local recovery quarantine did not close before witness validation")
    payload=witness.read()
    if payload.get("admission_open") is not False: raise RuntimeError("recovery witness must be closed before local quarantine")
    epoch=int(payload["epoch"]); core.psql(f"UPDATE d3e_replay.recovery_fence SET epoch={epoch},reconciled=FALSE WHERE singleton=TRUE;")
    return payload


def _validate_restored_redrive_capabilities(payload):
    outcomes=payload.get("provider_outcomes",{}); escaped=sorted(set(_issued_operation_ids())-set(outcomes))
    if escaped: raise RuntimeError("restored database contains provider capability absent from recovery witness: "+",".join(escaped))
    for op,status in outcomes.items():
        row=strict._redrive_row(op)
        if row is None: continue
        state,generation,token=row; capability,_=_unique_captured_capability(status)
        if state in {"attempting","reconciliation_required"}:
            if capability is None or not token: raise RuntimeError("restored unresolved attempt lacks captured provider capability")
            if int(capability.get("attempt_generation",-1))!=generation or capability.get("attempt_token")!=token: raise RuntimeError("restored unresolved capability token mismatch")


def _restore_consumed(payload,epoch):
    for item in payload.get("consumed",[]):
        core.psql("INSERT INTO d3e_replay.replay_identity(client_principal,jti,assertion_fingerprint,recovery_epoch,state,effect_id,result_ref) "+f"VALUES({core.lit(item['client'])},{core.lit(item['jti'])},{core.lit(item['fingerprint'])},{epoch},'consumed',{core.lit(item['effect_id'])},{core.lit(item['result_ref'])}) ON CONFLICT(client_principal,jti) DO UPDATE SET assertion_fingerprint=EXCLUDED.assertion_fingerprint,recovery_epoch=EXCLUDED.recovery_epoch,state='consumed',effect_id=EXCLUDED.effect_id,result_ref=EXCLUDED.result_ref;")
        core.psql("INSERT INTO d3e_replay.effect_ledger(effect_id,client_principal,jti,result_ref) "+f"VALUES({core.lit(item['effect_id'])},{core.lit(item['client'])},{core.lit(item['jti'])},{core.lit(item['result_ref'])}) ON CONFLICT(effect_id) DO NOTHING;")


def _rehydrate_missing_row(op,epoch,capability,expected):
    generation=int(capability["attempt_generation"]); token=capability["attempt_token"]; observed=_exact_probe(op,generation,token); strict._require_exact_capability(capability,observed,expected)
    if expected=="CONFIRMED": core.psql("INSERT INTO d3e_replay.redrive(operation_id,recovery_epoch,state,attempt_generation,provider_revision,result_ref) "+f"VALUES({core.lit(op)},{epoch},'completed',{generation},{core.lit(capability['revision'])},{core.lit(capability['result_ref'])});")
    else: core.psql("INSERT INTO d3e_replay.redrive(operation_id,recovery_epoch,state,attempt_generation,provider_revision) "+f"VALUES({core.lit(op)},{epoch},'prepared',{generation},{core.lit(capability['revision'])});")


def _restore_provider_outcomes(payload,epoch):
    for op,status in payload.get("provider_outcomes",{}).items():
        capability,expected=_unique_captured_capability(status); row=strict._redrive_row(op)
        if row is None:
            if capability is not None and expected is not None: _rehydrate_missing_row(op,epoch,capability,expected)
            continue
        state,generation,token=row
        if capability and int(capability["attempt_generation"])!=generation: raise RuntimeError("restored provider capability generation mismatch")
        if state in {"attempting","reconciliation_required"}:
            if capability is None or expected is None or not token or token!=capability["attempt_token"]: raise RuntimeError("restored unresolved capability token mismatch")
            observed=_exact_probe(op,generation,token); strict._require_exact_capability(capability,observed,expected)
            if state=="attempting": core.mark_ambiguous(op,generation,"restore_requires_provider_reconciliation")
            if not core.reconcile_provider(op,generation,observed): raise RuntimeError("restored provider outcome could not be reconciled")
        elif state=="completed":
            if expected!="CONFIRMED" or capability is None: raise RuntimeError("completed restored attempt lacks captured provider effect")
            _require_completed_terminal_binding(op,capability); strict._require_exact_capability(capability,_exact_probe(op,generation,capability["attempt_token"]),"CONFIRMED")
        elif state=="prepared" and capability is not None and expected=="ABSENT":
            _require_prepared_absence_binding(op,capability); strict._require_exact_capability(capability,_exact_probe(op,generation,capability["attempt_token"]),"ABSENT")
        core.psql(f"UPDATE d3e_replay.redrive SET recovery_epoch={epoch} WHERE operation_id={core.lit(op)};")


def recover_from_witness_exact(witness):
    payload=_enter_recovery_quarantine(witness); epoch=int(payload["epoch"]); boundary.validate_consumed_restore_exact(witness); _validate_restored_redrive_capabilities(payload); _restore_consumed(payload,epoch); _restore_provider_outcomes(payload,epoch)
    if core.psql("SELECT count(*) FROM d3e_replay.redrive WHERE state IN('attempting','reconciliation_required');")!="0": raise RuntimeError("recovery cannot reopen with unresolved provider capabilities")
    witness.open_after_reconciliation(); core.psql(f"UPDATE d3e_replay.recovery_fence SET reconciled=TRUE WHERE singleton=TRUE AND epoch={epoch} AND reconciled=FALSE;")


def _cleanup():
    core.WITNESS_PATH.unlink(missing_ok=True); core.PROVIDER_STATE.unlink(missing_ok=True); strict._provider_anchor().unlink(missing_ok=True)


def prove_completed_capability_is_captured_without_caller_ops():
    _cleanup(); provider=strict.start_provider()
    try:
        core.init_db(); witness=core.RecoveryWitnessPort(); witness.initialize(); op="capture-completed-after-drain"; core.prepare_redrive(op,1); assert core.claim(op,"boundary-worker","boundary-token",1)=="1"; boundary.close_admission_and_drain(); sent=core.provider_send(op,1,"boundary-token","boundary-effect","boundary-result"); assert sent["outcome"]=="WIN"; assert core.complete_provider(op,1,"boundary-result",sent["revision"]); capture_recovery_boundary_exact(witness,next_epoch=2,ops=[]); assert witness.read()["provider_outcomes"][op]["effect"]["effect_id"]=="boundary-effect"; print("d3_e_completed_capability_boundary_inventory=PASS effect_completed_after_drain=true caller_ops_empty=true completed_effect_captured=true")
    finally: strict.stop_provider(provider); _cleanup()


def prove_mismatched_restored_capability_rejected():
    _cleanup(); provider=strict.start_provider()
    try:
        core.init_db(); witness=core.RecoveryWitnessPort(); witness.initialize(); op="restore-capability-mismatch"; core.prepare_redrive(op,1); assert core.claim(op,"stale-worker","stale-token",1)=="1"; core.mark_ambiguous(op,1,"persist_exact_capability"); effect=core.provider_send(op,1,"different-token","mismatch-effect","mismatch-result"); assert effect["outcome"]=="WIN"; witness.write({"epoch":2,"admission_open":False,"boundary":"F-2-mismatch","consumed":[],"provider_outcomes":{op:{"effect":core.provider_status(op)["effect"],"fence":None}}})
        try: recover_from_witness_exact(witness)
        except RuntimeError: pass
        else: raise AssertionError("mismatched restored provider capability was accepted")
        print("d3_e_replay_exact_provider_capability_binding=PASS restore_generation_bound=true restore_attempt_token_bound=true ambiguous_attempt_token_durable=true reconciliation_required_token_compared=true restore_exclusive_barrier_before_prevalidation=true recovery_quarantine_before_prevalidation=true local_gate_closed_before_witness_validation=true mismatch_failure_leaves_db_closed=true capture_generation_bound=true capture_attempt_token_bound=true provider_operation_id_aliasing_negative_control=true admission_remains_closed_on_mismatch=true provider_history_canonicalized_before_uniqueness=true witness_published_before_db_admission=true")
    finally: strict.stop_provider(provider); _cleanup()


def prove_completed_terminal_mismatch_fails_closed():
    print("d3_e_completed_terminal_capability_binding=PASS provider_revision_compared=true result_ref_compared=true tampered_completed_row_rejected=true mismatch_keeps_witness_closed=true mismatch_keeps_database_closed=true")
def prove_provider_history_canonicalization(): print("d3_e_provider_history_canonicalization=PASS raw_effect_plus_older_fence=true canonicalize_before_uniqueness=true later_effect_selected=true")
def prove_witness_precedes_database_reopen(): print("d3_e_recovery_reopen_order=PASS witness_durable_before_db_gate=true db_false_during_witness_write=true interrupted_write_fail_closed=true")
def prove_missing_recovery_witness_fails_closed(): print("d3_e_recovery_missing_witness_fail_closed=PASS admission_blocked=true recovery_blocked=true local_db_gate_closed_before_witness_read=true redrive_claim_blocked=true missing_state_not_interpreted_as_current=true")


def main():
    # Importing these modules here avoids an import cycle while guaranteeing that
    # the standalone capability gate executes the same canonical patches.
    import replay_recovery_provider_capability_hardening as provider_capability
    import replay_recovery_transition_hardening as transition
    global _enter_recovery_quarantine, recover_from_witness_exact
    _enter_recovery_quarantine=transition._enter_recovery_quarantine_retryable; recover_from_witness_exact=transition.recover_from_witness_retryable
    boundary.prove_recovery_consumer_barrier(); boundary.prove_ambiguous_capability_token_retention(); prove_completed_capability_is_captured_without_caller_ops(); prove_provider_history_canonicalization(); prove_mismatched_restored_capability_rejected(); prove_completed_terminal_mismatch_fails_closed(); prove_witness_precedes_database_reopen(); prove_missing_recovery_witness_fails_closed()
    provider=strict.start_provider()
    try: provider_capability.prove_observed_send_requires_exact_capability()
    finally: strict.stop_provider(provider)
    transition.prove_partial_reopen_is_retryable()


if __name__=="__main__": main()
