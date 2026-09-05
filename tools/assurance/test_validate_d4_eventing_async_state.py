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
    rogue["evidence_completed"] = [rogue["required_evidence"][0]]
    rogue["evidence_remaining"] = rogue["required_evidence"][1:]
    state["tracks"].insert(0, rogue)


def main() -> int:
    state = baseline()
    errors = validator.validate_manifest(state)
    if errors:
        raise AssertionError(f"canonical D4 selected-track state failed validation: {errors!r}")
    if validator.EXPECTED_TOTAL_EVIDENCE != 26:
        raise AssertionError(f"unexpected D4 evidence inventory size: {validator.EXPECTED_TOTAL_EVIDENCE}")
    if validator.EXPECTED_TOTAL_CREDITED != 12:
        raise AssertionError(f"unexpected D4 credited evidence count: {validator.EXPECTED_TOTAL_CREDITED}")

    d4a = lambda s: next(t for t in s["tracks"] if t["track_id"] == "D4-A")
    d4b = lambda s: next(t for t in s["tracks"] if t["track_id"] == "D4-B")

    must_fail(lambda s: s.__setitem__("gate_state", "separately_accepted"), "must remain scoped")
    must_fail(lambda s: s.__setitem__("d4_transport_authority", "granted"), "selected but authority must remain ungranted")
    must_fail(lambda s: s.__setitem__("d4_transport_authority", "not_selected_not_granted"), "selected but authority must remain ungranted")
    must_fail(lambda s: s.__setitem__("wave4_implementation_authority", "granted"), "must not grant Wave 4")
    must_fail(lambda s: s.__setitem__("production_authority", "granted"), "must not grant production")

    must_fail(lambda s: d4a(s)["evidence_completed"].pop(), "completed evidence drift")
    must_fail(lambda s: d4a(s)["evidence_remaining"].append("broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark"), "remaining evidence drift")
    must_fail(lambda s: d4a(s).__setitem__("state", "evidence_complete_selection_pending"), "scoped state drift")
    must_fail(lambda s: d4a(s).__setitem__("candidate_status", "leading_candidate_evidence_complete_selection_pending"), "selected at bounded C2 scope")
    must_fail(lambda s: d4a(s).__setitem__("candidate", "rabbitmq"), "selected candidate must remain Kafka")

    must_fail(lambda s: d4b(s).__setitem__("candidate", None), "D4-B selected profile drift")
    must_fail(lambda s: d4b(s)["candidate"]["serialization"].__setitem__("internal_broker", "avro_profile"), "D4-B selected profile drift")
    must_fail(lambda s: d4b(s)["candidate"]["serialization"].__setitem__("outbound_webhook", "protobuf_profile"), "D4-B selected profile drift")
    must_fail(lambda s: d4b(s)["candidate"].__setitem__("schema_catalog", "registry_backed_catalog"), "D4-B selected profile drift")
    must_fail(lambda s: d4b(s)["candidate"].__setitem__("contract_version", "semantic_version_like_contract_revision"), "D4-B selected profile drift")
    must_fail(lambda s: d4b(s).__setitem__("candidate_status", "not_selected"), "selected_c2_profile")
    must_fail(lambda s: d4b(s).__setitem__("state", "evidence_complete_selection_pending"), "scoped state drift")
    must_fail(lambda s: d4b(s)["evidence_completed"].pop(), "completed evidence drift")
    must_fail(lambda s: d4b(s)["evidence_remaining"].append("canonical_bounded_serialization_profile"), "remaining evidence drift")

    must_fail(lambda s: s["tracks"][2]["evidence_completed"].append(s["tracks"][2]["required_evidence"][0]), "completed evidence drift")
    must_fail(duplicate_rogue_d4c, "D4 track identity multiplicity drift")
    must_fail(lambda s: s["explicit_c3_exclusions"].remove("OPEN-EVT-006"), "C3 exclusion set drift")
    must_fail(lambda s: s["explicit_product_or_later_gate_exclusions"].remove("OPEN-EVT-021"), "Product/later-gate exclusion set drift")

    print("d4_state_falsification=PASS full_d4_acceptance=blocked transport_grant=blocked d4a_selection_rollback=blocked d4b_profile_drift=blocked d4b_surface_swap=blocked d4b_catalog_swap=blocked d4b_version_swap=blocked evidence_regression=blocked duplicate_track_identity=blocked sibling_credit=blocked product_wave4_production=blocked c3_scope_leak=blocked total_required=26 total_credited=12")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
