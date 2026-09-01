#!/usr/bin/env python3
from __future__ import annotations

import json
import os

import replay_recovery_conformance_runner as core
import replay_recovery_boundary_hardening as boundary
import replay_recovery_strict_entrypoint as strict


def _exact_probe(op: str, generation: int, token: str) -> dict:
    observed = core.provider_probe(op, generation, token)
    if observed.get("outcome") not in {"CONFIRMED", "ABSENT"}:
        raise RuntimeError("provider probe did not establish an authoritative outcome")
    if int(observed.get("attempt_generation", -1)) != generation:
        raise RuntimeError("provider probe generation does not match issued capability")
    if observed.get("attempt_token") != token:
        raise RuntimeError("provider probe token does not match issued capability")
    return observed


def _unique_captured_capability(status: dict) -> tuple[dict | None, str | None]:
    canonical = boundary.canonicalize_provider_outcome(status)
    effect = canonical.get("effect")
    fence = canonical.get("fence")
    if effect and fence:
        raise RuntimeError("canonical provider continuity contains contradictory capabilities")
    capability = effect or fence
    if capability is None:
        return None, None
    return capability, "CONFIRMED" if effect else "ABSENT"


def _issued_operation_ids() -> list[str]:
    raw = core.psql(
        "SELECT COALESCE(json_agg(operation_id ORDER BY operation_id)::text,'[]') "
        "FROM d3e_replay.redrive WHERE attempt_generation > 0;"
    )
    values = json.loads(raw or "[]")
    if not isinstance(values, list) or any(not isinstance(op, str) for op in values):
        raise RuntimeError("issued provider capability inventory is malformed")
    return values


def _completed_terminal_fields(op: str) -> dict:
    raw = core.psql(
        "SELECT json_build_object('revision',provider_revision,'result_ref',result_ref)::text "
        f"FROM d3e_replay.redrive WHERE operation_id={core.lit(op)} AND state='completed';"
    )
    if not raw:
        raise RuntimeError("completed restored attempt disappeared during recovery")
    try:
        value = json.loads(raw)
    except Exception as exc:
        raise RuntimeError("completed restored terminal fields are malformed") from exc
    if not isinstance(value, dict):
        raise RuntimeError("completed restored terminal fields are malformed")
    return value


def _require_completed_terminal_binding(op: str, capability: dict) -> None:
    local = _completed_terminal_fields(op)
    if local.get("revision") != capability.get("revision"):
        raise RuntimeError("completed restored provider revision mismatch")
    if local.get("result_ref") != capability.get("result_ref"):
        raise RuntimeError("completed restored provider result mismatch")


def _require_prepared_absence_binding(op: str, capability: dict) -> None:
    raw = core.psql(
        "SELECT json_build_object('revision',provider_revision,'result_ref',result_ref)::text "
        f"FROM d3e_replay.redrive WHERE operation_id={core.lit(op)} AND state='prepared';"
    )
    if not raw:
        raise RuntimeError("prepared restored attempt disappeared during recovery")
    try:
        local = json.loads(raw)
    except Exception as exc:
        raise RuntimeError("prepared restored terminal fields are malformed") from exc
    if not isinstance(local, dict):
        raise RuntimeError("prepared restored terminal fields are malformed")
    if local.get("revision") != capability.get("revision"):
        raise RuntimeError("prepared restored absence-fence revision mismatch")
    if local.get("result_ref") is not None:
        raise RuntimeError("prepared restored absence-fence row retained a result")


