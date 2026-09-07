#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PLAN = Path("implementation/d4-eventing-async/d4-c-evidence-plan.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")
PROMOTION_025 = Path("implementation/d4-eventing-async/ledger-promotions/d4-c-open-evt-025-promotion-v1.json")
SOURCE_025 = Path("implementation/d4-eventing-async/source-evidence/d4-c-recovery-generation-source.json")

SOURCE_DECISIONS = [
    "OPEN-EVT-008",
    "OPEN-EVT-009",
    "OPEN-EVT-010",
    "OPEN-EVT-011",
    "OPEN-EVT-012",
    "OPEN-EVT-013",
    "OPEN-EVT-014",
    "OPEN-EVT-015",
    "OPEN-EVT-025",
]
CREDITS = [
    "ack_after_durable_responsibility_and_lease_ambiguity",
    "quarantine_redrive_current_authority_and_dedup_preservation",
    "bounded_message_batch_compression_and_parser_limits",
    "scoped_content_equivalence_confidentiality_and_conflict_rejection",
    "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity",
    "producer_generation_nonresurrection_across_failover_restore",
    "privileged_bounded_replay_with_original_identity_and_effect_safety",
    "historical_reader_upcaster_semantic_and_equivalence_continuity",
    "recovery_generation_rf_inventory_reconciliation_and_activation_gates",
]
CREDIT_025 = CREDITS[-1]

HISTORICAL_PROMOTIONS = {
    Path("implementation/d4-eventing-async/ledger-promotions/d4-c-open-evt-008-promotion-v1.json"): "1fa1251a79504176ed6583640c2812bfe178dd87",
    Path("implementation/d4-eventing-async/ledger-promotions/d4-c-open-evt-009-promotion-v1.json"): "491a13179316e03d02fe17e229244d4667b0ee81",
    Path("implementation/d4-eventing-async/ledger-promotions/d4-c-open-evt-010-promotion-v1.json"): "6723c7bfde777e2888591fa443c059db0e0ba586",
    Path("implementation/d4-eventing-async/ledger-promotions/d4-c-open-evt-011-promotion-v1.json"): "2cde2242347cac39ce9eb5a4d972c4338385e419",
    Path("implementation/d4-eventing-async/ledger-promotions/d4-c-open-evt-012-promotion-v1.json"): "17566e0b99741cb1197dc4301b9d8b3a8b88609a",
    Path("implementation/d4-eventing-async/ledger-promotions/d4-c-open-evt-013-promotion-v1.json"): "79690e653894abb370726040f270a998836000cb",
    Path("implementation/d4-eventing-async/ledger-promotions/d4-c-open-evt-014-promotion-v1.json"): "1245faf35161ce0aa014f4910dd4db437cab16c9",
    Path("implementation/d4-eventing-async/ledger-promotions/d4-c-open-evt-015-promotion-v1.json"): "6ab3685f26a4b9601d8a06ef2a8226d1403637f0",
}

EXPECTED_PLAN_KEYS = {
    "schema_version","gate_id","track_id","name","source_decisions","candidate","candidate_status",
    "source_evidence_state","ledger_credit_state","required_evidence","credited_evidence","remaining_evidence",
    "current_run_auto_credit","selection_state","selection_authority","separate_selection_required",
    "separate_d4_acceptance_required","d4_transport_authority","canonical_product_implementation_authority",
    "wave4_implementation_authority","production_authority","c3_numeric_topology_authority",
}
EXPECTED_PROMOTION_KEYS = {
    "schema_version","promotion_id","gate_id","track_id","promotion_base","source_pr","source_reviewed_head",
    "source_merge_commit","source_review","source_workflow","source_manifest","credited_evidence","credit_count",
    "selection_state","selection_authority","d4_gate_state","d4_transport_authority",
    "canonical_product_implementation_authority","wave4_implementation_authority","production_authority",
    "c3_numeric_topology_authority","separate_selection_required","separate_d4_acceptance_required",
}
EXPECTED_REVIEW_KEYS = {"review_id","review_mode","material_threads_unresolved"}
EXPECTED_WORKFLOW_KEYS = {
    "workflow_id","workflow_path","workflow_event","source_head_branch","run_id","run_attempt","job_id",
    "job_name","artifact_id","artifact_name","artifact_digest",
}
EXPECTED_MANIFEST_KEYS = {"path","sha256"}

