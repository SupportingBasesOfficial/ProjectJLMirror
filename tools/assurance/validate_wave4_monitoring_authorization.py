#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "860dbf5ffab465504f75ae7a13f13a13ed3bcd7f"
MANIFEST = ROOT / "implementation/wave-4-monitoring-authorization/AUTHORIZATION_MANIFEST.json"
DOC = ROOT / "implementation/wave-4-monitoring-authorization/AUTHORIZATION.md"

EXPECTED_CAPABILITY_SCOPE = {
    "accepted_monitoring_track_a_domain_api_and_event_contracts",
    "accepted_d2_track_b_customer_telemetry_durable_acceptance_projection_profile",
    "accepted_monitoring_zabbix_read_only_provider_and_normalization_subprofile",
}
EXPECTED_AUTHORIZED_SLICES = [
    {"slice_id": "impl.customer-telemetry@1", "scope": "accepted_d2_track_b_profile_only"},
    {"slice_id": "impl.provider-integration@1", "scope": "accepted_monitoring_zabbix_subprofile_only"},
]
EXPECTED_CONSUMED = {
    "impl.identity-bff@1",
    "impl.control-plane@1",
    "impl.platform-runtime@1",
    "impl.cell-data-runtime@1",
    "impl.async-core@1",
    "impl.observability@1",
    "impl.release-supply-chain@1",
}
EXPECTED_RUNTIME = {
    "runtime.api@1",
    "runtime.worker@1",
    "worker.customer-telemetry@1",
    "worker.provider-integration@1",
}
EXPECTED_CONTRACT_SURFACES = {
    "docs/03-domains/monitoring-domain-contract.md",
    "docs/09-api-contracts/monitoring-domain-api-contract.md",
    "docs/10-event-contracts/monitoring-domain-event-contracts.md",
    "docs/09-api-contracts/zabbix-monitoring-source-provider-contract.md",
    "docs/09-api-contracts/zabbix-monitoring-normalization-profile.md",
    "docs/08-data/telemetry-plane.md",
}
EXPECTED_EXCLUSIONS = {
    "alerting_product_vertical",
    "itsm_product_vertical",
    "automation_product_vertical",
    "aiops_product_vertical",
    "finops_product_vertical",
    "commercial_product_vertical",
    "unrelated_provider_subprofiles",
    "provider_write_back",
    "public_or_outbound_monitoring_webhooks",
    "browser_realtime_activation",
    "public_sdk_or_public_projection_families",
    "privileged_direct_query_surface",
    "production_deployment",
    "production_capacity_numerics",
    "production_partition_topology",
    "production_retry_backoff_numerics",
    "production_retention_replay_quarantine_horizons",
    "frontend_route_generation_from_backend_shape",
}
ALLOWED_PR_PATHS = {
    "implementation/wave-4-monitoring-authorization/AUTHORIZATION.md",
    "implementation/wave-4-monitoring-authorization/AUTHORIZATION_MANIFEST.json",
    "tools/assurance/validate_wave4_monitoring_authorization.py",
    "tools/assurance/test_validate_wave4_monitoring_authorization.py",
    "tools/assurance/test_validate_adversarial_learning.py",
    ".github/workflows/wave4-monitoring-implementation-authorization.yml",
    "governance/adversarial/learning-ledger.d/pr-123-review-findings.json",
}


