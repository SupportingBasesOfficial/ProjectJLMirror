#!/usr/bin/env python3
"""Observer-only validation for Wave 1 identity/authority skeleton."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.runtime_profiles import WAVE1_RUNTIME_BINDINGS  # noqa: E402
from tools.contracts.core import build_bundle  # noqa: E402

PROFILE = "jlmirror-wave1-authority/v1"


def _third_party_import_findings() -> list[str]:
    findings: list[str] = []
    stdlib = set(sys.stdlib_module_names)
    for path in sorted((SRC / "jlmirror_authority").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for name in names:
                if name and name not in stdlib and name != "jlmirror_authority":
                    findings.append(f"third-party/runtime dependency is not accepted in Wave 1 core: {path}:{name}")
    return findings


def _runtime_catalog_findings() -> list[str]:
    bundle = build_bundle(ROOT)
    catalog_ids = {record["id"] for record in bundle["profile_catalog"]["records"]}
    required: set[str] = set()
    for binding in WAVE1_RUNTIME_BINDINGS:
        required.update(
            {
                binding.runtime_profile_id,
                binding.principal_class,
                binding.lifecycle_class,
                binding.isolation_class,
                binding.ingress_profile,
                binding.resource_profile,
                *binding.egress_profiles,
                *binding.secret_reference_classes,
                *(environment.value for environment in binding.allowed_environment_classes),
            }
        )
    missing = sorted(required - catalog_ids)
    return [f"Wave 1 runtime binding references unknown canonical profile: {value}" for value in missing]


def _fence_sql_findings() -> list[str]:
    path = ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql"
    text = path.read_text(encoding="utf-8")
    required_fragments = (
        "current_fence_epoch bigint NOT NULL CHECK (current_fence_epoch > 0)",
        "ON CONFLICT (fence_scope_id) DO NOTHING",
        "current_fence_epoch = current_fence_epoch + 1",
        "current_fence_epoch = p_expected_predecessor_epoch",
        "current_fence_epoch < 9223372036854775807",
        "SECURITY INVOKER",
        "same PostgreSQL transaction as the protected effect",
    )
    return [f"IR-D-003 SQL contract missing required invariant: {fragment}" for fragment in required_fragments if fragment not in text]


def validate() -> list[str]:
    findings: list[str] = []
    findings.extend(_third_party_import_findings())
    findings.extend(_runtime_catalog_findings())
    findings.extend(_fence_sql_findings())
    return findings


def main() -> int:
    findings = validate()
    print(f"JLMIRROR Wave 1 authority profile: {PROFILE}")
    print(f"Repository root: {ROOT}")
    if findings:
        print("RESULT: FAIL")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("RESULT: PASS — Wave 1 authority skeleton preserves accepted profile/currentness/fence boundaries")
    print("NOTE: PASS is conformance evidence only; C2 adapters remain non-canonical until accepted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
