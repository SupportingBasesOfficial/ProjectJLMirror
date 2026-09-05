#!/usr/bin/env python3
from __future__ import annotations

import copy
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


def inject_duplicate_rogue_d4c(data: dict[Path, object]) -> None:
    state = data[validator.STATE]
    assert isinstance(state, dict)
    rogue = copy.deepcopy(next(t for t in state["tracks"] if t["track_id"] == "D4-C"))
    rogue["candidate"] = "rogue-selected"
    rogue["candidate_status"] = "selected"
    rogue["state"] = "selected_candidate"
    rogue["evidence_completed"] = [rogue["required_evidence"][0]]
    rogue["evidence_remaining"] = rogue["required_evidence"][1:]
    state["tracks"].insert(0, rogue)


def inject_candidate_fields(data: dict[Path, object]) -> None:
    promotion = data[validator.PROMOTION]
    assert isinstance(promotion, dict)
    promotion["candidate"] = "protobuf"
    promotion["candidate_status"] = "selected"


def raw_promotion_bytes() -> bytes:
    return (ROOT / validator.PROMOTION).read_bytes()


def inject_duplicate_top_level_selection(data: dict[Path, object]) -> None:
    raw = raw_promotion_bytes()
    needle = b'  "selection_state": "not_selected",\n'
    replacement = b'  "selection_state": "selected",\n' + needle
    if raw.count(needle) != 1:
        raise AssertionError("canonical promotion selection_state line not uniquely located")
    data[validator.PROMOTION] = raw.replace(needle, replacement, 1)


def inject_duplicate_nested_review_mode(data: dict[Path, object]) -> None:
    raw = raw_promotion_bytes()
    needle = b'    "review_mode": "independent_exact_head_adversarial_clean_with_fresh_codex_no_findings_reaction",\n'
    replacement = b'    "review_mode": "tampered_first_value",\n' + needle
    if raw.count(needle) != 1:
        raise AssertionError("canonical promotion review_mode line not uniquely located")
    data[validator.PROMOTION] = raw.replace(needle, replacement, 1)


