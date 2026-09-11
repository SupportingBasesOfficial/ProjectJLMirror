#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import validate_adversarial_learning as v
import validate_adversarial_learning_strict as s
import validate_repository as vr

ROOT = Path(__file__).resolve().parents[2]
FILES = [v.TAXONOMY, v.INVARIANTS, v.LEDGER, v.BOOTSTRAP_EXCEPTIONS, v.STOP_POLICY]
D4C_CURRENT_WORKFLOWS = [
    Path(".github/workflows/d4-eventing-async-entry-gate.yml"),
    Path(".github/workflows/d4-d-profile-selection.yml"),
]
GUARDRAIL_FILES = [
    v.WORKFLOW,
    s.HEAD_STATUS_WORKFLOW,
    *D4C_CURRENT_WORKFLOWS,
    Path("tools/assurance/d4d_trace_context_source.py"),
    Path("tools/assurance/test_validate_d4d_trace_context_source.py"),
    Path("tools/assurance/test_validate_adversarial_learning.py"),
    Path("tools/assurance/validate_adversarial_learning_strict.py"),
    Path("tools/assurance/validate_repository.py"),
    Path("tools/assurance/test_validate_d4d_selection.py"),
    Path("tools/assurance/test_validate_d4c_selection.py"),
    Path("tools/assurance/d4b_wire_schema/test_source_evidence.py"),
    Path("tools/wave4/run_zabbix_initial_validation_postgres_conformance.sh"),
    Path("tools/wave4/validate_zabbix_initial_validation_worker.py"),
    Path("implementation/wave-4-host-inventory-authorization/AUTHORIZATION_MANIFEST.json"),
]


def clone(tmp: Path) -> None:
    for rel in FILES + GUARDRAIL_FILES:
        dst = tmp / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    shard_src = ROOT / v.LEDGER_SHARDS
    if shard_src.is_dir():
        for src in shard_src.glob("*.json"):
            rel = v.LEDGER_SHARDS / src.name
            dst = tmp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def mutate_json(root: Path, rel: Path, fn) -> None:
    path = root / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def mutate_text(root: Path, rel: Path, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, f"expected mutation marker missing: {old}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def expect_failure(mutator, *, comments=None) -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        clone(root)
        mutator(root)
        review_comments = None
        if comments is not None:
            review_comments = root / "comments.json"
            review_comments.write_text(json.dumps(comments), encoding="utf-8")
        assert s.validate(root, review_comments), "mutation unexpectedly accepted"


def expect_repository_failure(mutator) -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        clone(root)
        mutator(root)
        assert vr.validate_repository(root), "repository-policy mutation unexpectedly accepted"


def falsify_stale_d4c_current_workflow_projection() -> None:
    def mutate(root: Path) -> None:
        rel = D4C_CURRENT_WORKFLOWS[0]
        mutate_text(
            root,
            rel,
            "assert d4c['candidate']==expected_c and d4c['candidate_status']=='selected_c2_delivery_recovery_profile' and d4c['state']=='selected_candidate'",
            "assert d4c['candidate'] is None and d4c['candidate_status']=='not_selected' and d4c['state']=='candidate_selection_open'",
        )
    expect_failure(mutate)


def falsify_top_level_review_surface_coverage() -> None:
    expect_failure(lambda r: mutate_text(r, v.WORKFLOW, "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments?per_page=100", "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/labels?per_page=100"))


def falsify_incidental_guardrail_substring() -> None:
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0]["guardrails"][0].__setitem__("probe", "TraceContext")))


def falsify_unreachable_guardrail_call() -> None:
    def mutate(root: Path) -> None:
        mutate_text(root, Path("tools/assurance/test_validate_adversarial_learning.py"), "    falsify_incidental_guardrail_substring()\n", "    if False:\n        falsify_incidental_guardrail_substring()\n")
    expect_failure(mutate)


def falsify_missing_falsifier_entrypoint() -> None:
    def mutate(root: Path) -> None:
        mutate_text(root, Path("tools/assurance/test_validate_adversarial_learning.py"), 'if __name__ == "__main__":\n    main()\n', 'if False:\n    main()\n')
    expect_failure(mutate)


