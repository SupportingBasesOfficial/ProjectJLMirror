#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

CANDIDATES = (
    "positive_integer_fenced_generation",
    "opaque_fenced_generation_token",
    "authority_issued_epoch_generation",
)

PROOFS = (
    "current_source_generation_is_explicitly_validated_at_effectful_admission",
    "retired_generation_cannot_regain_current_authority",
    "restore_or_failover_cannot_resurrect_retired_source_authority",
    "historical_fact_identity_remains_distinct_from_current_source_authority",
    "tenant_logical_identity_is_independent_of_generation_and_placement",
    "generation_comparison_rule_is_unambiguous_and_does_not_infer_ungranted_ordering_semantics",
    "provider_or_broker_generation_is_not_platform_source_generation_by_implication",
)

PROOF_CHECKS = {
    PROOFS[0]: (
        "current_generation_admitted",
        "stale_generation_rejected",
        "future_generation_rejected",
        "missing_generation_rejected",
    ),
    PROOFS[1]: (
        "retired_generation_rejected_after_rotation",
        "retired_generation_rejected_after_second_rotation",
    ),
    PROOFS[2]: (
        "failover_preserves_retirement_fence",
        "restore_snapshot_cannot_resurrect_retired_generation",
        "restore_snapshot_cannot_override_surviving_current_generation",
    ),
    PROOFS[3]: (
        "historical_fact_remains_readable",
        "historical_generation_does_not_authorize_effect",
    ),
    PROOFS[4]: (
        "logical_identity_stable_across_generation",
        "logical_identity_stable_across_placement",
    ),
    PROOFS[5]: (
        "comparison_is_exact_current_generation_equality",
        "numeric_magnitude_does_not_imply_authority",
        "opaque_or_epoch_lexical_order_does_not_imply_authority",
    ),
    PROOFS[6]: (
        "provider_generation_does_not_substitute_platform_generation",
        "broker_generation_does_not_substitute_platform_generation",
        "matching_external_generation_cannot_revive_retired_platform_generation",
    ),
}


class ContractViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceIdentity:
    tenant_id: str
    logical_source_id: str


@dataclass(frozen=True)
class SourceAuthority:
    identity: SourceIdentity
    generation: str
    placement: str


@dataclass(frozen=True)
class HistoricalFact:
    identity: SourceIdentity
    generation: str
    message_id: str
    semantic_content: str


@dataclass(frozen=True)
class DurableAuthorityState:
    current: SourceAuthority
    retired_generations: frozenset[str]
    sequence: int


