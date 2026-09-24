#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import validate_adversarial_learning as v
import validate_adversarial_learning_strict as s
import validate_repository as vr
import validate_governance_pr_scope as gps

ROOT = Path(__file__).resolve().parents[2]
FILES = [v.TAXONOMY, v.INVARIANTS, v.LEDGER, v.BOOTSTRAP_EXCEPTIONS, v.STOP_POLICY]
D4C_CURRENT_WORKFLOWS = [
    Path(".github/workflows/d4-eventing-async-entry-gate.yml"),
    Path(".github/workflows/d4-d-profile-selection.yml"),
]
DELIVERY_GUARDRAIL_FILES = [
    Path("tools/assurance/validate_ai_e2e_delivery.py"),
    Path("docs/00-foundation/ai-e2e-delivery/AI-E2E-DELIVERY-CONSTITUTION.md"),
    Path("docs/00-foundation/ai-e2e-delivery/VERTICAL-SLICE-DELIVERY-MODEL.md"),
    Path("docs/00-foundation/ai-e2e-delivery/PRODUCT-EXECUTION-ROADMAP.md"),
    Path("docs/00-foundation/ai-e2e-delivery/DAY-1-IMPLEMENTATION-BOOTSTRAP.md"),
    Path("implementation/e2e-delivery/EXECUTION_MANIFEST.json"),
]
GUARDRAIL_FILES = [
    v.WORKFLOW,
    s.HEAD_STATUS_WORKFLOW,
    *D4C_CURRENT_WORKFLOWS,
    Path("tools/assurance/d4d_trace_context_source.py"),
    Path("tools/assurance/test_validate_d4d_trace_context_source.py"),
    Path("tools/assurance/test_validate_adversarial_learning.py"),
    Path("tools/assurance/test_validate_g1_identity_tenant_shell_authorization.py"),
    Path("tools/assurance/test_validate_g1_identity_tenant_shell_implementation_scope.py"),
    Path("tools/assurance/validate_g1_identity_tenant_shell_implementation_scope.py"),
    Path("tools/assurance/test_validate_g1_identity_tenant_shell_scope_readiness.py"),
    Path("tools/assurance/validate_g1_identity_tenant_shell_scope_readiness.py"),
    Path("tools/assurance/validate_adversarial_learning_strict.py"),
    Path("tools/assurance/validate_repository.py"),
    Path("tools/assurance/validate_governance_pr_scope.py"),
    Path("docs/16-implementation-readiness/66-alert-evaluation-incident-response-decision-record.md"),
    Path("tools/assurance/test_validate_d4d_selection.py"),
    Path("tools/assurance/test_validate_d4c_selection.py"),
    Path("tools/assurance/d4b_wire_schema/test_source_evidence.py"),
    Path("tools/wave4/run_zabbix_initial_validation_postgres_conformance.sh"),
    Path("tools/wave4/validate_zabbix_initial_validation_worker.py"),
    Path("implementation/wave-4-host-inventory-authorization/AUTHORIZATION_MANIFEST.json"),
    *DELIVERY_GUARDRAIL_FILES,
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
            review_comments = root / "review-comments.json"
            review_comments.write_text(json.dumps(comments), encoding="utf-8")
        errors = s.validate(root, review_comments)
        assert errors, "adversarial learning mutation unexpectedly passed"


def expect_repository_failure(mutator) -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        clone(root)
        mutator(root)
        errors = vr.validate_repository(root)
        assert errors, "repository-policy mutation unexpectedly passed"


def falsify_incidental_guardrail_substring() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_d4c_selection.py"),
            "def falsify_selection_record_product_authority():",
            "def renamed_selection_record_product_authority():",
        )
    )


def falsify_unreachable_guardrail_call() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_d4c_selection.py"),
            " falsify_selection_record_product_authority()\n",
            " if False:\n  falsify_selection_record_product_authority()\n",
        )
    )


def falsify_missing_falsifier_entrypoint() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_d4c_selection.py"),
            "if __name__=='__main__': main()\n",
            "",
        )
    )


def falsify_terminated_falsifier_entrypoint() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_d4c_selection.py"),
            " falsify_selection_record_product_authority()\n",
            " return 0\n falsify_selection_record_product_authority()\n",
        )
    )


def falsify_head_status_publication() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            s.HEAD_STATUS_WORKFLOW,
            "statuses/${PR_HEAD_SHA}",
            "statuses/${GITHUB_SHA}",
        )
    )


def falsify_noop_falsifier_body() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_d4c_selection.py"),
            " def grant_product(selection,ledger,state,evaluation): selection['canonical_product_implementation_authority']='granted'\n must_fail(grant_product,'Product authority escalation')",
            " pass",
        )
    )


