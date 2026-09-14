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
    must_fail(lambda d: d["explicitly_not_authorized"].remove("monitoring_product_ui"), "explicit exclusion drift")
    must_fail(lambda d: d["explicitly_not_authorized"].remove("browser_refresh_token_or_long_lived_platform_access_credential"), "explicit exclusion drift")
    must_fail(lambda d: d["explicitly_not_authorized"].remove("production_c3_numerics"), "explicit exclusion drift")


def falsify_implementation_path_policy() -> None:
    must_fail(lambda d: d["implementation_path_policy"]["allowed_prefixes"].append("src/jlmirror_authority/"), "implementation allowed prefix drift")
    must_fail(lambda d: d["implementation_path_policy"]["allowed_prefixes"].remove("src/jlmirror_g1/"), "implementation allowed prefix drift")
    must_fail(lambda d: d["implementation_path_policy"]["allowed_exact_paths"].append("pyproject.toml"), "implementation exact path drift")
    must_fail(lambda d: d["implementation_path_policy"].__setitem__("shared_existing_paths_policy", "implementation_pr_may_extend_shared_paths"), "shared existing path policy drift")
    must_fail(lambda d: d["implementation_path_policy"].__setitem__("implementation_pr_must_validate_diff_against_this_policy", False), "implementation PR path validation requirement drift")


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
    falsify_authority_source_corpus()
    falsify_g1_scope_and_invariants()
    falsify_merge_and_production_boundaries()
    falsify_successor_governance_rules()
    print("g1_identity_tenant_shell_authorization_falsification=PASS authority_escalation=blocked successor_transition_weakening=blocked implementation_path_expansion=blocked scope_expansion=blocked invariant_loss=blocked bootstrap_expansion=blocked authority_source_drift=blocked exclusion_removal=blocked successor_rule_weakening=blocked")
    return 0


if __name__ == "__main__":
    main()