EXPECTED_025 = {
    "promotion_id":"d4-c-open-evt-025-promotion-v1",
    "promotion_base":"f98bf5d6b1905dcb3a8b53356e1bab0879076511",
    "source_pr":105,
    "source_reviewed_head":"1cc709f02189e7cf8cc429f4a9b60d6554b79da7",
    "source_merge_commit":"f98bf5d6b1905dcb3a8b53356e1bab0879076511",
    "review_id":5126669191,
    "workflow":{
        "workflow_id":351814203,
        "workflow_path":".github/workflows/d4-c-recovery-generation-source-evidence.yml",
        "workflow_event":"pull_request",
        "source_head_branch":"d4c/open-evt-025-recovery-generation-source",
        "run_id":34061206063,
        "run_attempt":1,
        "job_id":101561958282,
        "job_name":"D4-C OPEN-EVT-025 source evidence",
        "artifact_id":9997516312,
        "artifact_name":"d4-c-recovery-generation-source-1cc709f02189e7cf8cc429f4a9b60d6554b79da7-34061206063-1",
        "artifact_digest":"sha256:1f32307e4f43f9f510abebf42f32e300f066896013ecfbd09f544a9d290faa27",
    },
    "source_sha256":"069cb3551b64a65ec0e4aa66e416289ee0d5c2d7037f1a3d07effd9333cbdeda",
}
REVIEW_MODE = "independent_exact_head_adversarial_clean_after_exact_head_ci"

class DuplicateKeyError(ValueError):
    pass

def no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateKeyError(f"duplicate JSON member: {key}")
        out[key] = value
    return out

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)

def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _validate_historical(root: Path, errors: list[str]) -> None:
    for path, expected_blob in HISTORICAL_PROMOTIONS.items():
        label = path.stem
        full = root / path
        if git_blob_sha(full) != expected_blob:
            errors.append(f"{label}: historical promotion blob drift")
            continue
        try:
            record = load(full)
            manifest = record["source_manifest"]
            source = root / manifest["path"]
            source_data = load(source)
        except Exception as exc:
            errors.append(f"{label}: {exc}")
            continue
        if sha256(source) != manifest.get("sha256"):
            errors.append(f"{label}: historical source manifest bytes drift")
        if source_data.get("current_run_auto_credit") is not False or source_data.get("ledger_credit") != []:
            errors.append(f"{label}: historical source package must remain non-promoting")
        if source_data.get("selection_state") != "not_selected" or source_data.get("selection_authority") != "not_granted":
            errors.append(f"{label}: historical source selection leakage")

def _validate_025(root: Path, errors: list[str]) -> None:
    try:
        p = load(root / PROMOTION_025)
        source = load(root / SOURCE_025)
    except Exception as exc:
        errors.append(f"OPEN-EVT-025: {exc}")
        return
    if not isinstance(p, dict) or set(p) != EXPECTED_PROMOTION_KEYS:
        errors.append("OPEN-EVT-025: promotion exact key schema drift")
        return
    expected_scalars = {
        "schema_version":1,"promotion_id":EXPECTED_025["promotion_id"],"gate_id":"D4","track_id":"D4-C",
        "promotion_base":EXPECTED_025["promotion_base"],"source_pr":EXPECTED_025["source_pr"],
        "source_reviewed_head":EXPECTED_025["source_reviewed_head"],"source_merge_commit":EXPECTED_025["source_merge_commit"],
        "credit_count":1,"selection_state":"not_selected","selection_authority":"not_granted","d4_gate_state":"scoped",
        "d4_transport_authority":"selected_not_granted","canonical_product_implementation_authority":"not_granted",
        "wave4_implementation_authority":"not_granted","production_authority":"none","c3_numeric_topology_authority":"not_selected",
        "separate_selection_required":True,"separate_d4_acceptance_required":True,
    }
    for key, expected in expected_scalars.items():
        if p.get(key) != expected or type(p.get(key)) is not type(expected):
            errors.append(f"OPEN-EVT-025: promotion scalar drift: {key}")
    review = p.get("source_review")
    if not isinstance(review, dict) or set(review) != EXPECTED_REVIEW_KEYS:
        errors.append("OPEN-EVT-025: source review exact key schema drift")
    else:
        if review.get("review_id") != EXPECTED_025["review_id"] or type(review.get("review_id")) is not int:
            errors.append("OPEN-EVT-025: source review id drift")
        if review.get("review_mode") != REVIEW_MODE or review.get("material_threads_unresolved") != 0:
            errors.append("OPEN-EVT-025: source review boundary drift")
    workflow = p.get("source_workflow")
    if not isinstance(workflow, dict) or set(workflow) != EXPECTED_WORKFLOW_KEYS:
        errors.append("OPEN-EVT-025: source workflow exact key schema drift")
    elif workflow != EXPECTED_025["workflow"]:
        errors.append("OPEN-EVT-025: source workflow provenance drift")
    manifest = p.get("source_manifest")
    expected_manifest = {"path":str(SOURCE_025),"sha256":EXPECTED_025["source_sha256"]}
    if not isinstance(manifest, dict) or set(manifest) != EXPECTED_MANIFEST_KEYS or manifest != expected_manifest:
        errors.append("OPEN-EVT-025: source manifest provenance drift")
    elif sha256(root / SOURCE_025) != EXPECTED_025["source_sha256"]:
        errors.append("OPEN-EVT-025: source manifest bytes drift")
    if p.get("credited_evidence") != [CREDIT_025]:
        errors.append("OPEN-EVT-025: promotion credit drift")
    if source.get("source_decision") != "OPEN-EVT-025" or source.get("evidence_id") != CREDIT_025:
        errors.append("OPEN-EVT-025: source evidence binding drift")
    if source.get("current_run_auto_credit") is not False or source.get("ledger_credit") != []:
        errors.append("OPEN-EVT-025: source package must remain non-promoting")
    if source.get("selection_state") != "not_selected" or source.get("selection_authority") != "not_granted":
        errors.append("OPEN-EVT-025: source package selection leakage")