def falsify_assert_true_guardrail() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_d4c_selection.py"),
            " must_fail(grant_product,'Product authority escalation')",
            " assert True",
        )
    )


def falsify_dead_branch_negative_helper() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_d4c_selection.py"),
            " must_fail(grant_product,'Product authority escalation')",
            " if False:\n  must_fail(grant_product,'Product authority escalation')",
        )
    )


def falsify_priority_prefixed_material_finding() -> None:
    expect_failure(lambda r: None, comments=[[{"id": 9999999998, "body": "[P1] unmapped material finding"}]])


def falsify_privileged_job_executes_pr_content() -> None:
    def mutate(root: Path) -> None:
        mutate_text(
            root,
            s.HEAD_STATUS_WORKFLOW,
            "      - name: Publish pending reconciliation status on resolved PR HEAD\n",
            "      - name: Unsafe PR-controlled execution\n        run: python3 tools/assurance/validate_adversarial_learning.py\n      - name: Publish pending reconciliation status on resolved PR HEAD\n",
        )
    expect_repository_failure(mutate)


def falsify_implicit_gh_api_write() -> None:
    def mutate(root: Path) -> None:
        mutate_text(
            root,
            s.HEAD_STATUS_WORKFLOW,
            "          gh api --paginate --slurp \"repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments?per_page=100\" > runtime-evidence/top-level-pr-comments.json\n",
            "          gh api \"repos/${GITHUB_REPOSITORY}/statuses/${PR_HEAD_SHA}\" -f state=success\n          gh api --paginate --slurp \"repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments?per_page=100\" > runtime-evidence/top-level-pr-comments.json\n",
        )
    expect_repository_failure(mutate)


def falsify_spoofed_status_endpoint() -> None:
    def mutate(root: Path) -> None:
        mutate_text(
            root,
            s.HEAD_STATUS_WORKFLOW,
            'gh api --method POST "repos/${GITHUB_REPOSITORY}/statuses/${PR_HEAD_SHA}"',
            'gh api --method POST "repos/${GITHUB_REPOSITORY}/statuses/0000000000000000000000000000000000000000" # statuses/${PR_HEAD_SHA}',
        )
    expect_repository_failure(mutate)


def falsify_reconciliation_concurrency() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            s.HEAD_STATUS_WORKFLOW,
            "cancel-in-progress: true",
            "cancel-in-progress: false",
        )
    )


def falsify_unbound_manual_dispatch() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            s.HEAD_STATUS_WORKFLOW,
            "  issue_comment:\n",
            "  workflow_dispatch:\n  issue_comment:\n",
        )
    )


def falsify_non_strict_deterministic_reconciliation() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            v.WORKFLOW,
            "validate_adversarial_learning_strict.py --root . --review-comments",
            "validate_adversarial_learning.py --root . --review-comments",
        )
    )


def falsify_stale_d4c_current_workflow_projection() -> None:
    current = "d4c['candidate_status']=='selected_c2_delivery_recovery_profile'"
    stale = "d4c['candidate_status']=='not_selected'"
    expect_failure(lambda r: mutate_text(r, D4C_CURRENT_WORKFLOWS[0], current, stale))


def falsify_top_level_review_surface_coverage() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            v.WORKFLOW,
            "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments?per_page=100",
            "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/comments?per_page=100",
        )
    )


def falsify_bootstrap_exception_scope() -> None:
    expect_failure(lambda r: mutate_json(r, v.BOOTSTRAP_EXCEPTIONS, lambda d: d["exceptions"][0].__setitem__("pr", 119)))


def falsify_stop_policy_relaxation() -> None:
    expect_failure(lambda r: mutate_json(r, v.STOP_POLICY, lambda d: d.__setitem__("merge_blocking_severities", ["P0"])))



def falsify_governance_only_pr_scope() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_adversarial_learning.py"),
            "    falsify_governance_only_pr_scope()\n",
            "",
        )
    )
    allowed_docs = [
        "docs/16-implementation-readiness/65-frontend-stack-decision-record.md",
        "governance/adversarial/learning-ledger.d/pr-example.json",
        "tools/assurance/validate_governance_pr_scope.py",
        "tools/assurance/test_validate_adversarial_learning.py",
        ".github/workflows/deterministic-assurance.yml",
    ]
    assert not gps.scope_errors(head_ref="docs/example", changed_paths=allowed_docs)

    for forbidden in (
        "Makefile",
        "docker/db-init/001-create-app-role.sql",
        "tests/wave2/__init__.py",
        "src/jlmirror_monitoring/metric_history.py",
        "sql/monitoring/001.sql",
        "apps/api/main.py",
    ):
        errors = gps.scope_errors(head_ref="docs/example", changed_paths=allowed_docs + [forbidden])
        assert errors and any(forbidden in error for error in errors), (forbidden, errors)

    unsupported_governance_tool = gps.scope_errors(
        head_ref="docs/example",
        changed_paths=["tools/assurance/unrelated_validator.py"],
    )
    assert unsupported_governance_tool and "tools/assurance/unrelated_validator.py" in unsupported_governance_tool[0]

    governance_errors = gps.scope_errors(
        head_ref="governance/example",
        changed_paths=["governance/adversarial/example.json", "src/domain/runtime.py"],
    )
    assert governance_errors and "src/domain/runtime.py" in governance_errors[0]

    assert not gps.scope_errors(
        head_ref="impl/g11-example",
        changed_paths=["src/domain/runtime.py"],
    )


