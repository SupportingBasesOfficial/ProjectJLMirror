#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = "implementation/g3-resource-inventory-authorization/AUTHORIZATION_MANIFEST.json"

def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()

def allowed(path: str, policy: dict) -> bool:
    return path in set(policy.get("allowed_exact_paths") or []) or any(path.startswith(prefix) for prefix in policy.get("allowed_prefixes") or [])

def candidate_text(path: str, head: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{head}:{path}"], text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return ""

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    errors: list[str] = []
    manifest = json.loads(subprocess.check_output(["git", "-C", str(ROOT), "show", f"{args.base}:{MANIFEST_PATH}"], text=True))
    policy = manifest["implementation_path_policy"]
    if manifest.get("implementation_authority_after_merge") != "granted_for_exact_g3_resource_inventory_only":
        errors.append("base does not grant exact G3 implementation authority")
    changed = [p for p in git("diff", "--name-only", f"{args.base}...{args.head}").splitlines() if p]
    if not changed:
        errors.append("implementation diff is empty")
    for path in changed:
        if not allowed(path, policy):
            errors.append(f"path outside G3 implementation authority: {path}")
            continue
        if path.startswith(tuple(policy.get("semantic_scan_prefixes") or [])):
            text = candidate_text(path, args.head).lower()
            for marker in policy.get("forbidden_code_markers") or []:
                if marker.lower() in text:
                    errors.append(f"forbidden G3 semantic marker '{marker}' in {path}")
    claim_path = policy["implementation_claim_path"]
    claim_text = candidate_text(claim_path, args.head)
    if not claim_text:
        errors.append("G3 implementation claim missing")
    else:
        try:
            claim = json.loads(claim_text)
            if claim.get("authorization_id") != "g3.resource-inventory@1" or claim.get("slice_id") != "g3.resource-inventory@1":
                errors.append("G3 implementation claim identity drift")
        except Exception:
            errors.append("G3 implementation claim is invalid JSON")
    for error in errors:
        print(f"G3_SCOPE_ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"g3_scope=PASS base={args.base} head={args.head} changed_files={len(changed)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
