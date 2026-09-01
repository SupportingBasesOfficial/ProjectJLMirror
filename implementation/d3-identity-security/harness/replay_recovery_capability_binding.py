#!/usr/bin/env python3
from __future__ import annotations

import json
import os

import replay_recovery_conformance_runner as core
import replay_recovery_boundary_hardening as boundary
import replay_recovery_strict_entrypoint as strict

# Capture the already-hardened restore implementation before the canonical
# entrypoint replaces the public hook with this exact-capability wrapper.
_ORIGINAL_RECOVER = strict.recover_from_witness_strict


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
    effect = status.get("effect")
    fence = status.get("fence")
    if effect and fence:
        raise RuntimeError("captured provider continuity contains effect and absence fence")
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


def resolve_provider_capability_exact(op: str) -> dict:
    row = strict._redrive_row(op)
    if row is None:
        return core.provider_status(op)
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
        status = core.provider_status(op)
        capability, expected = _unique_captured_capability(status)
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
    status = core.provider_status(op)
    if final and final[0] == "completed" and not status.get("effect"):
        raise RuntimeError("completed redrive lacks durable provider effect")
    if final and final[0] == "prepared" and status.get("effect"):
        raise RuntimeError("prepared redrive has an unaccounted provider effect")
    return status


def capture_recovery_boundary_exact(
    witness: core.RecoveryWitnessPort, *, next_epoch: int, ops: list[str]
) -> None:
    # The exclusive barrier drains all claims admitted under the old epoch and
    # closes admission. Once it returns, every capability already issued by the
    # DB is durably visible via attempt_generation>0. Include all of them in the
    # witness, even if a worker completed its external effect immediately after
    # the drain and changed local state from attempting to completed.
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
    boundary.capture_boundary_structured(
        witness, next_epoch=next_epoch, provider_outcomes=outcomes
    )


def _enter_recovery_quarantine(witness: core.RecoveryWitnessPort) -> dict:
    """Drain restored stale admissions before any recovery prevalidation.

    The surviving witness is trusted first only to establish that recovery is
    closed and to obtain its epoch. Before inspecting restored rows, acquire the
    *same exclusive advisory barrier* used at capture. This drains any consume or
    claim transaction that already read a rollbacked `reconciled=TRUE` fence and
    atomically closes that local fence. Only then is the local epoch advanced.
    """
    payload = witness.read()
    if payload.get("admission_open") is not False:
        raise RuntimeError("recovery witness must be closed before local quarantine")
    try:
        epoch = int(payload["epoch"])
    except Exception as exc:
        raise RuntimeError("recovery witness epoch is malformed") from exc
    if epoch <= 0:
        raise RuntimeError("recovery witness epoch is invalid")

    boundary.close_admission_and_drain()
    core.psql(
        f"UPDATE d3e_replay.recovery_fence SET epoch={epoch},reconciled=FALSE "
        "WHERE singleton=TRUE;"
    )
    state = core.psql(
        "SELECT epoch::text||'|'||reconciled::text "
        "FROM d3e_replay.recovery_fence WHERE singleton=TRUE;"
    )
    if state != f"{epoch}|false":
        raise RuntimeError("local recovery quarantine did not close admission")
    return payload


def _validate_restored_redrive_capabilities(witness: core.RecoveryWitnessPort) -> None:
    payload = witness.read()
    provider_outcomes = payload.get("provider_outcomes", {})
    if not isinstance(provider_outcomes, dict):
        raise RuntimeError("recovery witness provider outcomes are malformed")

    # Any local capability issued before the restored DB was quarantined must
    # have existed at the trusted recovery boundary. A rollbacked worker that
    # reclaims using stale `reconciled=TRUE` after F therefore cannot silently
    # create a new provider capability: its operation is absent from the witness
    # and recovery stays closed.
    issued = set(_issued_operation_ids())
    witnessed = set(provider_outcomes)
    escaped = sorted(issued - witnessed)
    if escaped:
        raise RuntimeError(
            "restored database contains provider capability absent from recovery witness: "
            + ",".join(escaped)
        )

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


def recover_from_witness_exact(witness: core.RecoveryWitnessPort) -> None:
    _enter_recovery_quarantine(witness)
    boundary.validate_consumed_restore_exact(witness)
    _validate_restored_redrive_capabilities(witness)
    _ORIGINAL_RECOVER(witness)


