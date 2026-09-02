#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path

from validate_d4a_evidence_plan import EXPECTED_EVIDENCE, REQUIRED_ASSERTIONS

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "implementation/d4-eventing-async/d4-a-evidence-plan.json"
ENTRY_PATH = ROOT / "implementation/d4-eventing-async/state-manifest.json"


def errors_for(plan: dict, entry: dict) -> list[str]:
    errors: list[str] = []
    def require(ok: bool, message: str) -> None:
        if not ok:
            errors.append(message)
    items = plan.get("required_evidence", [])
    by_id = {item.get("evidence_id"): item for item in items if isinstance(item, dict)}
    require(set(by_id) == EXPECTED_EVIDENCE, "inventory")
    require(len(items) == len(EXPECTED_EVIDENCE), "multiplicity")
    for evidence_id, required in REQUIRED_ASSERTIONS.items():
        require(required <= set(by_id.get(evidence_id, {}).get("must_prove", [])), evidence_id)
    require(plan.get("current_run_auto_credit") is False, "auto-credit")
    require(plan.get("ledger_credit_state") == "zero_of_seven", "ledger")
    require(plan.get("selection_state") == "not_selected", "selection")
    require(plan.get("production_numeric_authority") == "not_granted", "production-numerics")
    d4a = next(t for t in entry["tracks"] if t["track_id"] == "D4-A")
    require(d4a["evidence_completed"] == [], "entry-credit")
    return errors


def must_fail(name: str, mutate) -> None:
    plan = json.loads(PLAN_PATH.read_text())
    entry = json.loads(ENTRY_PATH.read_text())
    mutate(plan, entry)
    assert errors_for(plan, entry), f"negative control unexpectedly passed: {name}"


def main() -> int:
    must_fail("collapse inventory", lambda p, e: p.update(required_evidence=[{"evidence_id":"documentation","evidence_kind":"documentation_only","must_prove":[]}]))
    must_fail("auto credit", lambda p, e: p.update(current_run_auto_credit=True))
    must_fail("premature Kafka selection", lambda p, e: p.update(selection_state="selected"))
    must_fail("production numeric escalation", lambda p, e: p.update(production_numeric_authority="granted"))
    must_fail("remove partition fallback", lambda p, e: next(i for i in p["required_evidence"] if i["evidence_id"].startswith("ordering_scope_"))["must_prove"].remove("tenant_cohort_topic_sharding_fallback_is_exercised"))
    must_fail("remove backlog recovery", lambda p, e: next(i for i in p["required_evidence"] if i["evidence_id"].startswith("broker_outbox_"))["must_prove"].remove("recovery_drains_backlog_without_starving_current_protected_work"))
    must_fail("precredit entry ledger", lambda p, e: next(t for t in e["tracks"] if t["track_id"] == "D4-A")["evidence_completed"].append("capacity_envelope_baseline_growth_stress"))
    print("d4a_evidence_plan_negative_controls=PASS cases=7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
