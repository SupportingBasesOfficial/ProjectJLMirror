#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "7c20c9301711e9a4bf355517d7aa23faad7a05b7"
MANIFEST = ROOT / "implementation/g1-identity-tenant-shell-authorization/AUTHORIZATION_MANIFEST.json"
DOC = ROOT / "implementation/g1-identity-tenant-shell-authorization/AUTHORIZATION.md"
PACKET = ROOT / "implementation/g1-identity-tenant-shell-authorization/TASK_PACKET.md"
LEARNING = "governance/adversarial/learning-ledger.d/pr-153-g1-authorization-review-findings.json"
LEARNING_RESOLVER = "tools/assurance/validate_adversarial_learning.py"
LEARNING_STRICT = "tools/assurance/validate_adversarial_learning_strict.py"
LEARNING_FALSIFIER = "tools/assurance/test_validate_adversarial_learning.py"
IMPLEMENTATION_SCOPE_VALIDATOR = "tools/assurance/validate_g1_identity_tenant_shell_implementation_scope.py"
IMPLEMENTATION_SCOPE_FALSIFIER = "tools/assurance/test_validate_g1_identity_tenant_shell_implementation_scope.py"
IMPLEMENTATION_SCOPE_WORKFLOW = ".github/workflows/g1-identity-tenant-shell-implementation-scope.yml"
EXPECTED_HEAD_PREFIX = "impl/g1-identity-tenant-protected-shell"
EXPECTED_LABEL = "jlmirror-slice:g1-identity-tenant-shell"
EXPECTED_CLAIM_PATH = "implementation/g1-identity-tenant-shell/IMPLEMENTATION_CLAIM.json"
EXPECTED_COMMAND = "/jlmirror-g1-scope-attest"
EXPECTED_STATUS_CONTEXT = "JLMIRROR / g1-identity-tenant-shell-implementation-scope"
EXPECTED_PREFIXES = {
    "apps/g1-identity-tenant-shell/", "contracts/g1-identity-tenant-shell/",
    "implementation/g1-identity-tenant-shell/", "sql/g1/", "src/jlmirror_g1/",
    "tests/g1/", "tools/g1/",
}
EXPECTED_EXACT = {".github/workflows/g1-identity-tenant-shell-runtime.yml"}
EXPECTED_SCOPE = {
    "oidc_authorization_code_pkce_s256_through_confidential_bff", "opaque_server_side_bff_session_capability",
    "current_platform_tenant_admission", "current_membership_and_permission_read_for_shell",
    "authenticated_bff_shell_route", "protected_application_shell", "forbidden_cross_tenant_browser_e2e",
    "stale_or_revoked_authority_fail_closed",
}
EXPECTED_INVARIANTS = {
    "jwt_validity_not_current_authorization", "idp_identity_not_platform_membership_authority",
    "workload_identity_not_tenant_business_authority", "network_presence_not_trust",
    "browser_session_handle_not_business_authority", "client_tenant_id_not_tenant_authority",
}
EXPECTED_BOOTSTRAP = {
    "g1_local_dependency_stack", "g1_database_bootstrap_or_migration_entrypoint",
    "g1_backend_bff_start_entrypoint", "g1_frontend_start_entrypoint",
    "g1_fixture_test_tenant_and_identity", "g1_exact_head_local_ci_parity_commands", "g1_container_runtime_proof",
}
EXPECTED_CONSUMED = {
    "accepted_wave1_identity_bff_current_authorization_substrate", "d3_identity_security_separately_accepted",
    "canonical_api_bff_security_contracts", "canonical_tenant_current_authority_rules",
    "ai_e2e_delivery_constitution", "product_execution_roadmap", "vertical_slice_delivery_model",
}
EXPECTED_AUTHORITY_PATHS = {
    "implementation/wave-1/AUTHORITY_BOUNDARY.md",
    "docs/16-implementation-readiness/20-d3-identity-security-acceptance-propagation.md",
    "docs/09-api-contracts/authentication-authorization-and-tenant-context.md",
    "docs/09-api-contracts/surface-routing-and-resource-identity.md",
    "docs/07-system-design/request-auth-and-authorization-lifecycle.md",
    "docs/00-foundation/ai-e2e-delivery/AI-E2E-DELIVERY-CONSTITUTION.md",
    "docs/00-foundation/ai-e2e-delivery/PRODUCT-EXECUTION-ROADMAP.md",
    "docs/00-foundation/ai-e2e-delivery/VERTICAL-SLICE-DELIVERY-MODEL.md",
    "docs/00-foundation/ai-e2e-delivery/DAY-1-IMPLEMENTATION-BOOTSTRAP.md",
}
EXPECTED_EXCLUSIONS = {
    "g2_monitoring_source_onboarding", "monitoring_product_ui", "resource_metric_problem_health_product_surfaces",
    "alert_creation_or_alert_policy_evaluation", "ack_notification_escalation", "itsm_product_vertical",
    "automation_product_vertical", "aiops_product_vertical", "finops_product_vertical", "commercial_product_vertical",
    "production_deployment", "production_c3_numerics", "provider_native_authorization_truth",
    "browser_refresh_token_or_long_lived_platform_access_credential", "client_supplied_tenant_as_authorization_proof",
    "speculative_generic_frontend_information_architecture",
}
ALLOWED_PATHS = {
    "implementation/g1-identity-tenant-shell-authorization/AUTHORIZATION.md",
    "implementation/g1-identity-tenant-shell-authorization/AUTHORIZATION_MANIFEST.json",
    "implementation/g1-identity-tenant-shell-authorization/TASK_PACKET.md",
    "tools/assurance/validate_g1_identity_tenant_shell_authorization.py",
    "tools/assurance/test_validate_g1_identity_tenant_shell_authorization.py",
    IMPLEMENTATION_SCOPE_VALIDATOR, IMPLEMENTATION_SCOPE_FALSIFIER, IMPLEMENTATION_SCOPE_WORKFLOW,
    LEARNING_RESOLVER, LEARNING_STRICT, LEARNING_FALSIFIER,
    "tools/assurance/validate_repository.py",
    ".github/workflows/g1-identity-tenant-shell-authorization.yml", LEARNING,
}


