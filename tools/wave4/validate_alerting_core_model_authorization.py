from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "implementation/wave-4-alerting-core-model-authorization/AUTHORIZATION.md"
MANIFEST = ROOT / "implementation/wave-4-alerting-core-model-authorization/AUTHORIZATION_MANIFEST.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    auth = AUTH.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    require(manifest["authorization_id"] == "wave4.alerting-core-model@1", "wrong authorization id")
    require(manifest["canonical_base"] == "e7cb9512846926f01429d3fbc4c6d6b0a2a9db71", "wrong canonical base")
    require(manifest["owner_domain"] == "alerting", "Alerting must own alert state")
    require(manifest["lifecycle_states"] == ["active", "resolved"], "lifecycle state drift")
    require(manifest["source_kinds"] == ["monitoring_problem", "monitoring_health_projection"], "source-kind drift")
    require(manifest["resolved_is_terminal"] is True, "resolved must be terminal")
    require(manifest["same_alert_id_reopen_authorized"] is False, "same alert reopen must remain blocked")
    require(manifest["policy_identity_version_required_for_effectful_transition"] is True, "policy identity/version must be required")
    require(manifest["policyless_lifecycle_transition_authorized"] is False, "policy-less lifecycle transition must remain blocked")
    require(manifest["mixed_source_family_authorized"] is False, "mixed source family must remain blocked")
    require(manifest["transition_history_immutable"] is True, "transition history must be immutable")
    require(manifest["tenant_isolation_required"] is True, "tenant isolation required")
    require(manifest["source_currentness_required_for_future_effects"] is True, "source currentness law missing")

    for field in (
        "provider_id_is_alert_identity",
        "monitoring_event_is_alert",
        "monitoring_state_is_alert_state",
        "automatic_creation_authorized",
        "automatic_resolution_authorized",
        "alert_policy_evaluation_authorized",
        "acknowledgement_authorized",
        "suppression_authorized",
        "routing_authorized",
        "notification_authorized",
        "notification_delivery_authorized",
        "escalation_authorized",
        "realtime_authorized",
        "public_webhook_authorized",
        "itsm_authorized",
        "aiops_authorized",
        "automation_authorized",
        "provider_writeback_authorized",
        "frontend_authorized",
        "broker_order_is_authority",
        "provider_time_is_lifecycle_authority",
    ):
        require(manifest[field] is False, f"forbidden authority enabled: {field}")

    require(manifest["production_authority"] == "none", "production authority must remain none")

    for marker in (
        "MONITORING PROBLEM != ALERT",
        "MONITORING HEALTH != ALERT",
        "MONITORING EVENT != ALERT",
        "ALERT != ITSM INCIDENT",
        "PROVIDER ID != ALERT ID",
        "EVENT ARRIVAL != ALERT CREATION AUTHORITY",
        "POLICY VERSION != MUTABLE LOOKUP AT EXECUTION TIME",
        "active | resolved",
        "A resolved `alert_id` never reopens",
        "source_kind = monitoring_problem | monitoring_health_projection",
        "one Alert occurrence has exactly one source evidence family",
        "There is no policy-less create/resolve path",
        "there is **no automatic Alert creation or resolution authority**",
        "Acknowledgement and suppression are explicitly separate concerns from lifecycle",
        "automatic alert creation/resolution remains blocked",
    ):
        require(marker in auth, f"authorization marker missing: {marker}")

    print("wave4_alerting_core_model_authorization=PASS")


if __name__ == "__main__":
    main()
