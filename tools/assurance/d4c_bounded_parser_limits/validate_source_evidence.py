#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from evaluate_candidates import (  # noqa: E402
    CANDIDATES,
    TEST_LIMIT_PROFILE,
    evaluate_all,
)

MANIFEST = Path("implementation/d4-eventing-async/source-evidence/d4-c-bounded-parser-limits-source.json")
PLAN = Path("implementation/d4-eventing-async/d4-c-candidate-evaluation-plan.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")
AXIS = "bounded_message_payload_batch_and_compression"
DECISION = "OPEN-EVT-010"
EVIDENCE = "bounded_message_batch_compression_and_parser_limits"
BASE = "c72f53100e504922563106d1f8d2d3a5e7577589"
CREDITS = [
    "ack_after_durable_responsibility_and_lease_ambiguity",
    "quarantine_redrive_current_authority_and_dedup_preservation",
]

EXPECTED_ASSERTIONS = [
    "all_three_concrete_candidate_classes_enforce_one_contract_owned_admission_boundary",
    "declared_oversize_is_rejected_before_stream_consumption_or_payload_allocation",
    "unknown_length_streams_are_read_only_within_a_contract_owned_byte_budget",
    "batch_item_count_is_bounded_before_per_item_semantic_admission",
    "nesting_string_collection_and_total_field_counts_are_explicitly_bounded",
    "gzip_output_is_incrementally_bounded_and_decompression_bombs_fail_closed",
    "structured_validation_is_iterative_and_bounded_after_wire_and_decompression_limits",
    "transport_configuration_can_be_stricter_but_cannot_relax_the_contract_limit",
    "artifact_and_raw_telemetry_payload_classes_require_references_to_specialized_planes",
    "limit_rejections_emit_stable_machine_codes_and_are_marked_non_retryable",
    "repeating_the_same_invalid_input_does_not_create_retry_amplification_authority",
    "numeric_limit_values_are_evidence_fixtures_only_and_do_not_select_production_limits",
    "codec_and_transport_library_choices_remain_replaceable_mechanics_not_contract_identity",
    "candidate_source_evidence_does_not_select_a_codec_transport_parser_or_production_topology",
]

EXPECTED_NON_AUTHORITY = {
    "d4c_mechanism_selection": "not_selected",
    "d4c_content_equivalence_profile_selection": "not_selected",
    "open_evt_010_ledger_credit": "uncredited",
    "d4c_ledger_credit": "current_2_of_9_unchanged",
    "d4d_ledger_credit": "0_of_5",
    "d4_gate": "scoped",
    "d4_transport_authority": "selected_not_granted",
    "canonical_product_implementation_authority": "not_granted",
    "wave4_implementation_authority": "not_granted",
    "production_authority": "none",
    "c3_numeric_topology_authority": "not_selected",
}


