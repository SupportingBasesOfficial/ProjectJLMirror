import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../apps/g11-incident-response"))

import pytest
from domain import (
    ApplicationErrorEvent, IncidentResponsePolicy,
    validate_event, evaluate_policy, severity_meets_threshold, minute_bucket,
    deterministic_id,
)


def _event(**kwargs) -> ApplicationErrorEvent:
    defaults = dict(
        tenant_id="t1", application_id="app-erp", error_code="ERR_DB_CONN",
        error_message="Connection refused", occurred_at="2026-09-23T14:05:00Z",
        source_principal_id="machine-principal-1", severity_hint="HIGH",
    )
    defaults.update(kwargs)
    return ApplicationErrorEvent(**defaults)


def _policy(**kwargs) -> IncidentResponsePolicy:
    defaults = dict(tenant_id="t1")
    defaults.update(kwargs)
    return IncidentResponsePolicy(**defaults)


# --- validate_event ---

def test_valid_event_passes():
    validate_event(_event())


def test_missing_tenant_id_raises():
    with pytest.raises(ValueError, match="tenant_id"):
        validate_event(_event(tenant_id=""))


def test_missing_application_id_raises():
    with pytest.raises(ValueError, match="application_id"):
        validate_event(_event(application_id=""))


def test_empty_error_message_raises():
    with pytest.raises(ValueError, match="error_message"):
        validate_event(_event(error_message=""))


def test_too_long_error_message_raises():
    with pytest.raises(ValueError, match="error_message"):
        validate_event(_event(error_message="x" * 4001))


def test_invalid_severity_hint_raises():
    with pytest.raises(ValueError, match="severity_hint"):
        validate_event(_event(severity_hint="CATASTROPHIC"))


def test_none_severity_hint_is_valid():
    validate_event(_event(severity_hint=None))


# --- severity_meets_threshold ---

def test_critical_meets_high_threshold():
    assert severity_meets_threshold("CRITICAL", "HIGH") is True


def test_high_meets_high_threshold():
    assert severity_meets_threshold("HIGH", "HIGH") is True


def test_medium_does_not_meet_high_threshold():
    assert severity_meets_threshold("MEDIUM", "HIGH") is False


def test_low_does_not_meet_critical_threshold():
    assert severity_meets_threshold("LOW", "CRITICAL") is False


def test_none_hint_never_meets_threshold():
    assert severity_meets_threshold(None, "LOW") is False


# --- evaluate_policy ---

def test_manual_override_returns_empty():
    p = _policy(manual_override_only=True, auto_open_ticket=True, severity_threshold="LOW")
    assert evaluate_policy(_event(severity_hint="CRITICAL"), p) == []


def test_below_threshold_returns_empty():
    p = _policy(severity_threshold="CRITICAL", auto_open_ticket=True)
    assert evaluate_policy(_event(severity_hint="HIGH"), p) == []


def test_auto_open_ticket_included_when_meets_threshold():
    p = _policy(severity_threshold="HIGH", auto_open_ticket=True)
    actions = evaluate_policy(_event(severity_hint="HIGH"), p)
    assert "open_ticket" in actions


def test_notify_included_when_channel_matches_severity():
    p = _policy(
        severity_threshold="LOW",
        notify_channels=({"on_severities": ["HIGH", "CRITICAL"]},),
    )
    actions = evaluate_policy(_event(severity_hint="HIGH"), p)
    assert "notify" in actions


def test_notify_not_included_when_channel_does_not_match():
    p = _policy(
        severity_threshold="LOW",
        notify_channels=({"on_severities": ["CRITICAL"]},),
    )
    actions = evaluate_policy(_event(severity_hint="HIGH"), p)
    assert "notify" not in actions


def test_no_actions_with_default_policy_low_severity():
    p = _policy()  # severity_threshold=HIGH, auto_open_ticket=False
    actions = evaluate_policy(_event(severity_hint="LOW"), p)
    assert actions == []


def test_automation_included_when_trigger_configured():
    p = _policy(
        severity_threshold="LOW",
        automation_triggers=({"trigger": "ALERT_OPEN", "runbook_id": "rb-1"},),
    )
    actions = evaluate_policy(_event(severity_hint="HIGH"), p)
    assert "automation" in actions


# --- minute_bucket ---

def test_minute_bucket_truncates_to_minute():
    assert minute_bucket("2026-09-23T14:05:47Z") == "2026-09-23T14:05"


def test_minute_bucket_already_at_minute():
    assert minute_bucket("2026-09-23T14:05:00Z") == "2026-09-23T14:05"


# --- deterministic_id ---

def test_deterministic_id_is_stable():
    a = deterministic_id("evt:", "t1", "app", "ERR", "2026-09-23T14:05")
    b = deterministic_id("evt:", "t1", "app", "ERR", "2026-09-23T14:05")
    assert a == b


def test_deterministic_id_differs_for_different_inputs():
    a = deterministic_id("evt:", "t1", "app", "ERR_A")
    b = deterministic_id("evt:", "t1", "app", "ERR_B")
    assert a != b