def req(condition: bool, message: str) -> None:
    if not condition: raise AssertionError(message)


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def load() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def validate_manifest(data: dict) -> None:
    req(type(data.get("schema_version")) is int and data["schema_version"] == 1, "schema_version drift")
    req(data.get("authorization_id") == "g1.identity-tenant-protected-shell@1", "authorization id drift")
    req(data.get("canonical_base_main_commit") == BASE, "canonical base drift")
    req(data.get("authorization_state") == "proposed_exact_scope_authorization", "authorization state drift")
    req(data.get("effective_rule") == "becomes_canonical_only_after_exact_head_review_and_separately_authorized_merge", "effective rule drift")
    req(data.get("canonical_effect_after_merge") == "authorized_to_implement_exact_g1_identity_tenant_protected_shell_only", "canonical effect drift")
    req(data.get("implementation_authority_before_merge") == "blocked", "pre-merge implementation authority drift")
    req(data.get("implementation_authority_after_merge") == "granted_for_exact_g1_identity_tenant_protected_shell_only", "post-merge implementation authority drift")
    req(data.get("authorized_program_gate") == "G1", "program gate drift")
    req(data.get("authorized_slice") == {"slice_id":"g1.identity-tenant-protected-shell@1","capability":"identity_tenant_protected_application_shell"}, "authorized slice drift")
    policy = data.get("implementation_path_policy"); req(isinstance(policy, dict), "implementation path policy missing")
    exact = {
        "mode": "exact_prefix_allowlist",
        "shared_existing_paths_policy": "read_only_unless_separate_successor_authorization",
        "implementation_pr_head_prefix": EXPECTED_HEAD_PREFIX,
        "implementation_pr_required_label": EXPECTED_LABEL,
        "implementation_claim_path": EXPECTED_CLAIM_PATH,
        "implementation_claim_authorization_id": "g1.identity-tenant-protected-shell@1",
        "same_repository_required": True,
        "implementation_pr_base_ref_policy": "must_equal_repository_default_branch",
        "diff_enforcement_rule": "every_changed_path_must_match_canonical_base_policy",
        "diff_policy_source": "pull_request_exact_base_commit",
        "trusted_evaluator_event": "issue_comment",
        "trusted_scope_attestation_command": EXPECTED_COMMAND,
        "trusted_evaluator_source": "default_branch_issue_comment_workflow_plus_exact_default_branch_base_git_object",
        "trusted_scope_status_context": EXPECTED_STATUS_CONTEXT,
        "trusted_scope_status_publication": "pending_then_final_on_resolved_pr_head",
        "trusted_scope_freshness_rule": "final_success_requires_unchanged_head_base_sha_and_default_branch_ref",
        "trusted_scope_concurrency_rule": "per_pr_cancel_in_progress",
        "diff_enforcement_validator": IMPLEMENTATION_SCOPE_VALIDATOR,
        "diff_enforcement_workflow": IMPLEMENTATION_SCOPE_WORKFLOW,
        "implementation_pr_must_validate_diff_against_this_policy": True,
        "implementation_pr_requires_trusted_scope_attestation_on_exact_head": True,
        "candidate_controlled_relevance_inference": "forbidden",
    }
    for key, expected in exact.items(): req(policy.get(key) == expected, f"implementation path policy drift: {key}")
    req(set(policy.get("allowed_prefixes", [])) == EXPECTED_PREFIXES, "implementation allowed prefix drift")
    req(set(policy.get("allowed_exact_paths", [])) == EXPECTED_EXACT, "implementation exact path drift")
    req(not any(key.startswith("bootstrap_authorization_") for key in policy), "implementation path policy must not contain reusable authorization bootstrap")
    req(set(data.get("authorized_capability_scope", [])) == EXPECTED_SCOPE, "capability scope drift")
    req(set(data.get("required_invariants", [])) == EXPECTED_INVARIANTS, "required invariant drift")
    req(set(data.get("authorized_g0_bootstrap_scope", [])) == EXPECTED_BOOTSTRAP, "G0 bootstrap scope drift")
    req(set(data.get("consumed_existing_authority", [])) == EXPECTED_CONSUMED, "consumed authority drift")
    req(set(data.get("authority_source_paths", [])) == EXPECTED_AUTHORITY_PATHS, "authority source corpus drift")
    req(set(data.get("explicitly_not_authorized", [])) == EXPECTED_EXCLUSIONS, "explicit exclusion drift")
    req(data.get("frontend_authority") == "g1_protected_shell_only", "frontend authority escalation")
    req(data.get("production_authority") == "none", "production authority escalation")
    req(data.get("c3_production_state") == "open", "C3 production state escalation")
    req(data.get("historical_authority_rule") == "earlier_not_granted_snapshots_remain_immutable_source_time_truth_and_are_not_rewritten_by_this_successor_g1_authorization", "historical authority rule drift")
    req(data.get("implementation_boundary_rule") == "canonical_g1_product_code_may_begin_only_after_this_exact_scope_authorization_becomes_canonical", "implementation boundary drift")
    req(data.get("merge_authorization") == "not_granted", "merge authority escalation")


