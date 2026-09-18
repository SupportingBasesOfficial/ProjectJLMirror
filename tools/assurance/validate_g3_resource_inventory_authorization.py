#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_SHA = "a0f5e436812b2ebb5334485dbf4fc4abb393befa"
AUTH_ID = "g3.resource-inventory@1"
MANIFEST = ROOT / "implementation/g3-resource-inventory-authorization/AUTHORIZATION_MANIFEST.json"
AUTH = ROOT / "implementation/g3-resource-inventory-authorization/AUTHORIZATION.md"
TASK = ROOT / "implementation/g3-resource-inventory-authorization/TASK_PACKET.md"

EXPECTED_PREFIXES = {"apps/g3-resource-inventory/", "contracts/g3-resource-inventory/", "implementation/g3-resource-inventory/", "tests/g3/", "tools/g3/"}
EXPECTED_EXACT = {".github/workflows/g3-resource-inventory-runtime.yml"}
EXPECTED_CAPS = {
    "canonical_monitoring_resource_list_through_current_tenant_authority",
    "canonical_monitoring_resource_detail_through_current_tenant_authority",
    "active_generation_inventory_default",
    "bounded_provider_provenance_view",
    "resource_kind_host_projection",
    "provider_object_kind_zabbix_host_as_external_evidence",
    "truthful_presence_generation_and_evidence_state_presentation",
    "resource_inventory_browser_e2e",
    "cross_tenant_and_stale_authority_fail_closed",
}
EXPECTED_INVARIANTS = {
    "current_platform_authorization_precedes_monitoring_resource_read",
    "client_tenant_id_not_tenant_authority",
    "monitoring_resource_id_is_canonical_platform_identity",
    "provider_native_id_not_canonical_identity",
    "resource_kind_host_not_device_taxonomy",
    "provider_object_kind_not_device_taxonomy",
    "provider_evidence_not_canonical_device_classification",
    "active_generation_inventory_default",
    "incomplete_or_stale_evidence_not_resource_absence",
    "scope_exclusion_not_removal",
    "shared_wave4_host_inventory_reused_not_reimplemented",
}

def require(ok: bool, msg: str, errors: list[str]) -> None:
    if not ok:
        errors.append(msg)

def main() -> int:
    errors: list[str] = []
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    auth = AUTH.read_text(encoding="utf-8")
    task = TASK.read_text(encoding="utf-8")
    require(data.get("authorization_id") == AUTH_ID, "authorization_id drift", errors)
    require(data.get("canonical_base") == f"main@{BASE_SHA}", "canonical base drift", errors)
    require(data.get("implementation_authority_before_merge") == "blocked", "pre-merge implementation authority must remain blocked", errors)
    require(data.get("implementation_authority_after_merge") == "granted_for_exact_g3_resource_inventory_only", "post-merge authority drift", errors)
    require(data.get("merge_authorization") == "not_granted", "authorization package cannot authorize its own merge", errors)
    policy = data.get("implementation_path_policy") or {}
    require(set(policy.get("allowed_prefixes") or []) == EXPECTED_PREFIXES, "implementation prefix allowlist drift", errors)
    require(set(policy.get("allowed_exact_paths") or []) == EXPECTED_EXACT, "implementation exact-path allowlist drift", errors)
    require(policy.get("implementation_pr_head_prefix") == "impl/g3-resource-inventory", "implementation branch prefix drift", errors)
    require(policy.get("implementation_pr_required_label") == "jlmirror-slice:g3-resource-inventory", "implementation label drift", errors)
    require(policy.get("implementation_claim_path") == "implementation/g3-resource-inventory/IMPLEMENTATION_CLAIM.json", "claim path drift", errors)
    require(policy.get("implementation_claim_authorization_id") == AUTH_ID, "claim authorization id drift", errors)
    require(policy.get("shared_existing_paths_policy") == "read_only_unless_separate_successor_authorization", "shared path policy drift", errors)
    require(set(data.get("authorized_capability_scope") or []) == EXPECTED_CAPS, "authorized capability scope drift", errors)
    require(set(data.get("required_invariants") or []) == EXPECTED_INVARIANTS, "required invariant set drift", errors)
    for marker in ("MONITORING_RESOURCE_ID = CANONICAL_PLATFORM_IDENTITY", "RESOURCE_KIND = host", "ZABBIX_HOSTID != MONITORING_RESOURCE_ID", "G3_AUTHORIZED != G4_AUTHORIZED", "GREEN_STATUS != MERGE_AUTHORIZATION"):
        require(marker in auth, f"authorization missing marker: {marker}", errors)
    for marker in ("monitoring_resource_id = canonical identity", "resource_kind = host", "G3 != G4 metrics", "READY_FOR_MERGE != AUTHORIZED_TO_MERGE"):
        require(marker in task, f"task packet missing marker: {marker}", errors)
    for path in data.get("authority_source_paths") or []:
        require((ROOT / path).is_file(), f"authority source missing: {path}", errors)
    forbidden = {"metric_definition_or_metric_value_product_surface", "problem_or_health_product_surface", "canonical_device_taxonomy_or_classification", "production_deployment"}
    require(forbidden.issubset(set(data.get("explicitly_not_authorized") or [])), "critical G4+/classification/production exclusions missing", errors)
    for error in errors:
        print(f"G3_AUTHORIZATION_ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print("g3_authorization=PASS exact_scope=resource-inventory merge_authorization=not-granted")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
