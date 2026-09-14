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
ALLOWED_PATHS = {
    "implementation/g1-identity-tenant-shell-authorization/AUTHORIZATION.md",
    "implementation/g1-identity-tenant-shell-authorization/AUTHORIZATION_MANIFEST.json",
    "implementation/g1-identity-tenant-shell-authorization/TASK_PACKET.md",
    "tools/assurance/validate_g1_identity_tenant_shell_authorization.py",
    "tools/assurance/test_validate_g1_identity_tenant_shell_authorization.py",
    ".github/workflows/g1-identity-tenant-shell-authorization.yml",
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
    req(data.get("canonical_effect_after_merge") == "authorized_to_implement_exact_g1_identity_tenant_protected_shell_only", "canonical effect drift")
    req(data.get("authorized_program_gate") == "G1", "program gate drift")
    req(data.get("authorized_slice") == {"slice_id":"g1.identity-tenant-protected-shell@1","capability":"identity_tenant_protected_application_shell"}, "authorized slice drift")
    req(set(data.get("authorized_capability_scope", [])) == EXPECTED_SCOPE, "capability scope drift")
    req(set(data.get("required_invariants", [])) == EXPECTED_INVARIANTS, "required invariant drift")
    req(set(data.get("authorized_g0_bootstrap_scope", [])) == EXPECTED_BOOTSTRAP, "G0 bootstrap scope drift")
    req(data.get("frontend_authority") == "g1_protected_shell_only", "frontend authority escalation")
    req(data.get("production_authority") == "none", "production authority escalation")
    req(data.get("c3_production_state") == "open", "C3 production state escalation")
    req(data.get("merge_authorization") == "not_granted", "merge authority escalation")
    blocked = set(data.get("explicitly_not_authorized", []))
    for marker in (
        "g2_monitoring_source_onboarding",
        "monitoring_product_ui",
        "alert_creation_or_alert_policy_evaluation",
        "production_deployment",
        "provider_native_authorization_truth",
        "client_supplied_tenant_as_authorization_proof",
    ):
        req(marker in blocked, f"missing explicit exclusion: {marker}")


def validate_predecessor_truth() -> None:
    d3 = (ROOT / "docs/16-implementation-readiness/20-d3-identity-security-acceptance-propagation.md").read_text(encoding="utf-8")
    req("separately_accepted" in d3, "D3 acceptance missing")
    req("canonical_product_implementation_authority = not_granted" in d3, "historical D3 Product not-granted snapshot missing")
    roadmap = (ROOT / "docs/00-foundation/ai-e2e-delivery/PRODUCT-EXECUTION-ROADMAP.md").read_text(encoding="utf-8")
    req("### G1 — Identity + tenant + shell golden path" in roadmap, "G1 roadmap authority missing")
    day1 = (ROOT / "docs/00-foundation/ai-e2e-delivery/DAY-1-IMPLEMENTATION-BOOTSTRAP.md").read_text(encoding="utf-8")
    req("first full-stack target is **G1 Identity + tenant + protected application shell**" in day1, "G1 Day-1 target missing")


def validate_document() -> None:
    text = DOC.read_text(encoding="utf-8")
    packet = PACKET.read_text(encoding="utf-8")
    for marker in (
        "JWT_VALIDITY != CURRENT_AUTHORIZATION",
        "SUCCESSOR_G1_AUTHORIZATION != GLOBAL_PRODUCT_AUTHORITY",
        "G1_AUTHORIZED != G2_AUTHORIZED",
        "READY_FOR_MERGE != AUTHORIZED_TO_MERGE",
    ):
        req(marker in text, f"authorization document missing marker: {marker}")
    for marker in (
        "SLICE: g1.identity-tenant-protected-shell@1",
        "BASE SHA: " + BASE,
        "STOP IF:",
        "G2+",
    ):
        req(marker in packet, f"task packet missing marker: {marker}")


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
    print("g1_identity_tenant_shell_authorization=PASS gate=G1 product_scope=identity-tenant-protected-shell production=none merge_authority=not_granted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
