#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "assurance"))
import validate_g1_identity_tenant_shell_authorization as validator


def must_fail(mutator, fragment: str) -> None:
    data = copy.deepcopy(validator.load())
    mutator(data)
    try:
        validator.validate_manifest(data)
    except AssertionError as exc:
        if fragment not in str(exc):
            raise AssertionError(f"expected {fragment!r}, got {exc!r}")
        return
    raise AssertionError(f"mutation unexpectedly accepted: {fragment}")


def falsify_successor_authority_transition() -> None:
    must_fail(lambda d: d.__setitem__("implementation_authority_before_merge", "granted"), "pre-merge implementation authority drift")
    must_fail(lambda d: d.__setitem__("implementation_authority_after_merge", "granted_global_product"), "post-merge implementation authority drift")


def falsify_effective_rule() -> None:
    must_fail(lambda d: d.__setitem__("effective_rule", "effective_immediately"), "effective rule drift")


def falsify_exact_exclusion_set() -> None:
    for value in ("monitoring_product_ui", "browser_refresh_token_or_long_lived_platform_access_credential", "production_c3_numerics"):
        must_fail(lambda d, v=value: d["explicitly_not_authorized"].remove(v), "explicit exclusion drift")


def falsify_implementation_path_policy() -> None:
    must_fail(lambda d: d["implementation_path_policy"]["allowed_prefixes"].append("src/jlmirror_authority/"), "implementation allowed prefix drift")
    mutations = [
        (lambda d: d["implementation_path_policy"]["allowed_prefixes"].remove("src/jlmirror_g1/"), "implementation allowed prefix drift"),
        (lambda d: d["implementation_path_policy"]["allowed_exact_paths"].append("pyproject.toml"), "implementation exact path drift"),
        (lambda d: d["implementation_path_policy"].__setitem__("shared_existing_paths_policy", "writable"), "implementation path policy drift: shared_existing_paths_policy"),
        (lambda d: d["implementation_path_policy"].__setitem__("implementation_pr_head_prefix", "impl/anything"), "implementation path policy drift: implementation_pr_head_prefix"),
        (lambda d: d["implementation_path_policy"].__setitem__("implementation_pr_required_label", "optional"), "implementation path policy drift: implementation_pr_required_label"),
        (lambda d: d["implementation_path_policy"].__setitem__("implementation_claim_path", "implementation/optional.json"), "implementation path policy drift: implementation_claim_path"),
        (lambda d: d["implementation_path_policy"].__setitem__("same_repository_required", False), "implementation path policy drift: same_repository_required"),
        (lambda d: d["implementation_path_policy"].__setitem__("implementation_pr_base_ref_policy", "any_branch"), "implementation path policy drift: implementation_pr_base_ref_policy"),
        (lambda d: d["implementation_path_policy"].__setitem__("trusted_evaluator_event", "pull_request"), "implementation path policy drift: trusted_evaluator_event"),
        (lambda d: d["implementation_path_policy"].__setitem__("trusted_scope_attestation_command", "/optional"), "implementation path policy drift: trusted_scope_attestation_command"),
        (lambda d: d["implementation_path_policy"].__setitem__("trusted_evaluator_source", "pull_request_head"), "implementation path policy drift: trusted_evaluator_source"),
        (lambda d: d["implementation_path_policy"].__setitem__("implementation_pr_requires_trusted_scope_attestation_on_exact_head", False), "implementation path policy drift: implementation_pr_requires_trusted_scope_attestation_on_exact_head"),
        (lambda d: d["implementation_path_policy"].__setitem__("candidate_controlled_relevance_inference", "allowed"), "implementation path policy drift: candidate_controlled_relevance_inference"),
    ]
    for mutation, fragment in mutations:
        must_fail(mutation, fragment)


def falsify_trusted_scope_publication_contract() -> None:
    must_fail(
        lambda d: d["implementation_path_policy"].__setitem__("trusted_scope_status_evidence_role", "standalone_merge_authority"),
        "implementation path policy drift: trusted_scope_status_evidence_role",
    )
    mutations = [
        (lambda d: d["implementation_path_policy"].__setitem__("implementation_pr_base_ref_policy", "any_writable_branch"), "implementation path policy drift: implementation_pr_base_ref_policy"),
        (lambda d: d["implementation_path_policy"].__setitem__("trusted_evaluator_source", "default_branch_caller_plus_arbitrary_base_object"), "implementation path policy drift: trusted_evaluator_source"),
        (lambda d: d["implementation_path_policy"].__setitem__("trusted_scope_status_context", "optional"), "implementation path policy drift: trusted_scope_status_context"),
        (lambda d: d["implementation_path_policy"].__setitem__("trusted_scope_status_publication", "green_status_is_authority"), "implementation path policy drift: trusted_scope_status_publication"),
        (lambda d: d["implementation_path_policy"].__setitem__("trusted_scope_freshness_rule", "push_event_invalidation"), "implementation path policy drift: trusted_scope_freshness_rule"),
        (lambda d: d["implementation_path_policy"].__setitem__("trusted_scope_concurrency_rule", "parallel_unordered"), "implementation path policy drift: trusted_scope_concurrency_rule"),
    ]
    for mutation, fragment in mutations:
        must_fail(mutation, fragment)


