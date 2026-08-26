from __future__ import annotations

import json
from pathlib import Path

from jlmirror_release.model import CANONICAL_RUNTIME_PROFILES
from jlmirror_release.verification import RUNTIME_PROFILE_MINIMUM_RELIABILITY_BINDINGS

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "implementation/wave-3/source-registry.json"
MANIFEST = ROOT / "implementation/wave-3/IMPLEMENTATION_MANIFEST.json"
TESTS = ROOT / "tests/wave3/test_runtime_profile_reliability.py"

PHASE13_PATH = "docs/13-platform-runtime/09-runtime-semantic-manifest.md"
PHASE13_BLOB = "a0b2aaa950bab2a71f54f8df37a855b6ed34ad8b"
REQUIRED_LAW = "PHASE 13 RUNTIME PROFILE != RELEASE-POLICY-DISCRETIONARY RELIABILITY MINIMUM"
REQUIRED_FORBIDDEN = "phase13_runtime_profile_with_omitted_mandatory_reliability_binding"
EXPECTED_MINIMUMS = {
    "runtime.web-bff@1": {"rel.security-session-authority@1"},
    "runtime.api@1": {
        "rel.cell-transactional-store@1",
        "rel.security-session-authority@1",
        "rel.performance-cache@1",
        "rel.configuration-authority@1",
    },
    "runtime.worker@1": set(),
    "runtime.realtime@1": {
        "rel.realtime-fanout@1",
        "rel.security-session-authority@1",
        "rel.replay-consume-state@1",
    },
    "runtime.control-plane@1": {
        "rel.control-plane-placement@1",
        "rel.placement-reference-cache@1",
        "rel.configuration-authority@1",
    },
    "runtime.automation@1": {"rel.privileged-operations@1"},
    "runtime.untrusted-parser@1": set(),
    "runtime.migration-admin@1": {
        "rel.privileged-operations@1",
        "rel.cell-transactional-store@1",
        "rel.configuration-authority@1",
    },
    "runtime.recovery@1": {
        "rel.privileged-operations@1",
        "rel.control-plane-placement@1",
        "rel.replay-consume-state@1",
        "rel.secret-key-authority@1",
    },
    "runtime.edge-optional@1": set(),
}
REQUIRED_TEST_NAMES = {
    "test_runtime_api_cannot_omit_configuration_reliability",
    "test_runtime_api_complete_minimum_is_accepted",
    "test_control_plane_cannot_omit_placement_cache_reliability",
    "test_web_bff_does_not_make_conditional_performance_cache_mandatory",
    "test_unknown_runtime_profile_is_rejected",
    "test_duplicate_runtime_profile_is_rejected",
}


def fail(message: str) -> None:
    raise SystemExit(f"WAVE3 RUNTIME PROFILE RELIABILITY VALIDATION FAILED: {message}")


def validate() -> None:
    if set(EXPECTED_MINIMUMS) != set(CANONICAL_RUNTIME_PROFILES):
        fail("validator expected runtime profile set drift")
    actual = {key: set(value) for key, value in RUNTIME_PROFILE_MINIMUM_RELIABILITY_BINDINGS.items()}
    if actual != EXPECTED_MINIMUMS:
        fail(f"runtime profile reliability minimum mapping drift: {actual!r}")

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    pins = {item["path"]: item["git_blob_sha"] for item in registry["sources"]}
    if pins.get(PHASE13_PATH) != PHASE13_BLOB:
        fail("Phase 13 runtime semantic manifest is not pinned to the accepted authority blob")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if REQUIRED_LAW not in set(manifest.get("canonical_release_laws", [])):
        fail("implementation manifest is missing the Phase 13 runtime reliability law")
    if REQUIRED_FORBIDDEN not in set(manifest.get("forbidden_substitutions", [])):
        fail("implementation manifest is missing the runtime reliability omission anti-laundering rule")

    tests_text = TESTS.read_text(encoding="utf-8")
    for name in REQUIRED_TEST_NAMES:
        if f"def {name}(" not in tests_text:
            fail(f"missing adversarial test {name}")

    print(
        "WAVE3 RUNTIME PROFILE RELIABILITY VALIDATION: PASS — Phase 13 runtime profiles "
        "cannot omit their fixed minimum Phase 11 reliability bindings from pre-effect release requirements."
    )


if __name__ == "__main__":
    validate()