class GenerationAuthority:
    """Minimal authority model for C2 source evidence.

    Generation values are opaque at admission time. The only effectful rule is
    exact equality with the durable current platform generation plus explicit
    retirement non-membership. Numeric/lexical ordering is never authority.
    """

    def __init__(self, candidate: str, *, tenant_id: str = "tenant-a", logical_source_id: str = "source-1") -> None:
        if candidate not in CANDIDATES:
            raise ValueError(candidate)
        self.candidate = candidate
        self.identity = SourceIdentity(tenant_id, logical_source_id)
        first = self._format_generation(1)
        self._state = DurableAuthorityState(
            current=SourceAuthority(self.identity, first, "cell-a"),
            retired_generations=frozenset(),
            sequence=1,
        )

    def _format_generation(self, sequence: int) -> str:
        if self.candidate == "positive_integer_fenced_generation":
            return str(sequence)
        if self.candidate == "opaque_fenced_generation_token":
            return f"g-{sequence:04d}-opaque-token"
        if self.candidate == "authority_issued_epoch_generation":
            return f"epoch-{sequence:04d}"
        raise AssertionError(self.candidate)

    @property
    def state(self) -> DurableAuthorityState:
        return self._state

    @property
    def current_generation(self) -> str:
        return self._state.current.generation

    def snapshot(self) -> DurableAuthorityState:
        return self._state

    def rotate(self, *, placement: str | None = None) -> str:
        old = self._state.current
        next_sequence = self._state.sequence + 1
        next_generation = self._format_generation(next_sequence)
        next_authority = SourceAuthority(
            old.identity,
            next_generation,
            old.placement if placement is None else placement,
        )
        self._state = DurableAuthorityState(
            current=next_authority,
            retired_generations=self._state.retired_generations | frozenset({old.generation}),
            sequence=next_sequence,
        )
        return next_generation

    def failover(self, *, placement: str) -> None:
        current = self._state.current
        self._state = DurableAuthorityState(
            current=SourceAuthority(current.identity, current.generation, placement),
            retired_generations=self._state.retired_generations,
            sequence=self._state.sequence,
        )

    def restore_snapshot(self, restored: DurableAuthorityState) -> None:
        """Restore cannot lower surviving authority or erase retirement evidence.

        The surviving durable authority state is the activation fence. Restored
        bytes may contribute history, but they cannot become current merely by
        being older or by containing a generation value.
        """
        surviving = self._state
        if restored.current.identity != surviving.current.identity:
            raise ContractViolation("restore_identity_mismatch")
        merged_retired = surviving.retired_generations | restored.retired_generations
        self._state = DurableAuthorityState(
            current=surviving.current,
            retired_generations=merged_retired,
            sequence=surviving.sequence,
        )

    def admit_effect(
        self,
        *,
        tenant_id: str,
        logical_source_id: str,
        platform_generation: str | None,
        provider_generation: str | None = None,
        broker_generation: str | None = None,
    ) -> bool:
        if SourceIdentity(tenant_id, logical_source_id) != self._state.current.identity:
            raise ContractViolation("source_identity_mismatch")
        if platform_generation is None:
            raise ContractViolation("platform_generation_required")
        if platform_generation in self._state.retired_generations:
            raise ContractViolation("retired_generation")
        if platform_generation != self._state.current.generation:
            raise ContractViolation("generation_not_current")
        # External generations are observations only. They are intentionally not
        # consulted to derive or substitute platform source authority.
        _ = provider_generation, broker_generation
        return True

    def read_historical_fact(self, fact: HistoricalFact) -> HistoricalFact:
        if fact.identity != self.identity:
            raise ContractViolation("historical_identity_mismatch")
        return fact


def _blocked(fn: Any, code: str) -> bool:
    try:
        fn()
    except ContractViolation as exc:
        return str(exc) == code
    return False


def _future_generation(candidate: str) -> str:
    if candidate == "positive_integer_fenced_generation":
        return "999999"
    if candidate == "opaque_fenced_generation_token":
        return "zzzz-future-looking-token"
    return "epoch-999999"


