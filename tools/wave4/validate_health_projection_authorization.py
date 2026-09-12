from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "implementation/wave-4-health-projection-authorization/AUTHORIZATION.md"
MANIFEST = ROOT / "implementation/wave-4-health-projection-authorization/AUTHORIZATION_MANIFEST.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    auth = AUTH.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    require(manifest["authorization_id"] == "wave4.monitoring-health-projection@1", "wrong health authorization id")
    require(manifest["status"] == "proposed_bounded_implementation_authorization", "wrong health authorization status")
    require(manifest["canonical_base"] == "1da4350cb860d759549b6302e575a02af6f07b09", "wrong canonical base")
    require(manifest["projection_owner"] == "monitoring", "Health projection must remain Monitoring-owned")
    require(
        manifest["canonical_health_class"] == ["unknown", "healthy", "degraded", "unhealthy"],
        "canonical health classes drifted",
    )
    require(
        manifest["canonical_evidence_state"] == ["current", "stale", "incomplete", "reconciliation_required", "unavailable"],
        "canonical evidence states drifted",
    )
    require(manifest["healthy_requires_authoritative_problem_completeness"] is True, "healthy must require Problem State completeness")
    require(manifest["current_health_requires_present_resource"] is True, "current health must require present resource authority")
    require(
        "durable_problem_state_snapshot_completeness_evidence" in manifest["authorized_inputs"],
        "Problem State completeness evidence missing from authorized inputs",
    )

    for field in (
        "provider_polling_authorized",
        "historical_generation_current_authority",
        "stale_evidence_can_prove_healthy",
        "problem_absence_without_completeness_can_prove_healthy",
        "removed_resource_current_health_authority",
        "provider_acknowledgement_health_authority",
        "cross_domain_health_event_authorized",
        "alerting_authorized",
        "itsm_authorized",
        "automation_authorized",
        "aiops_authorized",
        "provider_writeback_authorized",
        "frontend_authorized",
    ):
        require(manifest[field] is False, f"forbidden authority enabled: {field}")

    require(manifest["health_read_action"] == "monitoring.health.read", "wrong health read action")
    require(manifest["health_cache_class"] == "private_revalidate", "wrong health cache class")
    require(manifest["health_cursor_anchor"] == "monitoring_resource_id", "wrong health cursor anchor")
    require(manifest["production_authority"] == "none", "production authority must remain none")

    for marker in (
        "HEALTH DERIVATION != PROVIDER POLLING AUTHORITY",
        "STALE/INCOMPLETE EVIDENCE != PROVEN HEALTHY",
        "PROBLEM ABSENCE WITHOUT AUTHORITATIVE COMPLETENESS != HEALTHY",
        "HISTORICAL GENERATION != CURRENT HEALTH AUTHORITY",
        "REMOVED RESOURCE != CURRENT HEALTH AUTHORITY",
        "PROVIDER ACKNOWLEDGED != HEALTH AUTHORITY",
        "HEALTH PROJECTION != ALERTING STATE",
        "HEALTH PROJECTION != ITSM STATE",
        "HEALTH PROJECTION != AIOPS FINDING",
        "`healthy` requires **durable current authoritative Problem State completeness evidence**",
        "active `critical` problem requires `unhealthy`",
        "active `unknown`-severity problem prevents the resource from being proven `healthy`",
        "informational-only active problems may coexist with `healthy`",
        "monitoring_resource_id` in ascending deterministic order",
        "`private_revalidate` cache class",
        "Track A still does not authorize a public/cross-domain `health.changed` integration event",
    ):
        require(marker in auth, f"health authorization marker missing: {marker}")

    serialized_manifest = json.dumps(manifest, sort_keys=True)
    for runtime_path in (
        "src/jlmirror_monitoring/health_projection.py",
        "sql/wave4/047_health_projection.sql",
    ):
        require(runtime_path not in auth, f"authorization artifact grants runtime path: {runtime_path}")
        require(runtime_path not in serialized_manifest, f"authorization manifest grants runtime path: {runtime_path}")

    print("wave4_health_projection_authorization=PASS")


if __name__ == "__main__":
    main()