def falsify_g10_auto_incident_extension_boundary() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_adversarial_learning.py"),
            "    falsify_g10_auto_incident_extension_boundary()\n",
            "",
        )
    )
    path = ROOT / "docs/16-implementation-readiness/66-alert-evaluation-incident-response-decision-record.md"
    text = path.read_text(encoding="utf-8")
    required = (
        "outside current G10 authority",
        "separately accepted G10 extension",
        "automatic Alert-to-Incident creation",
        "G10 automatic incident extension",
        "Alert != Incident",
        "orchestration cannot write ITSM tables",
    )
    for marker in required:
        assert marker in text, f"record 66 missing G10 extension boundary: {marker}"

    weakened = text.replace(
        "a separately accepted G10 extension must explicitly authorize automatic Alert-to-Incident creation",
        "the existing G10 boundary is sufficient for automatic Alert-to-Incident creation",
        1,
    )
    assert "a separately accepted G10 extension must explicitly authorize automatic Alert-to-Incident creation" not in weakened
    assert "the existing G10 boundary is sufficient" in weakened

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
    manifest = json.loads((ROOT / "implementation/wave-4-host-inventory-authorization/AUTHORIZATION_MANIFEST.json").read_text(encoding="utf-8"))
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



def _g10_review_guardrail_errors(sql: str) -> list[str]:
    errors: list[str] = []
    if "SELECT alert_id,lifecycle_state,opened_at,resolved_at" not in sql:
        errors.append("G10 Alert summary must use canonical opened_at")
    if "SELECT alert_id,lifecycle_state,created_at,resolved_at" in sql:
        errors.append("G10 Alert summary must not reference non-canonical created_at")
    if "(o.sync_state='dispatching' AND o.claim_expires_at<=transaction_timestamp())" not in sql:
        errors.append("G10 sync discovery must surface expired dispatching leases")
    if "FROM pg_auth_members" not in sql or "roleid=v_role.oid OR member=v_role.oid" not in sql:
        errors.append("G10 privileged roles must reject incoming and outgoing memberships")
    if "hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10)" not in sql:
        errors.append("G10 Incident creation must serialize same logical action")
    if "g10.transition_equivalence_conflict" not in sql or "v_existing_transition.to_state IS DISTINCT FROM p_target_state" not in sql:
        errors.append("G10 transition replay must reject divergent target state")
    if "UNIQUE (tenant_id,sync_identity)" in sql:
        errors.append("G10 retries must reuse provider idempotency identity across attempts")
    if "v_last.adapter_instance_ref,v_last.sync_identity" not in sql:
        errors.append("G10 retry must carry forward provider idempotency identity")
    return errors


def _assert_g10_guardrail_case(*, unsafe: str, safe: str, expected_fragment: str) -> None:
    unsafe_errors = _g10_review_guardrail_errors(unsafe)
    assert any(expected_fragment in e for e in unsafe_errors), unsafe_errors
    safe_errors = _g10_review_guardrail_errors(safe)
    assert not safe_errors, safe_errors


def _g10_safe_guardrail_sql() -> str:
    return """
SELECT alert_id,lifecycle_state,opened_at,resolved_at
FROM alerting.alert;
SELECT 1
FROM q o
WHERE (o.sync_state='dispatching' AND o.claim_expires_at<=transaction_timestamp());
SELECT 1 FROM pg_auth_members WHERE roleid=v_role.oid OR member=v_role.oid;
SELECT hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10);
IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
  RAISE EXCEPTION 'g10.transition_equivalence_conflict';
END IF;
INSERT INTO x(adapter_instance_ref,sync_identity)
VALUES (v_last.adapter_instance_ref,v_last.sync_identity);
"""


