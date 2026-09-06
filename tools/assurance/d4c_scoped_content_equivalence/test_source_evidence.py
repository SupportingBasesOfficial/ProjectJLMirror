#!/usr/bin/env python3
from __future__ import annotations

import copy

from evaluate_candidates import (
    CANDIDATES,
    ELIGIBLE,
    INELIGIBLE,
    KEY_V1,
    TEST_MAX_COLLECTION_ITEMS,
    TEST_MAX_NESTING_DEPTH,
    EquivalenceEngine,
    EvidenceViolation,
    ExplodingImmutable,
    Identity,
    base_event,
    deeply_nested_payload,
    evaluate_all,
    scope_key,
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
    require(fingerprint["low_entropy_confidentiality_is_scope_safe"] is False, "unkeyed fingerprint must expose cross-scope/dictionary oracle in the falsification vector")
    require(fingerprint["all_required_immutable_semantic_fields_are_covered"] is True, "fingerprint must still cover every immutable semantic field")
    require(fingerprint["conflicting_same_scoped_identity_fails_closed"] is True, "fingerprint must reject conflicting same-id content")

    identity = Identity("ticket-projection/v3", "tenant-a:cell-1", "msg-falsify")
    for candidate in CANDIDATES:
        engine = EquivalenceEngine(candidate)
        event = base_event()
        require(engine.classify_or_commit(identity, event) == "new_effect_committed", candidate)
        require(engine.classify_or_commit(identity, copy.deepcopy(event)) == "benign_duplicate", candidate)

        conflict = copy.deepcopy(event)
        conflict["payload"]["count"] = 2
        require(engine.classify_or_commit(identity, conflict) == "integrity_conflict", f"identity-only duplicate bypass: {candidate}")

        # P2 regression: comparison access must be denied before semantic content is inspected.
        require(
            engine.classify_or_commit(identity, ExplodingImmutable(), comparison_access=False)
            == "uncertain_access_denied",
            f"comparison access checked after semantic inspection: {candidate}",
        )

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

        # P2 regression: deep/wide structures must fail closed under fixture work bounds,
        # never recurse or traverse unboundedly before the work limit is enforced.
        try:
            EquivalenceEngine(candidate).classify_or_commit(
                Identity("ticket-projection/v3", "tenant-a:cell-1", f"msg-deep-{candidate}"),
                deeply_nested_payload(TEST_MAX_NESTING_DEPTH + 4),
            )
        except EvidenceViolation as exc:
            require(exc.code == "verification_work_exceeded", f"deep input escaped bounded verification: {candidate}")
        else:
            raise AssertionError(f"deep input admitted beyond bounded verification: {candidate}")

        wide = base_event()
        wide["payload"] = {f"k{i}": i for i in range(TEST_MAX_COLLECTION_ITEMS + 1)}
        try:
            EquivalenceEngine(candidate).classify_or_commit(
                Identity("ticket-projection/v3", "tenant-a:cell-1", f"msg-wide-{candidate}"),
                wide,
            )
        except EvidenceViolation as exc:
            require(exc.code == "verification_work_exceeded", f"wide input escaped bounded verification: {candidate}")
        else:
            raise AssertionError(f"wide input admitted beyond bounded verification: {candidate}")

        # P2 regression: delimiter-containing identity components must remain injective.
        collision_a = Identity("a\x1fb", "c", "msg-collision")
        collision_b = Identity("a", "b\x1fc", "msg-collision")
        require(
            engine.stable_external_operation_id(collision_a)
            != engine.stable_external_operation_id(collision_b),
            f"external operation identity tuple collision: {candidate}",
        )
        if candidate in {"keyed_authenticated_digest_profile", "hybrid_equivalence_authority_profile"}:
            require(
                scope_key(collision_a, KEY_V1) != scope_key(collision_b, KEY_V1),
                f"scope key tuple collision: {candidate}",
            )

    for candidate in CANDIDATES[1:]:
        checks = result["checks"][candidate]
        require(all(checks.values()), f"eligible candidate has unproven obligation: {candidate}: {checks}")

    try:
        EquivalenceEngine("keyed_authenticated_digest_profile").classify_or_commit(
            identity,
            {"tenant_id": "tenant-a"},
        )
    except EvidenceViolation as exc:
        require(exc.code == "immutable_semantic_field_missing", "wrong missing-field failure")
    else:
        raise AssertionError("missing immutable field admitted")

    print("d4c_open_evt_011_source_falsification=PASS fingerprint=ineligible_confidentiality_only fingerprint_conflict=fail_closed bounded_traversal=preencode comparison_access=precanonical identity_encoding=injective keyed_digest=eligible retained_original=eligible hybrid=eligible trusted_contract_scope=precondition missing=uncertainty selection=none credit=none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