def main() -> int:
    errors = validator.validate(ROOT)
    if errors:
        raise AssertionError(f"canonical D4-B promotion/current selection failed: {errors!r}")

    # Current ledger exactness: evidence is unchanged while current selection is exact.
    must_fail(lambda d: d[validator.PLAN]["credited_evidence"].pop(), "credited evidence drift")
    must_fail(lambda d: d[validator.PLAN]["credited_evidence"].append("canonical_bounded_serialization_profile"), "credited evidence drift")
    must_fail(lambda d: d[validator.PLAN].__setitem__("selection_state", "not_selected"), "current selection must remain selected")
    must_fail(lambda d: d[validator.PLAN].__setitem__("candidate", None), "current selected profile drift")
    must_fail(lambda d: d[validator.PLAN]["candidate"]["serialization"].__setitem__("internal_broker", "avro_profile"), "current selected profile drift")
    must_fail(lambda d: d[validator.PLAN]["candidate"].__setitem__("schema_catalog", "registry_backed_catalog"), "current selected profile drift")
    must_fail(lambda d: d[validator.PLAN]["candidate"].__setitem__("contract_version", "semantic_version_like_contract_revision"), "current selected profile drift")
    must_fail(lambda d: d[validator.PLAN].__setitem__("d4_transport_authority", "granted"), "plan transport authority drift")
    must_fail(lambda d: d[validator.PLAN].__setitem__("separate_d4_acceptance_required", False), "full D4 acceptance remains separate")

    # Historical promotion identity, schema, strict JSON, review and provenance remain immutable.
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("gate_id", "D3"), "promotion identity envelope drift")
    must_fail(inject_candidate_fields, "promotion exact key schema drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("unexpected_field", "smuggled"), "promotion exact key schema drift")
    must_fail(lambda d: d[validator.PROMOTION]["source_review"].__setitem__("unexpected_field", "smuggled"), "source review exact key schema drift")
    must_fail(lambda d: d[validator.PROMOTION]["source_workflow"].__setitem__("unexpected_field", "smuggled"), "source workflow exact key schema drift")
    must_fail(lambda d: d[validator.PROMOTION]["source_manifest"].__setitem__("unexpected_field", "smuggled"), "source manifest exact key schema drift")
    must_fail(inject_duplicate_top_level_selection, "duplicate JSON member 'selection_state'")
    must_fail(inject_duplicate_nested_review_mode, "duplicate JSON member 'review_mode'")
    must_fail(lambda d: d[validator.PROMOTION]["source_review"].__setitem__("review_mode", "older_review_reused"), "source review mode drift")
    must_fail(lambda d: d[validator.PROMOTION]["source_review"].__setitem__("material_threads_unresolved", 1), "zero unresolved material threads")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("source_reviewed_head", "0" * 40), "source reviewed HEAD drift")
    must_fail(lambda d: d[validator.PROMOTION]["source_workflow"].__setitem__("workflow_id", 1), "source workflow id provenance drift")
    must_fail(lambda d: d[validator.PROMOTION]["source_workflow"].__setitem__("workflow_path", ".github/workflows/other.yml"), "source workflow path provenance drift")
    must_fail(lambda d: d[validator.PROMOTION]["source_workflow"].__setitem__("workflow_event", "workflow_dispatch"), "source workflow event provenance drift")
    must_fail(lambda d: d[validator.PROMOTION]["source_workflow"].__setitem__("source_head_branch", "rogue/source"), "source workflow branch provenance drift")
    must_fail(lambda d: d[validator.PROMOTION]["source_workflow"].__setitem__("artifact_digest", "sha256:deadbeef"), "source artifact digest drift")
    must_fail(lambda d: d[validator.PROMOTION]["source_manifest"].__setitem__("path", "implementation/other.json"), "source-manifest path drift")
    must_fail(lambda d: d[validator.PROMOTION]["credited_evidence"].append("canonical_bounded_serialization_profile"), "promotion credit set drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("credit_count", 4), "promotion credit set drift")

    # Historical promotion may never be rewritten to pretend selection already existed.
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("selection_state", "selected"), "historical promotion must remain not_selected")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("serialization_selection_state", "selected"), "historical promotion serialization selection drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("schema_catalog_selection_state", "selected"), "historical promotion schema catalog selection drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("contract_version_syntax_selection_state", "selected"), "historical promotion contract version syntax selection drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("d4_gate_state", "separately_accepted"), "promotion must not accept D4")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("d4_transport_authority", "granted"), "promotion transport authority drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("canonical_product_implementation_authority", "granted"), "promotion Product authority drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("wave4_implementation_authority", "granted"), "promotion Wave 4 authority drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("production_authority", "granted"), "promotion production authority drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("c3_numeric_topology_authority", "selected"), "promotion C3 authority drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("separate_selection_required", False), "historical promotion must preserve separate selection")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("separate_d4_acceptance_required", False), "historical promotion must preserve separate selection")

    # Immutable source package and current global-state boundaries.
    must_fail(lambda d: d.__setitem__(validator.SOURCE, d[validator.SOURCE] + b"\n"), "source manifest byte drift")
    must_fail(lambda d: track(d, "D4-B").__setitem__("candidate", None), "current state selected profile drift")
    must_fail(lambda d: track(d, "D4-B")["candidate"]["serialization"].__setitem__("outbound_webhook", "protobuf_profile"), "current state selected profile drift")
    must_fail(lambda d: track(d, "D4-B")["evidence_completed"].pop(), "state credit drift")
    must_fail(lambda d: track(d, "D4-A").__setitem__("candidate", "rabbitmq"), "D4-A selected candidate drift")
    must_fail(lambda d: track(d, "D4-A")["evidence_completed"].pop(), "D4-A exact 7/7 evidence membership drift")
    must_fail(substitute_d4a_with_d4b_evidence, "D4-A exact 7/7 evidence membership drift")
    must_fail(inject_duplicate_rogue_d4c, "D4 track identities must be exactly")
    must_fail(lambda d: track(d, "D4-C")["evidence_completed"].append(track(d, "D4-C")["required_evidence"][0]), "D4-C must remain uncredited")
    must_fail(lambda d: track(d, "D4-D").__setitem__("candidate", "candidate-x"), "D4-D candidate must remain unselected")
    must_fail(lambda d: d[validator.STATE].__setitem__("gate_state", "separately_accepted"), "D4 must remain scoped")
    must_fail(lambda d: d[validator.STATE].__setitem__("production_authority", "granted"), "production authority must remain none")

    print(
        "d4b_ledger_falsification=PASS exact_credit=locked current_selection=locked historical_promotion_selection=locked "
        "exact_promotion_schema=locked duplicate_json_members=blocked duplicate_track_identity=blocked source_workflow_identity=blocked "
        "provenance_tamper=blocked source_mutation=blocked d4a_exact_membership=blocked cross_track_substitution=blocked "
        "d4c_d_leak=blocked full_d4_acceptance=blocked authority_escalation=blocked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