def check_candidate(candidate: str) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    authority = GenerationAuthority(candidate)
    identity = authority.identity
    g1 = authority.current_generation

    checks["current_generation_admitted"] = authority.admit_effect(
        tenant_id=identity.tenant_id,
        logical_source_id=identity.logical_source_id,
        platform_generation=g1,
    )
    checks["missing_generation_rejected"] = _blocked(
        lambda: authority.admit_effect(
            tenant_id=identity.tenant_id,
            logical_source_id=identity.logical_source_id,
            platform_generation=None,
        ),
        "platform_generation_required",
    )
    checks["future_generation_rejected"] = _blocked(
        lambda: authority.admit_effect(
            tenant_id=identity.tenant_id,
            logical_source_id=identity.logical_source_id,
            platform_generation=_future_generation(candidate),
        ),
        "generation_not_current",
    )

    pre_rotation = authority.snapshot()
    g2 = authority.rotate()
    checks["stale_generation_rejected"] = _blocked(
        lambda: authority.admit_effect(
            tenant_id=identity.tenant_id,
            logical_source_id=identity.logical_source_id,
            platform_generation=g1,
        ),
        "retired_generation",
    )
    checks["retired_generation_rejected_after_rotation"] = checks["stale_generation_rejected"]

    authority.failover(placement="cell-b")
    checks["failover_preserves_retirement_fence"] = (
        g1 in authority.state.retired_generations
        and authority.current_generation == g2
        and authority.state.current.placement == "cell-b"
        and _blocked(
            lambda: authority.admit_effect(
                tenant_id=identity.tenant_id,
                logical_source_id=identity.logical_source_id,
                platform_generation=g1,
            ),
            "retired_generation",
        )
    )

    authority.restore_snapshot(pre_rotation)
    checks["restore_snapshot_cannot_resurrect_retired_generation"] = (
        authority.current_generation == g2
        and g1 in authority.state.retired_generations
        and _blocked(
            lambda: authority.admit_effect(
                tenant_id=identity.tenant_id,
                logical_source_id=identity.logical_source_id,
                platform_generation=g1,
            ),
            "retired_generation",
        )
    )
    checks["restore_snapshot_cannot_override_surviving_current_generation"] = authority.current_generation == g2

    fact = HistoricalFact(identity, g1, "msg-historical-1", '{"event":"source.changed"}')
    checks["historical_fact_remains_readable"] = authority.read_historical_fact(fact) == fact
    checks["historical_generation_does_not_authorize_effect"] = _blocked(
        lambda: authority.admit_effect(
            tenant_id=identity.tenant_id,
            logical_source_id=identity.logical_source_id,
            platform_generation=fact.generation,
        ),
        "retired_generation",
    )

    before_identity = authority.state.current.identity
    before_placement = authority.state.current.placement
    g3 = authority.rotate(placement="cell-c")
    checks["retired_generation_rejected_after_second_rotation"] = _blocked(
        lambda: authority.admit_effect(
            tenant_id=identity.tenant_id,
            logical_source_id=identity.logical_source_id,
            platform_generation=g2,
        ),
        "retired_generation",
    )
    checks["logical_identity_stable_across_generation"] = authority.state.current.identity == before_identity
    checks["logical_identity_stable_across_placement"] = (
        before_placement != authority.state.current.placement
        and authority.state.current.identity == before_identity
    )

    checks["comparison_is_exact_current_generation_equality"] = authority.admit_effect(
        tenant_id=identity.tenant_id,
        logical_source_id=identity.logical_source_id,
        platform_generation=g3,
    )
    checks["numeric_magnitude_does_not_imply_authority"] = _blocked(
        lambda: authority.admit_effect(
            tenant_id=identity.tenant_id,
            logical_source_id=identity.logical_source_id,
            platform_generation="999999999",
        ),
        "generation_not_current",
    )
    checks["opaque_or_epoch_lexical_order_does_not_imply_authority"] = _blocked(
        lambda: authority.admit_effect(
            tenant_id=identity.tenant_id,
            logical_source_id=identity.logical_source_id,
            platform_generation="zzzzzzzzzz",
        ),
        "generation_not_current",
    )

    checks["provider_generation_does_not_substitute_platform_generation"] = _blocked(
        lambda: authority.admit_effect(
            tenant_id=identity.tenant_id,
            logical_source_id=identity.logical_source_id,
            platform_generation=g1,
            provider_generation=g3,
        ),
        "retired_generation",
    )
    checks["broker_generation_does_not_substitute_platform_generation"] = _blocked(
        lambda: authority.admit_effect(
            tenant_id=identity.tenant_id,
            logical_source_id=identity.logical_source_id,
            platform_generation=g2,
            broker_generation=g3,
        ),
        "retired_generation",
    )
    checks["matching_external_generation_cannot_revive_retired_platform_generation"] = _blocked(
        lambda: authority.admit_effect(
            tenant_id=identity.tenant_id,
            logical_source_id=identity.logical_source_id,
            platform_generation=g1,
            provider_generation=g1,
            broker_generation=g1,
        ),
        "retired_generation",
    )

    return checks


def evaluate() -> dict[str, Any]:
    candidate_checks = {candidate: check_candidate(candidate) for candidate in CANDIDATES}
    candidate_results: dict[str, str] = {}
    proof_results: dict[str, dict[str, bool]] = {}
    for candidate, checks in candidate_checks.items():
        proof_results[candidate] = {
            proof: all(checks[name] for name in names)
            for proof, names in PROOF_CHECKS.items()
        }
        candidate_results[candidate] = (
            "eligible_for_evidence_execution"
            if all(checks.values()) and all(proof_results[candidate].values())
            else "insufficient_evidence"
        )
    return {
        "schema_version": 1,
        "source_decision": "OPEN-EVT-013",
        "evidence_id": "producer_generation_nonresurrection_across_failover_restore",
        "candidate_results": candidate_results,
        "proof_results": proof_results,
        "check_results": candidate_checks,
        "selection": "not_selected",
        "selection_authority": "not_granted",
        "ledger_credit": [],
        "current_run_auto_credit": False,
    }


def main() -> int:
    print(json.dumps(evaluate(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