def falsify_trusted_scope_readiness_execution() -> None:
    must_fail(
        lambda d: d["implementation_path_policy"].__setitem__("trusted_status_creator_id", 0),
        "implementation path policy drift: trusted_status_creator_id",
    )
    mutations = [
        (lambda d: d["implementation_path_policy"].__setitem__("trusted_scope_readiness_command", "/optional"), "implementation path policy drift: trusted_scope_readiness_command"),
        (lambda d: d["implementation_path_policy"].__setitem__("trusted_scope_readiness_status_context", "optional"), "implementation path policy drift: trusted_scope_readiness_status_context"),
        (lambda d: d["implementation_path_policy"].__setitem__("trusted_status_creator_login", "anyone"), "implementation path policy drift: trusted_status_creator_login"),
        (lambda d: d["implementation_path_policy"].__setitem__("trusted_scope_merge_preflight_rule", "trust_green_status"), "implementation path policy drift: trusted_scope_merge_preflight_rule"),
        (lambda d: d["implementation_path_policy"].__setitem__("implementation_pr_requires_trusted_scope_readiness_on_exact_head_base", False), "implementation path policy drift: implementation_pr_requires_trusted_scope_readiness_on_exact_head_base"),
    ]
    for mutation, fragment in mutations:
        must_fail(mutation, fragment)
    import test_validate_g1_identity_tenant_shell_scope_readiness as readiness_falsifier
    readiness_falsifier.falsify_live_readiness_guards()


def falsify_implementation_scope_gate_execution() -> None:
    must_fail(lambda d: d["implementation_path_policy"].__setitem__("trusted_evaluator_event", "pull_request"), "implementation path policy drift: trusted_evaluator_event")
    must_fail(lambda d: d["implementation_path_policy"].__setitem__("trusted_evaluator_source", "pull_request_head"), "implementation path policy drift: trusted_evaluator_source")
    must_fail(lambda d: d["implementation_path_policy"].__setitem__("candidate_controlled_relevance_inference", "allowed"), "implementation path policy drift: candidate_controlled_relevance_inference")
    import test_validate_g1_identity_tenant_shell_implementation_scope as scope_falsifier
    scope_falsifier.falsify_real_git_diff_gate()
    scope_falsifier.falsify_candidate_metadata_fail_closed()
    scope_falsifier.falsify_all_voluntary_metadata_omission()


def falsify_authority_source_corpus() -> None:
    must_fail(lambda d: d["consumed_existing_authority"].append("provider_native_identity_authority"), "consumed authority drift")
    must_fail(lambda d: d["authority_source_paths"].remove("implementation/wave-1/AUTHORITY_BOUNDARY.md"), "authority source corpus drift")


def falsify_g1_scope_and_invariants() -> None:
    must_fail(lambda d: d["authorized_capability_scope"].append("g2_monitoring_source_onboarding"), "capability scope drift")
    must_fail(lambda d: d["required_invariants"].remove("client_tenant_id_not_tenant_authority"), "required invariant drift")
    must_fail(lambda d: d["authorized_g0_bootstrap_scope"].append("generic_shared_platform_framework"), "G0 bootstrap scope drift")


def falsify_merge_and_production_boundaries() -> None:
    must_fail(lambda d: d.__setitem__("merge_authorization", "granted"), "merge authority escalation")
    must_fail(lambda d: d.__setitem__("production_authority", "granted"), "production authority escalation")
    must_fail(lambda d: d.__setitem__("frontend_authority", "generic_product_ui"), "frontend authority escalation")


def falsify_successor_governance_rules() -> None:
    must_fail(lambda d: d.__setitem__("historical_authority_rule", "rewrite_predecessors"), "historical authority rule drift")
    must_fail(lambda d: d.__setitem__("implementation_boundary_rule", "implementation_may_begin_before_merge"), "implementation boundary drift")
    must_fail(lambda d: d.__setitem__("schema_version", True), "schema_version drift")


def main() -> int:
    validator.validate()
    falsify_successor_authority_transition()
    falsify_effective_rule()
    falsify_exact_exclusion_set()
    falsify_implementation_path_policy()
    falsify_trusted_scope_publication_contract()
    falsify_trusted_scope_readiness_execution()
    falsify_implementation_scope_gate_execution()
    falsify_authority_source_corpus()
    falsify_g1_scope_and_invariants()
    falsify_merge_and_production_boundaries()
    falsify_successor_governance_rules()
    print("g1_identity_tenant_shell_authorization_falsification=PASS authority_escalation=blocked implementation_path_expansion=blocked trusted_default_branch_caller=bound status=evidence-only readiness=source-authenticated-live-preflight spoofed_status=blocked skip_ci_stale_base=blocked mutable_label=blocked candidate_workflow_authority=blocked candidate_relevance_bypass=blocked real_git_diff=executed")
    return 0


if __name__ == "__main__":
    main()