class DuplicateKeyError(ValueError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateKeyError(f"duplicate JSON member: {key}")
        out[key] = value
    return out


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        manifest = load(root / MANIFEST)
        plan = load(root / PLAN)
        state = load(root / STATE)
    except Exception as exc:
        return [str(exc)]

    expected_manifest_keys = {
        "schema_version", "gate_id", "track_id", "axis", "source_decision", "evidence_id", "canonical_base",
        "mode", "selection_state", "selection_authority", "current_run_auto_credit", "ledger_credit",
        "candidate_results", "equivalent_reviewed_profile", "required_proofs", "source_assertions", "non_authority",
    }
    if not isinstance(manifest, dict) or set(manifest) != expected_manifest_keys:
        errors.append("source manifest exact key schema drift")
    for key, expected in {
        "schema_version": 1,
        "gate_id": "D4",
        "track_id": "D4-C",
        "axis": AXIS,
        "source_decision": DECISION,
        "evidence_id": EVIDENCE,
        "canonical_base": BASE,
        "mode": "candidate_source_evidence_only",
        "selection_state": "not_selected",
        "selection_authority": "not_granted",
    }.items():
        if manifest.get(key) != expected or type(manifest.get(key)) is not type(expected):
            errors.append(f"source manifest scalar drift: {key}")
    if manifest.get("current_run_auto_credit") is not False or manifest.get("ledger_credit") != []:
        errors.append("source evidence must remain non-promoting")

    axes = plan.get("axes") if isinstance(plan, dict) else None
    axis = axes.get(AXIS) if isinstance(axes, dict) else None
    if not isinstance(axis, dict):
        errors.append("accepted D4-C axis missing")
    else:
        if axis.get("decision") != DECISION or axis.get("evidence_id") != EVIDENCE:
            errors.append("source decision/evidence binding drift")
        expected_candidates = [x for x in axis.get("candidate_classes", []) if x != "equivalent_reviewed_profile"]
        if expected_candidates != list(CANDIDATES):
            errors.append("concrete candidate inventory drift")
        if manifest.get("required_proofs") != axis.get("must_prove"):
            errors.append("required proofs must exactly match accepted candidate plan")

    expected_results = {candidate: "eligible_for_evidence_execution" for candidate in CANDIDATES}
    if manifest.get("candidate_results") != expected_results:
        errors.append("source candidate results drift")
    if manifest.get("equivalent_reviewed_profile") != "insufficient_evidence":
        errors.append("equivalent reviewed profile must remain insufficient_evidence")
    if manifest.get("source_assertions") != EXPECTED_ASSERTIONS:
        errors.append("source assertions drift")
    if manifest.get("non_authority") != EXPECTED_NON_AUTHORITY:
        errors.append("non-authority boundary drift")

    runtime = evaluate_all()
    if runtime.get("limit_profile") != TEST_LIMIT_PROFILE or not TEST_LIMIT_PROFILE.endswith("_noncanonical"):
        errors.append("numeric fixture profile became canonical")
    if runtime.get("candidate_results") != manifest.get("candidate_results"):
        errors.append("runtime candidate results do not match source manifest")
    if runtime.get("equivalent_reviewed_profile") != "insufficient_evidence":
        errors.append("runtime equivalent profile drift")
    if runtime.get("selection") != "not_selected" or runtime.get("selection_authority") != "not_granted":
        errors.append("runtime selection leakage")
    if runtime.get("ledger_credit") != [] or runtime.get("current_run_auto_credit") is not False:
        errors.append("runtime source auto-credit leakage")
    checks = runtime.get("checks")
    if not isinstance(checks, dict) or set(checks) != set(CANDIDATES) or not all(all(v.values()) for v in checks.values()):
        errors.append("runtime proof checks incomplete")

    tracks_raw = state.get("tracks") if isinstance(state, dict) else None
    if not isinstance(tracks_raw, list) or len(tracks_raw) != 4:
        errors.append("global D4 track structure drift")
        return errors
    tracks = {t.get("track_id"): t for t in tracks_raw if isinstance(t, dict)}
    if set(tracks) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
        errors.append("global D4 track identity drift")
        return errors
    d4a, d4b, d4c, d4d = tracks["D4-A"], tracks["D4-B"], tracks["D4-C"], tracks["D4-D"]
    if len(d4a.get("evidence_completed", [])) != 7 or d4a.get("candidate") != "kafka":
        errors.append("D4-A accepted state drift")
    if len(d4b.get("evidence_completed", [])) != 5 or d4b.get("candidate_status") != "selected_c2_profile":
        errors.append("D4-B accepted state drift")
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open":
        errors.append("D4-C selection/state leakage")
    if d4c.get("evidence_completed") != CREDITS:
        errors.append("D4-C current credited evidence drift")
    if EVIDENCE not in d4c.get("evidence_remaining", []):
        errors.append("OPEN-EVT-010 must remain uncredited")
    if len(d4c.get("evidence_remaining", [])) != 7:
        errors.append("D4-C remaining evidence count drift")
    if d4d.get("evidence_completed") != [] or d4d.get("candidate") is not None:
        errors.append("D4-D state leakage")
    if sum(len(t.get("evidence_completed", [])) for t in tracks_raw) != 14:
        errors.append("D4-wide ledger must remain exactly 14/26")
    for key, expected in {
        "gate_state": "scoped",
        "d4_transport_authority": "selected_not_granted",
        "canonical_product_implementation_authority": "not_granted",
        "wave4_implementation_authority": "not_granted",
        "production_authority": "none",
        "c3_numeric_topology_authority": "not_selected",
    }.items():
        if state.get(key) != expected:
            errors.append(f"global authority drift: {key}")
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else ROOT
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4C_OPEN_EVT_010_SOURCE_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4c_open_evt_010_source=PASS candidates=3 proofs=7 bounded_before_allocation=true decompression_bomb=blocked parser_amplification=blocked specialized_planes=referenced deterministic_nonretryable=true fixture_limits_noncanonical=true source_auto_credit=false current_d4c=2_of_9 open_evt_010_uncredited=true d4wide=14_of_26 selection=not_selected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
