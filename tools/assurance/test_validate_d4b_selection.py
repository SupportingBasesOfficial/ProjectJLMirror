#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import validate_d4b_selection as validator

ROOT = Path(__file__).resolve().parents[2]
FILES = [validator.SELECTION, validator.PLAN, validator.STATE, validator.AXIS_A, validator.AXIS_B, validator.AXIS_C]


def baseline() -> dict[Path, object]:
    return {path: json.loads((ROOT / path).read_text(encoding="utf-8")) for path in FILES}


def write_fixture(root: Path, documents: dict[Path, object]) -> None:
    for path, payload in documents.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, bytes):
            target.write_bytes(payload)
        else:
            target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def must_fail(mutator, expected_fragment: str) -> None:
    docs = copy.deepcopy(baseline())
    mutator(docs)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_fixture(root, docs)
        errors = validator.validate(root)
    if not any(expected_fragment in error for error in errors):
        raise AssertionError(f"expected failure containing {expected_fragment!r}, got {errors!r}")


def inject_duplicate_selection_state(documents: dict[Path, object]) -> None:
    raw = (ROOT / validator.SELECTION).read_bytes()
    needle = b'  "selection_state": "selected",\n  "selection_scope": "bounded_c2_contract_profile_selection_only",\n'
    if raw.count(needle) != 1:
        raise AssertionError("top-level selection_state/selection_scope pair not uniquely located")
    replacement = (
        b'  "selection_state": "not_selected",\n'
        b'  "selection_state": "selected",\n'
        b'  "selection_scope": "bounded_c2_contract_profile_selection_only",\n'
    )
    documents[validator.SELECTION] = raw.replace(needle, replacement, 1)


def main() -> int:
    errors = validator.validate(ROOT)
    if errors:
        raise AssertionError(f"canonical D4-B selection failed validation: {errors!r}")

    must_fail(inject_duplicate_selection_state, "duplicate JSON member 'selection_state'")
    must_fail(lambda d: d[validator.SELECTION].__setitem__("selection_base_main_commit", "drift"), "selection base drift")
    must_fail(lambda d: d[validator.SELECTION]["serialization"].__setitem__("internal_broker", "avro_profile"), "internal broker serialization drift")
    must_fail(lambda d: d[validator.SELECTION]["serialization"].__setitem__("outbound_webhook", "protobuf_profile"), "outbound webhook serialization drift")
    must_fail(lambda d: d[validator.SELECTION]["serialization"].__setitem__("realtime_protocol", "protobuf_profile"), "realtime protocol must remain independent")
    must_fail(lambda d: d[validator.SELECTION]["schema_catalog"].__setitem__("mechanism", "registry_backed_catalog"), "catalog mechanism drift")
    must_fail(lambda d: d[validator.SELECTION]["schema_catalog"].__setitem__("registry_role", "canonical_contract_authority"), "registry role drift")
    must_fail(lambda d: d[validator.SELECTION]["schema_catalog"].__setitem__("registry_product", "vendor-x"), "registry vendor/product must remain unselected")
    must_fail(lambda d: d[validator.SELECTION]["contract_version"].__setitem__("representation", "semantic_version_like_contract_revision"), "contract-version representation drift")
    must_fail(lambda d: d[validator.SELECTION]["contract_version"].__setitem__("zero_allowed", True), "zero must remain forbidden")
    must_fail(lambda d: d[validator.SELECTION]["contract_version"].__setitem__("ordering_authority", "numeric_order"), "must not gain ordering authority")

    must_fail(lambda d: d[validator.AXIS_A].__setitem__("selection_state", "selected"), "Axis A source history must remain not_selected")
    must_fail(lambda d: d[validator.AXIS_B].__setitem__("ledger_credit", ["schema_catalog_semantic_manifest_compatibility_ci"]), "Axis B source ledger-credit history drift")
    must_fail(lambda d: d[validator.AXIS_C].__setitem__("current_run_auto_credit", True), "Axis C source auto-credit history drift")
    must_fail(lambda d: d[validator.AXIS_A]["candidate_results"].__setitem__("protobuf_profile", "ineligible_by_contract"), "selected internal profile lacks eligible Axis A evidence")
    must_fail(lambda d: d[validator.AXIS_B]["candidate_results"].__setitem__("hybrid_reviewed_git_plus_registry_catalog", "ineligible_by_contract"), "selected catalog mechanism lacks eligible Axis B evidence")
    must_fail(lambda d: d[validator.AXIS_C]["candidate_results"].__setitem__("positive_integer_family_revision", "ineligible_by_contract"), "selected contract-version representation lacks eligible Axis C evidence")

    must_fail(lambda d: d[validator.PLAN].__setitem__("selection_state", "not_selected"), "evidence-plan selection state drift")
    must_fail(lambda d: d[validator.PLAN].__setitem__("current_run_auto_credit", True), "cannot invent source-run auto-credit")
    must_fail(lambda d: d[validator.PLAN]["credited_evidence"].pop(), "must preserve 5/5 evidence accounting")
    must_fail(lambda d: d[validator.PLAN].__setitem__("separate_d4_acceptance_required", False), "full D4 acceptance must remain separate")

    must_fail(lambda d: d[validator.STATE].__setitem__("gate_state", "separately_accepted"), "D4 must remain scoped")
    must_fail(lambda d: d[validator.STATE].__setitem__("canonical_product_implementation_authority", "granted"), "Product implementation authority must remain ungranted")
    must_fail(lambda d: d[validator.STATE].__setitem__("wave4_implementation_authority", "granted"), "Wave4 implementation authority must remain ungranted")
    must_fail(lambda d: d[validator.STATE].__setitem__("production_authority", "granted"), "production authority must remain none")
    must_fail(lambda d: d[validator.STATE].__setitem__("c3_numeric_topology_authority", "selected"), "C3 numeric/topology authority must remain not_selected")
    must_fail(lambda d: next(t for t in d[validator.STATE]["tracks"] if t["track_id"] == "D4-C").__setitem__("candidate", "rabbitmq"), "D4-C must remain open/uncredited")

    print("d4b_selection_falsification=PASS duplicate_json=blocked internal_surface_swap=blocked webhook_surface_swap=blocked realtime_coupling=blocked catalog_swap=blocked registry_role_escalation=blocked registry_vendor_selection=blocked contract_version_swap=blocked version_ordering_authority=blocked source_history_rewrite=blocked unsupported_selection=blocked evidence_credit_drift=blocked full_d4_acceptance=blocked product_wave4_production=blocked c3_scope_leak=blocked sibling_selection=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
