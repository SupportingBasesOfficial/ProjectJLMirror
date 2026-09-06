#!/usr/bin/env python3
from __future__ import annotations

import copy

from evaluate_candidates import (
    CANDIDATES,
    ELIGIBLE,
    INELIGIBLE,
    EquivalenceEngine,
    EvidenceViolation,
    ExplodingImmutable,
    Identity,
    base_event,
    evaluate_all,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    result = evaluate_all()
    expected = {
        "canonical_collision_resistant_fingerprint_profile": INELIGIBLE,
        "keyed_authenticated_digest_profile": ELIGIBLE,
        "protected_retained_immutable_original_profile": ELIGIBLE,
        "hybrid_equivalence_authority_profile": ELIGIBLE,
    }
    require(result["candidate_results"] == expected, "candidate classification drift")
    require(result["selection"] == "not_selected", "source run selected a candidate")
    require(result["selection_authority"] == "not_granted", "source run granted selection authority")
    require(result["ledger_credit"] == [], "source run auto-credited ledger")
    require(result["current_run_auto_credit"] is False, "auto-credit must remain false")

    fingerprint = result["checks"]["canonical_collision_resistant_fingerprint_profile"]
    require(fingerprint["low_entropy_confidentiality_is_scope_safe"] is False, "unkeyed fingerprint must expose cross-scope equality in the falsification vector")
    for candidate in CANDIDATES[1:]:
        checks = result["checks"][candidate]
        require(all(checks.values()), f"eligible candidate has unproven obligation: {candidate}: {checks}")

    identity = Identity("ticket-projection/v3", "tenant-a:cell-1", "msg-falsify")
    for candidate in CANDIDATES[1:]:
        engine = EquivalenceEngine(candidate)
        event = base_event()
        require(engine.classify_or_commit(identity, event) == "new_effect_committed", candidate)
        require(engine.classify_or_commit(identity, copy.deepcopy(event)) == "benign_duplicate", candidate)

        conflict = copy.deepcopy(event)
        conflict["payload"]["count"] = 2
        require(engine.classify_or_commit(identity, conflict) == "integrity_conflict", f"identity-only duplicate bypass: {candidate}")
        require(engine.classify_or_commit(identity, event, comparison_access=False) == "uncertain_access_denied", f"comparison access bypass: {candidate}")

        try:
            engine.classify_or_commit(
                Identity("untrusted-contract", "tenant-a:cell-1", "msg-u1"),
                ExplodingImmutable(),
                trusted_consumer_contract=False,
            )
        except EvidenceViolation as exc:
            require(exc.code == "untrusted_consumer_contract", f"consumer-contract trust bypass: {candidate}")
        else:
            raise AssertionError(f"untrusted consumer contract reached semantic comparison: {candidate}")

        try:
            engine.classify_or_commit(
                Identity("ticket-projection/v3", "untrusted-scope", "msg-u2"),
                ExplodingImmutable(),
                trusted_message_scope=False,
            )
        except EvidenceViolation as exc:
            require(exc.code == "untrusted_message_identity_scope", f"message-scope trust bypass: {candidate}")
        else:
            raise AssertionError(f"untrusted message scope reached semantic comparison: {candidate}")

    try:
        EquivalenceEngine("keyed_authenticated_digest_profile").classify_or_commit(
            identity,
            {"tenant_id": "tenant-a"},
        )
    except EvidenceViolation as exc:
        require(exc.code == "immutable_semantic_field_missing", "wrong missing-field failure")
    else:
        raise AssertionError("missing immutable field admitted")

    print("d4c_open_evt_011_source_falsification=PASS fingerprint=ineligible keyed_digest=eligible retained_original=eligible hybrid=eligible trusted_contract_scope=precondition conflict=fail_closed missing=uncertainty selection=none credit=none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
