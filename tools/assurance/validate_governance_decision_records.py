#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

RECORD_66 = Path("docs/16-implementation-readiness/66-alert-evaluation-incident-response-decision-record.md")


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    path = root / RECORD_66
    if not path.is_file():
        return errors

    text = path.read_text(encoding="utf-8")
    required = (
        "outside current G10 authority",
        "a separately accepted G10 extension must explicitly authorize automatic Alert-to-Incident creation",
        "G10 automatic incident extension",
        "Alert != Incident",
        "orchestration cannot write ITSM tables",
    )
    for marker in required:
        if marker not in text:
            errors.append(f"record 66 missing required G10 authority boundary: {marker}")

    forbidden = (
        "the existing G10 boundary is sufficient for automatic Alert-to-Incident creation",
        "current G10 authorizes automatic Alert-to-Incident creation",
    )
    for marker in forbidden:
        if marker in text:
            errors.append(f"record 66 illegally widens current G10 authority: {marker}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    errors = validate(args.root.resolve())
    for error in errors:
        print(f"GOVERNANCE_DECISION_RECORD_ERROR: {error}")
    if errors:
        return 1
    print("governance_decision_records=PASS record66_g10_auto_incident_boundary=preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