def falsify_g10_alert_timestamp_contract() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_adversarial_learning.py"),
            "    falsify_g10_alert_timestamp_contract()\n",
            "",
        )
    )
    safe = _g10_safe_guardrail_sql()
    unsafe = safe.replace(
        "SELECT alert_id,lifecycle_state,opened_at,resolved_at",
        "SELECT alert_id,lifecycle_state,created_at,resolved_at",
    )
    _assert_g10_guardrail_case(
        unsafe=unsafe,
        safe=safe,
        expected_fragment="canonical opened_at",
    )
    actual = ROOT / "sql/itsm/001_incident.sql"
    if actual.is_file():
        assert not _g10_review_guardrail_errors(actual.read_text(encoding="utf-8"))


def falsify_g10_expired_sync_discovery() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_adversarial_learning.py"),
            "    falsify_g10_expired_sync_discovery()\n",
            "",
        )
    )
    safe = _g10_safe_guardrail_sql()
    unsafe = safe.replace(
        "(o.sync_state='dispatching' AND o.claim_expires_at<=transaction_timestamp())",
        "(o.sync_state='pending' AND o.available_at<=transaction_timestamp())",
    )
    _assert_g10_guardrail_case(
        unsafe=unsafe,
        safe=safe,
        expected_fragment="expired dispatching leases",
    )


def falsify_g10_privileged_role_membership() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_adversarial_learning.py"),
            "    falsify_g10_privileged_role_membership()\n",
            "",
        )
    )
    safe = _g10_safe_guardrail_sql()
    unsafe = safe.replace(
        "SELECT 1 FROM pg_auth_members WHERE roleid=v_role.oid OR member=v_role.oid;",
        "SELECT 1 FROM pg_roles WHERE oid=v_role.oid;",
    )
    _assert_g10_guardrail_case(
        unsafe=unsafe,
        safe=safe,
        expected_fragment="incoming and outgoing memberships",
    )


def falsify_g10_concurrent_create_idempotency() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_adversarial_learning.py"),
            "    falsify_g10_concurrent_create_idempotency()\n",
            "",
        )
    )
    safe = _g10_safe_guardrail_sql()
    unsafe = safe.replace(
        "SELECT hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10);",
        "SELECT 1;",
    )
    _assert_g10_guardrail_case(
        unsafe=unsafe,
        safe=safe,
        expected_fragment="serialize same logical action",
    )


def falsify_g10_transition_replay_equivalence() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_adversarial_learning.py"),
            "    falsify_g10_transition_replay_equivalence()\n",
            "",
        )
    )
    safe = _g10_safe_guardrail_sql()
    unsafe = safe.replace(
        "IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN\n  RAISE EXCEPTION 'g10.transition_equivalence_conflict';\nEND IF;",
        "IF FOUND THEN RETURN; END IF;",
    )
    _assert_g10_guardrail_case(
        unsafe=unsafe,
        safe=safe,
        expected_fragment="reject divergent target state",
    )


def falsify_g10_provider_sync_identity_stability() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            Path("tools/assurance/test_validate_adversarial_learning.py"),
            "    falsify_g10_provider_sync_identity_stability()\n",
            "",
        )
    )
    safe = _g10_safe_guardrail_sql()
    unsafe = safe.replace(
        "INSERT INTO x(adapter_instance_ref,sync_identity)\nVALUES (v_last.adapter_instance_ref,v_last.sync_identity);",
        "UNIQUE (tenant_id,sync_identity);",
    )
    errors = _g10_review_guardrail_errors(unsafe)
    assert any("provider idempotency identity" in e for e in errors), errors
    assert not _g10_review_guardrail_errors(safe)


def main() -> None:
    baseline_errors = s.validate(ROOT)
    assert not baseline_errors, "strict baseline errors:\n" + "\n".join(baseline_errors)

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
    falsify_governance_only_pr_scope()
    falsify_g10_auto_incident_extension_boundary()
    falsify_wave4_authorization_exact_path_allowlist()
    falsify_wave4_authority_toctou_guardrail()
    falsify_wave4_host_inventory_authority_transition()
    falsify_wave4_metric_definition_claimed_input_liveness_guardrail()
    falsify_g10_provider_sync_identity_stability()
    falsify_g10_transition_replay_equivalence()
    falsify_g10_concurrent_create_idempotency()
    falsify_g10_privileged_role_membership()
    falsify_g10_expired_sync_discovery()
    falsify_g10_alert_timestamp_contract()
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

    print("adversarial_learning_falsification=PASS strict_static_graph=guarded review_surface=issues+inline+reviews top_level_comments=covered priority_prefix=covered head_status=fresh+isolated+concurrent+unspoofable privileged_pr_exec=denied stale_d4c_workflow_projection=blocked stop_policy=merge-blocking-preserved host_inventory_premerge_authority=preserved")


if __name__ == "__main__":
    main()
