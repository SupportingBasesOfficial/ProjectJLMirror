#!/usr/bin/env python3
from __future__ import annotations

import json
import os

import replay_recovery_conformance_runner as core
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
        if not core.reconcile_provider(op, generation, observed):
            raise RuntimeError("exact provider capability could not be reconciled during capture")
    elif state == "reconciliation_required":
        status = core.provider_status(op)
        effect = status.get("effect")
        fence = status.get("fence")
        if bool(effect) == bool(fence):
            raise RuntimeError("ambiguous provider state lacks a unique durable capability")
        capability = effect or fence
        generation_expected = int(capability["attempt_generation"])
        if generation_expected != generation:
            raise RuntimeError("provider continuity generation mismatch during capture")
        observed = _exact_probe(op, generation, capability["attempt_token"])
        strict._require_exact_capability(
            capability, observed, "CONFIRMED" if effect else "ABSENT"
        )
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
    core.psql("UPDATE d3e_replay.recovery_fence SET reconciled=FALSE WHERE singleton=TRUE;")
    outstanding_raw = core.psql(
        "SELECT COALESCE(json_agg(operation_id ORDER BY operation_id)::text,'[]') "
        "FROM d3e_replay.redrive WHERE state IN('attempting','reconciliation_required');"
    )
    outstanding = json.loads(outstanding_raw or "[]")
    all_ops = sorted(set(ops) | set(outstanding))
    outcomes = {op: resolve_provider_capability_exact(op) for op in all_ops}
    unresolved = core.psql(
        "SELECT count(*) FROM d3e_replay.redrive "
        "WHERE state IN('attempting','reconciliation_required');"
    )
    if unresolved != "0":
        raise RuntimeError("recovery capture cannot seal unresolved provider capabilities")
    witness.capture_boundary(next_epoch=next_epoch, provider_outcomes=outcomes)


def recover_from_witness_exact(witness: core.RecoveryWitnessPort) -> None:
    _ORIGINAL_RECOVER(witness)


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

        # Deliberately create an external outcome for the same operation and
        # generation but a different issued capability token.
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
            "SELECT reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;"
        ) == "false"

        # The same provider aliasing must be rejected while capturing a boundary.
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
    prove_mismatched_restored_capability_rejected()
    prove_missing_recovery_witness_fails_closed()


if __name__ == "__main__":
    main()
