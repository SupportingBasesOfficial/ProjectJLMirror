#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "assurance"))
import validate_d4b_evidence_plan as validator

FILES = [validator.PLAN, validator.STATE, validator.PROMOTION, validator.SOURCE]


def snapshot() -> dict[Path, object]:
    out: dict[Path, object] = {}
    for path in FILES:
        raw = (ROOT / path).read_bytes()
        out[path] = raw if path == validator.SOURCE else json.loads(raw)
    return out


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
        raise AssertionError(f"expected failure containing {fragment!r}, got {errors!r}")


def track(data: dict[Path, object], track_id: str) -> dict:
    state = data[validator.STATE]
    assert isinstance(state, dict)
    return next(t for t in state["tracks"] if t["track_id"] == track_id)


def substitute_d4a_with_d4b_evidence(data: dict[Path, object]) -> None:
    completed = track(data, "D4-A")["evidence_completed"]
    completed[0] = "canonical_bounded_serialization_profile"


def main() -> int:
    errors = validator.validate(ROOT)
    if errors:
        raise AssertionError(f"canonical D4-B promotion failed: {errors!r}")

    # Ledger exactness and candidate neutrality.
    must_fail(lambda d: d[validator.PLAN]["credited_evidence"].pop(), "credited evidence drift")
    must_fail(lambda d: d[validator.PLAN]["credited_evidence"].append("canonical_bounded_serialization_profile"), "credited evidence drift")
    must_fail(lambda d: d[validator.PLAN].__setitem__("selection_state", "selected"), "selection must remain not_selected")
    must_fail(lambda d: d[validator.PLAN].__setitem__("d4_transport_authority", "granted"), "plan transport authority drift")

    # Promotion identity, review and provenance must be immutable.
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("gate_id", "D3"), "promotion identity envelope drift")
    must_fail(lambda d: d[validator.PROMOTION]["source_review"].__setitem__("review_mode", "older_review_reused"), "source review mode drift")
    must_fail(lambda d: d[validator.PROMOTION]["source_review"].__setitem__("material_threads_unresolved", 1), "zero unresolved material threads")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("source_reviewed_head", "0" * 40), "source reviewed HEAD drift")
    must_fail(lambda d: d[validator.PROMOTION]["source_workflow"].__setitem__("artifact_digest", "sha256:deadbeef"), "artifact digest drift")
    must_fail(lambda d: d[validator.PROMOTION]["source_manifest"].__setitem__("path", "implementation/other.json"), "source-manifest path drift")
    must_fail(lambda d: d[validator.PROMOTION]["credited_evidence"].append("canonical_bounded_serialization_profile"), "promotion credit set drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("credit_count", 4), "promotion credit set drift")

    # The promotion record itself may not smuggle selection or authority.
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("serialization_selection_state", "selected"), "promotion serialization selection drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("schema_catalog_selection_state", "selected"), "promotion schema catalog selection drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("contract_version_syntax_selection_state", "selected"), "promotion contract version syntax selection drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("d4_gate_state", "separately_accepted"), "promotion must not accept D4")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("d4_transport_authority", "granted"), "promotion transport authority drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("canonical_product_implementation_authority", "granted"), "promotion Product authority drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("wave4_implementation_authority", "granted"), "promotion Wave 4 authority drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("production_authority", "granted"), "promotion production authority drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("c3_numeric_topology_authority", "selected"), "promotion C3 authority drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("separate_selection_required", False), "separate selection and D4 acceptance")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("separate_d4_acceptance_required", False), "separate selection and D4 acceptance")

    # Immutable source package and global state boundaries.
    must_fail(lambda d: d.__setitem__(validator.SOURCE, d[validator.SOURCE] + b"\n"), "source manifest byte drift")
    must_fail(lambda d: track(d, "D4-B").__setitem__("candidate", "protobuf"), "must not silently select")
    must_fail(lambda d: track(d, "D4-B")["evidence_completed"].pop(), "state credit drift")
    must_fail(lambda d: track(d, "D4-A").__setitem__("candidate", "rabbitmq"), "D4-A selected candidate drift")
    must_fail(lambda d: track(d, "D4-A")["evidence_completed"].pop(), "D4-A exact 7/7 evidence membership drift")
    must_fail(substitute_d4a_with_d4b_evidence, "D4-A exact 7/7 evidence membership drift")
    must_fail(lambda d: track(d, "D4-C")["evidence_completed"].append(track(d, "D4-C")["required_evidence"][0]), "D4-C must remain uncredited")
    must_fail(lambda d: track(d, "D4-D").__setitem__("candidate", "candidate-x"), "D4-D candidate must remain unselected")
    must_fail(lambda d: d[validator.STATE].__setitem__("gate_state", "separately_accepted"), "D4 must remain scoped")
    must_fail(lambda d: d[validator.STATE].__setitem__("production_authority", "granted"), "production authority must remain none")

    print(
        "d4b_ledger_falsification=PASS exact_credit=locked selection=blocked promotion_record_selection=blocked "
        "promotion_record_authority=blocked provenance_tamper=blocked source_mutation=blocked "
        "d4a_exact_membership=blocked cross_track_substitution=blocked d4c_d_leak=blocked full_d4_acceptance=blocked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
