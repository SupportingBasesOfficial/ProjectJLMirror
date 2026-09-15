from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "implementation/g2-monitoring-source-onboarding-authorization/AUTHORIZATION_MANIFEST.json"
AUTHORIZATION = ROOT / "implementation/g2-monitoring-source-onboarding-authorization/AUTHORIZATION.md"
TASK_PACKET = ROOT / "implementation/g2-monitoring-source-onboarding-authorization/TASK_PACKET.md"
SCOPE_WORKFLOW = ROOT / ".github/workflows/g2-monitoring-source-onboarding-implementation-scope.yml"
REPOSITORY_VALIDATOR = ROOT / "tools/assurance/validate_repository.py"
REVIEW_GUARDRAILS = ROOT / "tools/assurance/test_validate_g2_monitoring_source_onboarding_review_guardrails.py"
LEARNING_LEDGER = ROOT / "governance/adversarial/learning-ledger.d/pr-154-g2-authorization-review-findings.json"
BASE_SHA = "8e26b05596aeca2e45578908ca4afc4f1fa175d6"
AUTH_ID = "g2.monitoring-source-onboarding@1"
EXPECTED_SCOPE_WORKFLOW_BLOB = "f19ed6d94ffc63f3acffd773eaf9246217a80495"

_SCOPE_CORE_PATH = ROOT / "tools/assurance/g2_scope_core.py"
_spec = importlib.util.spec_from_file_location("jlmirror_g2_scope_core_for_auth", _SCOPE_CORE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("unable to load canonical G2 scope core")
_scope = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_scope)

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
    "governance/adversarial/learning-ledger.d/z-pr-154-g2-authorization-review-findings-032-037.json",
    "implementation/g2-monitoring-source-onboarding-authorization/AUTHORIZATION.md",
    "implementation/g2-monitoring-source-onboarding-authorization/AUTHORIZATION_MANIFEST.json",
    "implementation/g2-monitoring-source-onboarding-authorization/TASK_PACKET.md",
    "tools/assurance/g2_scope_core.py",
    "tools/assurance/g2_authorization_core.py",
    "tools/assurance/validate_g2_monitoring_source_onboarding_authorization.py",
    "tools/assurance/test_validate_g2_monitoring_source_onboarding_authorization.py",
    "tools/assurance/validate_g2_monitoring_source_onboarding_implementation_scope.py",
    "tools/assurance/test_validate_g2_monitoring_source_onboarding_implementation_scope.py",
    "tools/assurance/validate_g2_monitoring_source_onboarding_scope_readiness.py",
    "tools/assurance/test_validate_g2_monitoring_source_onboarding_scope_readiness.py",
    "tools/assurance/test_validate_g2_monitoring_source_onboarding_review_guardrails.py",
    "tools/assurance/validate_repository.py",
}


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
        if manifest.get(key) != expected:
            errors.append(f"{key} drift")
    if manifest.get("authorized_slice") != {"slice_id": AUTH_ID, "capability": "monitoring_source_initial_onboarding_validation_and_status"}:
        errors.append("authorized slice drift")
    if set(manifest.get("authorized_capability_scope", [])) != EXPECTED_CAPABILITIES:
        errors.append("authorized capability scope drift")
    if set(manifest.get("required_invariants", [])) != EXPECTED_INVARIANTS:
        errors.append("required invariant set drift")
    if set(manifest.get("explicitly_not_authorized", [])) != EXPECTED_EXCLUSIONS:
        errors.append("explicit exclusion set drift")
    policy = manifest.get("implementation_path_policy")
    if not isinstance(policy, dict):
        errors.append("implementation_path_policy missing")
    else:
        try:
            _scope.configured_policy(policy)
        except AssertionError as exc:
            errors.append(str(exc))
    return errors


def _git_blob_sha(text: str) -> str:
    raw = text.encode("utf-8")
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def validate_scope_workflow_text(text: str) -> list[str]:
    actual = _git_blob_sha(text)
    if actual != EXPECTED_SCOPE_WORKFLOW_BLOB:
        return [f"scope workflow canonical blob drift: expected {EXPECTED_SCOPE_WORKFLOW_BLOB}, got {actual}"]
    return []


def validate_docs() -> list[str]:
    errors: list[str] = []
    auth = AUTHORIZATION.read_text(encoding="utf-8").lower()
    task = TASK_PACKET.read_text(encoding="utf-8").lower()
    for marker in (AUTH_ID, "implementation_authority_before_merge = blocked", "ready_for_merge != authorized_to_merge", "wave4.zabbix-initial-validation-worker@1"):
        if marker.lower() not in auth:
            errors.append(f"AUTHORIZATION.md missing marker: {marker}")
    for marker in ("slice: `g2.monitoring-source-onboarding@1`", "stop conditions", "implementation claim", "/jlmirror-g2-scope-attest", "/jlmirror-g2-scope-ready", "ready_for_merge != authorized_to_merge"):
        if marker.lower() not in task:
            errors.append(f"TASK_PACKET.md missing marker: {marker}")
    return errors


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
    required = (MANIFEST, AUTHORIZATION, TASK_PACKET, SCOPE_WORKFLOW, REPOSITORY_VALIDATOR, REVIEW_GUARDRAILS, LEARNING_LEDGER, _SCOPE_CORE_PATH)
    errors = [f"required authorization artifact missing: {p.relative_to(ROOT)}" for p in required if not p.exists()]
    if errors:
        return errors
    try:
        manifest = load_manifest()
    except (json.JSONDecodeError, AssertionError) as exc:
        return [f"manifest parse error: {exc}"]
    errors.extend(validate_manifest(manifest))
    errors.extend(validate_docs())
    errors.extend(validate_scope_workflow_text(SCOPE_WORKFLOW.read_text(encoding="utf-8")))
    errors.extend(validate_changed_paths())
    return errors