def falsify_terminated_falsifier_entrypoint() -> None:
    def mutate(root: Path) -> None:
        mutate_text(root, Path("tools/assurance/test_validate_adversarial_learning.py"), 'if __name__ == "__main__":\n    main()\n', 'if __name__ == "__main__":\n    raise SystemExit(0)\n    main()\n')
    expect_failure(mutate)


def falsify_head_status_publication() -> None:
    expect_failure(lambda r: mutate_text(r, s.HEAD_STATUS_WORKFLOW, 'statuses/${PR_HEAD_SHA}', 'statuses/${GITHUB_SHA}'))


def falsify_noop_falsifier_body() -> None:
    def mutate(root: Path) -> None:
        mutate_text(root, Path("tools/assurance/test_validate_adversarial_learning.py"), 'def falsify_incidental_guardrail_substring() -> None:\n    expect_failure(', 'def falsify_incidental_guardrail_substring() -> None:\n    return\n    expect_failure(')
    expect_failure(mutate)


def falsify_assert_true_guardrail() -> None:
    def mutate(root: Path) -> None:
        path = root / Path("tools/assurance/test_validate_adversarial_learning.py")
        text = path.read_text(encoding="utf-8")
        start = text.index("def falsify_incidental_guardrail_substring() -> None:\n")
        end = text.index("\n\ndef falsify_unreachable_guardrail_call", start)
        text = text[:start] + "def falsify_incidental_guardrail_substring() -> None:\n    assert True\n" + text[end:]
        path.write_text(text, encoding="utf-8")
    expect_failure(mutate)


def falsify_dead_branch_negative_helper() -> None:
    def mutate(root: Path) -> None:
        path = root / Path("tools/assurance/test_validate_adversarial_learning.py")
        text = path.read_text(encoding="utf-8")
        start = text.index("def falsify_incidental_guardrail_substring() -> None:\n")
        end = text.index("\n\ndef falsify_unreachable_guardrail_call", start)
        replacement = "def falsify_incidental_guardrail_substring() -> None:\n    if False:\n        expect_failure(lambda r: None)\n"
        path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
    expect_failure(mutate)


def falsify_priority_prefixed_material_finding() -> None:
    expect_failure(lambda r: None, comments=[[{"id": 9999999998, "body": "[P1] unmapped material finding"}]])


def falsify_bootstrap_exception_scope() -> None:
    expect_failure(lambda r: mutate_json(r, v.BOOTSTRAP_EXCEPTIONS, lambda d: d["exceptions"][0].__setitem__("pr", 119)))


def falsify_stop_policy_relaxation() -> None:
    expect_failure(lambda r: mutate_json(r, v.STOP_POLICY, lambda d: d.__setitem__("merge_blocking_severities", ["P0"])))


def falsify_privileged_job_executes_pr_content() -> None:
    def mutate(root: Path) -> None:
        mutate_text(root, s.HEAD_STATUS_WORKFLOW, "      - name: Publish pending reconciliation status on resolved PR HEAD\n", "      - name: Unsafe PR-controlled execution\n        run: python3 tools/assurance/validate_adversarial_learning.py\n      - name: Publish pending reconciliation status on resolved PR HEAD\n")
    expect_repository_failure(mutate)


def falsify_implicit_gh_api_write() -> None:
    def mutate(root: Path) -> None:
        mutate_text(root, s.HEAD_STATUS_WORKFLOW, "          gh api --paginate --slurp \"repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments?per_page=100\" > runtime-evidence/top-level-pr-comments.json\n", "          gh api \"repos/${GITHUB_REPOSITORY}/statuses/${PR_HEAD_SHA}\" -f state=success\n          gh api --paginate --slurp \"repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments?per_page=100\" > runtime-evidence/top-level-pr-comments.json\n")
    expect_repository_failure(mutate)


def falsify_spoofed_status_endpoint() -> None:
    def mutate(root: Path) -> None:
        mutate_text(root, s.HEAD_STATUS_WORKFLOW, 'gh api --method POST "repos/${GITHUB_REPOSITORY}/statuses/${PR_HEAD_SHA}"', 'gh api --method POST "repos/${GITHUB_REPOSITORY}/statuses/0000000000000000000000000000000000000000" # statuses/${PR_HEAD_SHA}')
    expect_repository_failure(mutate)


