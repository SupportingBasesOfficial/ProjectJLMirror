from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "implementation/wave-4-monitoring-alerting-publication-authorization/AUTHORIZATION.md"
MANIFEST = ROOT / "implementation/wave-4-monitoring-alerting-publication-authorization/AUTHORIZATION_MANIFEST.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    auth = AUTH.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    require(manifest["authorization_id"] == "wave4.monitoring-alerting-publication@1", "wrong authorization id")
    require(manifest["status"] == "proposed_bounded_implementation_authorization", "wrong status")
    require(manifest["canonical_base"] == "193883f0b3ddfd3531ceb54e0849c2f6e04744bc", "wrong canonical base")
    require(manifest["producer_domain"] == "monitoring", "Monitoring must remain producer")
    require(manifest["consumer_domain_target"] == "alerting", "wrong target consumer domain")
    require(manifest["message_class"] == "integration_event", "wrong message class")
    require(manifest["contract_version"] == 1, "wrong contract version")
    require(manifest["delivery"] == "at_least_once", "wrong delivery law")
    require(manifest["data_classification"] == "confidential_tenant", "wrong data class")
    require(
        manifest["contracts"] == [
            "monitoring.problem-state.changed",
            "monitoring.health-projection.changed",
        ],
        "contract names drifted",
    )
    require(manifest["events_are_invalidation_not_state_replication"] is True, "events must be invalidation signals")
    require(manifest["consumer_must_reread_monitoring"] is True, "consumer reread requirement missing")
    require(manifest["semantic_state_values_allowed_in_payload"] is False, "semantic Monitoring state leaked into payload")
    require(manifest["authorized_consumer_effect"] == "durable_invalidation_resync_responsibility_only", "consumer effect widened")

    for field in (
        "broker_order_is_authority",
        "historical_generation_current_authority",
        "provider_ids_allowed_in_payload",
        "provider_payload_allowed",
        "metric_values_allowed",
        "public_webhook_authorized",
        "browser_realtime_authorized",
        "alert_lifecycle_authorized",
        "alert_acknowledgement_authorized",
        "alert_suppression_authorized",
        "notification_authorized",
        "escalation_authorized",
        "routing_authorized",
        "itsm_authorized",
        "automation_authorized",
        "aiops_authorized",
        "provider_writeback_authorized",
        "new_broker_or_outbox_substrate_authorized",
    ):
        require(manifest[field] is False, f"forbidden authority enabled: {field}")

    require(manifest["production_authority"] == "none", "production authority must remain none")

    for marker in (
        "MONITORING EVENT != ALERT STATE",
        "EVENT ARRIVAL != CURRENT STATE AUTHORITY",
        "BROKER ORDER != OWNER-DOMAIN ORDER",
        "HISTORICAL GENERATION != CURRENT ALERTING INPUT AUTHORITY",
        "EVENT PAYLOAD != CURRENT PROBLEM/HEALTH STATE REPLICA",
        "monitoring.problem-state.changed",
        "monitoring.health-projection.changed",
        "invalidation/resync signals rather than state replication",
        "deliberately omits `problem_state` and `severity_class`",
        "deliberately omits `health_class` and `health_evidence_state`",
        "re-establishes current tenant/placement/service authority",
        "stop without creating Alerting/ITSM/AIOps/Automation business state",
        "No new broker, outbox substrate or telemetry stream is authorized",
        "Runtime publication implementation and all Alerting business behavior remain blocked",
    ):
        require(marker in auth, f"authorization marker missing: {marker}")

    print("wave4_monitoring_alerting_publication_authorization=PASS")


if __name__ == "__main__":
    main()