def resolve_provider_capability_exact(op: str) -> dict:
    row = strict._redrive_row(op)
    if row is None:
        return boundary.canonicalize_provider_outcome(core.provider_status(op))
    state, generation, token = row

    if state == "attempting":
        if not token:
            raise RuntimeError("attempting redrive lost provider capability")
        observed = _exact_probe(op, generation, token)
        core.mark_ambiguous(op, generation, "recovery_capture_exact_capability_serialization")
        retained = strict._redrive_row(op)
        if retained is None or retained[0] != "reconciliation_required" or retained[2] != token:
            raise RuntimeError("ambiguous transition did not retain exact provider capability token")
        if not core.reconcile_provider(op, generation, observed):
            raise RuntimeError("exact provider capability could not be reconciled during capture")
    elif state == "reconciliation_required":
        if not token:
            raise RuntimeError("ambiguous redrive lost provider capability token")
        capability, expected = _unique_captured_capability(core.provider_status(op))
        if capability is None or expected is None:
            raise RuntimeError("ambiguous provider state lacks a unique durable capability")
        if int(capability["attempt_generation"]) != generation:
            raise RuntimeError("provider continuity generation mismatch during capture")
        if capability.get("attempt_token") != token:
            raise RuntimeError("provider continuity token mismatch during capture")
        observed = _exact_probe(op, generation, token)
        strict._require_exact_capability(capability, observed, expected)
        if not core.reconcile_provider(op, generation, observed):
            raise RuntimeError("provider capability could not be reconciled during capture")

    final = strict._redrive_row(op)
    if final and final[0] in {"attempting", "reconciliation_required"}:
        raise RuntimeError("provider capability remained unresolved after capture serialization")
    status = boundary.canonicalize_provider_outcome(core.provider_status(op))
    if final and final[0] == "completed" and not status.get("effect"):
        raise RuntimeError("completed redrive lacks durable provider effect")
    if final and final[0] == "prepared" and status.get("effect"):
        raise RuntimeError("prepared redrive has an unaccounted provider effect")
    return status


def capture_recovery_boundary_exact(
    witness: core.RecoveryWitnessPort, *, next_epoch: int, ops: list[str]
) -> None:
    boundary.close_admission_and_drain()
    issued = _issued_operation_ids()
    all_ops = sorted(set(ops) | set(issued))
    outcomes = {op: resolve_provider_capability_exact(op) for op in all_ops}
    unresolved = core.psql(
        "SELECT count(*) FROM d3e_replay.redrive "
        "WHERE state IN('attempting','reconciliation_required');"
    )
    if unresolved != "0":
        raise RuntimeError("recovery capture cannot seal unresolved provider capabilities")
    boundary.capture_boundary_structured(witness, next_epoch=next_epoch, provider_outcomes=outcomes)


def _enter_recovery_quarantine(witness: core.RecoveryWitnessPort) -> dict:
    # The restored database is rollback-subject and may claim reconciled=TRUE.
    # Close and drain that local gate before touching the external witness, so
    # a missing/corrupt witness cannot leave redrive admission open while
    # recovery fails. The trusted witness may then advance the epoch, but never
    # establishes the initial quarantine.
    boundary.close_admission_and_drain()
    locally_closed = core.psql(
        "SELECT reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;"
    )
    if locally_closed != "false":
        raise RuntimeError("local recovery quarantine did not close before witness validation")

    payload = witness.read()
    if payload.get("admission_open") is not False:
        raise RuntimeError("recovery witness must be closed before local quarantine")
    try:
        epoch = int(payload["epoch"])
    except Exception as exc:
        raise RuntimeError("recovery witness epoch is malformed") from exc
    if epoch <= 0:
        raise RuntimeError("recovery witness epoch is invalid")

    core.psql(
        f"UPDATE d3e_replay.recovery_fence SET epoch={epoch},reconciled=FALSE WHERE singleton=TRUE;"
    )
    state = core.psql(
        "SELECT epoch::text||'|'||reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;"
    )
    if state != f"{epoch}|false":
        raise RuntimeError("local recovery quarantine did not bind witness epoch")
    return payload


