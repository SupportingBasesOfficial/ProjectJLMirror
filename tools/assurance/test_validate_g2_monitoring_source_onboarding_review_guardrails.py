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


def _scope_policy() -> dict:
    return {
        "implementation_pr_head_prefix": scope.EXPECTED_HEAD_PREFIX,
        "implementation_pr_required_label": scope.EXPECTED_LABEL,
        "implementation_claim_path": scope.EXPECTED_CLAIM_PATH,
        "implementation_claim_authorization_id": scope.EXPECTED_AUTHORIZATION_ID,
        "implementation_pr_base_ref_policy": "must_equal_repository_default_branch",
        "trusted_evaluator_event": "issue_comment",
        "trusted_scope_attestation_command": scope.EXPECTED_ATTESTATION_COMMAND,
        "trusted_scope_readiness_command": scope.EXPECTED_READINESS_COMMAND,
        "trusted_evaluator_source": "default_branch_issue_comment_workflow_plus_exact_default_branch_base_git_object",
        "trusted_scope_status_context": scope.EXPECTED_STATUS_CONTEXT,
        "trusted_scope_readiness_status_context": scope.EXPECTED_READY_CONTEXT,
        "trusted_scope_status_evidence_role": "evidence_only_not_standalone_merge_authority",
        "trusted_scope_freshness_rule": "merge_readiness_revalidates_live_head_base_default_tip_label_and_trusted_status_run_provenance",
        "trusted_scope_concurrency_rule": "per_pr_cancel_in_progress",
        "trusted_status_creator_login": "github-actions[bot]",
        "trusted_status_creator_id": 41898282,
        "same_repository_required": True,
        "implementation_pr_requires_trusted_scope_attestation_on_exact_head": True,
        "implementation_pr_requires_trusted_scope_readiness_on_exact_head_base": True,
        "candidate_controlled_relevance_inference": "forbidden",
        "allowed_prefixes": list(scope.EXPECTED_PREFIXES),
        "allowed_exact_paths": list(scope.EXPECTED_EXACT),
        "diff_enforcement_rule": scope.EXPECTED_RULE,
        "semantic_guard_rule": scope.EXPECTED_SEMANTIC_RULE,
        "forbidden_path_tokens": list(scope.EXPECTED_FORBIDDEN_PATH_TOKENS),
        "forbidden_code_markers": list(scope.EXPECTED_FORBIDDEN_CODE_MARKERS),
        "semantic_scan_prefixes": list(scope.EXPECTED_SEMANTIC_SCAN_PREFIXES),
    }


