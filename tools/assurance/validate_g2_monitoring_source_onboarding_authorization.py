#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "implementation/g2-monitoring-source-onboarding-authorization/AUTHORIZATION_MANIFEST.json"
AUTHORIZATION = ROOT / "implementation/g2-monitoring-source-onboarding-authorization/AUTHORIZATION.md"
TASK_PACKET = ROOT / "implementation/g2-monitoring-source-onboarding-authorization/TASK_PACKET.md"
SCOPE_VALIDATOR = ROOT / "tools/assurance/validate_g2_monitoring_source_onboarding_implementation_scope.py"
READINESS_VALIDATOR = ROOT / "tools/assurance/validate_g2_monitoring_source_onboarding_scope_readiness.py"
SCOPE_WORKFLOW = ROOT / ".github/workflows/g2-monitoring-source-onboarding-implementation-scope.yml"
REPOSITORY_VALIDATOR = ROOT / "tools/assurance/validate_repository.py"
REVIEW_GUARDRAILS = ROOT / "tools/assurance/test_validate_g2_monitoring_source_onboarding_review_guardrails.py"
LEARNING_LEDGER = ROOT / "governance/adversarial/learning-ledger.d/pr-154-g2-authorization-review-findings.json"

BASE_SHA = "8e26b05596aeca2e45578908ca4afc4f1fa175d6"
AUTH_ID = "g2.monitoring-source-onboarding@1"
SLICE_ID = AUTH_ID
EXPECTED_PREFIXES = [
    "apps/g2-monitoring-source-onboarding/",
    "contracts/g2-monitoring-source-onboarding/",
    "implementation/g2-monitoring-source-onboarding/",
    "tests/g2/",
    "tools/g2/",
]
EXPECTED_EXACT = [".github/workflows/g2-monitoring-source-onboarding-runtime.yml"]
EXPECTED_SEMANTIC_RULE = "candidate_executable_artifacts_must_not_introduce_forbidden_g3_or_parallel_monitoring_authority"
EXPECTED_FORBIDDEN_PATH_TOKENS = [
    "inventory", "monitoring-resource", "monitoring_resource", "metric", "problem", "health", "alert", "replacement", "cutover",
]
EXPECTED_FORBIDDEN_CODE_MARKERS = [
    "monitoring_resource", "resource_inventory", "metric_definition", "metric_current_state", "metric_observation",
    "problem_state", "health_projection", "alert_policy", "alerting.", "replacement_candidate",
    "replace_source_instance", "candidate_generation", "create table monitoring.", "create schema monitoring",
    "src/jlmirror_monitoring", "sql/wave4",
]
EXPECTED_SEMANTIC_SCAN_PREFIXES = [
    "apps/g2-monitoring-source-onboarding/",
    "contracts/g2-monitoring-source-onboarding/",
    "implementation/g2-monitoring-source-onboarding/",
    "tests/g2/",
    "tools/g2/",
]
EXPECTED_CAPABILITIES = {
    "zabbix_monitoring_source_initial_create_through_current_tenant_authority",
    "safe_source_configuration_without_raw_credential_bytes",
    "opaque_credential_binding_reference_only",
    "initial_source_generation_and_scope_revision_creation",
    "durable_validation_and_initial_sync_responsibility",
    "reuse_accepted_wave4_zabbix_initial_validation_worker",
    "source_list_and_detail_read_through_bff",
    "validation_operation_status_read",
    "controlled_validation_failure_retry_and_reconciliation_presentation",
    "monitoring_source_onboarding_browser_e2e",
    "cross_tenant_and_stale_authority_fail_closed",
}
EXPECTED_INVARIANTS = {
    "current_platform_authorization_precedes_monitoring_use_case",
    "client_tenant_id_not_tenant_authority",
    "provider_identity_not_platform_identity",
    "provider_native_id_not_canonical_identity",
    "credential_binding_reference_not_secret_bytes",
    "provider_payload_not_tenant_authority",
    "no_dns_or_provider_network_call_inside_source_configuration_transaction",
    "source_create_success_not_provider_reachability_proof",
    "stale_generation_or_revision_evidence_cannot_update_current_source_state",
    "provider_failure_not_resource_absence",
    "idempotency_not_authorization",
    "shared_wave4_substrate_reused_not_reimplemented",
}
EXPECTED_EXCLUSIONS = {
    "monitoring_source_instance_replacement_candidate_or_cutover_product_flow",
    "host_or_resource_inventory_ingestion_product_flow",
    "resource_inventory_ui",
    "metric_definition_or_metric_value_product_surface",
    "metric_history_product_surface",
    "problem_or_health_product_surface",
    "monitoring_to_alerting_transport_changes",
    "alert_creation_or_alert_policy_evaluation",
    "ack_notification_escalation",
    "itsm_product_vertical",
    "automation_product_vertical",
    "aiops_product_vertical",
    "finops_product_vertical",
    "commercial_product_vertical",
    "production_deployment",
    "production_c3_numerics",
    "concrete_secret_manager_selection",
    "concrete_egress_transport_selection",
    "provider_native_authorization_truth",
    "raw_provider_credentials_in_browser_api_database_or_logs",
    "shared_monitoring_substrate_modification_without_successor_authorization",
}
AUTH_PR_ALLOWED_PATHS = {
    ".github/workflows/g2-monitoring-source-onboarding-authorization.yml",
    ".github/workflows/g2-monitoring-source-onboarding-implementation-scope.yml",
    "governance/adversarial/learning-ledger.d/pr-154-g2-authorization-review-findings.json",
    "implementation/g2-monitoring-source-onboarding-authorization/AUTHORIZATION.md",
    "implementation/g2-monitoring-source-onboarding-authorization/AUTHORIZATION_MANIFEST.json",
    "implementation/g2-monitoring-source-onboarding-authorization/TASK_PACKET.md",
    "tools/assurance/validate_g2_monitoring_source_onboarding_authorization.py",
    "tools/assurance/test_validate_g2_monitoring_source_onboarding_authorization.py",
    "tools/assurance/validate_g2_monitoring_source_onboarding_implementation_scope.py",
    "tools/assurance/test_validate_g2_monitoring_source_onboarding_implementation_scope.py",
    "tools/assurance/validate_g2_monitoring_source_onboarding_scope_readiness.py",
    "tools/assurance/test_validate_g2_monitoring_source_onboarding_scope_readiness.py",
    "tools/assurance/test_validate_g2_monitoring_source_onboarding_review_guardrails.py",
    "tools/assurance/validate_repository.py",
}


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def load_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("authorization manifest must be a JSON object")
    return value


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    exact = {
        "schema_version": 1,
        "authorization_id": AUTH_ID,
        "canonical_base_main_commit": BASE_SHA,
        "authorization_state": "proposed_exact_scope_authorization",
        "effective_rule": "becomes_canonical_only_after_exact_head_review_and_separately_authorized_merge",
        "canonical_effect_after_merge": "authorized_to_implement_exact_g2_monitoring_source_onboarding_only",
        "implementation_authority_before_merge": "blocked",
        "implementation_authority_after_merge": "granted_for_exact_g2_monitoring_source_onboarding_only",
        "authorized_program_gate": "G2",
        "merge_authorization": "not_granted",
        "production_authority": "none",
        "c3_production_state": "open",
        "frontend_authority": "g2_monitoring_source_onboarding_only",
    }
    for key, expected in exact.items():
        require(manifest.get(key) == expected, f"{key} drift", errors)
    require(manifest.get("authorized_slice") == {"slice_id": SLICE_ID, "capability": "monitoring_source_initial_onboarding_validation_and_status"}, "authorized slice drift", errors)
    require(set(manifest.get("authorized_capability_scope", [])) == EXPECTED_CAPABILITIES, "authorized capability scope drift", errors)
    require(set(manifest.get("required_invariants", [])) == EXPECTED_INVARIANTS, "required invariant set drift", errors)
    require(set(manifest.get("explicitly_not_authorized", [])) == EXPECTED_EXCLUSIONS, "explicit exclusion set drift", errors)
    require(set(manifest.get("depends_on", [])) == {"g1.identity-tenant-protected-shell@1", "wave4.monitoring-zabbix.vertical@1", "wave4.zabbix-initial-validation-worker@1"}, "dependency set drift", errors)

    policy = manifest.get("implementation_path_policy")
    require(isinstance(policy, dict), "implementation_path_policy missing", errors)
    if isinstance(policy, dict):
        exact_policy = {
            "mode": "exact_prefix_allowlist",
            "shared_existing_paths_policy": "read_only_unless_separate_successor_authorization",
            "implementation_pr_head_prefix": "impl/g2-monitoring-source-onboarding",
            "implementation_pr_required_label": "jlmirror-slice:g2-monitoring-source-onboarding",
            "implementation_claim_path": "implementation/g2-monitoring-source-onboarding/IMPLEMENTATION_CLAIM.json",
            "implementation_claim_authorization_id": AUTH_ID,
            "implementation_pr_base_ref_policy": "must_equal_repository_default_branch",
            "diff_enforcement_rule": "every_changed_path_must_match_canonical_base_policy",
            "diff_policy_source": "pull_request_exact_base_commit",
            "semantic_guard_rule": EXPECTED_SEMANTIC_RULE,
            "diff_enforcement_validator": "tools/assurance/validate_g2_monitoring_source_onboarding_implementation_scope.py",
            "trusted_scope_readiness_validator": "tools/assurance/validate_g2_monitoring_source_onboarding_scope_readiness.py",
            "diff_enforcement_workflow": ".github/workflows/g2-monitoring-source-onboarding-implementation-scope.yml",
            "trusted_evaluator_event": "issue_comment",
            "trusted_scope_attestation_command": "/jlmirror-g2-scope-attest",
            "trusted_scope_readiness_command": "/jlmirror-g2-scope-ready",
            "trusted_evaluator_source": "default_branch_issue_comment_workflow_plus_exact_default_branch_base_git_object",
            "trusted_scope_status_context": "JLMIRROR / g2-monitoring-source-onboarding-implementation-scope",
            "trusted_scope_readiness_status_context": "JLMIRROR / g2-monitoring-source-onboarding-merge-readiness",
            "trusted_scope_status_publication": "pending_then_final_coordinate_bound_evidence_on_resolved_pr_head",
            "trusted_scope_status_evidence_role": "evidence_only_not_standalone_merge_authority",
            "trusted_scope_freshness_rule": "merge_readiness_revalidates_live_head_base_default_tip_label_and_trusted_status_run_provenance",
            "trusted_scope_concurrency_rule": "per_pr_cancel_in_progress",
            "trusted_scope_merge_preflight_rule": "live_revalidate_ready_evidence_current_coordinates_label_and_workflow_run_immediately_before_merge",
            "candidate_controlled_relevance_inference": "forbidden",
        }
        for key, expected in exact_policy.items():
            require(policy.get(key) == expected, f"implementation policy field drift: {key}", errors)
        require(policy.get("trusted_status_creator_login") == "github-actions[bot]", "trusted status creator login drift", errors)
        require(policy.get("trusted_status_creator_id") == 41898282, "trusted status creator id drift", errors)
        require(policy.get("same_repository_required") is True, "same repository requirement drift", errors)
        require(policy.get("implementation_pr_must_validate_diff_against_this_policy") is True, "implementation diff validation requirement drift", errors)
        require(policy.get("implementation_pr_requires_trusted_scope_attestation_on_exact_head") is True, "scope attestation requirement drift", errors)
        require(policy.get("implementation_pr_requires_trusted_scope_readiness_on_exact_head_base") is True, "scope readiness requirement drift", errors)
        require(policy.get("allowed_prefixes") == EXPECTED_PREFIXES, "allowed prefix order/content drift", errors)
        require(policy.get("allowed_exact_paths") == EXPECTED_EXACT, "allowed exact path drift", errors)
        require(policy.get("forbidden_path_tokens") == EXPECTED_FORBIDDEN_PATH_TOKENS, "forbidden path token drift", errors)
        require(policy.get("forbidden_code_markers") == EXPECTED_FORBIDDEN_CODE_MARKERS, "forbidden code marker drift", errors)
        require(policy.get("semantic_scan_prefixes") == EXPECTED_SEMANTIC_SCAN_PREFIXES, "semantic scan prefix drift", errors)

    authority_paths = manifest.get("authority_source_paths")
    require(isinstance(authority_paths, list) and bool(authority_paths), "authority source paths missing", errors)
    if isinstance(authority_paths, list):
        for rel in authority_paths:
            require(isinstance(rel, str) and (ROOT / rel).exists(), f"authority source path missing: {rel}", errors)
    return errors