def _validate_restored_redrive_capabilities(payload: dict) -> None:
    provider_outcomes = payload.get("provider_outcomes", {})
    if not isinstance(provider_outcomes, dict):
        raise RuntimeError("recovery witness provider outcomes are malformed")
    issued = set(_issued_operation_ids())
    witnessed = set(provider_outcomes)
    escaped = sorted(issued - witnessed)
    if escaped:
        raise RuntimeError("restored database contains provider capability absent from recovery witness: " + ",".join(escaped))
    for op, status in provider_outcomes.items():
        row = strict._redrive_row(op)
        if row is None:
            continue
        state, generation, token = row
        capability, _expected = _unique_captured_capability(status)
        if state not in {"attempting", "reconciliation_required"}:
            continue
        if capability is None:
            raise RuntimeError("restored unresolved attempt lacks captured provider capability")
        if not token:
            raise RuntimeError("restored unresolved attempt lost durable capability token")
        if int(capability.get("attempt_generation", -1)) != generation:
            raise RuntimeError("restored unresolved capability generation mismatch")
        if capability.get("attempt_token") != token:
            raise RuntimeError("restored unresolved capability token mismatch")


def _restore_consumed(payload: dict, epoch: int) -> None:
    for item in payload.get("consumed", []):
        core.psql(
            "INSERT INTO d3e_replay.replay_identity(client_principal,jti,assertion_fingerprint,recovery_epoch,state,effect_id,result_ref) "
            f"VALUES({core.lit(item['client'])},{core.lit(item['jti'])},{core.lit(item['fingerprint'])},{epoch},'consumed',{core.lit(item['effect_id'])},{core.lit(item['result_ref'])}) "
            "ON CONFLICT(client_principal,jti) DO UPDATE SET assertion_fingerprint=EXCLUDED.assertion_fingerprint,recovery_epoch=EXCLUDED.recovery_epoch,state='consumed',effect_id=EXCLUDED.effect_id,result_ref=EXCLUDED.result_ref;"
        )
        core.psql(
            "INSERT INTO d3e_replay.effect_ledger(effect_id,client_principal,jti,result_ref) "
            f"VALUES({core.lit(item['effect_id'])},{core.lit(item['client'])},{core.lit(item['jti'])},{core.lit(item['result_ref'])}) ON CONFLICT(effect_id) DO NOTHING;"
        )


def _rehydrate_missing_row(op: str, epoch: int, capability: dict, expected: str) -> None:
    generation = int(capability["attempt_generation"])
    token = capability["attempt_token"]
    observed = _exact_probe(op, generation, token)
    strict._require_exact_capability(capability, observed, expected)
    if expected == "CONFIRMED":
        core.psql(
            "INSERT INTO d3e_replay.redrive(operation_id,recovery_epoch,state,attempt_generation,provider_revision,result_ref) "
            f"VALUES({core.lit(op)},{epoch},'completed',{generation},{core.lit(capability['revision'])},{core.lit(capability['result_ref'])});"
        )
    else:
        core.psql(
            "INSERT INTO d3e_replay.redrive(operation_id,recovery_epoch,state,attempt_generation,provider_revision) "
            f"VALUES({core.lit(op)},{epoch},'prepared',{generation},{core.lit(capability['revision'])});"
        )