def falsify_reconciliation_concurrency() -> None:
    expect_failure(lambda r: mutate_text(r, s.HEAD_STATUS_WORKFLOW, "  cancel-in-progress: true\n", "  cancel-in-progress: false\n"))


def falsify_unbound_manual_dispatch() -> None:
    expect_failure(lambda r: mutate_text(r, s.HEAD_STATUS_WORKFLOW, "  issue_comment:\n", "  workflow_dispatch:\n  issue_comment:\n"))


def falsify_non_strict_deterministic_reconciliation() -> None:
    expect_failure(lambda r: mutate_text(r, v.WORKFLOW, "validate_adversarial_learning_strict.py --root . --review-comments", "validate_adversarial_learning.py --root . --review-comments"))


def falsify_wave4_authorization_exact_path_allowlist() -> None:
    validator = ROOT / "tools/assurance/validate_wave4_monitoring_authorization.py"
    text = validator.read_text(encoding="utf-8")
    assert "ALLOWED_PR_PATHS = {" in text, "Wave 4 authorization must use an exact path allowlist"
    assert "ALLOWED_PR_PATH_PREFIXES" not in text, "Wave 4 authorization must not regress to prefix allowlisting"
    assert "path in ALLOWED_PR_PATHS" in text, "Wave 4 authorization scope check must require exact path membership"
    assert "implementation/wave-4-monitoring-authorization/AUTHORIZATION.md" in text
    assert "implementation/wave-4-monitoring-authorization/AUTHORIZATION_MANIFEST.json" in text
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0]["guardrails"][0].__setitem__("probe", "nonexistent_exact_allowlist_probe")))


def falsify_wave4_authority_toctou_guardrail() -> None:
    sql = (ROOT / "sql/wave4/003_zabbix_initial_validation_worker.sql").read_text(encoding="utf-8")
    conformance = (ROOT / "tools/wave4/run_zabbix_initial_validation_postgres_conformance.sh").read_text(encoding="utf-8")
    validator = (ROOT / "tools/wave4/validate_zabbix_initial_validation_worker.py").read_text(encoding="utf-8")
    assert "FOR UPDATE OF s" in sql, "Wave 4 completion must hold the authoritative source row lock"
    assert "race=source_row_lock_blocks_concurrent_edit" in conformance, "Wave 4 concurrency falsifier missing"
    assert 'require("FOR UPDATE OF s" in sql' in validator, "Wave 4 validator does not require source-row lock"
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_adversarial_learning.py"),
            "    falsify_wave4_authority_toctou_guardrail()\n",
            "",
        )
    )


def falsify_wave4_host_inventory_authority_transition() -> None:
    path = Path("implementation/wave-4-host-inventory-authorization/AUTHORIZATION_MANIFEST.json")
    manifest = json.loads((ROOT / path).read_text(encoding="utf-8"))
    assert manifest.get("effective_rule") == "this_successor_clarification_becomes_canonical_and_unblocks_exact_host_inventory_implementation_only_after_exact_head_review_and_separately_authorized_merge"
    assert manifest.get("canonical_effect_after_merge") == "host_inventory_ingestion_authorized_for_exact_accepted_behavior_with_monitoring_resource_kind_host"
    assert manifest.get("implementation_authority_before_merge") == "blocked"
    assert manifest.get("implementation_authority_after_merge") == "granted_for_exact_host_inventory_ingestion_slice_only"
    finding = manifest.get("post_merge_finding") or {}
    assert finding.get("implementation_blocked_until_this_clarification_is_canonical") is True
    assert finding.get("canonical_resolution_after_merge") == "resolved_by_binding_monitoring_resource_kind_host_and_preserving_separate_provider_object_kind_and_device_taxonomy"
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_adversarial_learning.py"),
            "    falsify_wave4_host_inventory_authority_transition()\n",
            "",
        )
    )