def validate_docs() -> list[str]:
    errors: list[str] = []
    auth = AUTHORIZATION.read_text(encoding="utf-8").lower()
    task = TASK_PACKET.read_text(encoding="utf-8").lower()
    for marker in (
        AUTH_ID,
        "implementation_authority_before_merge = blocked",
        "implementation_authority_after_merge = granted_for_exact_g2_monitoring_source_onboarding_only",
        "ready_for_merge != authorized_to_merge",
        "wave4.zabbix-initial-validation-worker@1",
        "no g2 sql namespace and no g2 domain-source namespace",
    ):
        require(marker.lower() in auth, f"AUTHORIZATION.md missing marker: {marker}", errors)
    for marker in (
        "slice: `g2.monitoring-source-onboarding@1`",
        "stop conditions",
        "implementation claim",
        "provider failure/omission cannot create resource-absence truth",
        "/jlmirror-g2-scope-attest",
        "/jlmirror-g2-scope-ready",
        "ready_for_merge != authorized_to_merge",
        "there is intentionally no `sql/g2/` or `src/jlmirror_g2/` authority",
    ):
        require(marker.lower() in task, f"TASK_PACKET.md missing marker: {marker}", errors)
    return errors


def _job_block(text: str, name: str) -> str | None:
    marker = "\njobs:\n"
    if marker not in text:
        return None
    lines = text.split(marker, 1)[1].splitlines()
    start = next((i for i, line in enumerate(lines) if line == f"  {name}:"), None)
    if start is None:
        return None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.fullmatch(r"  [A-Za-z0-9_-]+:\s*", lines[i]):
            end = i
            break
    return "\n".join(lines[start:end])


