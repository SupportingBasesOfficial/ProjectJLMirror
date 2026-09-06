#!/usr/bin/env python3
from __future__ import annotations

from evaluate_candidates import (
    CANDIDATES,
    PROOFS,
    ContractViolation,
    GenerationAuthority,
    HistoricalFact,
    evaluate,
)


def blocked(fn, code: str) -> bool:
    try:
        fn()
    except ContractViolation as exc:
        return str(exc) == code
    return False


def main() -> int:
    result = evaluate()
    assert tuple(result["candidate_results"]) == CANDIDATES
    assert set(result["candidate_results"].values()) == {"eligible_for_evidence_execution"}
    assert result["selection"] == "not_selected"
    assert result["selection_authority"] == "not_granted"
    assert result["ledger_credit"] == []
    assert result["current_run_auto_credit"] is False

    for candidate in CANDIDATES:
        proof_result = result["proof_results"][candidate]
        assert tuple(proof_result) == PROOFS
        assert all(proof_result.values())
        assert all(result["check_results"][candidate].values())

        authority = GenerationAuthority(candidate)
        identity = authority.identity
        retired = authority.current_generation
        historical = HistoricalFact(identity, retired, "hist-1", "{}")
        authority.rotate(placement="cell-b")
        current = authority.current_generation

        # Stale authority remains stale even if an external system reports the
        # current generation. External provider/broker metadata is observation,
        # never platform generation authority.
        assert blocked(
            lambda: authority.admit_effect(
                tenant_id=identity.tenant_id,
                logical_source_id=identity.logical_source_id,
                platform_generation=retired,
                provider_generation=current,
                broker_generation=current,
            ),
            "retired_generation",
        )

        # Historical facts remain readable but cannot be replayed as current
        # source authority merely because they carry an old generation value.
        assert authority.read_historical_fact(historical) == historical
        assert blocked(
            lambda: authority.admit_effect(
                tenant_id=identity.tenant_id,
                logical_source_id=identity.logical_source_id,
                platform_generation=historical.generation,
            ),
            "retired_generation",
        )

        # A numerically or lexically "greater" token has no ordering authority.
        assert blocked(
            lambda: authority.admit_effect(
                tenant_id=identity.tenant_id,
                logical_source_id=identity.logical_source_id,
                platform_generation="999999999999999999",
            ),
            "generation_not_current",
        )
        assert blocked(
            lambda: authority.admit_effect(
                tenant_id=identity.tenant_id,
                logical_source_id=identity.logical_source_id,
                platform_generation="zzzzzzzzzzzzzzzz",
            ),
            "generation_not_current",
        )

        # Restore of a stale snapshot cannot demote the surviving authority.
        stale_snapshot = GenerationAuthority(candidate).snapshot()
        before_restore = authority.current_generation
        authority.restore_snapshot(stale_snapshot)
        assert authority.current_generation == before_restore
        assert retired in authority.state.retired_generations

    print(
        "d4c_open_evt_013_source_falsification=PASS "
        "candidates=3 proofs=7 stale=blocked future=blocked restore_resurrection=blocked "
        "history_not_authority=true external_generation_not_authority=true selection=none credit=none"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
