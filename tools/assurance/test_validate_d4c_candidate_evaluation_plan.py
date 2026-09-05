#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "assurance"))
import validate_d4c_candidate_evaluation_plan as validator


def snapshot() -> dict[Path, object]:
    return {
        validator.PLAN: json.loads((ROOT / validator.PLAN).read_text(encoding="utf-8")),
        validator.STATE: json.loads((ROOT / validator.STATE).read_text(encoding="utf-8")),
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
        raise AssertionError("selection_state line not uniquely located")
    data[validator.PLAN] = raw.replace(needle, b'  "selection_state": "selected",\n' + needle, 1)


def main() -> int:
    errors = validator.validate(ROOT)
    if errors:
        raise AssertionError(f"canonical D4-C candidate evaluation failed: {errors!r}")

    must_fail(lambda d: obj(d, validator.PLAN).__setitem__("candidate", "some_profile"), "exact key schema drift")
    must_fail(inject_duplicate_selection_state, "duplicate JSON member 'selection_state'")
    must_fail(lambda d: obj(d, validator.PLAN).__setitem__("schema_version", True), "schema version drift")
    must_fail(lambda d: obj(d, validator.PLAN).__setitem__("selection_state", "selected"), "must remain not selected")
    must_fail(lambda d: obj(d, validator.PLAN).__setitem__("selection_authority", "granted"), "selection authority must remain ungranted")
    must_fail(lambda d: obj(d, validator.PLAN)["axes"].pop("historical_reader_and_upcaster"), "exact nine-axis inventory drift")
    must_fail(lambda d: obj(d, validator.PLAN)["axes"]["ack_visibility_lease_and_checkpoint"].__setitem__("preferred_candidate", "durable_inbox_claim_then_broker_ack_profile"), "exact key schema drift")
    must_fail(lambda d: obj(d, validator.PLAN)["axes"]["quarantine_and_redrive"]["candidate_classes"].pop(), "candidate class inventory drift")
    must_fail(lambda d: obj(d, validator.PLAN)["axes"]["scoped_content_equivalence_authority"]["must_prove"].pop(), "proof inventory drift")
    must_fail(lambda d: obj(d, validator.PLAN)["axes"]["recovery_generation_reconciliation_and_activation"].__setitem__("evidence_id", "wrong"), "evidence binding drift")
    must_fail(lambda d: obj(d, validator.PLAN)["source_decisions"].pop(), "source decision inventory drift")
    must_fail(lambda d: obj(d, validator.PLAN)["cross_axis_invariants"].pop(), "cross-axis invariant inventory drift")
    must_fail(lambda d: obj(d, validator.PLAN)["evaluation_output_states"].append("selected"), "evaluation output inventory drift")
    must_fail(lambda d: obj(d, validator.PLAN)["forbidden_outputs"].remove("ledger_credit_granted"), "forbidden output inventory drift")

    must_fail(lambda d: track(d, "D4-A").__setitem__("candidate", "rabbitmq"), "D4-A selected 7/7 regression")
    must_fail(lambda d: track(d, "D4-B").__setitem__("candidate", None), "D4-B selected 5/5 regression")
    must_fail(lambda d: track(d, "D4-C").__setitem__("candidate", "some_profile"), "D4-C state must remain open/unselected")
    must_fail(lambda d: track(d, "D4-C")["evidence_completed"].append(track(d, "D4-C")["required_evidence"][0]), "D4-C evidence must remain 0/9")
    must_fail(lambda d: track(d, "D4-D")["evidence_completed"].append(track(d, "D4-D")["required_evidence"][0]), "D4-D must remain open")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("gate_state", "separately_accepted"), "D4 gate must remain scoped")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("d4_transport_authority", "granted"), "D4 transport authority drift")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("canonical_product_implementation_authority", "granted"), "Product authority escalation")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("wave4_implementation_authority", "granted"), "Wave4 authority escalation")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("production_authority", "granted"), "production authority escalation")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("c3_numeric_topology_authority", "selected"), "C3 authority escalation")

    print("d4c_candidate_evaluation_falsification=PASS duplicate_json=blocked hidden_selection=blocked axis_removal=blocked hidden_preference=blocked candidate_collapse=blocked proof_weakening=blocked evidence_binding_drift=blocked source_decision_drift=blocked output_escalation=blocked d4a_d4b_regression=blocked d4c_credit_leak=blocked d4d_credit_leak=blocked authority_escalation=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
