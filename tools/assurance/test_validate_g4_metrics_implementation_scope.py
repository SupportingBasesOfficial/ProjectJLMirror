#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

VALIDATOR = Path(__file__).with_name("validate_g4_metrics_implementation_scope.py")
REPO = "SupportingBasesOfficial/ProjectJLMirror"

POLICY = {
    "allowed_prefixes": [
        "apps/g4-metrics/",
        "contracts/g4-metrics/",
        "implementation/g4-metrics/",
        "tests/g4/",
        "tools/g4/",
    ],
    "allowed_exact_paths": [".github/workflows/g4-metrics-runtime.yml"],
    "semantic_scan_prefixes": [
        "apps/g4-metrics/",
        "contracts/g4-metrics/",
        "implementation/g4-metrics/",
        "tests/g4/",
        "tools/g4/",
    ],
    "forbidden_path_tokens": [
        "problem", "health", "alert", "classification", "taxonomy", "topology", "replacement", "cutover"
    ],
    "forbidden_code_markers": [
        "problem_state", "problem_id", "health_projection", "health_class",
        "monitoring_to_alerting", "alert_policy", "alert_creation",
        "canonical_device_class", "canonical_device_type", "classification_confidence",
        "source_replacement", "source_cutover", "create table monitoring.", "create schema monitoring",
        "src/jlmirror_monitoring", "sql/wave4", "history.get(", "item.get(",
        "production_deployment", "production_c3",
    ],
    "implementation_claim_path": "implementation/g4-metrics/IMPLEMENTATION_CLAIM.json",
    "implementation_pr_head_prefix": "impl/g4-metrics",
    "implementation_pr_required_label": "jlmirror-slice:g4-metrics",
    "runtime_workflow": ".github/workflows/g4-metrics-runtime.yml",
    "runtime_workflow_name": "JLMIRROR G4 Metrics Runtime",
    "runtime_entrypoint": "python tools/g4/run_metrics_runtime.py",
    "runtime_allowed_actions": [
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1",
        "actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38",
    ],
}


def init_repo() -> tuple[tempfile.TemporaryDirectory, Path, str]:
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "G4 test"], check=True)
    manifest = {
        "implementation_authority_after_merge": "granted_for_exact_g4_metrics_only",
        "implementation_path_policy": POLICY,
    }
    p = root / "implementation/g4-metrics-authorization/AUTHORIZATION_MANIFEST.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest), encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], check=True)
    base = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    return td, root, base


def canonical_runtime() -> str:
    return json.dumps({
        "name": "JLMIRROR G4 Metrics Runtime",
        "on": {"pull_request": {}, "workflow_dispatch": {}},
        "permissions": {},
        "jobs": {
            "g4-runtime": {
                "runs-on": "ubuntu-24.04",
                "steps": [
                    {"uses": "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"},
                    {"uses": "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"},
                    {"uses": "actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38"},
                    {"run": "python tools/g4/run_metrics_runtime.py"},
                ],
            }
        },
    })


def invoke(root: Path, base: str) -> subprocess.CompletedProcess:
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    return subprocess.run([
        "python3", str(VALIDATOR),
        "--repo-root", str(root),
        "--base", base,
        "--head", head,
        "--head-ref", "impl/g4-metrics-test",
        "--labels-json", '["jlmirror-slice:g4-metrics"]',
        "--head-repo", REPO,
        "--base-repo", REPO,
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def run_case(files: dict[str, str], *, expect_ok: bool) -> None:
    td, root, base = init_repo()
    try:
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

        claim = root / "implementation/g4-metrics/IMPLEMENTATION_CLAIM.json"
        claim.parent.mkdir(parents=True, exist_ok=True)
        claim.write_text(json.dumps({
            "schema_version": 1,
            "authorization_id": "g4.metrics@1",
            "slice_id": "g4.metrics@1",
        }), encoding="utf-8")

        runtime = root / ".github/workflows/g4-metrics-runtime.yml"
        runtime.parent.mkdir(parents=True, exist_ok=True)
        if not runtime.exists():
            runtime.write_text(canonical_runtime(), encoding="utf-8")

        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "candidate"], check=True)
        cp = invoke(root, base)
        if (cp.returncode == 0) != expect_ok:
            raise AssertionError(
                f"unexpected validator result ok={cp.returncode == 0}\nstdout={cp.stdout}\nstderr={cp.stderr}"
            )
    finally:
        td.cleanup()


