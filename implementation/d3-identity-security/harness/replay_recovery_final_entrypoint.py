#!/usr/bin/env python3
from __future__ import annotations

import replay_recovery_conformance_entrypoint as base
import replay_recovery_conformance_runner as core


_ORIGINAL_RECOVER = base.recover_from_witness_strict
_ORIGINAL_INFLIGHT_PROBE = base.prove_recovery_capture_fences_inflight


def _require_exact_capability(expected: dict, observed: dict, outcome: str) -> None:
    if observed.get("outcome") != outcome:
        raise RuntimeError("external provider outcome diverged during recovery rehydration")
    fields = ("attempt_generation", "attempt_token", "revision")
    if outcome == "CONFIRMED":
        fields += ("effect_id", "result_ref")
    for field in fields:
        if observed.get(field) != expected.get(field):
            raise RuntimeError(f"external provider continuity mismatch for {field}")


def _rehydrate_missing_redrive_rows(witness: core.RecoveryWitnessPort) -> int:
    payload = witness.read()
    epoch = int(payload["epoch"])
    if payload["admission_open"] is not False:
        raise RuntimeError("recovery rehydration requires closed admission")

    restored = 0
    for op, status in payload["provider_outcomes"].items():
        if base.strict._redrive_row(op) is not None:
            continue
        effect = status.get("effect")
        fence = status.get("fence")
        if effect and fence:
            raise RuntimeError("provider continuity cannot be both effect and absence fence")
        if effect:
            generation = int(effect["attempt_generation"])
            token = effect["attempt_token"]
            observed = core.provider_probe(op, generation, token)
            _require_exact_capability(effect, observed, "CONFIRMED")
            core.psql(
                "INSERT INTO d3e_replay.redrive("
                "operation_id,recovery_epoch,state,attempt_generation,provider_revision,result_ref) "
                f"VALUES({core.lit(op)},{epoch},'completed',{generation},"
                f"{core.lit(effect['revision'])},{core.lit(effect['result_ref'])});"
            )
            restored += 1
        elif fence:
            generation = int(fence["attempt_generation"])
            token = fence["attempt_token"]
            observed = core.provider_probe(op, generation, token)
            _require_exact_capability(fence, observed, "ABSENT")
            core.psql(
                "INSERT INTO d3e_replay.redrive("
                "operation_id,recovery_epoch,state,attempt_generation,provider_revision) "
                f"VALUES({core.lit(op)},{epoch},'prepared',{generation},"
                f"{core.lit(fence['revision'])});"
            )
            restored += 1
    return restored


def recover_from_witness_with_missing_row_rehydration(
    witness: core.RecoveryWitnessPort,
) -> None:
    restored = _rehydrate_missing_redrive_rows(witness)
    _ORIGINAL_RECOVER(witness)
    if restored:
        print(
            "d3_e_post_snapshot_provider_outcome_rehydration=PASS "
            f"rows_rehydrated={restored} provider_reconfirmed_before_local_rebuild=true "
            "recovery_witness_not_effect_source_alone=true admission_closed_during_rebuild=true"
        )


def _prove_post_snapshot_effect_row_rehydration(
    witness: core.RecoveryWitnessPort,
) -> None:
    core.recover_from_witness(witness)
    payload = witness.read()
    assert payload["epoch"] == 3 and payload["admission_open"] is True

    stale_dump = core.whole_database_dump()
    op = "post-snapshot-effect-row-loss"
    token = "post-snapshot-token"
    effect_id = "post-snapshot-effect"
    result_ref = "post-snapshot-result"

    core.prepare_redrive(op, 3)
    assert core.claim(op, "post-snapshot-worker", token, 3) == "1"
    ambiguous = core.provider_send(op, 1, token, effect_id, result_ref, drop=True)
    assert ambiguous["outcome"] == "AMBIGUOUS"

    core.capture_recovery_boundary(witness, next_epoch=4, ops=[op])
    witnessed = witness.read()
    assert witnessed["epoch"] == 4 and witnessed["admission_open"] is False
    effect = witnessed["provider_outcomes"][op]["effect"]
    assert effect["effect_id"] == effect_id and effect["result_ref"] == result_ref

    base.strict.restore_entire_database(stale_dump)
    assert base.strict._redrive_row(op) is None
    assert core.psql(
        "SELECT epoch||'|'||reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;"
    ) == "3|true"

    core.recover_from_witness(witness)
    rebuilt = core.psql(
        "SELECT state||'|'||attempt_generation||'|'||provider_revision||'|'||result_ref "
        f"FROM d3e_replay.redrive WHERE operation_id={core.lit(op)};"
    )
    assert rebuilt == f"completed|{effect['attempt_generation']}|{effect['revision']}|{result_ref}"
    reopened = witness.read()
    assert reopened["epoch"] == 4 and reopened["admission_open"] is True

    observed = core.provider_send(
        op,
        int(effect["attempt_generation"]),
        effect["attempt_token"],
        effect_id,
        result_ref,
    )
    assert observed["outcome"] == "OBSERVE"
    _require_exact_capability(
        effect,
        {"outcome": "CONFIRMED", **core.provider_status(op)["effect"]},
        "CONFIRMED",
    )

    print(
        "d3_e_post_snapshot_redrive_row_rehydration=PASS "
        "operation_created_after_stale_snapshot=true external_effect_survives_restore=true "
        "entire_local_redrive_row_lost=true external_provider_reconfirmed=true "
        "completed_row_recreated_before_admission=true exact_effect_not_repeated=true "
        "missing_local_state_not_interpreted_as_no_effect=true"
    )


def prove_inflight_and_post_snapshot_rehydration(
    witness: core.RecoveryWitnessPort,
) -> None:
    _ORIGINAL_INFLIGHT_PROBE(witness)
    _prove_post_snapshot_effect_row_rehydration(witness)


def main() -> None:
    base.recover_from_witness_strict = recover_from_witness_with_missing_row_rehydration
    base.prove_recovery_capture_fences_inflight = prove_inflight_and_post_snapshot_rehydration
    base.strict.recover_from_witness_strict = recover_from_witness_with_missing_row_rehydration
    base.strict.prove_recovery_capture_fences_inflight = prove_inflight_and_post_snapshot_rehydration
    base.main()


if __name__ == "__main__":
    main()
