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


def track(documents: dict[Path, object], track_id: str) -> dict:
    state = documents[validator.STATE]
    assert isinstance(state, dict)
    return next(item for item in state["tracks"] if item["track_id"] == track_id)


def as_keyed_object(values: list[str]) -> dict[str, object]:
    return {value: {} for value in values}


def main() -> int:
    errors = validator.validate(ROOT)
    if errors:
        raise AssertionError(f"canonical D4-B selection failed validation: {errors!r}")

    must_fail(inject_duplicate_selection_state, "duplicate JSON member 'selection_state'")
    must_fail(lambda d: d[validator.SELECTION].__setitem__("hidden_authority", "granted"), "selection exact key schema drift")
    must_fail(lambda d: d[validator.PLAN].__setitem__("full_d4_acceptance", "granted"), "D4-B evidence-plan exact key schema drift")
    must_fail(lambda d: d[validator.STATE].__setitem__("full_d4_acceptance", "granted"), "D4 state exact key schema drift")
    must_fail(lambda d: track(d, "D4-B").__setitem__("hidden_authority", "granted"), "D4-B exact track key schema drift")
    must_fail(lambda d: d[validator.STATE]["predecessor"].__setitem__("hidden_authority", "granted"), "D4 predecessor exact key schema drift")
    must_fail(lambda d: d[validator.SELECTION].__setitem__("selection_base_main_commit", "drift"), "selection base drift")
    must_fail(lambda d: d[validator.SELECTION]["evidence_completion"].__setitem__("evidence_plan_path", "implementation/d4-eventing-async/other.json"), "selection evidence-plan provenance path drift")
    must_fail(lambda d: d[validator.SELECTION]["evidence_completion"].__setitem__("axis_a_source_path", "implementation/d4-eventing-async/source-evidence/other.json"), "Axis A source provenance path drift")
    must_fail(lambda d: d[validator.SELECTION]["evidence_completion"].__setitem__("axis_b_source_path", "implementation/d4-eventing-async/source-evidence/other.json"), "Axis B source provenance path drift")
    must_fail(lambda d: d[validator.SELECTION]["evidence_completion"].__setitem__("axis_c_source_path", "implementation/d4-eventing-async/source-evidence/other.json"), "Axis C source provenance path drift")
    must_fail(lambda d: d[validator.SELECTION]["serialization"].__setitem__("internal_broker", "avro_profile"), "internal broker serialization drift")
    must_fail(lambda d: d[validator.SELECTION]["serialization"].__setitem__("outbound_webhook", "protobuf_profile"), "outbound webhook serialization drift")
    must_fail(lambda d: d[validator.SELECTION]["serialization"].__setitem__("realtime_protocol", "protobuf_profile"), "realtime protocol must remain independent")
    must_fail(lambda d: d[validator.SELECTION]["serialization"].__setitem__("divergence_rule", "representations may redefine semantics"), "serialization divergence rule drift")
    must_fail(lambda d: d[validator.SELECTION]["schema_catalog"].__setitem__("mechanism", "registry_backed_catalog"), "catalog mechanism drift")
    must_fail(lambda d: d[validator.SELECTION]["schema_catalog"].__setitem__("registry_role", "canonical_contract_authority"), "registry role drift")
    must_fail(lambda d: d[validator.SELECTION]["schema_catalog"].__setitem__("registry_product", "vendor-x"), "registry vendor/product must remain unselected")
    must_fail(lambda d: d[validator.SELECTION]["schema_catalog"].__setitem__("unselected_eligible_alternatives", {"reviewed_git_catalog": {}, "registry_backed_catalog": {}}), "catalog alternative inventory must be an exact list")
    must_fail(lambda d: d[validator.SELECTION]["contract_version"].__setitem__("representation", "semantic_version_like_contract_revision"), "contract-version representation drift")
    must_fail(lambda d: d[validator.SELECTION]["contract_version"].__setitem__("zero_allowed", True), "zero must remain forbidden")
    must_fail(lambda d: d[validator.SELECTION]["contract_version"].__setitem__("ordering_authority", "numeric_order"), "must not gain ordering authority")
    must_fail(lambda d: d[validator.SELECTION]["contract_version"].__setitem__("unselected_eligible_alternatives", {"semantic_version_like_contract_revision": {}, "opaque_monotonic_contract_token": {}}), "contract-version alternative inventory must be an exact list")
    must_fail(lambda d: d[validator.SELECTION].__setitem__("non_authority_rule", "Product authority granted"), "selection non-authority rule drift")

    must_fail(lambda d: d[validator.AXIS_A].__setitem__("selection_state", "selected"), "Axis A source history must remain not_selected")
    must_fail(lambda d: d[validator.AXIS_B].__setitem__("ledger_credit", ["schema_catalog_semantic_manifest_compatibility_ci"]), "Axis B source ledger-credit history drift")
    must_fail(lambda d: d[validator.AXIS_C].__setitem__("current_run_auto_credit", True), "Axis C source auto-credit history drift")
    must_fail(lambda d: d[validator.AXIS_A]["candidate_results"].__setitem__("protobuf_profile", "ineligible_by_contract"), "selected internal profile lacks eligible Axis A evidence")
    must_fail(lambda d: d[validator.AXIS_B]["candidate_results"].__setitem__("hybrid_reviewed_git_plus_registry_catalog", "ineligible_by_contract"), "selected catalog mechanism lacks eligible Axis B evidence")
    must_fail(lambda d: d[validator.AXIS_C]["candidate_results"].__setitem__("positive_integer_family_revision", "ineligible_by_contract"), "selected contract-version representation lacks eligible Axis C evidence")

    must_fail(lambda d: d[validator.PLAN].__setitem__("selection_state", "not_selected"), "evidence-plan selection state drift")
    must_fail(lambda d: d[validator.PLAN].__setitem__("current_run_auto_credit", True), "cannot invent source-run auto-credit")
    must_fail(lambda d: d[validator.PLAN]["credited_evidence"].pop(), "D4-B evidence-plan credited inventory must be an exact list")
    must_fail(lambda d: d[validator.PLAN].__setitem__("required_evidence", as_keyed_object(d[validator.PLAN]["required_evidence"])), "D4-B evidence-plan required inventory must be an exact list")
    must_fail(lambda d: d[validator.PLAN].__setitem__("credited_evidence", as_keyed_object(d[validator.PLAN]["credited_evidence"])), "D4-B evidence-plan credited inventory must be an exact list")
    must_fail(lambda d: d[validator.PLAN].__setitem__("separate_d4_acceptance_required", False), "D4-B selection/full-acceptance separation drift")

    must_fail(lambda d: d[validator.STATE].__setitem__("gate_state", "separately_accepted"), "D4 must remain scoped")
    must_fail(lambda d: d[validator.STATE].__setitem__("canonical_product_implementation_authority", "granted"), "Product implementation authority must remain ungranted")
    must_fail(lambda d: d[validator.STATE].__setitem__("wave4_implementation_authority", "granted"), "Wave4 implementation authority must remain ungranted")
    must_fail(lambda d: d[validator.STATE].__setitem__("production_authority", "granted"), "production authority must remain none")
    must_fail(lambda d: d[validator.STATE].__setitem__("c3_numeric_topology_authority", "selected"), "C3 numeric/topology authority must remain not_selected")
    must_fail(lambda d: d[validator.STATE].__setitem__("explicit_c3_exclusions", as_keyed_object(d[validator.STATE]["explicit_c3_exclusions"])), "D4 C3 exclusions must be an exact list")
    must_fail(lambda d: d[validator.STATE].__setitem__("explicit_product_or_later_gate_exclusions", as_keyed_object(d[validator.STATE]["explicit_product_or_later_gate_exclusions"])), "D4 Product/later exclusions must be an exact list")
    must_fail(lambda d: d[validator.STATE].__setitem__("acceptance_rule", "full_d4_acceptance_granted"), "D4 acceptance rule drift")
    must_fail(lambda d: d[validator.STATE].__setitem__("merge_rule", "automatic_merge_allowed"), "D4 merge rule drift")
    must_fail(lambda d: track(d, "D4-B").__setitem__("evidence_completed", as_keyed_object(track(d, "D4-B")["evidence_completed"])), "D4-B completed evidence must be an exact list")
    must_fail(lambda d: track(d, "D4-C").__setitem__("evidence_remaining", as_keyed_object(track(d, "D4-C")["evidence_remaining"])), "D4-C remaining evidence must be an exact list")
    must_fail(lambda d: track(d, "D4-C").__setitem__("candidate", "rabbitmq"), "D4-C must remain open/unselected")

    print("d4b_selection_falsification=PASS duplicate_json=blocked exact_authoritative_schemas=locked hidden_authority=blocked provenance_paths=bound authoritative_arrays=typed acceptance_merge_rules=locked predecessor=locked internal_surface_swap=blocked webhook_surface_swap=blocked realtime_coupling=blocked divergence_rule=locked catalog_swap=blocked registry_role_escalation=blocked registry_vendor_selection=blocked contract_version_swap=blocked version_ordering_authority=blocked non_authority_rule=locked source_history_rewrite=blocked unsupported_selection=blocked evidence_credit_drift=blocked full_d4_acceptance=blocked product_wave4_production=blocked c3_scope_leak=blocked sibling_selection=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
