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

EXPECTED_SCOPE = {
    "oidc_authorization_code_pkce_s256_through_confidential_bff",
    "opaque_server_side_bff_session_capability",
    "current_platform_tenant_admission",
    "current_membership_and_permission_read_for_shell",
    "authenticated_bff_shell_route",
    "protected_application_shell",
    "forbidden_cross_tenant_browser_e2e",
    "stale_or_revoked_authority_fail_closed",
}
EXPECTED_INVARIANTS = {
    "jwt_validity_not_current_authorization",
    "idp_identity_not_platform_membership_authority",
    "workload_identity_not_tenant_business_authority",
    "network_presence_not_trust",
    "browser_session_handle_not_business_authority",
    "client_tenant_id_not_tenant_authority",
}
EXPECTED_BOOTSTRAP = {
    "g1_local_dependency_stack",
    "g1_database_bootstrap_or_migration_entrypoint",
    "g1_backend_bff_start_entrypoint",
    "g1_frontend_start_entrypoint",
    "g1_fixture_test_tenant_and_identity",
    "g1_exact_head_local_ci_parity_commands",
    "g1_container_runtime_proof",
}
EXPECTED_CONSUMED = {
    "accepted_wave1_identity_bff_current_authorization_substrate",
    "d3_identity_security_separately_accepted",
    "canonical_api_bff_security_contracts",
    "canonical_tenant_current_authority_rules",
    "ai_e2e_delivery_constitution",
    "product_execution_roadmap",
    "vertical_slice_delivery_model",
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
EXPECTED_IMPLEMENTATION_PREFIXES = {
    "apps/g1-identity-tenant-shell/",
    "contracts/g1-identity-tenant-shell/",
    "implementation/g1-identity-tenant-shell/",
    "sql/g1/",
    "src/jlmirror_g1/",
    "tests/g1/",
    "tools/g1/",
}
EXPECTED_IMPLEMENTATION_EXACT_PATHS = {
    ".github/workflows/g1-identity-tenant-shell-runtime.yml",
}
EXPECTED_EXCLUSIONS = {
    "g2_monitoring_source_onboarding",
    "monitoring_product_ui",
    "resource_metric_problem_health_product_surfaces",
    "alert_creation_or_alert_policy_evaluation",
    "ack_notification_escalation",
    "itsm_product_vertical",
    "automation_product_vertical",
    "aiops_product_vertical",
    "finops_product_vertical",
    "commercial_product_vertical",
    "production_deployment",
    "production_c3_numerics",
    "provider_native_authorization_truth",
    "browser_refresh_token_or_long_lived_platform_access_credential",
    "client_supplied_tenant_as_authorization_proof",
    "speculative_generic_frontend_information_architecture",
}
ALLOWED_PATHS = {
    "implementation/g1-identity-tenant-shell-authorization/AUTHORIZATION.md",
    "implementation/g1-identity-tenant-shell-authorization/AUTHORIZATION_MANIFEST.json",
    "implementation/g1-identity-tenant-shell-authorization/TASK_PACKET.md",
    "tools/assurance/validate_g1_identity_tenant_shell_authorization.py",
    "tools/assurance/test_validate_g1_identity_tenant_shell_authorization.py",
    LEARNING_RESOLVER,
    LEARNING_STRICT,
    LEARNING_FALSIFIER,
    ".github/workflows/g1-identity-tenant-shell-authorization.yml",
    LEARNING,
}


def req(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


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

    path_policy = data.get("implementation_path_policy")
    req(isinstance(path_policy, dict), "implementation path policy missing")
    req(path_policy.get("mode") == "exact_prefix_allowlist", "implementation path policy mode drift")
    req(set(path_policy.get("allowed_prefixes", [])) == EXPECTED_IMPLEMENTATION_PREFIXES, "implementation allowed prefix drift")
    req(set(path_policy.get("allowed_exact_paths", [])) == EXPECTED_IMPLEMENTATION_EXACT_PATHS, "implementation exact path drift")
    req(path_policy.get("shared_existing_paths_policy") == "read_only_unless_separate_successor_authorization", "shared existing path policy drift")
    req(path_policy.get("implementation_pr_must_validate_diff_against_this_policy") is True, "implementation PR path validation requirement drift")

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
    for relative in EXPECTED_AUTHORITY_PATHS:
        req((ROOT / relative).is_file(), f"authority source missing: {relative}")

    wave1 = (ROOT / "implementation/wave-1/AUTHORITY_BOUNDARY.md").read_text(encoding="utf-8")
    req("`impl.identity-bff@1`" in wave1, "Wave 1 identity/BFF substrate missing")
    req("SESSION VALID != CURRENT AUTHORITY" in wave1, "Wave 1 current-authority law missing")

    d3 = (ROOT / "docs/16-implementation-readiness/20-d3-identity-security-acceptance-propagation.md").read_text(encoding="utf-8")
    req("gate_state: per_track_conformed -> separately_accepted" in d3, "D3 separate acceptance transition missing")
    req("canonical_product_implementation_authority = not_granted" in d3, "historical D3 Product not-granted snapshot missing")

    auth = (ROOT / "docs/09-api-contracts/authentication-authorization-and-tenant-context.md").read_text(encoding="utf-8")
    req("A valid credential does not imply tenant access." in auth, "credential/tenant non-equivalence missing")
    req("Browser JavaScript SHALL NOT intentionally receive or persist long-lived platform access credentials or refresh credentials." in auth, "browser credential boundary missing")
    req("current membership / machine tenant scope" in auth, "current membership authority sequence missing")

    routing = (ROOT / "docs/09-api-contracts/surface-routing-and-resource-identity.md").read_text(encoding="utf-8")
    req("evaluate current membership or machine tenant scope" in routing, "surface current-authorization order missing")

    lifecycle = (ROOT / "docs/07-system-design/request-auth-and-authorization-lifecycle.md").read_text(encoding="utf-8")
    req("current authorization" in lifecycle, "request authorization lifecycle currentness missing")

    roadmap = (ROOT / "docs/00-foundation/ai-e2e-delivery/PRODUCT-EXECUTION-ROADMAP.md").read_text(encoding="utf-8")
    req("### G1 — Identity + tenant + shell golden path" in roadmap, "G1 roadmap authority missing")
    day1 = (ROOT / "docs/00-foundation/ai-e2e-delivery/DAY-1-IMPLEMENTATION-BOOTSTRAP.md").read_text(encoding="utf-8")
    req("first full-stack target is **G1 Identity + tenant + protected application shell**" in day1, "G1 Day-1 target missing")


def validate_document() -> None:
    text = DOC.read_text(encoding="utf-8")
    packet = PACKET.read_text(encoding="utf-8")
    for marker in (
        "implementation_authority_before_merge = blocked",
        "implementation_authority_after_merge = granted_for_exact_g1_identity_tenant_protected_shell_only",
        "JWT_VALIDITY != CURRENT_AUTHORIZATION",
        "SUCCESSOR_G1_AUTHORIZATION != GLOBAL_PRODUCT_AUTHORITY",
        "G1_AUTHORIZED != G2_AUTHORIZED",
        "READY_FOR_MERGE != AUTHORIZED_TO_MERGE",
        "All existing shared paths",
        "read-only under this authorization",
    ):
        req(marker in text, f"authorization document missing marker: {marker}")
    for marker in (
        "SLICE: g1.identity-tenant-protected-shell@1",
        "BASE SHA: " + BASE,
        "No new identity or authorization semantics.",
        "Client tenant identifiers are never authority.",
        "SHARED EXISTING PATHS: read-only unless a separate successor authorization",
        "STOP IF:",
        "G2+",
    ):
        req(marker in packet, f"task packet missing marker: {marker}")
    for prefix in EXPECTED_IMPLEMENTATION_PREFIXES:
        req(prefix in text and prefix in packet, f"implementation allowed prefix not rendered consistently: {prefix}")
    for exact_path in EXPECTED_IMPLEMENTATION_EXACT_PATHS:
        req(exact_path in text and exact_path in packet, f"implementation exact path not rendered consistently: {exact_path}")


def validate_changed_paths() -> None:
    changed = [p for p in git("diff", "--name-only", f"{BASE}...HEAD").splitlines() if p]
    req(changed, "authorization branch must contain an explicit delta")
    for path in changed:
        req(path in ALLOWED_PATHS, f"authorization PR touched forbidden path: {path}")


def validate() -> None:
    req(MANIFEST.is_file(), "missing authorization manifest")
    req(DOC.is_file(), "missing authorization document")
    req(PACKET.is_file(), "missing task packet")
    validate_manifest(load())
    validate_predecessor_truth()
    validate_document()
    validate_changed_paths()


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"g1_identity_tenant_shell_authorization=FAIL reason={exc}", file=sys.stderr)
        return 1
    print("g1_identity_tenant_shell_authorization=PASS gate=G1 implementation_transition=blocked->exact-g1 implementation_paths=pinned authority_corpus=pinned exclusions=exact production=none merge_authority=not_granted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