def prove_completed_capability_is_captured_without_caller_ops() -> None:
    """A post-drain completion remains part of the boundary by capability inventory."""
    core.WITNESS_PATH.unlink(missing_ok=True)
    core.PROVIDER_STATE.unlink(missing_ok=True)
    strict._provider_anchor().unlink(missing_ok=True)
    provider = strict.start_provider()
    try:
        core.init_db()
        witness = core.RecoveryWitnessPort()
        witness.initialize()
        op = "capture-completed-after-drain"
        core.prepare_redrive(op, 1)
        assert core.claim(op, "boundary-worker", "boundary-token", 1) == "1"

        # Simulate the precise race: claim committed before the drain returns;
        # provider effect and local completion happen immediately after admission
        # is closed, before the capture inventories issued capabilities.
        boundary.close_admission_and_drain()
        sent = core.provider_send(op, 1, "boundary-token", "boundary-effect", "boundary-result")
        assert sent["outcome"] == "WIN"
        assert core.complete_provider(op, 1, "boundary-result", sent["revision"])

        # The canonical capture is deliberately called with no caller-supplied op.
        capture_recovery_boundary_exact(witness, next_epoch=2, ops=[])
        captured = witness.read()["provider_outcomes"].get(op, {}).get("effect")
        if not captured or captured.get("effect_id") != "boundary-effect":
            raise RuntimeError("completed issued capability escaped recovery boundary")
        print(
            "d3_e_completed_capability_boundary_inventory=PASS "
            "claim_committed_before_drain=true effect_completed_after_drain=true "
            "caller_ops_empty=true issued_generation_inventory=true completed_effect_captured=true"
        )
    finally:
        strict.stop_provider(provider)
        core.WITNESS_PATH.unlink(missing_ok=True)
        core.PROVIDER_STATE.unlink(missing_ok=True)
        strict._provider_anchor().unlink(missing_ok=True)


def prove_mismatched_restored_capability_rejected() -> None:
    core.WITNESS_PATH.unlink(missing_ok=True)
    core.PROVIDER_STATE.unlink(missing_ok=True)
    strict._provider_anchor().unlink(missing_ok=True)
    provider = strict.start_provider()
    try:
        core.init_db()
        witness = core.RecoveryWitnessPort()
        witness.initialize()
        op = "restore-capability-mismatch"
        core.prepare_redrive(op, 1)
        assert core.claim(op, "stale-worker", "stale-token", 1) == "1"
        core.mark_ambiguous(op, 1, "persist_exact_capability")
        assert strict._redrive_row(op) == ("reconciliation_required", 1, "stale-token")

        effect = core.provider_send(
            op, 1, "different-token", "mismatch-effect", "mismatch-result"
        )
        assert effect["outcome"] == "WIN"
        witnessed_effect = core.provider_status(op)["effect"]
        witness.write({
            "epoch": 2,
            "admission_open": False,
            "boundary": "F-2-mismatch-negative-control",
            "consumed": [],
            "provider_outcomes": {op: {"effect": witnessed_effect, "fence": None}},
        })

        try:
            recover_from_witness_exact(witness)
        except RuntimeError as exc:
            assert "token mismatch" in str(exc) or "continuity mismatch" in str(exc)
        else:
            raise AssertionError("mismatched restored provider capability was accepted")
        assert witness.read()["admission_open"] is False
        assert core.psql(
            "SELECT epoch::text||'|'||reconciled::text "
            "FROM d3e_replay.recovery_fence WHERE singleton=TRUE;"
        ) == "2|false"

        witness.initialize()
        core.psql(
            "UPDATE d3e_replay.recovery_fence SET epoch=1,reconciled=TRUE WHERE singleton=TRUE;"
        )
        try:
            capture_recovery_boundary_exact(witness, next_epoch=2, ops=[op])
        except RuntimeError as exc:
            assert "token" in str(exc) or "capability" in str(exc)
        else:
            raise AssertionError("capture accepted provider outcome from a different capability")

        print(
            "d3_e_replay_exact_provider_capability_binding=PASS "
            "restore_generation_bound=true restore_attempt_token_bound=true "
            "ambiguous_attempt_token_durable=true reconciliation_required_token_compared=true "
            "restore_exclusive_barrier_before_prevalidation=true "
            "recovery_quarantine_before_prevalidation=true mismatch_failure_leaves_db_closed=true "
            "capture_generation_bound=true capture_attempt_token_bound=true "
            "provider_operation_id_aliasing_negative_control=true admission_remains_closed_on_mismatch=true"
        )
    finally:
        strict.stop_provider(provider)
        core.WITNESS_PATH.unlink(missing_ok=True)
        core.PROVIDER_STATE.unlink(missing_ok=True)
        strict._provider_anchor().unlink(missing_ok=True)
        os.environ.pop("D3E_UNUSED", None)


def prove_missing_recovery_witness_fails_closed() -> None:
    core.init_db()
    witness = core.RecoveryWitnessPort()
    witness.initialize()
    saved = witness.path.with_suffix(".missing-control")
    os.replace(witness.path, saved)
    try:
        port = core.ReplayAuthorityPort(witness)
        assert port.consume(
            "missing-witness-client", "missing-witness-jti", "fp", "effect", "result", 1
        ) == "BLOCKED"
        try:
            recover_from_witness_exact(witness)
        except RuntimeError:
            pass
        else:
            raise AssertionError("recovery opened without continuity witness")
    finally:
        os.replace(saved, witness.path)
    print(
        "d3_e_recovery_missing_witness_fail_closed=PASS "
        "admission_blocked=true recovery_blocked=true missing_state_not_interpreted_as_current=true"
    )


def main() -> None:
    boundary.prove_recovery_consumer_barrier()
    boundary.prove_ambiguous_capability_token_retention()
    prove_completed_capability_is_captured_without_caller_ops()
    prove_mismatched_restored_capability_rejected()
    prove_missing_recovery_witness_fails_closed()


if __name__ == "__main__":
    main()
