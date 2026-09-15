#!/usr/bin/env python3
from __future__ import annotations

import copy

import validate_g2_monitoring_source_onboarding_authorization as validator


def must_fail(manifest: dict, fragment: str) -> None:
    errors = validator.validate_manifest(manifest)
    if not errors or not any(fragment.lower() in error.lower() for error in errors):
        raise AssertionError(f"mutation unexpectedly accepted or wrong failure: {fragment}; errors={errors}")


def must_reject_workflow(text: str, fragment: str) -> None:
    errors = validator.validate_scope_workflow_text(text)
    if not errors or not any(fragment.lower() in error.lower() for error in errors):
        raise AssertionError(f"workflow mutation unexpectedly accepted or wrong failure: {fragment}; errors={errors}")


def main() -> int:
    canonical = validator.load_manifest()
    if validator.validate_manifest(canonical):
        raise AssertionError("canonical G2 authorization manifest does not validate")

    for mutate, fragment in (
        (lambda m: m.__setitem__("effective_rule", "effective_immediately"), "effective_rule"),
        (lambda m: m.__setitem__("implementation_authority_after_merge", "global_product_authority"), "implementation_authority_after_merge"),
        (lambda m: m.__setitem__("merge_authorization", "granted"), "merge_authorization"),
        (lambda m: m.__setitem__("production_authority", "granted"), "production_authority"),
        (lambda m: m["authorized_capability_scope"].append("resource_inventory_ui"), "capability scope"),
        (lambda m: m["explicitly_not_authorized"].remove("host_or_resource_inventory_ingestion_product_flow"), "exclusion"),
        (lambda m: m["required_invariants"].remove("credential_binding_reference_not_secret_bytes"), "invariant"),
        (lambda m: m["implementation_path_policy"]["allowed_prefixes"].append("src/jlmirror_monitoring/"), "allowed prefix"),
        (lambda m: m["implementation_path_policy"].__setitem__("shared_existing_paths_policy", "mutable"), "shared_existing_paths_policy"),
        (lambda m: m["implementation_path_policy"].__setitem__("trusted_evaluator_event", "pull_request_target"), "trusted_evaluator_event"),
        (lambda m: m["implementation_path_policy"].__setitem__("candidate_controlled_relevance_inference", "allowed"), "candidate_controlled_relevance_inference"),
        (lambda m: m["implementation_path_policy"].__setitem__("semantic_guard_rule", "path_only"), "semantic_guard_rule"),
        (lambda m: m["implementation_path_policy"]["forbidden_code_markers"].remove("monitoring_resource"), "forbidden code marker"),
    ):
        mutated = copy.deepcopy(canonical)
        mutate(mutated)
        must_fail(mutated, fragment)

    workflow = validator.SCOPE_WORKFLOW.read_text(encoding="utf-8")
    if validator.validate_scope_workflow_text(workflow):
        raise AssertionError("canonical G2 scope workflow does not validate")

    must_reject_workflow(
        workflow.replace('          python3 "$TRUSTED_VALIDATOR" \\\n', '          # python3 "$TRUSTED_VALIDATOR" \\\n', 1),
        "trusted validator invocation",
    )
    must_reject_workflow(
        workflow.replace('          python3 "$TRUSTED_READINESS_VALIDATOR" \\\n', '          # python3 "$TRUSTED_READINESS_VALIDATOR" \\\n', 1),
        "readiness invocation",
    )
    must_reject_workflow(
        workflow.replace("          state=failure\n", "          state=success\n", 1),
        "fail-closed control-flow",
    )
    must_reject_workflow(
        workflow.replace('          test "$state" = success\n', '          # test "$state" = success\n', 1),
        "fail-closed control-flow",
    )

    print("g2_authorization_falsifier=PASS manifest_mutations=13 workflow_mutations=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
