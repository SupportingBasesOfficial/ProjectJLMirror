#!/usr/bin/env python3
from __future__ import annotations

import copy

import validate_g2_monitoring_source_onboarding_authorization as validator


def must_fail(manifest: dict, fragment: str) -> None:
    errors = validator.validate_manifest(manifest)
    if not errors or not any(fragment.lower() in error.lower() for error in errors):
        raise AssertionError(f"mutation unexpectedly accepted or wrong failure: {fragment}; errors={errors}")


def main() -> int:
    canonical = validator.load_manifest()
    if validator.validate_manifest(canonical):
        raise AssertionError("canonical G2 authorization manifest does not validate")

    mutations = (
        ("effective_rule", "effective_immediately", "effective_rule"),
        ("implementation_authority_after_merge", "global_product_authority", "implementation_authority_after_merge"),
        ("merge_authorization", "granted", "merge_authorization"),
        ("production_authority", "granted", "production_authority"),
    )
    for key, value, fragment in mutations:
        mutated = copy.deepcopy(canonical)
        mutated[key] = value
        must_fail(mutated, fragment)

    # Historical PR154 diff admission must remain strict for its own branch,
    # but successor PRs that merely touch a watched cross-cutting validator
    # must not be reclassified as the old G2 authorization PR.
    if not validator.should_validate_historical_authorization_diff(event_name="", head_ref="", ref_name=""):
        raise AssertionError("local G2 authorization validation must remain strict")
    if not validator.should_validate_historical_authorization_diff(
        event_name="pull_request",
        head_ref="governance/g2-monitoring-source-onboarding-authorization",
        ref_name="158/merge",
    ):
        raise AssertionError("canonical G2 authorization PR must enforce historical diff allowlist")
    if validator.should_validate_historical_authorization_diff(
        event_name="pull_request",
        head_ref="governance/g3-resource-inventory-authorization",
        ref_name="158/merge",
    ):
        raise AssertionError("successor governance PR must not be treated as historical G2 authorization diff")
    if validator.should_validate_historical_authorization_diff(
        event_name="push",
        head_ref="",
        ref_name="main",
    ):
        raise AssertionError("main push must validate canonical G2 authority without replaying PR154 diff allowlist")

    workflow = validator.SCOPE_WORKFLOW.read_text(encoding="utf-8")
    if validator.validate_scope_workflow_text(workflow):
        raise AssertionError("canonical trusted workflow does not match its locked blob")

    # Any byte-level workflow mutation must fail. This covers extra steps,
    # reordered checks, dead branches, evaluator replacement, or publishers
    # without trying to maintain a partial shell/YAML parser.
    variants = (
        workflow + "\n# drift\n",
        workflow.replace("runs-on: ubuntu-24.04", "runs-on: ubuntu-latest", 1),
        workflow.replace("contents: read", "contents: write", 1),
        workflow.replace("cancel-in-progress: true", "cancel-in-progress: false", 1),
    )
    for mutated in variants:
        errors = validator.validate_scope_workflow_text(mutated)
        if not errors or not any("canonical blob drift" in error for error in errors):
            raise AssertionError(f"workflow mutation escaped blob lock: {errors}")

    print("g2_authorization_falsifier=PASS manifest_mutations=4 workflow_blob_mutations=4 historical_diff_scope=branch-bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())