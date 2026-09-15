#!/usr/bin/env python3
from __future__ import annotations

import copy

import validate_g2_monitoring_source_onboarding_authorization as authorization
import validate_g2_monitoring_source_onboarding_implementation_scope as scope
import validate_g2_monitoring_source_onboarding_scope_readiness as readiness

REPO = "SupportingBasesOfficial/ProjectJLMirror"
SERVER = "https://github.com"
BASE = "a" * 40
HEAD = "b" * 40
RUN_ID = 424242


def _policy() -> dict:
    value = authorization.load_manifest()["implementation_path_policy"]
    scope.configured_policy(value)
    return value


def falsify_g2_semantic_scope_guard() -> None:
    policy = _policy()
    rejected = (
        ("apps/g2-monitoring-source-onboarding/source.ts", "class ResourceInventory {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const metricCurrentState = true"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class SourceCutover {}"),
        ("tests/g2/parallel_store.py", "class Metric: pass"),
        ("implementation/g2-monitoring-source-onboarding/parallel.sql", "CREATE TABLE monitoring.metric_current_state (id uuid)"),
        ("tools/g2/run-onboarding", "class Health: pass"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const Мetric = true"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class ResourceІnventory {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class SourceСutover {}"),
    )
    for path, text in rejected:
        if not scope.validate_semantic_artifact(path, text, policy):
            raise AssertionError(f"forbidden semantic artifact unexpectedly accepted: {path}: {text}")

    allowed = (
        "export const browser_automation = true",
        "export const geometric_layout = true",
        "export const sourceStatus = 'reconciliation_required'",
    )
    for text in allowed:
        errors = scope.validate_semantic_artifact("apps/g2-monitoring-source-onboarding/source.ts", text, policy)
        if errors:
            raise AssertionError(f"bounded G2 semantics false-positive: {text}: {errors}")


def falsify_g2_trusted_workflow_semantics() -> None:
    workflow = authorization.SCOPE_WORKFLOW.read_text(encoding="utf-8")
    if authorization.validate_scope_workflow_text(workflow):
        raise AssertionError("canonical trusted workflow rejected")
    mutations = (
        workflow + "\n# extra workflow material\n",
        workflow.replace("name: JLMIRROR G2 Monitoring Source Onboarding Implementation Scope", "name: drifted", 1),
        workflow.replace("cancel-in-progress: true", "cancel-in-progress: false", 1),
        workflow.replace("runs-on: ubuntu-24.04", "runs-on: ubuntu-latest", 1),
        workflow.replace("statuses: write", "contents: write", 1),
    )
    for mutated in mutations:
        errors = authorization.validate_scope_workflow_text(mutated)
        if not errors or not any("canonical blob drift" in error for error in errors):
            raise AssertionError(f"trusted workflow mutation escaped exact lock: {errors}")


def _trusted_status(*, status_id: int, state: str, created_at: str = "2026-09-15T00:00:00Z") -> dict:
    context, description, _label, _mode = readiness.evidence_contract("scope", BASE, HEAD)
    return {
        "id": status_id,
        "context": context,
        "state": state,
        "description": description,
        "target_url": f"{SERVER}/{REPO}/actions/runs/{RUN_ID}",
        "created_at": created_at,
        "creator": {"login": readiness.TRUSTED_CREATOR_LOGIN, "id": readiness.TRUSTED_CREATOR_ID},
    }


def falsify_g2_same_second_status_ordering() -> None:
    success = _trusted_status(status_id=100, state="success")
    newer_pending = _trusted_status(status_id=101, state="pending")
    try:
        readiness.select_trusted_evidence([newer_pending, success], evidence="scope", repo=REPO, server_url=SERVER, base_sha=BASE, head_sha=HEAD)
    except AssertionError as exc:
        if "not successful" not in str(exc):
            raise
    else:
        raise AssertionError("same-second newer pending status did not supersede older success")
    duplicate = copy.deepcopy(success)
    try:
        readiness.select_trusted_evidence([success, duplicate], evidence="scope", repo=REPO, server_url=SERVER, base_sha=BASE, head_sha=HEAD)
    except AssertionError as exc:
        if "ordering is ambiguous" not in str(exc):
            raise
    else:
        raise AssertionError("duplicate trusted status ordering key did not fail closed")


def main() -> int:
    falsify_g2_semantic_scope_guard()
    falsify_g2_trusted_workflow_semantics()
    falsify_g2_same_second_status_ordering()
    print("g2_review_guardrails=PASS semantic=token-boundary+confusable-closed workflow=blob-exact status=total-order")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())