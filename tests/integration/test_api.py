"""Integration tests for the JLMIRROR FastAPI application.

These tests use FastAPI's TestClient and do not require a running database
(the DB pool is lazily initialized and only used by /health/ready and
persistence-backed endpoints). The domain endpoints use in-memory authorities
in development mode.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on the path for domain primitives.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_liveness():
    """Liveness probe returns 200 without checking the database."""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "environment" in body


def test_openapi_docs_available():
    """Interactive API docs are available."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi_schema_has_all_routers():
    """The OpenAPI schema includes routes from all domain routers."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = set(schema["paths"].keys())
    # Authority domain
    assert "/api/v1/auth/session/issue" in paths
    assert "/api/v1/auth/authorize" in paths
    assert "/api/v1/fence/acquire" in paths
    # Monitoring domain
    assert "/api/v1/monitoring/sources" in paths
    assert "/api/v1/monitoring/health/derive" in paths
    # Async domain
    assert "/api/v1/async/outbox/append" in paths
    assert "/api/v1/async/outbox/claim-next" in paths
    # Observability domain
    assert "/api/v1/observability/profiles" in paths
    # Release domain
    assert "/api/v1/release/outcomes" in paths


def test_observability_profiles_list():
    """List reliability profiles returns a non-empty list."""
    response = client.get("/api/v1/observability/profiles")
    assert response.status_code == 200
    profiles = response.json()
    assert isinstance(profiles, list)
    assert len(profiles) > 0
    # All profile IDs should start with "rel."
    assert all(p.startswith("rel.") for p in profiles)


def test_release_outcomes_list():
    """List outcome classes returns all accepted classes."""
    response = client.get("/api/v1/release/outcomes")
    assert response.status_code == 200
    outcomes = response.json()
    assert isinstance(outcomes, list)
    assert "rollback_eligible" in outcomes
    assert "reconciliation_required" in outcomes


def test_fence_bootstrap_and_acquire():
    """Bootstrap a fence and then acquire the next epoch."""
    # Bootstrap
    response = client.post(
        "/api/v1/fence/bootstrap",
        json={"fence_scope_id": "tenant:test-fence", "generation_id": "gen-1"},
        headers={"X-Principal-Id": "dev-test-user"},
    )
    assert response.status_code == 200
    bootstrapped = response.json()
    assert bootstrapped["current_fence_epoch"] == 1
    assert bootstrapped["current_generation_id"] == "gen-1"

    # Acquire next epoch
    response = client.post(
        "/api/v1/fence/acquire",
        json={
            "fence_scope_id": "tenant:test-fence",
            "expected_predecessor_epoch": 1,
            "expected_predecessor_generation_id": "gen-1",
            "successor_generation_id": "gen-2",
        },
        headers={"X-Principal-Id": "dev-test-user"},
    )
    assert response.status_code == 200
    acquired = response.json()
    assert acquired["current_fence_epoch"] == 2
    assert acquired["current_generation_id"] == "gen-2"


def test_session_issue_and_retire():
    """Issue a browser session and then retire it."""
    # Issue
    response = client.post(
        "/api/v1/auth/session/issue",
        json={"principal_id": "dev-test-user", "credential_generation": "credential-gen-dev-1"},
        headers={"X-Principal-Id": "dev-test-user"},
    )
    assert response.status_code == 200
    session = response.json()
    assert "session_handle" in session
    assert session["principal_id"] == "dev-test-user"
    handle = session["session_handle"]

    # Retire
    response = client.post(
        "/api/v1/auth/session/retire",
        json={"session_handle": handle},
        headers={"X-Principal-Id": "dev-test-user"},
    )
    assert response.status_code == 204


def test_monitoring_health_derive():
    """Derive a health decision from monitoring evidence."""
    response = client.post(
        "/api/v1/monitoring/health/derive",
        json={
            "monitoring_source_id": "mon-src-1",
            "monitoring_resource_id": "res-1",
            "source_is_current": True,
            "resource_present": True,
            "scope_is_current_and_in_scope": True,
            "problem_completeness_is_current": True,
            "evidence_state": "current",
            "active_problem_severities": [],
            "reason_refs": [],
        },
        headers={"X-Principal-Id": "dev-test-user", "X-Tenant-Id": "tenant:dev"},
    )
    assert response.status_code == 200
    decision = response.json()
    assert decision["health_class"] == "healthy"
    assert decision["evidence_state"] == "current"


def test_outcome_classify_rollback_eligible():
    """Classify a change outcome as rollback_eligible."""
    response = client.post(
        "/api/v1/release/outcome/classify",
        json={
            "scope_binding": "release:test-scope",
            "effect_outcome_ambiguous": False,
            "irreversible_without_governed_migration": False,
            "previous_runtime_can_interpret_current_state": True,
            "rollback_configuration_evidence_current": True,
            "cell_compatibility_allows_previous": True,
            "release_policy_and_verifier_current": True,
            "release_target_state_allows_rollback": True,
            "security_governance_reliability_current": True,
            "required_evidence_preserved": True,
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["outcome"] == "rollback_eligible"
