#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

TAXONOMY = Path("governance/adversarial/finding-taxonomy.json")
INVARIANTS = Path("governance/adversarial/engineering-invariants.json")
LEDGER = Path("governance/adversarial/learning-ledger.json")
MATERIAL_BADGE = re.compile(r"\bP[012] Badge\b")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten_comments(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    if value and all(isinstance(page, list) for page in value):
        return [item for page in value for item in page if isinstance(item, dict)]
    return [item for item in value if isinstance(item, dict)]


def validate(root: Path, review_comments: Path | None = None) -> list[str]:
    errors: list[str] = []
    taxonomy = _load(root / TAXONOMY)
    invariants = _load(root / INVARIANTS)
    ledger = _load(root / LEDGER)

    if taxonomy.get("schema_version") != 1:
        errors.append("taxonomy schema_version must be 1")
    if invariants.get("schema_version") != 1:
        errors.append("invariants schema_version must be 1")
    if ledger.get("schema_version") != 1:
        errors.append("ledger schema_version must be 1")

    invariant_rows = invariants.get("invariants")
    class_rows = taxonomy.get("classes")
    entries = ledger.get("entries")
    if not isinstance(invariant_rows, list) or not isinstance(class_rows, list) or not isinstance(entries, list):
        return errors + ["taxonomy, invariants and ledger collections must be arrays"]

    invariant_ids = [row.get("id") for row in invariant_rows if isinstance(row, dict)]
    if len(invariant_ids) != len(set(invariant_ids)) or any(not isinstance(i, str) or not i for i in invariant_ids):
        errors.append("invariant ids must be unique non-empty strings")
    invariant_set = set(invariant_ids)

    class_ids = [row.get("id") for row in class_rows if isinstance(row, dict)]
    if len(class_ids) != len(set(class_ids)) or any(not isinstance(i, str) or not i for i in class_ids):
        errors.append("class ids must be unique non-empty strings")
    class_map = {row["id"]: row for row in class_rows if isinstance(row, dict) and isinstance(row.get("id"), str)}
    for cid, row in class_map.items():
        refs = row.get("invariant_ids")
        if not isinstance(refs, list) or not refs or not set(refs).issubset(invariant_set):
            errors.append(f"class {cid} must reference only known invariants")
        if not isinstance(row.get("description"), str) or len(row["description"].strip()) < 40:
            errors.append(f"class {cid} description is too weak")

    entry_ids: set[str] = set()
    review_ids: set[int] = set()
    generations: dict[str, int] = defaultdict(int)
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("ledger entry must be an object")
            continue
        eid = entry.get("id")
        if not isinstance(eid, str) or not eid or eid in entry_ids:
            errors.append("ledger entry ids must be unique non-empty strings")
            continue
        entry_ids.add(eid)
        cid = entry.get("class_id")
        if cid not in class_map:
            errors.append(f"{eid}: unknown class_id")
            continue
        refs = entry.get("invariant_ids")
        allowed_refs = set(class_map[cid].get("invariant_ids", []))
        if not isinstance(refs, list) or not refs or not set(refs).issubset(allowed_refs):
            errors.append(f"{eid}: invariant_ids must be a non-empty subset of class invariants")
        if not isinstance(entry.get("root_cause"), str) or len(entry["root_cause"].strip()) < 40:
            errors.append(f"{eid}: root_cause is missing or too local")
        audit = entry.get("horizontal_audit")
        if not isinstance(audit, list) or not audit or any(not isinstance(v, str) or len(v.strip()) < 4 for v in audit):
            errors.append(f"{eid}: horizontal_audit must record audited siblings/boundaries")
        guardrails = entry.get("guardrails")
        if not isinstance(guardrails, list) or not guardrails:
            errors.append(f"{eid}: at least one permanent guardrail is required")
        else:
            for guardrail in guardrails:
                if not isinstance(guardrail, dict) or not isinstance(guardrail.get("path"), str):
                    errors.append(f"{eid}: malformed guardrail")
                    continue
                if not (root / guardrail["path"]).is_file():
                    errors.append(f"{eid}: guardrail path does not exist: {guardrail['path']}")
                if not isinstance(guardrail.get("probe"), str) or not guardrail["probe"].strip():
                    errors.append(f"{eid}: guardrail must name the probe/check it relies on")
        if entry.get("systemic_guardrail_updated") is not True:
            errors.append(f"{eid}: systemic_guardrail_updated must be true")
        generation = entry.get("guardrail_generation")
        if not isinstance(generation, int) or generation <= generations[cid]:
            errors.append(f"{eid}: recurring class {cid} must advance guardrail_generation")
        else:
            generations[cid] = generation

        source = entry.get("source")
        rid = entry.get("review_comment_id")
        if source == "external_review":
            if not isinstance(rid, int) or rid <= 0:
                errors.append(f"{eid}: external_review requires positive review_comment_id")
            elif rid in review_ids:
                errors.append(f"{eid}: duplicate review_comment_id {rid}")
            else:
                review_ids.add(rid)
        elif source == "internal_audit":
            if rid is not None:
                errors.append(f"{eid}: internal_audit must not impersonate external review identity")
        else:
            errors.append(f"{eid}: source must be external_review or internal_audit")

    if review_comments is not None:
        comments = _flatten_comments(_load(review_comments))
        material = {
            comment.get("id")
            for comment in comments
            if isinstance(comment.get("id"), int)
            and isinstance(comment.get("body"), str)
            and MATERIAL_BADGE.search(comment["body"])
        }
        missing = sorted(material - review_ids)
        if missing:
            errors.append("material PR review findings missing from learning ledger: " + ",".join(map(str, missing)))

    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--review-comments", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    errors = validate(root, args.review_comments)
    for error in errors:
        print("ADVERSARIAL_LEARNING_ERROR:", error)
    if errors:
        raise SystemExit(1)
    print("adversarial_learning=PASS taxonomy=linked invariants=linked ledger=complete recurrence=guardrail-advancing dynamic_findings=mapped")


if __name__ == "__main__":
    main()