def validate_predecessor_truth() -> None:
    for rel in EXPECTED_AUTHORITY_PATHS: req((ROOT / rel).is_file(), f"authority source missing: {rel}")
    wave1 = (ROOT / "implementation/wave-1/AUTHORITY_BOUNDARY.md").read_text(encoding="utf-8")
    req("`impl.identity-bff@1`" in wave1 and "SESSION VALID != CURRENT AUTHORITY" in wave1, "Wave 1 authority substrate drift")
    d3 = (ROOT / "docs/16-implementation-readiness/20-d3-identity-security-acceptance-propagation.md").read_text(encoding="utf-8")
    req("gate_state: per_track_conformed -> separately_accepted" in d3 and "canonical_product_implementation_authority = not_granted" in d3, "D3 predecessor truth drift")


def validate_enforcement_artifacts() -> None:
    for rel in (IMPLEMENTATION_SCOPE_VALIDATOR, IMPLEMENTATION_SCOPE_FALSIFIER, IMPLEMENTATION_SCOPE_WORKFLOW): req((ROOT / rel).is_file(), f"implementation scope enforcement artifact missing: {rel}")
    validator = (ROOT / IMPLEMENTATION_SCOPE_VALIDATOR).read_text(encoding="utf-8")
    workflow = (ROOT / IMPLEMENTATION_SCOPE_WORKFLOW).read_text(encoding="utf-8")
    for marker in ("policy_from_base(root, base_sha)", '"--no-renames"', "unauthorized G1 implementation path", "G1 implementation PR missing required canonical label", "G1 implementation PR missing required canonical head prefix", "G1 implementation PR missing or malformed required claim", "no candidate-controlled relevance inference"):
        req(marker in validator, f"implementation scope validator missing marker: {marker}")
    req("issue_comment:" in workflow, "implementation scope workflow must be default-branch issue_comment caller")
    req(EXPECTED_COMMAND in workflow, "implementation scope workflow missing canonical attestation command")
    req("pull_request_target:" not in workflow, "implementation scope workflow must not use privileged pull_request_target")
    req("pull_request:" not in workflow, "implementation scope workflow must not use candidate-controlled pull_request orchestration")
    req("permissions: {}" in workflow, "implementation scope workflow must default to zero workflow-level permissions")
    for job in ("  resolve:", "  publish-pending:", "  analyze:", "  publish-final:"):
        req(job in workflow, f"implementation scope workflow missing isolated job: {job.strip()}")
    req("group: g1-identity-tenant-shell-scope-${{ github.event.issue.number }}" in workflow and "cancel-in-progress: true" in workflow, "implementation scope workflow missing per-PR freshness concurrency")
    req("github.event.issue.number" in workflow, "implementation scope workflow missing trusted PR identity binding")
    req("repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}" in workflow, "implementation scope workflow must resolve PR coordinates through GitHub API")
    req('test "$PR_BASE_REF" = "$DEFAULT_BRANCH"' in workflow, "implementation scope workflow must require default-branch base ref")
    req('test "$PR_BASE_REPO" = "$GITHUB_REPOSITORY"' in workflow, "implementation scope workflow must require canonical base repository")
    req('git show "${PR_BASE_SHA}:${G1_SCOPE_VALIDATOR}" > "$trusted_validator"' in workflow, "implementation scope workflow must materialize validator from exact default-branch base Git object")
    req('python3 "$TRUSTED_VALIDATOR"' in workflow, "implementation scope workflow must execute materialized base validator")
    req("persist-credentials: false" in workflow, "implementation scope workflow must not persist checkout credentials")
    req('test "$(git rev-parse HEAD)" != "$PR_HEAD_SHA"' in workflow, "implementation scope workflow must not checkout candidate code")
    req(workflow.count("uses: actions/checkout@") == 1, "implementation scope workflow must checkout code only in isolated read-only analysis")
    req(workflow.count("statuses: write") == 2, "implementation scope workflow must isolate exactly two status publisher jobs")
    req(workflow.count('statuses/${PR_HEAD_SHA}') == 2, "implementation scope workflow must publish pending and final status to exact resolved PR head")
    req(EXPECTED_STATUS_CONTEXT in workflow, "implementation scope workflow missing stable exact-head status context")
    req("state=pending" in workflow, "implementation scope workflow missing exact-head pending status")
    for marker in ("CURRENT_HEAD_SHA", "CURRENT_BASE_SHA", "CURRENT_BASE_REF", 'test "$state" = success'):
        req(marker in workflow, f"implementation scope workflow missing final freshness guard: {marker}")
    req("bootstrap_authorization_" not in workflow and "G1_SCOPE_BOOTSTRAP" not in workflow, "implementation scope workflow must not contain authorization bootstrap")


