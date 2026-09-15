#!/usr/bin/env python3
from __future__ import annotations

import copy
import json

import validate_g2_monitoring_source_onboarding_implementation_scope as validator


def must_raise(fn, fragment: str) -> None:
    try:
        fn()
    except AssertionError as exc:
        if fragment.lower() not in str(exc).lower():
            raise AssertionError(f"wrong failure for {fragment}: {exc}") from exc
        return
    raise AssertionError(f"mutation unexpectedly accepted: {fragment}")


def canonical_policy() -> dict:
    return {
        "implementation_pr_head_prefix": validator.EXPECTED_HEAD_PREFIX,
        "implementation_pr_required_label": validator.EXPECTED_LABEL,
        "implementation_claim_path": validator.EXPECTED_CLAIM_PATH,
        "implementation_claim_authorization_id": validator.EXPECTED_AUTHORIZATION_ID,
        "implementation_pr_base_ref_policy": "must_equal_repository_default_branch",
        "trusted_evaluator_event": "issue_comment",
        "trusted_scope_attestation_command": validator.EXPECTED_ATTESTATION_COMMAND,
        "trusted_scope_readiness_command": validator.EXPECTED_READINESS_COMMAND,
        "trusted_evaluator_source": "default_branch_issue_comment_workflow_plus_exact_default_branch_base_git_object",
        "trusted_scope_status_context": validator.EXPECTED_STATUS_CONTEXT,
        "trusted_scope_readiness_status_context": validator.EXPECTED_READY_CONTEXT,
        "trusted_scope_status_publication": "pending_then_final_coordinate_bound_evidence_on_resolved_pr_head",
        "trusted_scope_status_evidence_role": "evidence_only_not_standalone_merge_authority",
        "trusted_scope_freshness_rule": "merge_readiness_revalidates_live_head_base_default_tip_label_and_trusted_status_run_provenance",
        "trusted_scope_concurrency_rule": "per_pr_cancel_in_progress",
        "trusted_status_creator_login": "github-actions[bot]",
        "trusted_status_creator_id": 41898282,
        "trusted_scope_merge_preflight_rule": "live_revalidate_ready_evidence_current_coordinates_label_and_workflow_run_immediately_before_merge",
        "trusted_scope_readiness_validator": validator.EXPECTED_READINESS_VALIDATOR,
        "same_repository_required": True,
        "implementation_pr_requires_trusted_scope_attestation_on_exact_head": True,
        "implementation_pr_requires_trusted_scope_readiness_on_exact_head_base": True,
        "candidate_controlled_relevance_inference": "forbidden",
        "allowed_prefixes": list(validator.EXPECTED_PREFIXES),
        "allowed_exact_paths": list(validator.EXPECTED_EXACT),
        "diff_enforcement_rule": validator.EXPECTED_RULE,
    }


def canonical_runtime() -> str:
    payload = {
        "name": validator.EXPECTED_RUNTIME_NAME,
        "on": {"pull_request": {}, "workflow_dispatch": {}},
        "permissions": {},
        "jobs": {
            "g2-runtime": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@" + "a" * 40},
                    {"uses": "actions/setup-python@" + "b" * 40},
                    {"uses": "actions/setup-node@" + "c" * 40},
                    {"run": validator.EXPECTED_RUNTIME_ENTRYPOINT},
                ],
            }
        },
    }
    return json.dumps(payload)


def main() -> int:
    policy = canonical_policy()
    validator.configured_policy(policy)

    for key, bad, fragment in (
        ("implementation_pr_head_prefix", "impl/other", "head prefix"),
        ("implementation_pr_required_label", "other", "required label"),
        ("trusted_evaluator_event", "pull_request_target", "trusted evaluator event"),
        ("candidate_controlled_relevance_inference", "allowed", "candidate relevance inference"),
    ):
        mutated = copy.deepcopy(policy)
        mutated[key] = bad
        must_raise(lambda m=mutated: validator.configured_policy(m), fragment)

    mutated = copy.deepcopy(policy)
    mutated["allowed_prefixes"].append("src/jlmirror_monitoring/")
    must_raise(lambda: validator.configured_policy(mutated), "allowed prefixes")

    if validator.validate_paths(["src/jlmirror_monitoring/source.py"], policy) == []:
        raise AssertionError("shared Monitoring path unexpectedly admitted")
    if validator.validate_paths(["src/jlmirror_g2/onboarding.py"], policy):
        raise AssertionError("canonical G2 path unexpectedly rejected")

    runtime = canonical_runtime()
    if validator.validate_runtime_workflow_text(runtime):
        raise AssertionError("canonical runtime workflow unexpectedly rejected")

    payload = json.loads(runtime)
    payload["permissions"] = {"statuses": "write"}
    if not validator.validate_runtime_workflow_text(json.dumps(payload)):
        raise AssertionError("privileged runtime workflow unexpectedly accepted")

    payload = json.loads(runtime)
    payload["jobs"]["g2-runtime"]["steps"].append({"run": "curl https://example.invalid"})
    if not validator.validate_runtime_workflow_text(json.dumps(payload)):
        raise AssertionError("extra runtime responsibility unexpectedly accepted")

    if not validator.validate_runtime_workflow_text("name: yaml-not-json"):
        raise AssertionError("noncanonical YAML surface unexpectedly accepted")

    print("g2_implementation_scope_falsifier=PASS policy_mutations=5 path_cases=2 runtime_cases=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
