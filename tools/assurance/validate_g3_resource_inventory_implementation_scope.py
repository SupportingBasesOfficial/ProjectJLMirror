#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

MANIFEST_PATH = "implementation/g3-resource-inventory-authorization/AUTHORIZATION_MANIFEST.json"

def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

def allowed(path: str, policy: dict) -> bool:
    return path in set(policy.get("allowed_exact_paths") or []) or any(path.startswith(prefix) for prefix in policy.get("allowed_prefixes") or [])

def candidate_text(root: Path, path: str, head: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(root), "show", f"{head}:{path}"], text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return ""

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--labels-json", required=True)
    parser.add_argument("--head-repo", required=True)
    parser.add_argument("--base-repo", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    errors: list[str] = []
    manifest = json.loads(subprocess.check_output(["git", "-C", str(root), "show", f"{args.base}:{MANIFEST_PATH}"], text=True))
    policy = manifest["implementation_path_policy"]
    if manifest.get("implementation_authority_after_merge") != "granted_for_exact_g3_resource_inventory_only": errors.append("base does not grant exact G3 implementation authority")
    if args.head_repo != args.base_repo: errors.append("implementation PR must use the canonical repository")
    if not args.head_ref.startswith(policy["implementation_pr_head_prefix"]): errors.append("implementation head prefix is not canonical G3 prefix")
    try:
        labels = set(json.loads(args.labels_json))
    except Exception:
        labels = set(); errors.append("labels-json is invalid")
    if policy["implementation_pr_required_label"] not in labels: errors.append("implementation PR missing required G3 label")
    changed = [p for p in git(root, "diff", "--name-only", "--no-renames", f"{args.base}...{args.head}").splitlines() if p]
    if not changed: errors.append("implementation diff is empty")
    forbidden_tokens = tuple(str(x).lower() for x in policy.get("forbidden_path_tokens") or [])
    for path in changed:
        lower_path = path.lower()
        if not allowed(path, policy):
            errors.append(f"path outside G3 implementation authority: {path}")
            continue
        if any(token in lower_path for token in forbidden_tokens):
            errors.append(f"forbidden G3 path token in {path}")
        if path.startswith(tuple(policy.get("semantic_scan_prefixes") or [])):
            text = candidate_text(root, path, args.head).lower()
            for marker in policy.get("forbidden_code_markers") or []:
                if marker.lower() in text:
                    errors.append(f"forbidden G3 semantic marker '{marker}' in {path}")
    claim_path = policy["implementation_claim_path"]
    claim_text = candidate_text(root, claim_path, args.head)
    if not claim_text:
        errors.append("G3 implementation claim missing")
    else:
        try:
            claim = json.loads(claim_text)
            if set(claim) != {"schema_version","authorization_id","slice_id"}: errors.append("G3 implementation claim shape drift")
            if claim.get("schema_version") != 1 or claim.get("authorization_id") != "g3.resource-inventory@1" or claim.get("slice_id") != "g3.resource-inventory@1": errors.append("G3 implementation claim identity drift")
        except Exception:
            errors.append("G3 implementation claim is invalid JSON")
    for error in errors:
        print(f"G3_SCOPE_ERROR: {error}", file=sys.stderr)
    if errors: return 1
    print(f"g3_scope=PASS base={args.base} head={args.head} changed_files={len(changed)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
