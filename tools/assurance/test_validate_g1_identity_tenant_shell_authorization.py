#!/usr/bin/env python3
from __future__ import annotations

import ast
import copy
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "assurance"))
import validate_g1_identity_tenant_shell_authorization as validator

ISOLATED_READINESS_CHILD_FLAG = "--g1-readiness-isolated-child"
ISOLATED_READINESS_PASS = "g1_readiness_isolated_permissive_rejection=PASS"
DELEGATION_CONTRACTS = {
    "falsify_trusted_scope_readiness_execution": (
        "test_validate_g1_identity_tenant_shell_scope_readiness",
        ("falsify_live_readiness_guards",),
    ),
    "falsify_implementation_scope_gate_execution": (
        "test_validate_g1_identity_tenant_shell_implementation_scope",
        (
            "falsify_real_git_diff_gate",
            "falsify_candidate_metadata_fail_closed",
            "falsify_all_voluntary_metadata_omission",
            "falsify_runtime_workflow_semantics",
        ),
    ),
}
FORBIDDEN_DELEGATION_NAMESPACE_CALLS = {
    "__import__", "delattr", "eval", "exec", "getattr", "globals", "hasattr", "locals", "setattr", "vars",
}


def _require_delegation_source_integrity() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=__file__)
    lines = source.splitlines()
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    for function_name, (module_name, expected_calls) in DELEGATION_CONTRACTS.items():
        function = functions.get(function_name)
        if function is None:
            raise AssertionError(f"delegation integrity missing outer probe: {function_name}")
        imports: list[tuple[str, ast.Import]] = []
        for statement in function.body:
            if not isinstance(statement, ast.Import):
                continue
            for imported in statement.names:
                if imported.name == module_name:
                    imports.append((imported.asname or imported.name, statement))
        if len(imports) != 1:
            raise AssertionError(f"delegation integrity import drift: {function_name}->{module_name}")
        alias = imports[0][0]
        direct_calls: list[tuple[str, ast.Expr, ast.Name]] = []
        for statement in function.body:
            if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
                continue
            call = statement.value
            if (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == alias
                and not call.args
                and not call.keywords
            ):
                direct_calls.append((call.func.attr, statement, call.func.value))
        if tuple(name for name, _, _ in direct_calls) != expected_calls:
            raise AssertionError(
                f"delegation integrity direct-call drift: {function_name}:"
                f"actual={tuple(name for name, _, _ in direct_calls)} expected={expected_calls}"
            )
        alias_names = [node for node in ast.walk(function) if isinstance(node, ast.Name) and node.id == alias]
        direct_name_nodes = [name_node for _, _, name_node in direct_calls]
        if len(alias_names) != len(direct_name_nodes) or {id(node) for node in alias_names} != {id(node) for node in direct_name_nodes}:
            raise AssertionError(f"delegation integrity alias interception/rebinding detected: {function_name}:{alias}")
        for expected_name, statement, _ in direct_calls:
            expected_line = f"{alias}.{expected_name}()"
            if statement.lineno != statement.end_lineno or lines[statement.lineno - 1].strip() != expected_line:
                raise AssertionError(f"delegation integrity physical-line drift: {function_name}:{expected_line}")
            if ast.get_source_segment(source, statement.value) != expected_line:
                raise AssertionError(f"delegation integrity expression drift: {function_name}:{expected_line}")
        for node in ast.walk(function):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_DELEGATION_NAMESPACE_CALLS:
                raise AssertionError(f"delegation integrity dynamic namespace access forbidden: {function_name}:{node.func.id}")
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in {"inspect", "builtins"}:
                raise AssertionError(f"delegation integrity reflective namespace access forbidden: {function_name}:{node.value.id}.{node.attr}")


def must_fail(mutator, fragment: str) -> None:
    _require_delegation_source_integrity()
    data = copy.deepcopy(validator.load())
    mutator(data)
    try:
        validator.validate_manifest(data)
    except AssertionError as exc:
        if fragment not in str(exc):
            raise AssertionError(f"expected {fragment!r}, got {exc!r}")
        return
    raise AssertionError(f"mutation unexpectedly accepted: {fragment}")


def _isolated_readiness_permissive_rejection_child() -> int:
    sys.argv = [str(Path(__file__).resolve())]
    import test_validate_g1_identity_tenant_shell_scope_readiness as readiness_falsifier

    base_sha = "a" * 40
    head_sha = "b" * 40
    run_id = 123456789
    calls: list[dict] = []

    def permissive_verifier(**kwargs):
        calls.append(copy.deepcopy(kwargs))
        return base_sha, head_sha, run_id

    readiness_falsifier.readiness.validate_live_readiness = permissive_verifier
    probe = getattr(readiness_falsifier, "falsify_live_readiness_guards", None)
    if not callable(probe):
        raise AssertionError("isolated G1 readiness probe missing")
    try:
        probe()
    except AssertionError as exc:
        if len(calls) != 3:
            raise AssertionError(f"isolated G1 readiness permissive rejection boundary drift: calls={len(calls)} expected=3") from exc
        if "readiness mutation unexpectedly accepted:" not in str(exc):
            raise AssertionError(f"isolated G1 readiness permissive rejection is not authoritative: {exc}") from exc
        print(ISOLATED_READINESS_PASS)
        return 0
    except Exception as exc:
        raise AssertionError(f"isolated G1 readiness permissive rejection failed unexpectedly: {type(exc).__name__}:{exc}") from exc
    raise AssertionError("isolated G1 readiness probe accepted a permissive verifier")


def _assert_isolated_readiness_permissive_rejection() -> None:
    script = str(Path(__file__).resolve())
    child_code = (
        "import runpy,sys;"
        f"sys.argv=[{script!r},{ISOLATED_READINESS_CHILD_FLAG!r}];"
        f"runpy.run_path({script!r},run_name='__main__')"
    )
    clean_env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT") if key in os.environ}
    completed = subprocess.run(
        [sys.executable, "-I", "-c", child_code],
        cwd=str(ROOT),
        env=clean_env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise AssertionError(f"isolated G1 readiness child failed: rc={completed.returncode}: {detail}")
    if ISOLATED_READINESS_PASS not in completed.stdout.splitlines():
        raise AssertionError(f"isolated G1 readiness child missing authenticated PASS marker: {completed.stdout!r}")


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
    _assert_isolated_readiness_permissive_rejection()
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
    scope_falsifier.falsify_runtime_workflow_semantics()


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
    if ISOLATED_READINESS_CHILD_FLAG in sys.argv:
        return _isolated_readiness_permissive_rejection_child()
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
    print("g1_identity_tenant_shell_authorization_falsification=PASS authority_escalation=blocked implementation_path_expansion=blocked runtime_workflow_semantics=bounded trusted_default_branch_caller=bound status=evidence-only readiness=source-authenticated-live-preflight+isolated-permissive-rejection delegation_aliases=single-purpose-bound spoofed_status=blocked skip_ci_stale_base=blocked mutable_label=blocked candidate_workflow_authority=blocked candidate_relevance_bypass=blocked real_git_diff=executed")
    return 0


if __name__ == "__main__":
    main()