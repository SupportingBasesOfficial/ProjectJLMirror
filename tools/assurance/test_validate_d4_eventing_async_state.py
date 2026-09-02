#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "assurance"))

import validate_d4_eventing_async_state as validator


def baseline() -> dict:
    return validator.load_manifest(ROOT)


def must_fail(mutator, expected_fragment: str) -> None:
    state = copy.deepcopy(baseline())
    mutator(state)
    errors = validator.validate_manifest(state)
    if not any(expected_fragment in error for error in errors):
        raise AssertionError(f"expected failure containing {expected_fragment!r}, got {errors!r}")


def collapse_evidence(state: dict) -> None:
    for track in state["tracks"]:
        track["required_evidence"] = ["documentation"]
        track["evidence_remaining"] = ["documentation"]


def main() -> int:
    state = baseline()
    errors = validator.validate_manifest(state)
    if errors:
        raise AssertionError(f"canonical D4 entry state failed validation: {errors!r}")

    if validator.EXPECTED_TOTAL_EVIDENCE != 26:
        raise AssertionError(f"unexpected D4 evidence inventory size: {validator.EXPECTED_TOTAL_EVIDENCE}")

    must_fail(lambda s: s.__setitem__("gate_state", "separately_accepted"), "must remain scoped")
    must_fail(lambda s: s.__setitem__("d4_transport_authority", "granted"), "must remain unselected/ungranted")
    must_fail(lambda s: s.__setitem__("wave4_implementation_authority", "granted"), "must not grant Wave 4")
    must_fail(lambda s: s.__setitem__("production_authority", "granted"), "must not grant production")
    must_fail(lambda s: s["predecessor"].__setitem__("state", "per_track_conformed"), "predecessor is not separately accepted")
    must_fail(lambda s: s["tracks"][0].__setitem__("candidate", "rabbitmq"), "leading candidate must remain Kafka")
    must_fail(lambda s: s["tracks"][1].__setitem__("candidate", "protobuf"), "must not silently select a candidate")
    must_fail(lambda s: s["tracks"][2]["evidence_completed"].append(s["tracks"][2]["required_evidence"][0]), "may not pre-credit evidence")
    must_fail(lambda s: s["tracks"][0]["evidence_remaining"].pop(), "remaining evidence must equal expected evidence")
    must_fail(lambda s: s["tracks"][0]["source_decisions"].append("OPEN-EVT-006"), "source decision drift")
    must_fail(lambda s: s["tracks"][2]["source_decisions"].remove("OPEN-EVT-025"), "source decision drift")
    must_fail(lambda s: s["explicit_c3_exclusions"].remove("OPEN-EVT-006"), "C3 exclusion set drift")
    must_fail(lambda s: s["explicit_product_or_later_gate_exclusions"].remove("OPEN-EVT-021"), "Product/later-gate exclusion set drift")
    must_fail(collapse_evidence, "required evidence inventory drift")

    print(
        "d4_entry_state_falsification=PASS "
        "premature_acceptance=blocked authority_escalation=blocked precredit=blocked "
        "candidate_leak=blocked c3_scope_leak=blocked recovery_scope_omission=blocked "
        "evidence_inventory_collapse=blocked total_required=26"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