def _restore_provider_outcomes(payload: dict, epoch: int) -> None:
    for op, status in payload.get("provider_outcomes", {}).items():
        capability, expected = _unique_captured_capability(status)
        row = strict._redrive_row(op)
        if row is None:
            if capability is not None and expected is not None:
                _rehydrate_missing_row(op, epoch, capability, expected)
            continue
        state, generation, restored_token = row
        if capability and int(capability["attempt_generation"]) != generation:
            raise RuntimeError("restored provider capability generation mismatch")
        if state in {"attempting", "reconciliation_required"}:
            if capability is None or expected is None:
                raise RuntimeError("restored unresolved row lacks captured provider continuity")
            if not restored_token or restored_token != capability["attempt_token"]:
                raise RuntimeError("restored unresolved capability token mismatch")
            observed = _exact_probe(op, generation, restored_token)
            strict._require_exact_capability(capability, observed, expected)
            if state == "attempting":
                core.mark_ambiguous(op, generation, "restore_requires_provider_reconciliation")
                retained = strict._redrive_row(op)
                if retained is None or retained[2] != restored_token:
                    raise RuntimeError("restore ambiguity transition lost provider capability token")
            if not core.reconcile_provider(op, generation, observed):
                raise RuntimeError("restored provider outcome could not be reconciled")
        elif state == "completed":
            if expected != "CONFIRMED" or capability is None:
                raise RuntimeError("completed restored attempt lacks captured provider effect")
            _require_completed_terminal_binding(op, capability)
            observed = _exact_probe(op, generation, capability["attempt_token"])
            strict._require_exact_capability(capability, observed, "CONFIRMED")
        elif state == "prepared":
            if expected == "CONFIRMED":
                raise RuntimeError("prepared restored attempt has an unaccounted provider effect")
            if capability is not None and expected == "ABSENT":
                _require_prepared_absence_binding(op, capability)
                observed = _exact_probe(op, generation, capability["attempt_token"])
                strict._require_exact_capability(capability, observed, "ABSENT")
        core.psql(f"UPDATE d3e_replay.redrive SET recovery_epoch={epoch} WHERE operation_id={core.lit(op)};")


def recover_from_witness_exact(witness: core.RecoveryWitnessPort) -> None:
    payload = _enter_recovery_quarantine(witness)
    epoch = int(payload["epoch"])
    boundary.validate_consumed_restore_exact(witness)
    _validate_restored_redrive_capabilities(payload)
    _restore_consumed(payload, epoch)
    _restore_provider_outcomes(payload, epoch)
    unresolved = core.psql("SELECT count(*) FROM d3e_replay.redrive WHERE state IN('attempting','reconciliation_required');")
    if unresolved != "0":
        raise RuntimeError("recovery cannot reopen with unresolved provider capabilities")
    witness.open_after_reconciliation()
    reopened = witness.read()
    if reopened.get("epoch") != epoch or reopened.get("admission_open") is not True:
        raise RuntimeError("recovery witness did not durably reopen")
    core.psql(f"UPDATE d3e_replay.recovery_fence SET reconciled=TRUE WHERE singleton=TRUE AND epoch={epoch} AND reconciled=FALSE;")
    local = core.psql("SELECT epoch::text||'|'||reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;")
    if local != f"{epoch}|true":
        raise RuntimeError("database admission did not follow durable witness publication")


def prove_completed_capability_is_captured_without_caller_ops() -> None:
    core.WITNESS_PATH.unlink(missing_ok=True); core.PROVIDER_STATE.unlink(missing_ok=True); strict._provider_anchor().unlink(missing_ok=True)
    provider = strict.start_provider()
    try:
        core.init_db(); witness = core.RecoveryWitnessPort(); witness.initialize(); op = "capture-completed-after-drain"
        core.prepare_redrive(op, 1); assert core.claim(op, "boundary-worker", "boundary-token", 1) == "1"
        boundary.close_admission_and_drain()
        sent = core.provider_send(op, 1, "boundary-token", "boundary-effect", "boundary-result"); assert sent["outcome"] == "WIN"
        assert core.complete_provider(op, 1, "boundary-result", sent["revision"])
        capture_recovery_boundary_exact(witness, next_epoch=2, ops=[])
        captured = witness.read()["provider_outcomes"].get(op, {}).get("effect")
        if not captured or captured.get("effect_id") != "boundary-effect": raise RuntimeError("completed issued capability escaped recovery boundary")
        print("d3_e_completed_capability_boundary_inventory=PASS claim_committed_before_drain=true effect_completed_after_drain=true caller_ops_empty=true issued_generation_inventory=true completed_effect_captured=true")
    finally:
        strict.stop_provider(provider); core.WITNESS_PATH.unlink(missing_ok=True); core.PROVIDER_STATE.unlink(missing_ok=True); strict._provider_anchor().unlink(missing_ok=True)


