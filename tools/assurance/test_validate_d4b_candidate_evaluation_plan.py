#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "assurance"))
import validate_d4b_candidate_evaluation_plan as validator


def snapshot() -> dict[Path, object]:
    return {
        validator.PLAN: json.loads((ROOT / validator.PLAN).read_text(encoding="utf-8")),
        validator.STATE: json.loads((ROOT / validator.STATE).read_text(encoding="utf-8")),
        validator.D4B_LEDGER: json.loads((ROOT / validator.D4B_LEDGER).read_text(encoding="utf-8")),
    }


def validate_mutated(mutator) -> list[str]:
    data = snapshot()
    mutator(data)
    with TemporaryDirectory() as td:
        root = Path(td)
        for path, value in data.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, bytes):
                target.write_bytes(value)
            else:
                target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return validator.validate(root)


def must_fail(mutator, fragment: str) -> None:
    errors = validate_mutated(mutator)
    if not any(fragment in e for e in errors):
        raise AssertionError(f"expected {fragment!r}, got {errors!r}")


def obj(data: dict[Path, object], path: Path) -> dict:
    value = data[path]
    assert isinstance(value, dict)
    return value


def track(data: dict[Path, object], track_id: str) -> dict:
    state = obj(data, validator.STATE)
    return next(t for t in state["tracks"] if t["track_id"] == track_id)


def inject_duplicate_selection_state(data: dict[Path, object]) -> None:
    raw = (ROOT / validator.PLAN).read_bytes()
    needle = b'  "selection_state": "not_selected",\n'
    if raw.count(needle) != 1:
        raise AssertionError("canonical selection_state line not uniquely located")
    data[validator.PLAN] = raw.replace(needle, b'  "selection_state": "selected",\n' + needle, 1)


def main() -> int:
    errors = validator.validate(ROOT)
    if errors:
        raise AssertionError(f"canonical evaluation plan failed: {errors!r}")

    must_fail(lambda d: obj(d, validator.PLAN).__setitem__("candidate", "protobuf"), "evaluation plan exact key schema drift")
    must_fail(inject_duplicate_selection_state, "duplicate JSON member 'selection_state'")
    must_fail(lambda d: obj(d, validator.PLAN)["axes"].pop("contract_version_representation"), "exact three-axis evaluation inventory drift")
    must_fail(lambda d: obj(d, validator.PLAN)["axes"]["wire_serialization_and_schema_language"].__setitem__("preferred_candidate", "protobuf_profile"), "exact key schema drift")
    must_fail(lambda d: obj(d, validator.PLAN)["axes"]["wire_serialization_and_schema_language"]["candidate_classes"].pop(), "candidate class inventory drift")
    must_fail(lambda d: obj(d, validator.PLAN)["axes"]["schema_registry_catalog_and_tooling"]["must_prove"].pop(), "exact proof inventory drift")
    must_fail(lambda d: obj(d, validator.PLAN)["cross_axis_invariants"].remove("a_catalog_or_registry_product_cannot_select_wire_serialization_by_implication"), "cross-axis exact invariant inventory drift")
    must_fail(lambda d: obj(d, validator.PLAN).__setitem__("selection_state", "selected"), "must not select D4-B")
    must_fail(lambda d: obj(d, validator.PLAN)["evaluation_output_states"].append("selected"), "evaluation output state inventory drift")
    must_fail(lambda d: obj(d, validator.D4B_LEDGER)["credited_evidence"].pop(), "D4-B 5/5 ledger drift")
    must_fail(lambda d: track(d, "D4-A").__setitem__("candidate", "rabbitmq"), "D4-A Kafka 7/7 regression")
    must_fail(lambda d: track(d, "D4-B").__setitem__("candidate", "protobuf"), "D4-B premature selection")
    must_fail(lambda d: track(d, "D4-C")["evidence_completed"].append(track(d, "D4-C")["required_evidence"][0]), "D4-C/D must remain open")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("gate_state", "separately_accepted"), "D4 gate must remain scoped")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("canonical_product_implementation_authority", "granted"), "Product authority escalation")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("wave4_implementation_authority", "granted"), "Wave4 authority escalation")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("production_authority", "granted"), "production authority escalation")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("c3_numeric_topology_authority", "selected"), "C3 authority escalation")

    print("d4b_candidate_evaluation_falsification=PASS duplicate_json=blocked additive_selection=blocked axis_removal=blocked hidden_preference=blocked candidate_collapse=blocked proof_weakening=blocked coupling=blocked premature_selection=blocked evidence_mutation=blocked d4a_regression=blocked sibling_leak=blocked authority_escalation=blocked")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
