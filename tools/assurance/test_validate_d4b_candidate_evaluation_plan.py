#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "assurance"))
import validate_d4b_candidate_evaluation_plan as validator


def baseline() -> tuple[dict, dict, dict]:
    return (
        json.loads((ROOT / validator.PLAN).read_text(encoding="utf-8")),
        json.loads((ROOT / validator.STATE).read_text(encoding="utf-8")),
        json.loads((ROOT / validator.D4B_LEDGER).read_text(encoding="utf-8")),
    )


def run(plan: dict, state: dict, ledger: dict) -> list[str]:
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as td:
        root = Path(td)
        for path, value in ((validator.PLAN, plan), (validator.STATE, state), (validator.D4B_LEDGER, ledger)):
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return validator.validate(root)


def must_fail(mutator, fragment: str) -> None:
    plan, state, ledger = baseline()
    mutator(plan, state, ledger)
    errors = run(plan, state, ledger)
    if not any(fragment in e for e in errors):
        raise AssertionError(f"expected {fragment!r}, got {errors!r}")


def track(state: dict, track_id: str) -> dict:
    return next(t for t in state["tracks"] if t["track_id"] == track_id)


def main() -> int:
    plan, state, ledger = baseline()
    errors = run(plan, state, ledger)
    if errors:
        raise AssertionError(f"canonical plan failed: {errors!r}")

    must_fail(lambda p, s, l: p["axes"].pop("contract_version_representation"), "exact three-axis evaluation inventory drift")
    must_fail(lambda p, s, l: p["axes"]["wire_serialization_and_schema_language"]["candidate_classes"].pop(), "wire candidate class inventory drift")
    must_fail(lambda p, s, l: p["axes"]["schema_registry_catalog_and_tooling"]["must_prove"].clear(), "proof inventory weakened")
    must_fail(lambda p, s, l: p["cross_axis_invariants"].remove("a_catalog_or_registry_product_cannot_select_wire_serialization_by_implication"), "cross-axis anti-coupling")
    must_fail(lambda p, s, l: p.__setitem__("selection_state", "selected"), "must not select D4-B")
    must_fail(lambda p, s, l: p["evaluation_output_states"].append("selected"), "evaluation output state inventory drift")
    must_fail(lambda p, s, l: l["credited_evidence"].pop(), "D4-B 5/5 ledger drift")
    must_fail(lambda p, s, l: track(s, "D4-A").__setitem__("candidate", "rabbitmq"), "D4-A Kafka 7/7 regression")
    must_fail(lambda p, s, l: track(s, "D4-B").__setitem__("candidate", "protobuf"), "D4-B premature selection")
    must_fail(lambda p, s, l: track(s, "D4-C")["evidence_completed"].append(track(s, "D4-C")["required_evidence"][0]), "D4-C/D must remain open")
    must_fail(lambda p, s, l: s.__setitem__("gate_state", "separately_accepted"), "D4 gate must remain scoped")
    must_fail(lambda p, s, l: s.__setitem__("canonical_product_implementation_authority", "granted"), "Product authority escalation")
    must_fail(lambda p, s, l: s.__setitem__("wave4_implementation_authority", "granted"), "Wave4 authority escalation")
    must_fail(lambda p, s, l: s.__setitem__("production_authority", "granted"), "production authority escalation")
    must_fail(lambda p, s, l: s.__setitem__("c3_numeric_topology_authority", "selected"), "C3 authority escalation")

    print("d4b_candidate_evaluation_falsification=PASS axis_removal=blocked candidate_collapse=blocked proof_weakening=blocked coupling=blocked premature_selection=blocked evidence_mutation=blocked d4a_regression=blocked sibling_leak=blocked authority_escalation=blocked")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