def req(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def load() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def validate_manifest(data: dict) -> None:
    req(data.get("schema_version") == 1, "schema_version drift")
    req(data.get("authorization_id") == "wave4.monitoring-zabbix.vertical@1", "authorization id drift")
    req(data.get("canonical_base_main_commit") == BASE, "canonical base drift")
    req(data.get("authorization_state") == "proposed_exact_scope_authorization", "authorization state drift")
    req(data.get("effective_rule") == "becomes_canonical_only_after_exact_head_review_and_separately_authorized_merge", "effective rule drift")
    req(data.get("canonical_effect_after_merge") == "authorized_to_implement_exact_scoped_monitoring_vertical_only", "canonical effect drift")
    req(data.get("authorized_product_vertical") == "monitoring", "product vertical drift")
    req(set(data.get("authorized_capability_scope", [])) == EXPECTED_CAPABILITY_SCOPE, "authorized capability scope drift")
    req(data.get("authorized_slices") == EXPECTED_AUTHORIZED_SLICES, "authorized slices drift")
    req(set(data.get("consumed_existing_substrate", [])) == EXPECTED_CONSUMED, "consumed substrate drift")
    req(set(data.get("authorized_runtime_roles", [])) == EXPECTED_RUNTIME, "runtime role drift")
    req(set(data.get("authorized_contract_surfaces", [])) == EXPECTED_CONTRACT_SURFACES, "authorized contract surface drift")
    for relative in EXPECTED_CONTRACT_SURFACES:
        req((ROOT / relative).is_file(), f"authorized contract surface missing: {relative}")
    req(data.get("production_authority") == "none", "production authority escalation")
    req(data.get("c3_production_state") == "open", "C3 production state escalation")
    req(data.get("frontend_authority") == "not_granted_by_this_gate", "frontend authority escalation")
    req(data.get("frontend_route_policy") == "backend_entity_table_endpoint_or_use_case_does_not_imply_frontend_route", "frontend route policy drift")
    req(set(data.get("explicitly_not_authorized", [])) == EXPECTED_EXCLUSIONS, "explicit exclusion drift")
    req(data.get("merge_authorization") == "not_granted", "merge authority escalation")
    pred = data.get("required_predecessor_authority", {})
    req(pred == {
        "monitoring_track_a": "accepted",
        "open_rel_030_track_b": "accepted_selected_and_conformed",
        "d3_identity_security": "separately_accepted",
        "d4_eventing_async": "separately_accepted",
    }, "predecessor authority drift")


def validate_predecessors() -> None:
    d4 = json.loads((ROOT / "implementation/d4-eventing-async/state-manifest.json").read_text(encoding="utf-8"))
    req(d4.get("gate_state") == "separately_accepted", "D4 predecessor must be separately accepted")
    req(d4.get("production_authority") == "none", "D4 predecessor production authority drift")
    d2 = (ROOT / "docs/16-implementation-readiness/18-d2-track-b-acceptance-propagation.md").read_text(encoding="utf-8")
    req("open_rel_030_profile = selected_and_conformed" in d2, "D2 Track B conformance missing")
    req("wave4_implementation_authorization = not_granted" in d2, "D2 predecessor Wave4 snapshot drift")
    d3 = (ROOT / "docs/16-implementation-readiness/20-d3-identity-security-acceptance-propagation.md").read_text(encoding="utf-8")
    req("separately_accepted" in d3, "D3 separate acceptance missing")


def validate_document() -> None:
    text = DOC.read_text(encoding="utf-8")
    for marker in (
        "impl.customer-telemetry@1",
        "impl.provider-integration@1",
        "AUTHORIZED BACKEND CAPABILITY != FRONTEND ROUTE",
        "AUTHORIZED_TO_IMPLEMENT != PRODUCTION_AUTHORIZED",
        "HISTORICAL NOT_GRANTED != CURRENT AUTHORIZATION REGRESSION",
        "frontend route creation",
    ):
        req(marker in text, f"authorization document missing marker: {marker}")


def validate_changed_paths(changed: list[str]) -> None:
    req(changed, "authorization branch must contain an explicit delta")
    for path in changed:
        req(path in ALLOWED_PR_PATHS, f"authorization PR touched forbidden path: {path}")


def validate_pr_scope() -> None:
    changed = [p for p in git("diff", "--name-only", f"{BASE}...HEAD").splitlines() if p]
    validate_changed_paths(changed)


def validate() -> None:
    req(MANIFEST.exists(), "missing authorization manifest")
    req(DOC.exists(), "missing authorization document")
    validate_manifest(load())
    validate_predecessors()
    validate_document()
    validate_pr_scope()


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"wave4_monitoring_authorization=FAIL reason={exc}", file=sys.stderr)
        return 1
    print("wave4_monitoring_authorization=PASS vertical=monitoring capability_scope=3 slices=customer-telemetry,provider-integration:zabbix production=none frontend_routes=not_granted exact_artifact_allowlist=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
