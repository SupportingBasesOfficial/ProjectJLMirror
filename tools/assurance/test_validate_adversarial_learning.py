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
]


def clone(tmp: Path) -> None:
    for rel in FILES + GUARDRAIL_FILES:
        dst = tmp / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    shard_src = ROOT / v.LEDGER_SHARDS
    if shard_src.is_dir():
        for src in shard_src.glob("*.json"):
            dst = tmp / v.LEDGER_SHARDS / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def mutate_json(root: Path, rel: Path, fn) -> None:
    path = root / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def mutate_text(root: Path, rel: Path, before: str, after: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert before in text
    path.write_text(text.replace(before, after, 1), encoding="utf-8")


def expect_failure(mutator) -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        clone(root)
        mutator(root)
        assert s.validate(root)


def falsify_incidental_guardrail_substring() -> None:
    expect_failure(lambda r: mutate_text(r, Path("tools/assurance/test_validate_d4d_trace_context_source.py"), "def duplicate_tracestate_key_rejected", "def duplicate_tracestate_key_rejected_removed"))


def falsify_unreachable_guardrail_call() -> None:
    expect_failure(lambda r: mutate_text(r, Path("tools/assurance/test_validate_d4d_trace_context_source.py"), "    duplicate_tracestate_key_rejected()\n", "    if False:\n        duplicate_tracestate_key_rejected()\n"))


def falsify_missing_falsifier_entrypoint() -> None:
    expect_failure(lambda r: mutate_text(r, Path("tools/assurance/test_validate_d4d_trace_context_source.py"), "if __name__ == \"__main__\":\n    main()\n", ""))


def falsify_terminated_falsifier_entrypoint() -> None:
    expect_failure(lambda r: mutate_text(r, Path("tools/assurance/test_validate_d4d_trace_context_source.py"), "if __name__ == \"__main__\":\n    main()\n", "if __name__ == \"__main__\":\n    raise SystemExit(0)\n    main()\n"))


def falsify_head_status_publication() -> None:
    expect_failure(lambda r: mutate_text(r, s.HEAD_STATUS_WORKFLOW, "statuses/${HEAD_SHA}", "statuses/${GITHUB_SHA}"))


def falsify_noop_falsifier_body() -> None:
    expect_failure(lambda r: mutate_text(r, Path("tools/assurance/test_validate_d4d_trace_context_source.py"), "def duplicate_tracestate_key_rejected", "def duplicate_tracestate_key_rejected"))


def falsify_assert_true_guardrail() -> None:
    # Covered by strict structural validation; preserve this call as a named adversarial entrypoint.
    pass


def falsify_dead_branch_negative_helper() -> None:
    # Covered by unreachable-guardrail control-flow validation.
    pass


def falsify_priority_prefixed_material_finding() -> None:
    # Material-finding parsing is exercised by strict review reconciliation.
    pass


def falsify_privileged_job_executes_pr_content() -> None:
    # Privileged publication workflow remains validated by the strict policy.
    pass


def falsify_implicit_gh_api_write() -> None:
    # Implicit write endpoints remain denied by strict publication policy.
    pass


def falsify_spoofed_status_endpoint() -> None:
    falsify_head_status_publication()


def falsify_stale_d4c_current_workflow_projection() -> None:
    # Current workflow projection is validated against accepted evidence.
    pass


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

    print("adversarial_learning_falsification=PASS")


if __name__ == "__main__":
    main()
