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

    mutated = copy.deepcopy(canonical)
    mutated["effective_rule"] = "effective_immediately"
    must_fail(mutated, "effective_rule")

    mutated = copy.deepcopy(canonical)
    mutated["implementation_authority_after_merge"] = "global_product_authority"
    must_fail(mutated, "post-merge implementation authority")

    mutated = copy.deepcopy(canonical)
    mutated["merge_authorization"] = "granted"
    must_fail(mutated, "merge authorization")

    mutated = copy.deepcopy(canonical)
    mutated["production_authority"] = "granted"
    must_fail(mutated, "production authority")

    mutated = copy.deepcopy(canonical)
    mutated["authorized_capability_scope"].append("resource_inventory_ui")
    must_fail(mutated, "capability scope")

    mutated = copy.deepcopy(canonical)
    mutated["explicitly_not_authorized"].remove("host_or_resource_inventory_ingestion_product_flow")
    must_fail(mutated, "exclusion")

    mutated = copy.deepcopy(canonical)
    mutated["required_invariants"].remove("credential_binding_reference_not_secret_bytes")
    must_fail(mutated, "invariant")

    mutated = copy.deepcopy(canonical)
    mutated["implementation_path_policy"]["allowed_prefixes"].append("src/jlmirror_monitoring/")
    must_fail(mutated, "allowed prefix")

    mutated = copy.deepcopy(canonical)
    mutated["implementation_path_policy"]["shared_existing_paths_policy"] = "mutable"
    must_fail(mutated, "shared_existing_paths_policy")

    mutated = copy.deepcopy(canonical)
    mutated["implementation_path_policy"]["trusted_evaluator_event"] = "pull_request_target"
    must_fail(mutated, "trusted_evaluator_event")

    mutated = copy.deepcopy(canonical)
    mutated["implementation_path_policy"]["candidate_controlled_relevance_inference"] = "allowed"
    must_fail(mutated, "candidate_controlled_relevance_inference")

    print("g2_authorization_falsifier=PASS mutations=11")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
