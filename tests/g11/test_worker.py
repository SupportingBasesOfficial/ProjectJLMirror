import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../apps/g11-incident-response"))

import pytest
from worker import IncidentResponseWorker, FixtureNeutralTicketAdapter


class FakeActionPort:
    def __init__(self, candidate=None):
        self._candidate = candidate
        self.completed = []

    def next_pending_action(self, tenant_id):
        return self._candidate

    def claim_action(self, tenant_id, request_id, executor_id, claim_seconds):
        if self._candidate is None:
            return {"state": "conflict"}
        return {"state": "dispatching", "request_id": request_id}

    def complete_action(self, tenant_id, request_id, executor_id, result_state, provider_ref, failure_class):
        self.completed.append((request_id, result_state, provider_ref, failure_class))
        return {"state": result_state, "request_id": request_id}


def _candidate(action_kind="open_ticket"):
    return {
        "request_id": "req-1",
        "action_kind": action_kind,
        "attempts": 0,
        "event": {
            "event_id": "evt-1", "tenant_id": "t1", "application_id": "erp",
            "error_code": "ERR_DB", "error_message": "DB failed",
            "occurred_at": "2026-09-23T14:05:00Z", "severity_hint": "HIGH",
        },
    }


def _worker(candidate=None, ticket_state="linked"):
    port = FakeActionPort(candidate)
    adapter = FixtureNeutralTicketAdapter(state=ticket_state)
    return IncidentResponseWorker(port=port, ticket_adapter=adapter, notify_adapter=None, executor_id="w1"), port, adapter


def test_idle_when_no_candidate():
    worker, _, _ = _worker(candidate=None)
    result = worker.process_next("t1")
    assert result == {"state": "idle"}


def test_linked_ticket_completes_successfully():
    worker, port, adapter = _worker(candidate=_candidate(), ticket_state="linked")
    result = worker.process_next("t1")
    assert result["state"] == "linked"
    assert len(port.completed) == 1
    assert port.completed[0][1] == "linked"
    assert port.completed[0][2] == "fixture-ticket-1"


def test_failed_ticket_records_failure():
    worker, port, adapter = _worker(candidate=_candidate(), ticket_state="failed")
    result = worker.process_next("t1")
    assert result["state"] == "failed"
    assert port.completed[0][3] == "fixture_failure"


def test_adapter_exception_records_unknown():
    class ErrorAdapter:
        version = "error@1"
        def create_ticket(self, **_): raise RuntimeError("boom")

    port = FakeActionPort(_candidate())
    worker = IncidentResponseWorker(port=port, ticket_adapter=ErrorAdapter(), notify_adapter=None, executor_id="w1")
    result = worker.process_next("t1")
    assert result["state"] == "unknown"
    assert port.completed[0][3] == "adapter_execution_unknown"


def test_unknown_action_kind_records_skipped():
    worker, port, _ = _worker(candidate=_candidate(action_kind="automation"))
    result = worker.process_next("t1")
    assert result["state"] == "skipped"
