#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_CORE_PATH = Path(__file__).resolve().with_name("g2_scope_core.py")
REPOSITORY_CORE_PATH = ROOT / "tools/assurance/g2_scope_core.py"
CORE_PATH = LOCAL_CORE_PATH if LOCAL_CORE_PATH.is_file() else REPOSITORY_CORE_PATH
spec = importlib.util.spec_from_file_location("jlmirror_g2_scope_core", CORE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load canonical G2 scope core")
_core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_core)
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

DEFAULT_ROOT = Path.cwd()
EXPECTED_READINESS_VALIDATOR = "tools/assurance/validate_g2_monitoring_source_onboarding_scope_readiness.py"


def parse_labels(value: str) -> set[str]:
    parsed = json.loads(value)
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise ValueError("labels JSON must be an array of strings")
    return set(parsed)


def main() -> int:
    parser = argparse.ArgumentParser()
    for arg in ("base", "head", "head-ref", "labels-json", "head-repo", "base-repo"):
        parser.add_argument(f"--{arg}", required=True)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    try:
        labels = parse_labels(args.labels_json)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"G2_IMPLEMENTATION_SCOPE_ERROR: invalid labels metadata: {exc}", file=sys.stderr)
        return 1
    _classified, errors = validate(args.base, args.head, args.head_ref, labels, args.head_repo, args.base_repo, root=args.repo_root)
    for error in errors:
        print(f"G2_IMPLEMENTATION_SCOPE_ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print("g2_implementation_scope=PASS classification=trusted_explicit_attestation path_scope=allowlisted semantic_scope=structural+bounded readiness=live-source-authenticated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())