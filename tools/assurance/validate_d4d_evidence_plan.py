#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PLAN = Path("implementation/d4-eventing-async/d4-d-evidence-plan.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")
PROMOTION = Path("implementation/d4-eventing-async/ledger-promotions/d4-d-open-evt-016-promotion-v1.json")
SOURCE = Path("implementation/d4-eventing-async/source-evidence/d4-d-workload-identity/source-evidence-manifest.json")

EVIDENCE = "workload_identity_to_broker_credential_adapter_least_privilege"
REQUIRED = [
    EVIDENCE,
    "tenant_and_contract_scoped_producer_consumer_authorization",
    "message_protection_key_authority_and_historical_verifier_continuity",
    "secret_credential_payload_exclusion_and_erasure_boundary",
    "trace_context_observability_only_validation_and_redaction",
]
EXPECTED_SOURCE_SHA256 = "005b3943f7638e136150758d10d4ec6af1c6852d4e658127c7258ff546dce0ae"
EXPECTED_PROMOTION = {
    "promotion_id": "d4-d-open-evt-016-promotion-v1",
    "promotion_base": "491c99784637d20189034807a1722371a90a54ee",
    "source_pr": 108,
    "source_reviewed_head": "4442b4f2ca398eb92833c89abecc835a47598b59",
    "source_merge_commit": "491c99784637d20189034807a1722371a90a54ee",
    "review_id": 5127223369,
    "workflow_id": 351889856,
    "run_id": 34071132161,
    "job_id": 101588568591,
    "artifact_id": 10000484264,
    "artifact_digest": "sha256:abce705d64376dc29c61cf752b328a871bf5c01d11e26911f8903619ad53bc20",
}


