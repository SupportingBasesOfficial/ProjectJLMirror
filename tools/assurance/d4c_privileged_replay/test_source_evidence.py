#!/usr/bin/env python3
from __future__ import annotations

from evaluate_candidates import (
    CANDIDATES,
    PROOFS,
    HistoricalMessage,
    ReplayController,
    blocked,
    evaluate,
    request,
    sample,
)


def main() -> int:
    result = evaluate()
    assert result["selection"] == "not_selected"
    assert result["selection_authority"] == "not_granted"
    assert result["ledger_credit"] == []
    assert result["current_run_auto_credit"] is False
    assert set(result["candidate_results"]) == set(CANDIDATES)
    assert all(v == "eligible_for_evidence_execution" for v in result["candidate_results"].values())
    assert all(set(result["proof_results"][c]) == set(PROOFS) for c in CANDIDATES)
    assert all(all(v.values()) for v in result["proof_results"].values())

    for candidate in CANDIDATES:
        msg = sample()
        c = ReplayController(candidate)
        safe = request(max_messages=1, target="shadow-projection", generation="replay-g1")

        assert blocked(
            lambda: c.replay(request(actor="unknown-actor"), [msg]),
            "current_privileged_authority_required",
        )
        assert blocked(
            lambda: c.replay(request(epoch="replay-auth-epoch-1"), [msg]),
            "current_privileged_authority_required",
        )
        assert blocked(
            lambda: c.replay(request(max_messages=0), [msg]),
            "replay_bound_exceeded",
        )
        assert blocked(
            lambda: c.replay(request(disable_dedup=True), [msg]),
            "dedup_bypass_forbidden",
        )
        assert blocked(
            lambda: c.replay(safe, [msg], verifier_available=False),
            "replay_history_authority_unavailable",
        )
        assert blocked(
            lambda: c.replay(safe, [msg], equivalence_available=False),
            "replay_history_authority_unavailable",
        )
        assert blocked(
            lambda: c.replay(safe, [msg], verifier_available=False, duplicate_sensitive=True),
            "historical_comparison_authority_unavailable",
        )
        assert blocked(
            lambda: c.replay(safe, [msg], equivalence_available=False, duplicate_sensitive=True),
            "historical_comparison_authority_unavailable",
        )
        assert blocked(
            lambda: c.replay(safe, [msg], recovery_evidence_available=False),
            "safe_replay_evidence_incomplete",
        )
        assert blocked(
            lambda: c.replay(safe, [msg], schema_supported=False),
            "safe_replay_evidence_incomplete",
        )
        assert blocked(
            lambda: c.replay(safe, [msg], data_access_allowed=False),
            "safe_replay_evidence_incomplete",
        )
        assert blocked(
            lambda: c.replay(request(target="production-current"), [msg]),
            "isolated_replay_target_required",
        )
        assert blocked(
            lambda: c.replay(request(generation=""), [msg]),
            "isolated_replay_target_required",
        )

        missing_profile = HistoricalMessage(
            msg.tenant_id,
            msg.contract_id,
            msg.message_id,
            msg.semantic_content,
            msg.schema_version,
            "",
            msg.verifier_version,
        )
        assert blocked(
            lambda: c.replay(safe, [missing_profile]),
            "historical_verifier_metadata_missing",
        )

        first = c.replay(safe, [msg], irreversible=True)
        assert first == [msg]
        assert blocked(
            lambda: c.replay(safe, [msg], irreversible=True),
            "irreversible_effect_already_completed",
        )
        replayed = c.replay(safe, [msg], storage_identity="different-backend")
        assert replayed[0].message_id == msg.message_id
        assert replayed[0].contract_id == msg.contract_id
        assert replayed[0].equivalence_profile == msg.equivalence_profile
        assert replayed[0].verifier_version == msg.verifier_version

    print(
        "d4c_open_evt_014_falsification=PASS candidates=3 proofs=8 "
        "current_authority_fenced=true history_authority_required=true "
        "no_dedup_bypass=true irreversible_repeat=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