def falsify_g2_semantic_scope_guard() -> None:
    policy = _scope_policy()
    scope.configured_policy(policy)
    if not scope.validate_paths(["src/jlmirror_g2/resource_inventory.py"], policy):
        raise AssertionError("parallel G2 domain namespace bypassed path policy")
    if not scope.validate_paths(["sql/g2/parallel_monitoring_source.sql"], policy):
        raise AssertionError("parallel G2 persistence namespace bypassed path policy")
    cases = (
        ("apps/g2-monitoring-source-onboarding/resource_inventory.ts", "export const page = true", "forbidden G3 inventory path bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const monitoring_resource = payload.resource", "forbidden G3 resource semantics bypassed semantic guard"),
        ("implementation/g2-monitoring-source-onboarding/parallel_monitoring.py", "CREATE TABLE monitoring.metric_current_state (id uuid)", "implementation namespace executable artifact bypassed semantic guard"),
        ("tests/g2/parallel_store.py", "class ResourceInventory: pass", "tests namespace executable artifact bypassed semantic guard"),
        ("implementation/g2-monitoring-source-onboarding/parallel.sql", "CREATE TABLE monitoring.metric_current_state (id uuid)", "SQL artifact bypassed semantic guard"),
        ("tools/g2/run-onboarding", "class ResourceInventory: pass", "extensionless executable artifact bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class ResourceInventory {}\nconst metricCurrentState = true", "camel/Pascal case forbidden semantics bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class HostInventory {}", "host inventory exclusion bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const metricValue = 1", "metric value exclusion bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class Problem {}", "problem exclusion bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const healthStatus = 'green'", "health exclusion bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class SourceCutover {}", "source cutover exclusion bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const secretManager = provider", "secret manager exclusion bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const egressTransport = provider", "egress transport exclusion bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const commercialPlan = true", "commercial exclusion bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/core.py", "class ＲｅｓｏｕｒｃｅＩｎｖｅｎｔｏｒｙ:\n    pass", "unicode compatibility identifier bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class Metric {}", "bare metric exclusion bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class ResourceIngestion {}", "resource ingestion exclusion bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class Health {}", "bare health exclusion bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class AckHandler {}", "ack handler exclusion bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class C3Numerics {}", "C3 numerics exclusion bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class ProviderNativeAuthority {}", "provider-native authority exclusion bypassed semantic guard"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const RawCredentials = request.body", "raw credentials exclusion bypassed semantic guard"),
    )
    for path, text, message in cases:
        if not scope.validate_semantic_artifact(path, text, policy):
            raise AssertionError(message)
    if scope.validate_semantic_artifact(
        "apps/g2-monitoring-source-onboarding/source.ts",
        "export const sourceStatus = 'reconciliation_required'",
        policy,
    ):
        raise AssertionError("bounded G2 onboarding semantics were rejected")


def falsify_g2_trusted_workflow_semantics() -> None:
    workflow = authorization.SCOPE_WORKFLOW.read_text(encoding="utf-8")
    if authorization.validate_scope_workflow_text(workflow):
        raise AssertionError("canonical G2 trusted workflow failed structural validation")
    mutations = (
        (workflow.replace('          python3 "$TRUSTED_VALIDATOR" \\\n', '          # python3 "$TRUSTED_VALIDATOR" \\\n', 1), "trusted validator"),
        (workflow.replace('          python3 "$TRUSTED_READINESS_VALIDATOR" \\\n', '          # python3 "$TRUSTED_READINESS_VALIDATOR" \\\n', 1), "readiness"),
        (workflow.replace("          state=failure\n", "          state=success\n", 1), "fail-closed control-flow"),
        (
            workflow.replace('          python3 "$TRUSTED_VALIDATOR" \\\n', '          if false; then\n          python3 "$TRUSTED_VALIDATOR" \\\n', 1).replace('            --base-repo "$PR_BASE_REPO"\n', '            --base-repo "$PR_BASE_REPO"\n          fi\n', 1),
            "command-only shape",
        ),
        (workflow.replace('            --base-repo "$PR_BASE_REPO"\n', '            --base-repo "$PR_BASE_REPO" || true\n', 1), "command-only shape"),
        (workflow.replace("          state=failure\n", "          state=failure\n          result=success\n", 1), "assignment authority"),
        (
            workflow.replace('          python3 "$TRUSTED_VALIDATOR" \\\n', '          python3() { return 0; }\n          python3 "$TRUSTED_VALIDATOR" \\\n', 1),
            "command-only shape",
        ),
        (workflow.replace("          state=failure\n", "          state=failure\n          printf -v result success\n", 1), "indirect result/state assignment"),
        (workflow.replace('          test "$state" = success\n', '          printf -v state success\n          test "$state" = success\n', 1), "indirect result/state assignment"),
        (
            workflow.replace('          test -s "$trusted_validator"\n', '          test -s "$trusted_validator"\n          printf \'raise SystemExit(0)\\n\' > "$trusted_validator"\n', 1),
            "materialization",
        ),
        (workflow.replace("          state=failure\n", "          state=failure\n          result[0]=success\n", 1), "assignment authority"),
        (workflow.replace('          test "$state" = success\n', '          state[0]=success\n          test "$state" = success\n', 1), "assignment authority"),
    )
    for mutated, expected in mutations:
        errors = authorization.validate_scope_workflow_text(mutated)
        if not errors or not any(expected in error for error in errors):
            raise AssertionError(f"trusted workflow weakening escaped structural guard: {expected}; errors={errors}")


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
    print("g2_review_guardrails=PASS probes=3 semantic=unicode+explicit-exclusions workflow=canonical-materialization+assignment-closure status=total-order")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())