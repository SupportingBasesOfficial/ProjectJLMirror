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


def duplicate_rogue_d4c(state: dict) -> None:
    rogue = copy.deepcopy(next(t for t in state["tracks"] if t["track_id"] == "D4-C"))
    rogue["candidate"] = "rogue-selected"
    rogue["candidate_status"] = "selected"
    rogue["state"] = "selected_candidate"
    state["tracks"].insert(0, rogue)


def main() -> int:
    state = baseline()
    errors = validator.validate_manifest(state)
    if errors:
        raise AssertionError(f"canonical D4 state failed validation: {errors!r}")
    if validator.EXPECTED_TOTAL_EVIDENCE != 26:
        raise AssertionError(f"unexpected D4 evidence inventory size: {validator.EXPECTED_TOTAL_EVIDENCE}")
    if validator.EXPECTED_TOTAL_CREDITED != 17:
        raise AssertionError(f"unexpected D4 credited evidence count: {validator.EXPECTED_TOTAL_CREDITED}")

    d4a = lambda s: next(t for t in s["tracks"] if t["track_id"] == "D4-A")
    d4b = lambda s: next(t for t in s["tracks"] if t["track_id"] == "D4-B")
    d4c = lambda s: next(t for t in s["tracks"] if t["track_id"] == "D4-C")

    must_fail(lambda s: s.__setitem__("gate_state", "separately_accepted"), "must remain scoped")
    must_fail(lambda s: s.__setitem__("d4_transport_authority", "granted"), "selected but authority must remain ungranted")
    must_fail(lambda s: s.__setitem__("wave4_implementation_authority", "granted"), "must not grant Wave 4")
    must_fail(lambda s: s.__setitem__("production_authority", "granted"), "must not grant production")

    must_fail(lambda s: d4a(s)["evidence_completed"].pop(), "completed evidence drift")
    must_fail(lambda s: d4a(s).__setitem__("candidate", "rabbitmq"), "selected candidate must remain Kafka")
    must_fail(lambda s: d4b(s).__setitem__("candidate", None), "D4-B selected profile drift")
    must_fail(lambda s: d4b(s)["evidence_completed"].pop(), "completed evidence drift")

    def regress_fifth_credit(s):
        d = d4c(s)
        credit = "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity"
        d["evidence_completed"].remove(credit)
        d["evidence_remaining"].insert(0, credit)
    must_fail(regress_fifth_credit, "completed evidence drift")

    def leak_sixth_credit(s):
        d = d4c(s)
        d["evidence_completed"].append(d["evidence_remaining"].pop(0))
    must_fail(leak_sixth_credit, "completed evidence drift")

    must_fail(lambda s: d4c(s).__setitem__("candidate", "durable_platform_quarantine_store_with_broker_dlq_adapter"), "must not silently select a candidate")
    must_fail(lambda s: d4c(s).__setitem__("candidate_status", "selected"), "candidate status must remain not_selected")
    must_fail(lambda s: d4c(s).__setitem__("state", "selected_candidate"), "scoped state drift")

    must_fail(duplicate_rogue_d4c, "D4 track identity multiplicity drift")
    must_fail(lambda s: s["explicit_c3_exclusions"].remove("OPEN-EVT-006"), "C3 exclusion set drift")
    must_fail(lambda s: s["explicit_product_or_later_gate_exclusions"].remove("OPEN-EVT-021"), "Product/later-gate exclusion set drift")

    print("d4_state_falsification=PASS full_d4_acceptance=blocked transport_grant=blocked d4a_b_regression=blocked d4c_fifth_credit_regression=blocked d4c_sixth_credit_leakage=blocked d4c_selection_leakage=blocked duplicate_track_identity=blocked product_wave4_production=blocked c3_scope_leak=blocked total_required=26 total_credited=17")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