def falsify_wave4_metric_definition_claimed_input_liveness_guardrail() -> None:
    migration = (ROOT / "sql/wave4/029_zabbix_metric_definitions_claimed_input_liveness.sql").read_text(encoding="utf-8")
    conformance = (ROOT / "tools/wave4/run_zabbix_metric_definitions_claimed_input_liveness_postgres_conformance.sh").read_text(encoding="utf-8")
    validator = (ROOT / "tools/wave4/validate_zabbix_metric_definitions.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/wave4-monitoring-source-foundation.yml").read_text(encoding="utf-8")
    claim_marker = "FROM monitoring.monitoring_sync_operation AS o"
    input_marker = "p_items IS NULL OR jsonb_typeof(p_items) IS DISTINCT FROM 'array'"
    assert claim_marker in migration and input_marker in migration
    assert migration.index(claim_marker) < migration.index(input_marker), "claimed-input validation must occur only after resolving running claim authority"
    assert "metric-reconciliation-" in migration and "claim_token=NULL" in migration
    assert "docker exec -i \"$PG_CONTAINER\" psql" in conformance, "overbound stdin falsifier must actually execute in PostgreSQL"
    assert "schema=001-029" in conformance and "overbound=terminal" in conformance and "collision=owner-derived" in conformance
    assert "M029" in validator and "CLAIMED_INPUT_LIVENESS" in validator and "claimed_input_liveness=001-029" in validator
    assert "Execute claimed metric-definition input liveness on final schema 001-029" in workflow
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_adversarial_learning.py"),
            "    falsify_wave4_metric_definition_claimed_input_liveness_guardrail()\n",
            "",
        )
    )


def main() -> None:
    assert not s.validate(ROOT)

    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("class_id", "UNKNOWN")))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("invariant_ids", ["UNKNOWN"])))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("root_cause", "local patch")))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("horizontal_audit", [])))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("guardrails", [])))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0]["guardrails"][0].__setitem__("path", "missing/file.py")))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0]["guardrails"][0].__setitem__("probe", "fictional_probe_that_does_not_exist")))
    falsify_incidental_guardrail_substring()
    falsify_unreachable_guardrail_call()
    falsify_missing_falsifier_entrypoint()
    falsify_terminated_falsifier_entrypoint()
    falsify_head_status_publication()
    falsify_noop_falsifier_body()
    falsify_assert_true_guardrail()
    falsify_dead_branch_negative_helper()
    falsify_priority_prefixed_material_finding()
    falsify_privileged_job_executes_pr_content()
    falsify_implicit_gh_api_write()
    falsify_spoofed_status_endpoint()
    falsify_reconciliation_concurrency()
    falsify_unbound_manual_dispatch()
    falsify_non_strict_deterministic_reconciliation()
    falsify_stale_d4c_current_workflow_projection()
    falsify_wave4_authorization_exact_path_allowlist()
    falsify_wave4_authority_toctou_guardrail()
    falsify_wave4_host_inventory_authority_transition()
    falsify_wave4_metric_definition_claimed_input_liveness_guardrail()
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][1].__setitem__("review_comment_id", 3961647090)))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][6].__setitem__("guardrail_generation", 1)))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("systemic_guardrail_updated", False)))
    falsify_top_level_review_surface_coverage()
    falsify_bootstrap_exception_scope()
    falsify_stop_policy_relaxation()
    expect_failure(lambda r: None, comments=[[{"id": 9999999999, "body": "**P1 Badge** unmapped material finding"}]])

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        clone(root)
        comments = root / "comments.json"
        comments.write_text(json.dumps([[[{"id": 3961647090, "body": "**P1 Badge** mapped finding"}]]]), encoding="utf-8")
        assert not s.validate(root, comments)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        clone(root)
        comments = root / "comments.json"
        comments.write_text(json.dumps([[{"id": 3963734258, "body": "**P1 Badge** exact bootstrap finding"}]]), encoding="utf-8")
        assert not s.validate(root, comments)

    print("adversarial_learning_falsification=PASS entrypoint_termination=blocked no_op_assertion=blocked dead_branch_helper=blocked privileged_job_pr_execution=blocked implicit_api_write=blocked exact_status_endpoint=bound reconciliation_concurrency=fresh manual_dispatch=removed strict_reconciliation=all-surfaces stale_d4c_workflow_projection=blocked d4c_product_authority_guardrail=attested wave4_exact_path_allowlist=attested wave4_authority_toctou=source-row-lock+postgres-race host_inventory_authority_transition=attested metric_definition_claimed_input_liveness=claim-first+001-029")


if __name__ == "__main__":
    main()
