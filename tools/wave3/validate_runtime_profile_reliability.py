from __future__ import annotations

import json
from pathlib import Path

from jlmirror_release.model import CANONICAL_RUNTIME_PROFILES, CANONICAL_WORKER_SPECIALIZATIONS
from jlmirror_release.verification import (
    RUNTIME_PROFILE_MINIMUM_RELIABILITY_BINDINGS,
    WORKER_SPECIALIZATION_MINIMUM_RELIABILITY_BINDINGS,
)

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "implementation/wave-3/source-registry.json"
MANIFEST = ROOT / "implementation/wave-3/IMPLEMENTATION_MANIFEST.json"
TESTS = ROOT / "tests/wave3/test_runtime_profile_reliability.py"

PHASE13_PATH = "docs/13-platform-runtime/09-runtime-semantic-manifest.md"
PHASE13_BLOB = "a0b2aaa950bab2a71f54f8df37a855b6ed34ad8b"
REQUIRED_LAWS = {
    "PHASE 13 RUNTIME PROFILE != RELEASE-POLICY-DISCRETIONARY RELIABILITY MINIMUM",
    "RUNTIME.WORKER@1 != UNSPECIALIZED RELEASE TARGET",
}
REQUIRED_FORBIDDEN = {
    "phase13_runtime_profile_with_omitted_mandatory_reliability_binding",
    "runtime_worker_without_exact_phase13_specialization",
}
EXPECTED_RUNTIME_MINIMUMS = {
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
EXPECTED_WORKER_MINIMUMS = {
    "worker.outbox-publication@1": {"rel.outbox-publication@1", "rel.broker-job-transport@1"},
    "worker.async-consumer@1": {"rel.consumer-inbox-effect@1", "rel.broker-job-transport@1"},
    "worker.provider-integration@1": {"rel.external-provider@1"},
    "worker.webhook-delivery@1": {"rel.webhook-delivery@1"},
    "worker.reporting-export@1": {"rel.reporting-derived@1"},
    "worker.customer-telemetry@1": {"rel.customer-telemetry-acceptance@1"},
    "worker.artifact-lifecycle@1": {"rel.artifact-storage@1"},
    "worker.reconciliation@1": set(),
}
REQUIRED_TEST_NAMES = {
    "test_runtime_api_cannot_omit_configuration_reliability",
    "test_runtime_api_complete_minimum_is_accepted",
    "test_control_plane_cannot_omit_placement_cache_reliability",
    "test_web_bff_does_not_make_conditional_performance_cache_mandatory",
    "test_unknown_runtime_profile_is_rejected",
    "test_duplicate_runtime_profile_is_rejected",
    "test_worker_runtime_requires_exact_specialization",
    "test_worker_specialization_without_worker_runtime_is_rejected",
    "test_unknown_or_duplicate_worker_specialization_is_rejected",
    "test_outbox_worker_cannot_omit_broker_transport_reliability",
    "test_outbox_worker_complete_minimum_is_accepted",
    "test_reconciliation_worker_uses_exact_pre_effect_affected_reliability",
}


def fail(message: str) -> None:
    raise SystemExit(f"WAVE3 RUNTIME PROFILE RELIABILITY VALIDATION FAILED: {message}")


def validate() -> None:
    if set(EXPECTED_RUNTIME_MINIMUMS) != set(CANONICAL_RUNTIME_PROFILES):
        fail("validator expected runtime profile set drift")
    actual_runtime = {key: set(value) for key, value in RUNTIME_PROFILE_MINIMUM_RELIABILITY_BINDINGS.items()}
    if actual_runtime != EXPECTED_RUNTIME_MINIMUMS:
        fail(f"runtime profile reliability minimum mapping drift: {actual_runtime!r}")

    if set(EXPECTED_WORKER_MINIMUMS) != set(CANONICAL_WORKER_SPECIALIZATIONS):
        fail("validator expected worker specialization set drift")
    actual_worker = {key: set(value) for key, value in WORKER_SPECIALIZATION_MINIMUM_RELIABILITY_BINDINGS.items()}
    if actual_worker != EXPECTED_WORKER_MINIMUMS:
        fail(f"worker specialization reliability minimum mapping drift: {actual_worker!r}")

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    pins = {item["path"]: item["git_blob_sha"] for item in registry["sources"]}
    if pins.get(PHASE13_PATH) != PHASE13_BLOB:
        fail("Phase 13 runtime semantic manifest is not pinned to the accepted authority blob")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    release_laws = set(manifest.get("canonical_release_laws", []))
    forbidden = set(manifest.get("forbidden_substitutions", []))
    missing_laws = REQUIRED_LAWS - release_laws
    if missing_laws:
        fail("implementation manifest is missing Phase 13 release laws: " + ",".join(sorted(missing_laws)))
    missing_forbidden = REQUIRED_FORBIDDEN - forbidden
    if missing_forbidden:
        fail("implementation manifest is missing Phase 13 anti-laundering rules: " + ",".join(sorted(missing_forbidden)))

    tests_text = TESTS.read_text(encoding="utf-8")
    for name in REQUIRED_TEST_NAMES:
        if f"def {name}(" not in tests_text:
            fail(f"missing adversarial test {name}")

    print(
        "WAVE3 RUNTIME PROFILE RELIABILITY VALIDATION: PASS — Phase 13 runtime profiles and exact worker "
        "specializations cannot omit their fixed minimum Phase 11 reliability bindings from pre-effect release requirements."
    )


if __name__ == "__main__":
    validate()