def validate_document() -> None:
    text, packet = DOC.read_text(encoding="utf-8"), PACKET.read_text(encoding="utf-8")
    for marker in ("implementation_authority_before_merge = blocked", "implementation_authority_after_merge = granted_for_exact_g1_identity_tenant_protected_shell_only", "JWT_VALIDITY != CURRENT_AUTHORIZATION", "SUCCESSOR_G1_AUTHORIZATION != GLOBAL_PRODUCT_AUTHORITY", "G1_AUTHORIZED != G2_AUTHORIZED", "READY_FOR_MERGE != AUTHORIZED_TO_MERGE", "All existing shared paths", "read-only under this authorization", EXPECTED_LABEL, EXPECTED_CLAIM_PATH, EXPECTED_COMMAND, "issue_comment", EXPECTED_STATUS_CONTEXT, "default branch", "There is no candidate-controlled `relevance=not-g1` success path"):
        req(marker in text, f"authorization document missing marker: {marker}")
    for marker in ("SLICE: g1.identity-tenant-protected-shell@1", "BASE SHA: " + BASE, "No new identity or authorization semantics.", "Client tenant identifiers are never authority.", "SHARED EXISTING PATHS: read-only unless a separate successor authorization", EXPECTED_LABEL, EXPECTED_CLAIM_PATH, EXPECTED_COMMAND, "issue_comment workflow loaded from the default branch", EXPECTED_STATUS_CONTEXT, "STOP IF:", "G2+"):
        req(marker in packet, f"task packet missing marker: {marker}")
    for prefix in EXPECTED_PREFIXES: req(prefix in text and prefix in packet, f"implementation allowed prefix not rendered consistently: {prefix}")
    for path in EXPECTED_EXACT: req(path in text and path in packet, f"implementation exact path not rendered consistently: {path}")


def validate_changed_paths() -> None:
    changed = [p for p in git("diff", "--name-only", f"{BASE}...HEAD").splitlines() if p]
    req(changed, "authorization branch must contain an explicit delta")
    for path in changed: req(path in ALLOWED_PATHS, f"authorization PR touched forbidden path: {path}")


def validate() -> None:
    req(MANIFEST.is_file() and DOC.is_file() and PACKET.is_file(), "missing G1 authorization artifact")
    validate_manifest(load()); validate_predecessor_truth(); validate_enforcement_artifacts(); validate_document(); validate_changed_paths()


def main() -> int:
    try: validate()
    except AssertionError as exc:
        print(f"g1_identity_tenant_shell_authorization=FAIL reason={exc}", file=sys.stderr); return 1
    print("g1_identity_tenant_shell_authorization=PASS gate=G1 implementation_transition=blocked->exact-g1 implementation_paths=pinned trusted_scope=default-branch-issue-comment exact_head_status=pending+fresh-final default_base=required candidate_relevance=forbidden authority_corpus=pinned exclusions=exact production=none merge_authority=not_granted")
    return 0


if __name__ == "__main__": raise SystemExit(main())