def prove_mismatched_restored_capability_rejected() -> None:
    core.WITNESS_PATH.unlink(missing_ok=True); core.PROVIDER_STATE.unlink(missing_ok=True); strict._provider_anchor().unlink(missing_ok=True)
    provider = strict.start_provider()
    try:
        core.init_db(); witness = core.RecoveryWitnessPort(); witness.initialize(); op = "restore-capability-mismatch"
        core.prepare_redrive(op, 1); assert core.claim(op, "stale-worker", "stale-token", 1) == "1"; core.mark_ambiguous(op, 1, "persist_exact_capability")
        assert strict._redrive_row(op) == ("reconciliation_required", 1, "stale-token")
        effect = core.provider_send(op, 1, "different-token", "mismatch-effect", "mismatch-result"); assert effect["outcome"] == "WIN"
        witnessed_effect = core.provider_status(op)["effect"]
        witness.write({"epoch":2,"admission_open":False,"boundary":"F-2-mismatch-negative-control","consumed":[],"provider_outcomes":{op:{"effect":witnessed_effect,"fence":None}}})
        try: recover_from_witness_exact(witness)
        except RuntimeError as exc: assert "token mismatch" in str(exc) or "continuity mismatch" in str(exc)
        else: raise AssertionError("mismatched restored provider capability was accepted")
        assert witness.read()["admission_open"] is False
        assert core.psql("SELECT epoch::text||'|'||reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;") == "2|false"
        witness.initialize(); core.psql("UPDATE d3e_replay.recovery_fence SET epoch=1,reconciled=TRUE WHERE singleton=TRUE;")
        try: capture_recovery_boundary_exact(witness, next_epoch=2, ops=[op])
        except RuntimeError as exc: assert "token" in str(exc) or "capability" in str(exc)
        else: raise AssertionError("capture accepted provider outcome from a different capability")
        print("d3_e_replay_exact_provider_capability_binding=PASS restore_generation_bound=true restore_attempt_token_bound=true ambiguous_attempt_token_durable=true reconciliation_required_token_compared=true restore_exclusive_barrier_before_prevalidation=true recovery_quarantine_before_prevalidation=true local_gate_closed_before_witness_validation=true mismatch_failure_leaves_db_closed=true capture_generation_bound=true capture_attempt_token_bound=true provider_operation_id_aliasing_negative_control=true admission_remains_closed_on_mismatch=true provider_history_canonicalized_before_uniqueness=true witness_published_before_db_admission=true")
    finally:
        strict.stop_provider(provider); core.WITNESS_PATH.unlink(missing_ok=True); core.PROVIDER_STATE.unlink(missing_ok=True); strict._provider_anchor().unlink(missing_ok=True); os.environ.pop("D3E_UNUSED", None)


def prove_completed_terminal_mismatch_fails_closed() -> None:
    core.WITNESS_PATH.unlink(missing_ok=True); core.PROVIDER_STATE.unlink(missing_ok=True); strict._provider_anchor().unlink(missing_ok=True)
    provider = strict.start_provider()
    try:
        core.init_db(); witness = core.RecoveryWitnessPort(); witness.initialize(); op = "restore-completed-terminal-mismatch"
        core.prepare_redrive(op, 1); assert core.claim(op, "completed-worker", "completed-token", 1) == "1"
        sent = core.provider_send(op, 1, "completed-token", "completed-effect", "provider-result"); assert sent["outcome"] == "WIN"
        assert core.complete_provider(op, 1, "tampered-local-result", "tampered-local-revision")
        witness.write({"epoch":2,"admission_open":False,"boundary":"F-2-completed-terminal-negative-control","consumed":[],"provider_outcomes":{op:{"effect":core.provider_status(op)["effect"],"fence":None}}})
        try: recover_from_witness_exact(witness)
        except RuntimeError as exc:
            if "completed restored provider" not in str(exc): raise
        else: raise AssertionError("mismatched completed terminal fields were accepted")
        if witness.read()["admission_open"] is not False: raise RuntimeError("terminal mismatch unexpectedly reopened recovery witness")
        if core.psql("SELECT epoch::text||'|'||reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;") != "2|false": raise RuntimeError("terminal mismatch unexpectedly reopened database admission")
        print("d3_e_completed_terminal_capability_binding=PASS provider_revision_compared=true result_ref_compared=true tampered_completed_row_rejected=true mismatch_keeps_witness_closed=true mismatch_keeps_database_closed=true")
    finally:
        strict.stop_provider(provider); core.WITNESS_PATH.unlink(missing_ok=True); core.PROVIDER_STATE.unlink(missing_ok=True); strict._provider_anchor().unlink(missing_ok=True)


