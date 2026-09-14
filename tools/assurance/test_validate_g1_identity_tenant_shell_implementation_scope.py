#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "assurance"))
import validate_g1_identity_tenant_shell_implementation_scope as scope

POLICY = {
    "allowed_prefixes": [
        "apps/g1-identity-tenant-shell/",
        "contracts/g1-identity-tenant-shell/",
        "implementation/g1-identity-tenant-shell/",
        "sql/g1/",
        "src/jlmirror_g1/",
        "tests/g1/",
        "tools/g1/",
    ],
    "allowed_exact_paths": [".github/workflows/g1-identity-tenant-shell-runtime.yml"],
    "implementation_pr_head_prefix": "impl/g1-identity-tenant-protected-shell",
    "diff_enforcement_rule": "every_changed_path_must_match_canonical_base_policy",
}


def must_reject(paths: list[str], fragment: str) -> None:
    errors = scope.validate_paths(paths, POLICY)
    if not any(fragment in error for error in errors):
        raise AssertionError(f"expected rejection containing {fragment!r}, got {errors!r}")


def falsify_shared_core_mutation() -> None:
    must_reject(["src/jlmirror_authority/session.py"], "unauthorized G1 implementation path")
    must_reject(["docs/09-api-contracts/authentication-authorization-and-tenant-context.md"], "unauthorized G1 implementation path")
    must_reject(["implementation/g1-identity-tenant-shell-authorization/AUTHORIZATION_MANIFEST.json"], "unauthorized G1 implementation path")


def falsify_mixed_diff_escape() -> None:
    errors = scope.validate_paths(
        [
            "src/jlmirror_g1/session_bridge.py",
            "tests/g1/test_shell.py",
            "src/jlmirror_authority/session.py",
        ],
        POLICY,
    )
    assert errors == ["unauthorized G1 implementation path: src/jlmirror_authority/session.py"]


def falsify_policy_rule_weakening() -> None:
    weakened = dict(POLICY)
    weakened["diff_enforcement_rule"] = "implementation_pr_declares_its_own_paths"
    errors = scope.validate_paths(["src/jlmirror_g1/shell.py"], weakened)
    assert "implementation diff enforcement rule drift" in errors


def prove_allowed_paths() -> None:
    errors = scope.validate_paths(
        [
            "apps/g1-identity-tenant-shell/frontend/index.html",
            "contracts/g1-identity-tenant-shell/shell.json",
            "implementation/g1-identity-tenant-shell/EXECUTION_MANIFEST.json",
            "sql/g1/001_identity_shell.sql",
            "src/jlmirror_g1/app.py",
            "tests/g1/test_browser.py",
            "tools/g1/run_e2e.py",
            ".github/workflows/g1-identity-tenant-shell-runtime.yml",
        ],
        POLICY,
    )
    assert not errors, errors


def main() -> int:
    prove_allowed_paths()
    falsify_shared_core_mutation()
    falsify_mixed_diff_escape()
    falsify_policy_rule_weakening()
    print("g1_implementation_scope_falsification=PASS shared_core=blocked mixed_diff=blocked policy_self_declaration=blocked allowed_paths=accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
