#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE_PATH = ROOT / "implementation/g2-monitoring-source-onboarding-authorization/g2_authorization_core.py"
spec = importlib.util.spec_from_file_location("jlmirror_g2_authorization_core", CORE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load canonical G2 authorization core")
_core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_core)
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)


def main() -> int:
    errors = validate()
    for error in errors:
        print(f"G2_AUTHORIZATION_ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print("g2_authorization=PASS exact_scope=monitoring-source-onboarding workflow=blob-exact semantic-scope=token-boundary+ascii-executable review-findings=internalized merge_authorization=not-granted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())