def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        plan = load(root / PLAN)
        state = load(root / STATE)
    except Exception as exc:
        return [str(exc)]
    if not isinstance(plan, dict) or set(plan) != EXPECTED_PLAN_KEYS:
        errors.append("D4-C evidence-plan exact key schema drift")
    scalars = {
        "schema_version":1,"gate_id":"D4","track_id":"D4-C",
        "name":"delivery_ack_quarantine_equivalence_outbox_replay_history_recovery",
        "candidate":None,"candidate_status":"not_selected","source_evidence_state":"reviewed_source_run_available",
        "ledger_credit_state":"nine_of_nine","current_run_auto_credit":False,"selection_state":"not_selected",
        "selection_authority":"not_granted","separate_selection_required":True,"separate_d4_acceptance_required":True,
        "d4_transport_authority":"selected_not_granted","canonical_product_implementation_authority":"not_granted",
        "wave4_implementation_authority":"not_granted","production_authority":"none","c3_numeric_topology_authority":"not_selected",
    }
    for key, expected in scalars.items():
        if plan.get(key) != expected or type(plan.get(key)) is not type(expected):
            errors.append(f"plan scalar drift: {key}")
    if plan.get("source_decisions") != SOURCE_DECISIONS:
        errors.append("D4-C source decision inventory drift")
    if plan.get("credited_evidence") != CREDITS:
        errors.append("D4-C credited evidence must be exactly all nine reviewed obligations")
    if plan.get("remaining_evidence") != []:
        errors.append("D4-C remaining evidence must be empty after ninth promotion")
    if plan.get("required_evidence") != CREDITS:
        errors.append("D4-C required evidence inventory drift")
    _validate_historical(root, errors)
    _validate_025(root, errors)

    tracks_raw = state.get("tracks", [])
    if not isinstance(tracks_raw, list) or len(tracks_raw) != 4 or not all(isinstance(t, dict) for t in tracks_raw):
        errors.append("D4 track structure drift")
        return errors
    ids = [t.get("track_id") for t in tracks_raw]
    if len(ids) != len(set(ids)) or set(ids) != {"D4-A","D4-B","D4-C","D4-D"}:
        errors.append("D4 track identity drift")
        return errors
    tracks = {t["track_id"]:t for t in tracks_raw}
    d4a,d4b,d4c,d4d = tracks["D4-A"],tracks["D4-B"],tracks["D4-C"],tracks["D4-D"]
    if d4a.get("candidate") != "kafka" or len(d4a.get("evidence_completed",[])) != 7 or d4a.get("evidence_remaining") != []:
        errors.append("D4-A accepted 7/7 state drift")
    if d4b.get("candidate_status") != "selected_c2_profile" or len(d4b.get("evidence_completed",[])) != 5 or d4b.get("evidence_remaining") != []:
        errors.append("D4-B accepted 5/5 state drift")
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open":
        errors.append("D4-C selection/state leakage")
    if d4c.get("evidence_completed") != CREDITS or d4c.get("evidence_remaining") != []:
        errors.append("D4-C state credit drift")
    if d4d.get("candidate") is not None or d4d.get("candidate_status") != "not_selected" or d4d.get("evidence_completed") != []:
        errors.append("D4-D state/credit leakage")
    if sum(len(t.get("evidence_completed",[])) for t in tracks_raw) != 21:
        errors.append("D4-wide credited evidence must be exactly 21/26")
    for key, expected in {
        "gate_state":"scoped","d4_transport_authority":"selected_not_granted",
        "canonical_product_implementation_authority":"not_granted","wave4_implementation_authority":"not_granted",
        "production_authority":"none","c3_numeric_topology_authority":"not_selected",
    }.items():
        if state.get(key) != expected:
            errors.append(f"global authority drift: {key}")
    return errors

def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4C_PROMOTION_ERROR: {error}")
        return 1
    print("d4c_open_evt_025_promotion=PASS promotion_records=9 historical_blobs_pinned=true d4c=9_of_9 d4wide=21_of_26 selection=not_selected authorities=unchanged")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
