#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_SHA = "644b74d3277fd33bdfe705c135dba2a3b4ffde48"
AUTH_ID = "g4.metrics@1"
MANIFEST = ROOT / "implementation/g4-metrics-authorization/AUTHORIZATION_MANIFEST.json"
AUTH = ROOT / "implementation/g4-metrics-authorization/AUTHORIZATION.md"
TASK = ROOT / "implementation/g4-metrics-authorization/TASK_PACKET.md"

EXPECTED_PREFIXES = {
    "apps/g4-metrics/",
    "contracts/g4-metrics/",
    "implementation/g4-metrics/",
    "tests/g4/",
    "tools/g4/",
}
EXPECTED_EXACT = {".github/workflows/g4-metrics-runtime.yml"}
EXPECTED_CAPS = {
    "canonical_metric_definition_list_for_one_resource",
    "canonical_metric_definition_detail",
    "canonical_metric_current_state_read",
    "bounded_metric_history_read",
    "active_generation_current_metric_default",
    "historical_generation_visibly_non_current",
    "truthful_metric_evidence_state_presentation",
    "truthful_history_completeness_presentation",
    "bounded_metric_value_serialization",
    "g4_metrics_browser_e2e",
    "cross_tenant_and_revoked_authority_fail_closed",
}
EXPECTED_INVARIANTS = {
    "current_platform_authorization_precedes_metric_read",
    "client_tenant_id_not_tenant_authority",
    "metric_definition_id_is_canonical_platform_identity",
    "provider_itemid_not_canonical_identity",
    "metric_definition_separate_from_current_state",
    "metric_current_state_separate_from_history",
    "missing_metric_value_not_zero",
    "metric_value_not_health_authority",
    "stale_or_incomplete_evidence_not_current",
    "active_generation_default_for_current_meaning",
    "history_window_is_finite_and_explicit",
    "history_completeness_is_evidence_backed",
    "cross_generation_history_union_forbidden",
    "shared_wave4_metric_substrate_reused_not_reimplemented",
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
    require(data.get("implementation_authority_after_merge") == "granted_for_exact_g4_metrics_only", "post-merge authority drift", errors)
    require(data.get("merge_authorization") == "not_granted", "authorization package cannot authorize its own merge", errors)

    policy = data.get("implementation_path_policy") or {}
    require(set(policy.get("allowed_prefixes") or []) == EXPECTED_PREFIXES, "implementation prefix allowlist drift", errors)
    require(set(policy.get("allowed_exact_paths") or []) == EXPECTED_EXACT, "implementation exact-path allowlist drift", errors)
    require(policy.get("implementation_pr_head_prefix") == "impl/g4-metrics", "implementation branch prefix drift", errors)
    require(policy.get("implementation_pr_required_label") == "jlmirror-slice:g4-metrics", "implementation label drift", errors)
    require(policy.get("implementation_claim_path") == "implementation/g4-metrics/IMPLEMENTATION_CLAIM.json", "claim path drift", errors)
    require(policy.get("implementation_claim_authorization_id") == AUTH_ID, "claim authorization id drift", errors)
    require(policy.get("shared_existing_paths_policy") == "read_only_unless_separate_successor_authorization", "shared path policy drift", errors)
    require(policy.get("runtime_workflow") == ".github/workflows/g4-metrics-runtime.yml", "runtime workflow path drift", errors)
    require(policy.get("runtime_workflow_name") == "JLMIRROR G4 Metrics Runtime", "runtime workflow name drift", errors)
    require(policy.get("runtime_entrypoint") == "python tools/g4/run_metrics_runtime.py", "runtime entrypoint drift", errors)
    require(set(policy.get("runtime_allowed_actions") or []) == {
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1",
        "actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38",
    }, "runtime allowed-action set drift", errors)
    require(policy.get("direct_persistence_writes") == "forbidden", "direct persistence write boundary drift", errors)
    require(policy.get("direct_schema_authority") == "forbidden", "direct schema authority boundary drift", errors)
    require(policy.get("direct_provider_calls") == "forbidden", "direct provider-call boundary drift", errors)

    require(set(data.get("authorized_capability_scope") or []) == EXPECTED_CAPS, "authorized capability scope drift", errors)
    require(set(data.get("required_invariants") or []) == EXPECTED_INVARIANTS, "required invariant set drift", errors)

    for marker in (
        "METRIC_DEFINITION_ID = CANONICAL_PLATFORM_IDENTITY",
        "ZABBIX_ITEMID != METRIC_DEFINITION_ID",
        "METRIC_CURRENT_STATE != METRIC_HISTORY",
        "MISSING_VALUE != ZERO",
        "METRICS != HEALTH",
        "G4_AUTHORIZED != G5_AUTHORIZED",
        "GREEN_STATUS != MERGE_AUTHORIZATION",
    ):
        require(marker in auth, f"authorization missing marker: {marker}", errors)

    for marker in (
        "metric_definition_id = canonical identity",
        "missing != zero",
        "metric value != health",
        "G4 != G5 Problem/Health",
        "READY_FOR_MERGE != AUTHORIZED_TO_MERGE",
    ):
        require(marker in task, f"task packet missing marker: {marker}", errors)

    for path in data.get("authority_source_paths") or []:
        require((ROOT / path).is_file(), f"authority source missing: {path}", errors)

    forbidden = {
        "problem_product_surface",
        "health_product_surface",
        "metric_derived_health_or_problem_authority",
        "production_deployment",
    }
    require(forbidden.issubset(set(data.get("explicitly_not_authorized") or [])), "critical G5+/health/problem/production exclusions missing", errors)

    for error in errors:
        print(f"G4_AUTHORIZATION_ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print("g4_authorization=PASS exact_scope=metrics merge_authorization=not-granted")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
