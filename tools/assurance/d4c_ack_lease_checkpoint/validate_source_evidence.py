#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import validate_source_evidence_historical as historical
from validate_source_evidence_historical import *  # noqa: F401,F403

D4C_CREDIT_008 = "ack_after_durable_responsibility_and_lease_ambiguity"
D4C_CREDIT_009 = "quarantine_redrive_current_authority_and_dedup_preservation"
D4C_CREDIT_010 = "bounded_message_batch_compression_and_parser_limits"
CURRENT_CREDITS = [D4C_CREDIT_008, D4C_CREDIT_009, D4C_CREDIT_010]
_legacy_load_json = historical.load_json


def _current_errors(state: dict) -> list[str]:
    tracks = {t.get("track_id"): t for t in state.get("tracks", []) if isinstance(t, dict)}
    d4c = tracks.get("D4-C", {})
    required = d4c.get("required_evidence", [])
    errors: list[str] = []
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open":
        errors.append("D4-C selection leakage")
    expected_remaining = [x for x in required if x not in CURRENT_CREDITS]
    if d4c.get("evidence_completed") != CURRENT_CREDITS or d4c.get("evidence_remaining") != expected_remaining:
        errors.append("D4-C current ledger drift beyond separately promoted OPEN-EVT-008, OPEN-EVT-009 and OPEN-EVT-010")
    if tracks.get("D4-D", {}).get("evidence_completed") != []:
        errors.append("D4-D state leakage")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 15:
        errors.append("D4-wide evidence count drift")
    return errors


def _project(state: dict) -> dict:
    result = copy.deepcopy(state)
    d4c = next(t for t in result["tracks"] if t.get("track_id") == "D4-C")
    d4c["evidence_completed"] = []
    d4c["evidence_remaining"] = list(d4c["required_evidence"])
    return result


def validate(root: Path) -> list[str]:
    state = json.loads((root / STATE_PATH).read_text(encoding="utf-8"))
    current = _current_errors(state)
    if current:
        return current

    original = historical.load_json
    try:
        def projected_load(path: Path):
            value = _legacy_load_json(path)
            try:
                if path.resolve() == (root / STATE_PATH).resolve():
                    return _project(value)
            except Exception:
                pass
            return value
        historical.load_json = projected_load
        return historical.validate(root)
    finally:
        historical.load_json = original


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("d4c_ack_lease_checkpoint_source=PASS source_auto_credit=false historical_oracle=preserved current_promoted_credit=3_of_9 d4wide=15_of_26 selection=not_selected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
