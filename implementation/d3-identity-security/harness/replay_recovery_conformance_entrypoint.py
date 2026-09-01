#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path

import replay_recovery_conformance_runner as core


_PROVIDER_STATE_KEY = os.environ.get(
    "D3E_PROVIDER_STATE_KEY", "d3e-test-external-provider-state-key"
).encode()
_PROVIDER_ANCHOR_TEXT = "jlmirror-d3e-external-provider-provisioned-v1\n"


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


class DurableProviderState:
    """Restart-safe external-effect state with fail-closed continuity.

    The provider remains a test double for a real external authority, but its
    effect/fence truth is no longer process memory. A restarted provider loads
    the sealed state file; an established state file that disappears or fails
    integrity validation cannot silently bootstrap empty.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.anchor_path = Path(str(self.path) + ".provisioned")
        self.lock = core.threading.Lock()
        self.effects: dict[str, dict]
        self.fences: dict[str, dict]
        self.revision: int

        if self.path.exists():
            self._load()
            return
        if self.anchor_path.exists():
            raise RuntimeError("provisioned external provider state is missing")

        self._atomic_write(self.anchor_path, _PROVIDER_ANCHOR_TEXT)
        self.effects = {}
        self.fences = {}
        self.revision = 0
        self.persist()

    def _seal(self, payload: dict) -> str:
        return hmac.new(_PROVIDER_STATE_KEY, _canonical_json(payload), hashlib.sha256).hexdigest()

    def _atomic_write(self, path: Path, text: str) -> None:
        tmp = Path(str(path) + ".tmp")
        tmp.write_text(text)
        os.replace(tmp, path)

    def _load(self) -> None:
        if not self.anchor_path.exists() or self.anchor_path.read_text() != _PROVIDER_ANCHOR_TEXT:
            raise RuntimeError("external provider provisioning anchor invalid")
        try:
            envelope = json.loads(self.path.read_text())
            payload = envelope["payload"]
            supplied = envelope["mac"]
            effects = payload["effects"]
            fences = payload["fences"]
            revision = payload["revision"]
        except Exception as exc:
            raise RuntimeError("malformed external provider state") from exc
        if (
            payload.get("version") != 1
            or not isinstance(effects, dict)
            or not isinstance(fences, dict)
            or type(revision) is not int
            or revision < 0
            or not isinstance(supplied, str)
        ):
            raise RuntimeError("malformed external provider state")
        if not hmac.compare_digest(supplied, self._seal(payload)):
            raise RuntimeError("external provider state integrity failure")
        self.effects = dict(effects)
        self.fences = dict(fences)
        self.revision = revision

    def next_revision(self) -> str:
        self.revision += 1
        return f"provider-r{self.revision}"

    def persist(self) -> None:
        payload = {
            "version": 1,
            "effects": self.effects,
            "fences": self.fences,
            "revision": self.revision,
        }
        envelope = {"payload": payload, "mac": self._seal(payload)}
        self._atomic_write(self.path, json.dumps(envelope, sort_keys=True))


def durable_provider_server() -> None:
    core.ProviderState = DurableProviderState
    core.provider_server()


def _provider_anchor() -> Path:
    return Path(str(core.PROVIDER_STATE) + ".provisioned")


def start_provider() -> core.subprocess.Popen:
    proc = core.subprocess.Popen(
        [core.sys.executable, __file__, "--durable-provider-server"],
        stdout=core.subprocess.DEVNULL,
        stderr=core.subprocess.DEVNULL,
    )
    core.wait_provider()
    return proc


def stop_provider(proc: core.subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except core.subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


def restart_provider(proc: core.subprocess.Popen) -> core.subprocess.Popen:
    stop_provider(proc)
    return start_provider()


def _redrive_row(op: str) -> tuple[str, int, str] | None:
    raw = core.psql(
        "SELECT state||'|'||attempt_generation||'|'||COALESCE(attempt_token,'') "
        f"FROM d3e_replay.redrive WHERE operation_id={core.lit(op)};"
    )
    if not raw:
        return None
    state, gen_text, token = raw.split("|", 2)
    return state, int(gen_text), token


def _resolve_provider_capability_before_capture(op: str) -> dict:
    row = _redrive_row(op)
    if row is None:
        return core.provider_status(op)
    state, generation, token = row

    if state == "attempting":
        if not token:
            raise RuntimeError("attempting redrive lost provider capability before recovery capture")
        outcome = core.provider_probe(op, generation, token)
        core.mark_ambiguous(op, generation, "recovery_capture_provider_serialization")
        if not core.reconcile_provider(op, generation, outcome):
            raise RuntimeError("recovery capture could not reconcile provider capability")
    elif state == "reconciliation_required":
        status = core.provider_status(op)
        capability = status.get("effect") or status.get("fence")
        if not capability:
            raise RuntimeError("ambiguous provider capability has no durable effect or absence fence")
        if int(capability["attempt_generation"]) != generation:
            raise RuntimeError("provider continuity generation mismatch during recovery capture")
        outcome = core.provider_probe(op, generation, capability["attempt_token"])
        if not core.reconcile_provider(op, generation, outcome):
            raise RuntimeError("ambiguous provider capability could not be reconciled before capture")

    final = _redrive_row(op)
    if final and final[0] in {"attempting", "reconciliation_required"}:
        raise RuntimeError("provider capability remained in flight after recovery serialization")
    status = core.provider_status(op)
    if final and final[0] == "completed" and not status.get("effect"):
        raise RuntimeError("completed redrive lacks durable external provider effect")
    if final and final[0] == "prepared" and status.get("effect"):
        raise RuntimeError("prepared redrive has an unaccounted external provider effect")
    return status


def capture_recovery_boundary_strict(
    witness: core.RecoveryWitnessPort, *, next_epoch: int, ops: list[str]
) -> None:
    # Close new claims/admission first. Every already-issued provider capability
    # is then serialized at the provider itself: either its effect is confirmed,
    # or provider_probe installs a durable absence fence that blocks a late send.
    core.psql("UPDATE d3e_replay.recovery_fence SET reconciled=FALSE WHERE singleton=TRUE;")

    outstanding_raw = core.psql(
        "SELECT COALESCE(json_agg(operation_id ORDER BY operation_id)::text,'[]') "
        "FROM d3e_replay.redrive WHERE state IN('attempting','reconciliation_required');"
    )
    outstanding = json.loads(outstanding_raw or "[]")
    all_ops = sorted(set(ops) | set(outstanding))
    outcomes = {op: _resolve_provider_capability_before_capture(op) for op in all_ops}

    unresolved = core.psql(
        "SELECT count(*) FROM d3e_replay.redrive "
        "WHERE state IN('attempting','reconciliation_required');"
    )
    if unresolved != "0":
        raise RuntimeError("recovery witness cannot capture unresolved provider capabilities")
    witness.capture_boundary(next_epoch=next_epoch, provider_outcomes=outcomes)


def recover_from_witness_strict(witness: core.RecoveryWitnessPort) -> None:
    payload = witness.read()
    epoch = int(payload["epoch"])
    if payload["admission_open"] is not False:
        raise RuntimeError("recovery witness must be closed during reconciliation")

    core.psql(
        f"UPDATE d3e_replay.recovery_fence SET epoch={epoch},reconciled=FALSE WHERE singleton=TRUE;"
    )
    for item in payload["consumed"]:
        prior = core.psql(
            "SELECT assertion_fingerprint||'|'||effect_id||'|'||result_ref "
            "FROM d3e_replay.replay_identity "
            f"WHERE client_principal={core.lit(item['client'])} AND jti={core.lit(item['jti'])};"
        )
        expected = f"{item['fingerprint']}|{item['effect_id']}|{item['result_ref']}"
        if prior and prior != expected:
            raise RuntimeError("recovery continuity conflicts with restored replay identity")
        core.psql(
            "INSERT INTO d3e_replay.replay_identity("
            "client_principal,jti,assertion_fingerprint,recovery_epoch,state,effect_id,result_ref) "
            f"VALUES({core.lit(item['client'])},{core.lit(item['jti'])},{core.lit(item['fingerprint'])},"
            f"{epoch},'consumed',{core.lit(item['effect_id'])},{core.lit(item['result_ref'])}) "
            "ON CONFLICT(client_principal,jti) DO UPDATE SET "
            "assertion_fingerprint=EXCLUDED.assertion_fingerprint,recovery_epoch=EXCLUDED.recovery_epoch,"
            "state='consumed',effect_id=EXCLUDED.effect_id,result_ref=EXCLUDED.result_ref;"
        )
        core.psql(
            "INSERT INTO d3e_replay.effect_ledger(effect_id,client_principal,jti,result_ref) "
            f"VALUES({core.lit(item['effect_id'])},{core.lit(item['client'])},"
            f"{core.lit(item['jti'])},{core.lit(item['result_ref'])}) "
            "ON CONFLICT(effect_id) DO NOTHING;"
        )

    for op, witnessed_status in payload["provider_outcomes"].items():
        row = _redrive_row(op)
        if row is None:
            continue
        state, generation, _token = row
        effect = witnessed_status.get("effect")
        fence = witnessed_status.get("fence")

        if state == "attempting":
            core.mark_ambiguous(op, generation, "restore_requires_provider_reconciliation")
            state = "reconciliation_required"

        if state == "reconciliation_required":
            capability = effect or fence
            if not capability:
                raise RuntimeError("restored ambiguous attempt lacks captured provider continuity")
            if int(capability["attempt_generation"]) != generation:
                raise RuntimeError("restored provider capability generation mismatch")
            probe = core.provider_probe(op, generation, capability["attempt_token"])
            expected_outcome = "CONFIRMED" if effect else "ABSENT"
            if probe.get("outcome") != expected_outcome:
                raise RuntimeError("provider state diverged from captured recovery continuity")
            if not core.reconcile_provider(op, generation, probe):
                raise RuntimeError("restored provider outcome could not be reconciled")
            state = "completed" if expected_outcome == "CONFIRMED" else "prepared"
        elif state == "completed":
            if not effect:
                raise RuntimeError("completed restored attempt lacks captured provider effect")
            probe = core.provider_probe(
                op, int(effect["attempt_generation"]), effect["attempt_token"]
            )
            if probe.get("outcome") != "CONFIRMED":
                raise RuntimeError("completed provider effect was not durable across recovery")
        elif state == "prepared":
            if effect:
                raise RuntimeError("prepared restored attempt has an unaccounted provider effect")
            if fence:
                probe = core.provider_probe(
                    op, int(fence["attempt_generation"]), fence["attempt_token"]
                )
                if probe.get("outcome") != "ABSENT":
                    raise RuntimeError("captured provider absence fence was not durable")

        core.psql(
            f"UPDATE d3e_replay.redrive SET recovery_epoch={epoch} "
            f"WHERE operation_id={core.lit(op)};"
        )

    unresolved = core.psql(
        "SELECT count(*) FROM d3e_replay.redrive "
        "WHERE state IN('attempting','reconciliation_required');"
    )
    if unresolved != "0":
        raise RuntimeError("recovery cannot reopen with unresolved provider capabilities")
    core.psql(
        f"UPDATE d3e_replay.recovery_fence SET reconciled=TRUE "
        f"WHERE singleton=TRUE AND epoch={epoch};"
    )
    witness.open_after_reconciliation()


def restore_entire_database(stale_dump: str) -> None:
    core.psql("DROP DATABASE d3 WITH (FORCE);", db="postgres")
    core.psql("CREATE DATABASE d3;", db="postgres")
    core.psql_script(stale_dump, db="d3")


def prove_provider_restart_durability(
    provider_proc: core.subprocess.Popen,
) -> core.subprocess.Popen:
    effect_op = "provider-restart-effect"
    core.prepare_redrive(effect_op, 1)
    assert core.claim(effect_op, "restart-worker", "restart-token", 1) == "1"
    ambiguous = core.provider_send(
        effect_op,
        1,
        "restart-token",
        "restart-effect",
        "restart-result",
        drop=True,
    )
    assert ambiguous["outcome"] == "AMBIGUOUS"

    provider_proc = restart_provider(provider_proc)
    status = core.provider_status(effect_op)
    assert status["effect"]["effect_id"] == "restart-effect"
    core.mark_ambiguous(effect_op, 1, "lost_response_before_provider_restart")
    probe = core.provider_probe(effect_op, 1, "restart-token")
    assert probe["outcome"] == "CONFIRMED"
    assert core.reconcile_provider(effect_op, 1, probe)

    fence_op = "provider-restart-fence"
    core.prepare_redrive(fence_op, 1)
    assert core.claim(fence_op, "fence-worker", "fence-token", 1) == "1"
    absent = core.provider_probe(fence_op, 1, "fence-token")
    assert absent["outcome"] == "ABSENT"

    provider_proc = restart_provider(provider_proc)
    assert core.provider_send(
        fence_op, 1, "fence-token", "forbidden-late-effect", "forbidden-result"
    )["outcome"] == "BLOCKED"
    core.mark_ambiguous(fence_op, 1, "absence_fence_survived_provider_restart")
    absent_after_restart = core.provider_probe(fence_op, 1, "fence-token")
    assert absent_after_restart["outcome"] == "ABSENT"
    assert core.reconcile_provider(fence_op, 1, absent_after_restart)

    stop_provider(provider_proc)
    loaded = DurableProviderState(core.PROVIDER_STATE)
    assert loaded.effects[effect_op]["effect_id"] == "restart-effect"
    assert loaded.fences[fence_op]["attempt_token"] == "fence-token"

    original = core.PROVIDER_STATE.read_bytes()
    try:
        core.PROVIDER_STATE.write_text('{"payload":{"version":1},"mac":"forged"}')
        try:
            DurableProviderState(core.PROVIDER_STATE)
        except RuntimeError:
            pass
        else:
            raise AssertionError("corrupted provider state was accepted after restart")
    finally:
        core.PROVIDER_STATE.write_bytes(original)

    saved = Path(str(core.PROVIDER_STATE) + ".saved")
    os.replace(core.PROVIDER_STATE, saved)
    try:
        try:
            DurableProviderState(core.PROVIDER_STATE)
        except RuntimeError:
            pass
        else:
            raise AssertionError("missing provisioned provider state reinitialized empty")
    finally:
        os.replace(saved, core.PROVIDER_STATE)

    provider_proc = start_provider()
    assert core.provider_status(effect_op)["effect"]["effect_id"] == "restart-effect"
    assert core.provider_status(fence_op)["fence"]["attempt_token"] == "fence-token"
    print(
        "d3_e_external_provider_restart_durability=PASS "
        "committed_effect_survives_restart=true absence_fence_survives_restart=true "
        "lost_response_probe_survives_restart=true state_integrity_hmac=true "
        "atomic_state_replace=true corrupted_state_fail_closed=true "
        "missing_provisioned_state_fail_closed=true"
    )
    return provider_proc


def prove_whole_restore_strict(
    port: core.ReplayAuthorityPort,
    witness: core.RecoveryWitnessPort,
) -> None:
    op = "restore-post-r-effect"
    core.prepare_redrive(op, 1)
    assert core.claim(op, "restore-worker", "restore-token", 1) == "1"
    stale_dump = core.whole_database_dump()

    assert port.consume(
        "restore-client", "restore-jti", "restore-fp",
        "restore-session-effect", "restore-session-result", 1,
    ) == "WIN"
    provider_effect = core.provider_send(
        op, 1, "restore-token", "restore-provider-effect", "restore-provider-result"
    )
    assert provider_effect["outcome"] == "WIN"
    assert core.complete_provider(op, 1, "restore-provider-result", provider_effect["revision"])

    core.capture_recovery_boundary(witness, next_epoch=2, ops=[op])
    assert port.consume(
        "post-f-client", "post-f-jti", "post-f-fp", "post-f-effect", "post-f-result", 1
    ) == "BLOCKED"

    restore_entire_database(stale_dump)
    assert core.psql(
        "SELECT count(*) FROM d3e_replay.replay_identity WHERE jti='restore-jti';"
    ) == "0"
    assert core.psql(
        "SELECT epoch FROM d3e_replay.recovery_fence WHERE singleton=TRUE;"
    ) == "1"
    assert core.psql(
        "SELECT reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;"
    ) == "true"

    surviving = witness.read()
    assert surviving["epoch"] == 2
    assert surviving["admission_open"] is False
    assert surviving["boundary"] == "F-2"
    assert port.consume(
        "restore-client", "restore-jti", "restore-fp",
        "restore-session-effect", "restore-session-result", 1,
    ) == "BLOCKED"
    assert port.consume(
        "restore-client", "restore-jti", "restore-fp",
        "restore-session-effect", "restore-session-result", 2,
    ) == "BLOCKED"

    saved = witness.path.with_suffix(".saved")
    os.replace(witness.path, saved)
    try:
        assert port.consume(
            "missing-witness", "mw-jti", "mw-fp", "mw-effect", "mw-result", 2
        ) == "BLOCKED"
        try:
            core.recover_from_witness(witness)
        except RuntimeError:
            pass
        else:
            raise AssertionError("recovery opened without surviving continuity witness")
    finally:
        os.replace(saved, witness.path)

    core.recover_from_witness(witness)
    assert port.consume(
        "restore-client", "restore-jti", "restore-fp",
        "restore-session-effect", "restore-session-result", 2,
    ) == "OBSERVE"
    assert port.consume(
        "restore-client", "restore-jti", "restore-fp",
        "restore-session-effect", "restore-session-result", 1,
    ) == "BLOCKED"
    assert core.psql(
        f"SELECT state||'|'||attempt_generation FROM d3e_replay.redrive "
        f"WHERE operation_id={core.lit(op)};"
    ) == "completed|1"
    assert core.provider_status(op)["effect"]["effect_id"] == "restore-provider-effect"

    print(
        "d3_e_replay_consumed_identity_survives_restore_loss=PASS "
        "whole_database_restore=true entire_database_recreated=true "
        "rollback_includes_local_control=true rollback_local_epoch=1 surviving_external_epoch=2 "
        "surviving_recovery_witness_external_to_snapshot=true stale_epoch_callers_fenced=true "
        "missing_witness_fail_closed=true consumed_identity_rehydrated=true "
        "ambiguous_external_effect_reconciled=true confirmed_effect_not_repeated=true"
    )


def prove_recovery_capture_fences_inflight(witness: core.RecoveryWitnessPort) -> None:
    op = "recovery-capture-inflight"
    core.prepare_redrive(op, 2)
    assert core.claim(op, "capture-worker", "capture-token", 2) == "1"

    go = core.threading.Event()
    result: dict[str, dict] = {}

    def late_send() -> None:
        go.wait()
        result["send"] = core.provider_send(
            op, 1, "capture-token", "capture-effect", "capture-result"
        )

    worker = core.threading.Thread(target=late_send)
    worker.start()
    go.set()
    core.capture_recovery_boundary(witness, next_epoch=3, ops=[op])
    worker.join(timeout=5)
    assert not worker.is_alive()

    final = _redrive_row(op)
    assert final is not None and final[0] in {"prepared", "completed"}
    status = core.provider_status(op)
    send_outcome = result["send"]["outcome"]
    assert send_outcome in {"WIN", "BLOCKED"}
    if send_outcome == "WIN":
        assert final[0] == "completed"
        assert status["effect"]["effect_id"] == "capture-effect"
    else:
        assert final[0] == "prepared"
        assert status["fence"]["attempt_token"] == "capture-token"

    payload = witness.read()
    assert payload["epoch"] == 3 and payload["admission_open"] is False
    witnessed = payload["provider_outcomes"][op]
    assert bool(witnessed.get("effect")) != bool(witnessed.get("fence"))
    assert core.psql(
        "SELECT count(*) FROM d3e_replay.redrive "
        "WHERE state IN('attempting','reconciliation_required');"
    ) == "0"
    print(
        "d3_e_recovery_capture_inflight_provider_fence=PASS "
        "local_admission_closed_before_capture=true provider_probe_serializes_with_send=true "
        "effect_confirmed_or_absence_fenced=true no_attempting_state_at_witness=true "
        "late_provider_capability_cannot_escape_boundary=true witness_remains_closed=true"
    )


def main() -> None:
    core.WITNESS_PATH.unlink(missing_ok=True)
    core.PROVIDER_STATE.unlink(missing_ok=True)
    _provider_anchor().unlink(missing_ok=True)
    Path(str(core.PROVIDER_STATE) + ".tmp").unlink(missing_ok=True)
    Path(str(_provider_anchor()) + ".tmp").unlink(missing_ok=True)

    core.capture_recovery_boundary = capture_recovery_boundary_strict
    core.recover_from_witness = recover_from_witness_strict

    provider_proc = start_provider()
    try:
        core.init_db()
        witness = core.RecoveryWitnessPort()
        witness.initialize()
        port = core.ReplayAuthorityPort(witness)

        core.prove_single_winner(port)
        core.prove_duplicate_recovery_gate_order(port)
        core.prove_partition()
        core.prove_redrive_external_boundary()
        core.prove_absence_effect_race()
        provider_proc = prove_provider_restart_durability(provider_proc)
        prove_whole_restore_strict(port, witness)
        prove_recovery_capture_fences_inflight(witness)

        print(
            "d3_e_replay_redrive_conformance=PASS postgres_replay_truth=true "
            "recovery_witness_recovery_only=true single_winner=true partition_fail_closed=true "
            "external_effect_network_boundary=true external_provider_restart_durable=true "
            "recovery_capture_provider_serialized=true whole_restore_nonresurrection=true "
            "c3_numerics_not_selected=true topology_not_selected=true"
        )
        print(
            "d3_e_replay_recovery_entrypoint=PASS "
            "stale_db_cannot_self_certify=true external_recovery_epoch_wins=true "
            "inflight_provider_capability_fenced_before_witness=true"
        )
    finally:
        stop_provider(provider_proc)


if __name__ == "__main__":
    if "--durable-provider-server" in core.sys.argv:
        durable_provider_server()
    else:
        main()