def run_rename_case() -> None:
    td, root, base = init_repo()
    try:
        shared = root / "src/jlmirror_monitoring/metrics.py"
        shared.parent.mkdir(parents=True, exist_ok=True)
        shared.write_text("CANONICAL = True\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "shared"], check=True)
        base = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()

        dest = root / "apps/g4-metrics/stolen_shared.py"
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "-C", str(root), "mv", "src/jlmirror_monitoring/metrics.py", str(dest.relative_to(root))], check=True)

        claim = root / "implementation/g4-metrics/IMPLEMENTATION_CLAIM.json"
        claim.parent.mkdir(parents=True, exist_ok=True)
        claim.write_text(json.dumps({
            "schema_version": 1,
            "authorization_id": "g4.metrics@1",
            "slice_id": "g4.metrics@1",
        }), encoding="utf-8")
        runtime = root / ".github/workflows/g4-metrics-runtime.yml"
        runtime.parent.mkdir(parents=True, exist_ok=True)
        runtime.write_text(canonical_runtime(), encoding="utf-8")

        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "candidate"], check=True)
        cp = invoke(root, base)
        if cp.returncode == 0 or "src/jlmirror_monitoring/metrics.py" not in cp.stderr:
            raise AssertionError(f"shared-substrate rename unexpectedly accepted\nstdout={cp.stdout}\nstderr={cp.stderr}")
    finally:
        td.cleanup()


def main() -> int:
    run_case({
        "apps/g4-metrics/read.py":
            "metric_definition_id = 'metric-1'\n"
            "sql = 'SELECT metric_definition_id FROM monitoring.metric_current_state'\n"
    }, expect_ok=True)
    run_case({"sql/g4/parallel.sql": "create table monitoring.metric_shadow(id text);\n"}, expect_ok=False)
    run_case({"apps/g4-metrics/health.py": "health_projection = 'healthy'\n"}, expect_ok=False)
    run_case({"apps/g4-metrics/problem.py": "problem_state = 'active'\n"}, expect_ok=False)
    run_case({"apps/g4-metrics/write.py": "db.update('metric_current_state', {'x': 1})\n"}, expect_ok=False)
    run_case({"apps/g4-metrics/sql.py": "db.execute(\"UPDATE monitoring.metric_current_state SET x=1\")\n"}, expect_ok=False)
    run_case({"apps/g4-metrics/provider.py": "value = client.history.get(request)\n"}, expect_ok=False)
    run_case({"apps/g4-metrics/provider2.py": "value = client.item.get(request)\n"}, expect_ok=False)

    bad_extra = json.loads(canonical_runtime())
    bad_extra["jobs"]["g4-runtime"]["steps"].append({"run": "python tools/g5/run_problem_health.py"})
    run_case({".github/workflows/g4-metrics-runtime.yml": json.dumps(bad_extra)}, expect_ok=False)

    bad_checkout = json.loads(canonical_runtime())
    bad_checkout["jobs"]["g4-runtime"]["steps"][0]["with"] = {"repository": "attacker/repo", "path": "tools/g4"}
    run_case({".github/workflows/g4-metrics-runtime.yml": json.dumps(bad_checkout)}, expect_ok=False)

    run_rename_case()
    print("g4_scope_falsification=PASS metrics=allowed path_widening=blocked rename_escape=blocked g5=blocked writes=blocked provider_passthrough=blocked runtime=bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