def _logical_shell_commands(text: str) -> list[str]:
    commands: list[str] = []
    current = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        current = f"{current} {line}".strip() if current else line
        if current.endswith("\\"):
            current = current[:-1].rstrip()
            continue
        commands.append(current)
        current = ""
    if current:
        commands.append(current)
    return commands


def _run_script_bodies(job_block: str) -> list[str]:
    lines = job_block.splitlines()
    scripts: list[str] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        if raw.strip() != "run: |":
            i += 1
            continue
        base_indent = len(raw) - len(raw.lstrip())
        i += 1
        body: list[str] = []
        while i < len(lines):
            line = lines[i]
            if line.strip() and len(line) - len(line.lstrip()) <= base_indent:
                break
            body.append(line)
            i += 1
        scripts.append("\n".join(body))
    return scripts


def _trusted_invocation_script(job_block: str, marker: str) -> str | None:
    matches = [script for script in _run_script_bodies(job_block) if marker in script]
    return matches[0] if len(matches) == 1 else None


def _script_has_control_flow(script: str) -> bool:
    active = [line.strip() for line in script.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    control = re.compile(r"^(?:if\b|then\b|fi\b|elif\b|else\b|for\b|while\b|until\b|case\b|esac\b|select\b|function\b|\{\s*$|\}\s*$)")
    return any(control.search(line) for line in active)


def validate_scope_workflow_text(text: str) -> list[str]:
    errors: list[str] = []
    require(re.search(r"^on:\s*$\n\s{2}issue_comment:\s*$\n\s{4}types:\s*\[created\]\s*$", text, re.MULTILINE) is not None, "scope workflow trigger structure drift", errors)
    require(re.search(r"^permissions:\s*\{\}\s*$", text, re.MULTILINE) is not None, "scope workflow must default to zero permissions", errors)
    require("pull_request_target" not in text and "workflow_dispatch:" not in text and "\n  push:\n" not in text, "scope workflow forbidden trigger drift", errors)
    require(text.count("statuses: write") == 2, "scope workflow must contain exactly two statuses: write grants", errors)
    require(text.count("uses: actions/checkout@") == 1, "scope workflow must checkout exactly once", errors)
    jobs = text.split("\njobs:\n", 1)[1] if "\njobs:\n" in text else ""
    require(re.findall(r"^  ([A-Za-z0-9_-]+):\s*$", jobs, re.MULTILINE) == ["resolve", "publish-pending", "analyze", "verify-ready", "publish-final"], "scope workflow job structure drift", errors)

    resolve = _job_block(text, "resolve") or ""
    resolve_cmds = _logical_shell_commands(resolve)
    for command in (
        'test "$PR_BASE_REF" = "$DEFAULT_BRANCH"',
        'test "$PR_BASE_REPO" = "$GITHUB_REPOSITORY"',
        'test "$PR_HEAD_REPO" = "$GITHUB_REPOSITORY"',
        'test "$PR_BASE_SHA" = "$DEFAULT_BRANCH_SHA"',
    ):
        require(command in resolve_cmds, f"resolve job missing executable authority check: {command}", errors)
    require("G2_REQUIRED_LABEL" in resolve and "G2_REQUIRED_HEAD_PREFIX" in resolve, "resolve job missing canonical label/head checks", errors)

    analyze = _job_block(text, "analyze") or ""
    analyze_cmds = _logical_shell_commands(analyze)
    require('git show "${PR_BASE_SHA}:${G2_SCOPE_VALIDATOR}" > "$trusted_validator"' in analyze_cmds, "analyze job missing executable exact-base validator materialization", errors)
    require('test "$(git rev-parse HEAD)" != "$PR_HEAD_SHA"' in analyze_cmds, "analyze job missing candidate-not-checkout proof", errors)
    scope_script = _trusted_invocation_script(analyze, 'python3 "$TRUSTED_VALIDATOR"')
    require(scope_script is not None, "analyze job missing unique trusted validator run script", errors)
    if scope_script is not None:
        require(not _script_has_control_flow(scope_script), "trusted validator invocation must be control-flow-free and unconditionally reachable", errors)
        scope_cmds = _logical_shell_commands(scope_script)
        expected_scope_command = 'python3 "$TRUSTED_VALIDATOR" --repo-root "$GITHUB_WORKSPACE" --base "$PR_BASE_SHA" --head "$PR_HEAD_SHA" --head-ref "$PR_HEAD_REF" --labels-json "$PR_LABELS_JSON" --head-repo "$PR_HEAD_REPO" --base-repo "$PR_BASE_REPO"'
        scope_invocations = [cmd for cmd in scope_cmds if cmd.startswith('python3 "$TRUSTED_VALIDATOR"')]
        require(scope_invocations == [expected_scope_command], "trusted validator invocation must match exact canonical command without status suppression", errors)
    require("statuses: write" not in analyze, "analyze job must remain read-only", errors)

    ready = _job_block(text, "verify-ready") or ""
    require("contents/${G2_READINESS_VALIDATOR}?ref=${PR_BASE_SHA}" in ready, "verify-ready job missing exact-base readiness materialization", errors)
    ready_script = _trusted_invocation_script(ready, 'python3 "$TRUSTED_READINESS_VALIDATOR"')
    require(ready_script is not None, "verify-ready job missing unique readiness run script", errors)
    if ready_script is not None:
        require(not _script_has_control_flow(ready_script), "trusted readiness invocation must be control-flow-free and unconditionally reachable", errors)
        ready_cmds = _logical_shell_commands(ready_script)
        expected_ready_command = 'python3 "$TRUSTED_READINESS_VALIDATOR" --repo "$GITHUB_REPOSITORY" --pr-number "$PR_NUMBER" --server-url "$GITHUB_SERVER_URL"'
        ready_invocations = [cmd for cmd in ready_cmds if cmd.startswith('python3 "$TRUSTED_READINESS_VALIDATOR"')]
        require(ready_invocations == [expected_ready_command], "trusted readiness invocation must match exact canonical command without status suppression", errors)
    require("statuses: write" not in ready, "verify-ready job must remain read-only", errors)

    final = _job_block(text, "publish-final") or ""
    raw = final.splitlines()
    pos_failure = [i for i, line in enumerate(raw) if line.strip() == "state=failure"]
    pos_if = [i for i, line in enumerate(raw) if line.strip().startswith('if [[ "$result" == \'success\'')]
    pos_success = [i for i, line in enumerate(raw) if line.strip() == "state=success"]
    pos_test = [i for i, line in enumerate(raw) if line.strip() == 'test "$state" = success']
    require(len(pos_failure) == len(pos_if) == len(pos_success) == len(pos_test) == 1, "publish-final fail-closed control-flow cardinality drift", errors)
    if pos_failure and pos_if and pos_success and pos_test:
        require(pos_failure[0] < pos_if[0] < pos_success[0] < pos_test[0], "publish-final fail-closed control-flow order drift", errors)
    result_assignments = [(i, line.strip()) for i, line in enumerate(raw) if re.match(r"^\s*result=", line)]
    expected_result_assignments = {'result="$ANALYZE_RESULT"', 'result="$READY_RESULT"'}
    require(len(result_assignments) == 2 and {value for _, value in result_assignments} == expected_result_assignments, "publish-final result assignment authority drift", errors)
    if pos_failure and result_assignments:
        require(all(i < pos_failure[0] for i, _ in result_assignments), "publish-final result may not be overwritten after fail-closed state initialization", errors)
    active = "\n".join(line for line in raw if not line.lstrip().startswith("#"))
    for marker in (
        "CURRENT_DEFAULT_BRANCH", "CURRENT_HEAD_SHA", "CURRENT_HEAD_REF", "CURRENT_BASE_SHA", "CURRENT_BASE_REF",
        "CURRENT_DEFAULT_SHA", "CURRENT_LABELS_JSON", 'jq -e --arg required "$G2_REQUIRED_LABEL"',
        "G2 scope PASS base=${PR_BASE_SHA} head=${PR_HEAD_SHA}", "G2 ready PASS base=${PR_BASE_SHA} head=${PR_HEAD_SHA}",
    ):
        require(marker in active, f"publish-final missing active live-authority marker: {marker}", errors)
    return errors


def validate_scope_workflow() -> list[str]:
    return validate_scope_workflow_text(SCOPE_WORKFLOW.read_text(encoding="utf-8"))


def validate_changed_paths() -> list[str]:
    try:
        out = subprocess.check_output(["git", "-C", str(ROOT), "diff", "--name-only", "--no-renames", f"{BASE_SHA}...HEAD"], text=True)
    except subprocess.CalledProcessError as exc:
        return [f"unable to enumerate exact authorization diff: {exc}"]
    paths = [line for line in out.splitlines() if line]
    errors = [] if paths else ["authorization PR has no changed paths"]
    errors.extend(f"unauthorized G2 authorization PR path: {path}" for path in paths if path not in AUTH_PR_ALLOWED_PATHS)
    return errors


def validate() -> list[str]:
    required = (MANIFEST, AUTHORIZATION, TASK_PACKET, SCOPE_VALIDATOR, READINESS_VALIDATOR, SCOPE_WORKFLOW, REPOSITORY_VALIDATOR, REVIEW_GUARDRAILS, LEARNING_LEDGER)
    errors = [f"required authorization artifact missing: {path.relative_to(ROOT)}" for path in required if not path.exists()]
    if errors:
        return errors
    try:
        manifest = load_manifest()
    except (json.JSONDecodeError, AssertionError) as exc:
        return [f"manifest parse error: {exc}"]
    errors.extend(validate_manifest(manifest))
    errors.extend(validate_docs())
    errors.extend(validate_scope_workflow())
    errors.extend(validate_changed_paths())
    return errors


def main() -> int:
    errors = validate()
    for error in errors:
        print(f"G2_AUTHORIZATION_ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print("g2_authorization=PASS exact_scope=monitoring-source-onboarding path+semantic-scope=guarded workflow=canonical-command+reachability-validated review-findings=internalized merge_authorization=not-granted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
