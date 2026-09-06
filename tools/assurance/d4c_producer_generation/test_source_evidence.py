#!/usr/bin/env python3
from __future__ import annotations

from evaluate_candidates import (
    CANDIDATES,
    PROOFS,
    ContractViolation,
    GenerationAuthority,
    HistoricalFact,
    SourceIdentity,
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
        if candidate == "positive_integer_fenced_generation":
            assert type(retired) is int and retired > 0
        else:
            assert type(retired) is str and retired

        historical = HistoricalFact(identity, retired, "hist-1", "{}")
        authority.rotate(placement="cell-b")
        current = authority.current_generation

        # Generation authority is scoped to the platform tenant/logical source
        # identity. A coincident current generation from another source is not
        # transferable authority.
        assert blocked(
            lambda: authority.admit_effect(
                tenant_id="tenant-b",
                logical_source_id=identity.logical_source_id,
                platform_generation=current,
            ),
            "source_identity_mismatch",
        )
        assert blocked(
            lambda: authority.admit_effect(
                tenant_id=identity.tenant_id,
                logical_source_id="source-other",
                platform_generation=current,
            ),
            "source_identity_mismatch",
        )

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

        # Neither provider nor broker generation may substitute for a missing
        # platform generation, even when the external value equals current.
        assert blocked(
            lambda: authority.admit_effect(
                tenant_id=identity.tenant_id,
                logical_source_id=identity.logical_source_id,
                platform_generation=None,
                provider_generation=current,
            ),
            "platform_generation_required",
        )
        assert blocked(
            lambda: authority.admit_effect(
                tenant_id=identity.tenant_id,
                logical_source_id=identity.logical_source_id,
                platform_generation=None,
                broker_generation=current,
            ),
            "platform_generation_required",
        )

        assert authority.read_historical_fact(historical) == historical
        foreign_historical = HistoricalFact(
            SourceIdentity("tenant-b", identity.logical_source_id),
            historical.generation,
            "hist-foreign",
            "{}",
        )
        assert blocked(
            lambda: authority.read_historical_fact(foreign_historical),
            "historical_identity_mismatch",
        )
        assert blocked(
            lambda: authority.admit_effect(
                tenant_id=identity.tenant_id,
                logical_source_id=identity.logical_source_id,
                platform_generation=historical.generation,
            ),
            "retired_generation",
        )

        if candidate == "positive_integer_fenced_generation":
            assert blocked(
                lambda: authority.admit_effect(
                    tenant_id=identity.tenant_id,
                    logical_source_id=identity.logical_source_id,
                    platform_generation=999999999999999999,
                ),
                "generation_not_current",
            )
            for bad in (0, -1, True, "2"):
                assert blocked(
                    lambda bad=bad: authority.admit_effect(
                        tenant_id=identity.tenant_id,
                        logical_source_id=identity.logical_source_id,
                        platform_generation=bad,
                    ),
                    "generation_representation_invalid",
                )
        else:
            assert blocked(
                lambda: authority.admit_effect(
                    tenant_id=identity.tenant_id,
                    logical_source_id=identity.logical_source_id,
                    platform_generation="zzzzzzzzzzzzzzzz",
                ),
                "generation_not_current",
            )
            assert blocked(
                lambda: authority.admit_effect(
                    tenant_id=identity.tenant_id,
                    logical_source_id=identity.logical_source_id,
                    platform_generation=999999999,
                ),
                "generation_representation_invalid",
            )

        stale_snapshot = GenerationAuthority(candidate).snapshot()
        before_restore = authority.current_generation
        authority.restore_snapshot(stale_snapshot)
        assert authority.current_generation == before_restore
        assert retired in authority.state.retired_generations

    print(
        "d4c_open_evt_013_source_falsification=PASS "
        "candidates=3 proofs=7 exact_representation=true identity_fence=blocked "
        "stale=blocked future=blocked restore_resurrection=blocked history_not_authority=true "
        "historical_cross_source=blocked external_generation_not_authority=true "
        "external_fallback_when_platform_missing=blocked selection=none credit=none"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
