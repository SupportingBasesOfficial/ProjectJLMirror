#!/usr/bin/env python3
"""Export the deterministic machine-readable projection bundle.

Writing a file is an explicit developer action; CI uses validate_contracts.py and
never writes generated state back to the repository. Inside the repository,
exports are confined to build/contract-projections so the tool cannot overwrite
normative sources by path accident.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.contracts.core import build_bundle, canonical_json  # noqa: E402


def _resolve_safe_output(root: Path, requested: Path) -> Path:
    output = requested.resolve() if requested.is_absolute() else (root / requested).resolve()
    try:
        output.relative_to(root)
    except ValueError:
        return output

    allowed = (root / "build" / "contract-projections").resolve()
    try:
        output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(
            "repository-local export must stay under build/contract-projections"
        ) from exc
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    payload = canonical_json(build_bundle(root))
    if args.output:
        try:
            output = _resolve_safe_output(root, args.output)
        except ValueError as exc:
            parser.error(str(exc))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
