#!/usr/bin/env python3
from __future__ import annotations

import json
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

BASE_SHA = "8e26b05596aeca2e45578908ca4afc4f1fa175d6"
AUTH_ID = "g2.monitoring-source-onboarding@1"
SLICE_ID = AUTH_ID
EXPECTED_PREFIXES = [
    "apps/g2-monitoring-source-onboarding/",
    "contracts/g2-monitoring-source-onboarding/",
    "implementation/g2-monitoring-source-onboarding/",
    "sql/g2/",
    "src/jlmirror_g2/",
    "tests/g2/",
    "tools/g2/",
]
EXPECTED_EXACT = [".github/workflows/g2-monitoring-source-onboarding-runtime.yml"]
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
    "implementation/g2-monitoring-source-onboarding-authorization/AUTHORIZATION.md",
    "implementation/g2-monitoring-source-onboarding-authorization/AUTHORIZATION_MANIFEST.json",
    "implementation/g2-monitoring-source-onboarding-authorization/TASK_PACKET.md",
    "tools/assurance/validate_g2_monitoring_source_onboarding_authorization.py",
    "tools/assurance/test_validate_g2_monitoring_source_onboarding_authorization.py",
    "tools/assurance/validate_g2_monitoring_source_onboarding_implementation_scope.py",
    "tools/assurance/test_validate_g2_monitoring_source_onboarding_implementation_scope.py",
    "tools/assurance/validate_g2_monitoring_source_onboarding_scope_readiness.py",
    "tools/assurance/test_validate_g2_monitoring_source_onboarding_scope_readiness.py",
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
    require(manifest.get("schema_version") == 1, "schema_version drift", errors)
    require(manifest.get("authorization_id") == AUTH_ID, "authorization_id drift", errors)
    require(manifest.get("canonical_base_main_commit") == BASE_SHA, "canonical base drift", errors)
    require(manifest.get("authorization_state") == "proposed_exact_scope_authorization", "authorization_state drift", errors)
    require(manifest.get("effective_rule") == "becomes_canonical_only_after_exact_head_review_and_separately_authorized_merge", "effective_rule drift", errors)
    require(manifest.get("canonical_effect_after_merge") == "authorized_to_implement_exact_g2_monitoring_source_onboarding_only", "canonical effect drift", errors)
    require(manifest.get("implementation_authority_before_merge") == "blocked", "pre-merge implementation authority drift", errors)
    require(manifest.get("implementation_authority_after_merge") == "granted_for_exact_g2_monitoring_source_onboarding_only", "post-merge implementation authority drift", errors)
    require(manifest.get("authorized_program_gate") == "G2", "authorized program gate drift", errors)
    slice_data = manifest.get("authorized_slice") or {}
    require(slice_data.get("slice_id") == SLICE_ID, "slice id drift", errors)
    require(slice_data.get("capability") == "monitoring_source_initial_onboarding_validation_and_status", "slice capability drift", errors)
    require(manifest.get("merge_authorization") == "not_granted", "merge authorization must remain not_granted", errors)
    require(manifest.get("production_authority") == "none", "production authority drift", errors)
    require(manifest.get("c3_production_state") == "open", "C3 production state drift", errors)
    require(manifest.get("frontend_authority") == "g2_monitoring_source_onboarding_only", "frontend authority drift", errors)
    require(set(manifest.get("authorized_capability_scope", [])) == EXPECTED_CAPABILITIES, "authorized capability scope drift", errors)
    require(set(manifest.get("required_invariants", [])) == EXPECTED_INVARIANTS, "required invariant set drift", errors)
    require(set(manifest.get("explicitly_not_authorized", [])) == EXPECTED_EXCLUSIONS, "explicit exclusion set drift", errors)

    dependencies = set(manifest.get("depends_on", []))
    require(dependencies == {"g1.identity-tenant-protected-shell@1", "wave4.monitoring-zabbix.vertical@1", "wave4.zabbix-initial-validation-worker@1"}, "dependency set drift", errors)

    policy = manifest.get("implementation_path_policy")
    require(isinstance(policy, dict), "implementation_path_policy missing", errors)
    if isinstance(policy, dict):
        checks = {
            "mode": "exact_prefix_allowlist",
            "shared_existing_paths_policy": "read_only_unless_separate_successor_authorization",
            "implementation_pr_head_prefix": "impl/g2-monitoring-source-onboarding",
            "implementation_pr_required_label": "jlmirror-slice:g2-monitoring-source-onboarding",
            "implementation_claim_path": "implementation/g2-monitoring-source-onboarding/IMPLEMENTATION_CLAIM.json",
            "implementation_claim_authorization_id": AUTH_ID,
            "implementation_pr_base_ref_policy": "must_equal_repository_default_branch",
            "diff_enforcement_rule": "every_changed_path_must_match_canonical_base_policy",
            "diff_policy_source": "pull_request_exact_base_commit",
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
        for key, expected in checks.items():
            require(policy.get(key) == expected, f"implementation policy field drift: {key}", errors)
        require(policy.get("trusted_status_creator_login") == "github-actions[bot]", "trusted status creator login drift", errors)
        require(policy.get("trusted_status_creator_id") == 41898282, "trusted status creator id drift", errors)
        require(policy.get("same_repository_required") is True, "same repository requirement drift", errors)
        require(policy.get("implementation_pr_must_validate_diff_against_this_policy") is True, "implementation diff validation requirement drift", errors)
        require(policy.get("implementation_pr_requires_trusted_scope_attestation_on_exact_head") is True, "scope attestation requirement drift", errors)
        require(policy.get("implementation_pr_requires_trusted_scope_readiness_on_exact_head_base") is True, "scope readiness requirement drift", errors)
        require(policy.get("allowed_prefixes") == EXPECTED_PREFIXES, "allowed prefix order/content drift", errors)
        require(policy.get("allowed_exact_paths") == EXPECTED_EXACT, "allowed exact path drift", errors)

    authority_paths = manifest.get("authority_source_paths")
    require(isinstance(authority_paths, list) and authority_paths, "authority source paths missing", errors)
    if isinstance(authority_paths, list):
        for rel in authority_paths:
            require(isinstance(rel, str) and (ROOT / rel).exists(), f"authority source path missing: {rel}", errors)
    return errors


def validate_docs() -> list[str]:
    errors: list[str] = []
    auth = AUTHORIZATION.read_text(encoding="utf-8")
    task = TASK_PACKET.read_text(encoding="utf-8")
    for marker in (
        AUTH_ID,
        "implementation_authority_before_merge = blocked",
        "implementation_authority_after_merge = granted_for_exact_g2_monitoring_source_onboarding_only",
        "READY_FOR_MERGE != AUTHORIZED_TO_MERGE",
        "shared existing paths are read-only",
        "wave4.zabbix-initial-validation-worker@1",
    ):
        require(marker.lower() in auth.lower(), f"AUTHORIZATION.md missing marker: {marker}", errors)
    for marker in (
        "SLICE: `g2.monitoring-source-onboarding@1`",
        "STOP CONDITIONS",
        "IMPLEMENTATION CLAIM",
        "provider failure/omission cannot create resource-absence truth",
        "/jlmirror-g2-scope-attest",
        "/jlmirror-g2-scope-ready",
        "READY_FOR_MERGE != AUTHORIZED_TO_MERGE",
    ):
        require(marker.lower() in task.lower(), f"TASK_PACKET.md missing marker: {marker}", errors)
    return errors


def validate_scope_workflow() -> list[str]:
    errors: list[str] = []
    text = SCOPE_WORKFLOW.read_text(encoding="utf-8")
    markers = (
        "name: JLMIRROR G2 Monitoring Source Onboarding Implementation Scope",
        "issue_comment:",
        "permissions: {}",
        "cancel-in-progress: true",
        "/jlmirror-g2-scope-attest",
        "/jlmirror-g2-scope-ready",
        "G2_REQUIRED_LABEL",
        "G2_REQUIRED_HEAD_PREFIX",
        'test "$PR_BASE_REF" = "$DEFAULT_BRANCH"',
        'test "$PR_BASE_SHA" = "$DEFAULT_BRANCH_SHA"',
        'git show "${PR_BASE_SHA}:${G2_SCOPE_VALIDATOR}" > "$trusted_validator"',
        "contents/${G2_READINESS_VALIDATOR}?ref=${PR_BASE_SHA}",
        "JLMIRROR / g2-monitoring-source-onboarding-implementation-scope",
        "JLMIRROR / g2-monitoring-source-onboarding-merge-readiness",
        "G2 scope PASS base=${PR_BASE_SHA} head=${PR_HEAD_SHA}",
        "G2 ready PASS base=${PR_BASE_SHA} head=${PR_HEAD_SHA}",
    )
    for marker in markers:
        require(marker in text, f"scope workflow missing marker: {marker}", errors)
    require("pull_request_target" not in text, "scope workflow must not use pull_request_target", errors)
    require("workflow_dispatch:" not in text, "scope workflow must not use workflow_dispatch", errors)
    require("\n  push:\n" not in text, "scope workflow must not depend on push invalidation", errors)
    require(text.count("statuses: write") == 2, "scope workflow must contain exactly two statuses: write grants", errors)
    require(text.count("uses: actions/checkout@") == 1, "scope workflow must checkout exactly once", errors)
    return errors


def changed_paths() -> list[str]:
    out = subprocess.check_output(
        ["git", "-C", str(ROOT), "diff", "--name-only", "--no-renames", f"{BASE_SHA}...HEAD"],
        text=True,
    )
    return [line for line in out.splitlines() if line]


def validate_changed_paths() -> list[str]:
    errors: list[str] = []
    try:
        paths = changed_paths()
    except subprocess.CalledProcessError as exc:
        return [f"unable to enumerate exact authorization diff: {exc}"]
    if not paths:
        errors.append("authorization PR has no changed paths")
    for path in paths:
        if path not in AUTH_PR_ALLOWED_PATHS:
            errors.append(f"unauthorized G2 authorization PR path: {path}")
    return errors


def validate() -> list[str]:
    errors: list[str] = []
    for required in (MANIFEST, AUTHORIZATION, TASK_PACKET, SCOPE_VALIDATOR, READINESS_VALIDATOR, SCOPE_WORKFLOW, REPOSITORY_VALIDATOR):
        require(required.exists(), f"required authorization artifact missing: {required.relative_to(ROOT)}", errors)
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
    print("g2_authorization=PASS exact_scope=monitoring-source-onboarding implementation_authority=post-merge-only shared_monitoring=read-only merge_authorization=not-granted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