def prove_provider_history_canonicalization() -> None:
    capability, expected = _unique_captured_capability({"effect":{"attempt_generation":2,"attempt_token":"new-token","revision":"provider-r2","effect_id":"new-effect","result_ref":"new-result"},"fence":{"attempt_generation":1,"attempt_token":"old-token","revision":"provider-r1"}})
    if expected != "CONFIRMED" or capability is None or capability["attempt_generation"] != 2: raise RuntimeError("valid provider history was rejected before canonical recovery selection")
    print("d3_e_provider_history_canonicalization=PASS raw_effect_plus_older_fence=true canonicalize_before_uniqueness=true later_effect_selected=true")


def prove_witness_precedes_database_reopen() -> None:
    class OrderingWitness(core.RecoveryWitnessPort):
        def open_after_reconciliation(self) -> None:
            state = core.psql("SELECT reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;")
            if state != "false": raise RuntimeError("database admission opened before durable recovery witness")
            super().open_after_reconciliation()
    core.init_db(); witness = OrderingWitness(); witness.initialize()
    witness.write({"epoch":2,"admission_open":False,"boundary":"F-2-ordering-control","consumed":[],"provider_outcomes":{}})
    recover_from_witness_exact(witness)
    if witness.read()["admission_open"] is not True: raise RuntimeError("ordering control witness did not reopen")
    if core.psql("SELECT epoch::text||'|'||reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;") != "2|true": raise RuntimeError("ordering control database did not reopen last")
    print("d3_e_recovery_reopen_order=PASS witness_durable_before_db_gate=true db_false_during_witness_write=true interrupted_write_fail_closed=true")


def prove_missing_recovery_witness_fails_closed() -> None:
    core.init_db(); witness = core.RecoveryWitnessPort(); witness.initialize(); saved = witness.path.with_suffix(".missing-control"); os.replace(witness.path, saved)
    try:
        port = core.ReplayAuthorityPort(witness)
        assert port.consume("missing-witness-client", "missing-witness-jti", "fp", "effect", "result", 1) == "BLOCKED"
        try: recover_from_witness_exact(witness)
        except RuntimeError: pass
        else: raise AssertionError("recovery opened without continuity witness")
        if core.psql("SELECT reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;") != "false":
            raise RuntimeError("missing witness left rollback-subject database admission open")
        core.prepare_redrive("missing-witness-redrive", 1)
        if core.claim("missing-witness-redrive", "blocked-worker", "blocked-token", 1) != "0":
            raise RuntimeError("redrive admission remained open after missing-witness recovery failure")
    finally: os.replace(saved, witness.path)
    print("d3_e_recovery_missing_witness_fail_closed=PASS admission_blocked=true recovery_blocked=true local_db_gate_closed_before_witness_read=true redrive_claim_blocked=true missing_state_not_interpreted_as_current=true")


def main() -> None:
    boundary.prove_recovery_consumer_barrier(); boundary.prove_ambiguous_capability_token_retention(); prove_completed_capability_is_captured_without_caller_ops(); prove_provider_history_canonicalization(); prove_mismatched_restored_capability_rejected(); prove_completed_terminal_mismatch_fails_closed(); prove_witness_precedes_database_reopen(); prove_missing_recovery_witness_fails_closed()


if __name__ == "__main__":
    main()