def load(root: Path, path: Path) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    plan = load(root, PLAN)
    state = load(root, STATE)
    promotion = load(root, PROMOTION)
    source = load(root, SOURCE)

    if plan.get("schema_version") != 1 or plan.get("gate_id") != "D4" or plan.get("track_id") != "D4-D":
        errors.append("D4-D evidence plan identity drift")
    if plan.get("source_decisions") != ["OPEN-EVT-016", "OPEN-EVT-017", "OPEN-EVT-018"]:
        errors.append("D4-D source decision inventory drift")
    if plan.get("required_evidence") != REQUIRED:
        errors.append("D4-D required evidence inventory drift")
    if plan.get("credited_evidence") != [EVIDENCE] or plan.get("remaining_evidence") != REQUIRED[1:]:
        errors.append("D4-D ledger must be exactly one-of-five")
    if plan.get("ledger_credit_state") != "one_of_five":
        errors.append("D4-D ledger credit state must be one_of_five")
    if plan.get("latest_promotion") != str(PROMOTION):
        errors.append("latest promotion pointer drift")
    if plan.get("current_run_auto_credit") is not False:
        errors.append("promotion must not authorize current-run auto-credit")
    if plan.get("candidate") is not None or plan.get("candidate_status") != "not_selected":
        errors.append("D4-D evidence promotion must not select candidate")
    if plan.get("selection_state") != "not_selected" or plan.get("selection_authority") != "not_granted":
        errors.append("selection authority leakage")
    if plan.get("separate_selection_required") is not True or plan.get("separate_d4_acceptance_required") is not True:
        errors.append("selection and D4 acceptance must remain separate")

    if source.get("source_decision") != "OPEN-EVT-016" or source.get("evidence_id") != EVIDENCE:
        errors.append("source manifest identity drift")
    if source.get("current_run_auto_credit") is not False or source.get("ledger_credit") != []:
        errors.append("immutable source-time manifest must remain non-promoting")
    if source.get("candidate") is not None or source.get("candidate_status") != "not_selected" or source.get("selection_authority") != "not_granted":
        errors.append("source-time selection boundary drift")
    if source.get("canonical_identity_authority") != "IR-D-002":
        errors.append("IR-D-002 canonical identity authority drift")
    source_time = source.get("source_time_state", {})
    if source_time.get("d4d") != "0_of_5_unselected" or source_time.get("d4wide") != "21_of_26":
        errors.append("source-time 0/5 and 21/26 snapshot must remain immutable")
    if sha256(root / SOURCE) != EXPECTED_SOURCE_SHA256:
        errors.append("source manifest byte digest drift")

    if promotion.get("schema_version") != 1 or promotion.get("gate_id") != "D4" or promotion.get("track_id") != "D4-D":
        errors.append("promotion record identity drift")
    if promotion.get("promotion_id") != EXPECTED_PROMOTION["promotion_id"]:
        errors.append("promotion id drift")
    for key in ("promotion_base", "source_pr", "source_reviewed_head", "source_merge_commit"):
        if promotion.get(key) != EXPECTED_PROMOTION[key]:
            errors.append(f"promotion {key} drift")
    review = promotion.get("source_review", {})
    if review.get("review_id") != EXPECTED_PROMOTION["review_id"] or review.get("material_threads_unresolved") != 0:
        errors.append("source review provenance drift")
    workflow = promotion.get("source_workflow", {})
    for key in ("workflow_id", "run_id", "job_id", "artifact_id", "artifact_digest"):
        if workflow.get(key) != EXPECTED_PROMOTION[key]:
            errors.append(f"source workflow {key} drift")
    if workflow.get("workflow_path") != ".github/workflows/d4-d-workload-identity-source-evidence.yml":
        errors.append("source workflow path drift")
    if workflow.get("source_head_branch") != "d4d/open-evt-016-workload-identity-source":
        errors.append("source branch provenance drift")
    if promotion.get("source_manifest", {}).get("path") != str(SOURCE) or promotion.get("source_manifest", {}).get("sha256") != EXPECTED_SOURCE_SHA256:
        errors.append("promotion source manifest provenance drift")
    if promotion.get("credited_evidence") != [EVIDENCE] or promotion.get("credit_count") != 1:
        errors.append("promotion must grant exactly one evidence credit")
    if promotion.get("selection_state") != "not_selected" or promotion.get("selection_authority") != "not_granted":
        errors.append("promotion cannot select D4-D candidate")

    tracks = {t.get("track_id"): t for t in state.get("tracks", []) if isinstance(t, dict)}
    if set(tracks) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
        errors.append("global D4 track inventory drift")
        return errors
    d4d = tracks["D4-D"]
    if d4d.get("candidate") is not None or d4d.get("candidate_status") != "not_selected" or d4d.get("state") != "candidate_selection_open":
        errors.append("D4-D current state must remain open/unselected")
    if d4d.get("required_evidence") != REQUIRED or d4d.get("evidence_completed") != [EVIDENCE] or d4d.get("evidence_remaining") != REQUIRED[1:]:
        errors.append("D4-D current state must be exactly one-of-five")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 22:
        errors.append("D4-wide current state must be exactly 22/26")

    authority = (
        state.get("gate_state"), state.get("d4_transport_authority"),
        state.get("canonical_product_implementation_authority"), state.get("wave4_implementation_authority"),
        state.get("production_authority"), state.get("c3_numeric_topology_authority"),
    )
    if authority != ("scoped", "selected_not_granted", "not_granted", "not_granted", "none", "not_selected"):
        errors.append("authority boundary changed")
    for key, expected in {
        "d4_gate_state": "scoped",
        "d4_transport_authority": "selected_not_granted",
        "canonical_product_implementation_authority": "not_granted",
        "wave4_implementation_authority": "not_granted",
        "production_authority": "none",
        "c3_numeric_topology_authority": "not_selected",
    }.items():
        if promotion.get(key) != expected:
            errors.append(f"promotion authority field {key} drift")
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4D_LEDGER_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4d_evidence_plan=PASS ledger=1_of_5 d4wide=22/26 selection=not_selected source_snapshot=0_of_5 authorities=unchanged")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
