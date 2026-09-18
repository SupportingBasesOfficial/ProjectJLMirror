#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

VALIDATOR = Path(__file__).with_name("validate_g3_resource_inventory_implementation_scope.py")


def run_case(files: dict[str, str], *, expect_ok: bool) -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "G3 test"], check=True)
        manifest = {
            "implementation_authority_after_merge": "granted_for_exact_g3_resource_inventory_only",
            "implementation_path_policy": {
                "allowed_prefixes": ["apps/g3-resource-inventory/","contracts/g3-resource-inventory/","implementation/g3-resource-inventory/","tests/g3/","tools/g3/"],
                "allowed_exact_paths": [".github/workflows/g3-resource-inventory-runtime.yml"],
                "semantic_scan_prefixes": ["apps/g3-resource-inventory/","contracts/g3-resource-inventory/","implementation/g3-resource-inventory/","tests/g3/","tools/g3/"],
                "forbidden_path_tokens": ["metric","problem","health","alert","classification","taxonomy","topology","replacement","cutover"],
                "forbidden_code_markers": ["metric_definition","metric_current_state","problem_state","health_projection","canonical_device_class","create table monitoring.","src/jlmirror_monitoring","sql/wave4"],
                "implementation_claim_path": "implementation/g3-resource-inventory/IMPLEMENTATION_CLAIM.json",
                "implementation_pr_head_prefix": "impl/g3-resource-inventory",
                "implementation_pr_required_label": "jlmirror-slice:g3-resource-inventory"
            }
        }
        p = root / "implementation/g3-resource-inventory-authorization/AUTHORIZATION_MANIFEST.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(manifest), encoding="utf-8")
        subprocess.run(["git","-C",str(root),"add","."],check=True)
        subprocess.run(["git","-C",str(root),"commit","-qm","base"],check=True)
        base = subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        claim = root / "implementation/g3-resource-inventory/IMPLEMENTATION_CLAIM.json"
        claim.parent.mkdir(parents=True, exist_ok=True)
        if not claim.exists():
            claim.write_text(json.dumps({"schema_version":1,"authorization_id":"g3.resource-inventory@1","slice_id":"g3.resource-inventory@1"}),encoding="utf-8")
        subprocess.run(["git","-C",str(root),"add","."],check=True)
        subprocess.run(["git","-C",str(root),"commit","-qm","candidate"],check=True)
        head = subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
        cp = subprocess.run([
            "python3", str(VALIDATOR),
            "--repo-root", str(root),
            "--base", base,
            "--head", head,
            "--head-ref", "impl/g3-resource-inventory-test",
            "--labels-json", '["jlmirror-slice:g3-resource-inventory"]',
            "--head-repo", "SupportingBasesOfficial/ProjectJLMirror",
            "--base-repo", "SupportingBasesOfficial/ProjectJLMirror"
        ],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        if (cp.returncode == 0) != expect_ok:
            raise AssertionError(f"unexpected validator result ok={cp.returncode == 0}\nstdout={cp.stdout}\nstderr={cp.stderr}")


def run_rename_case() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "G3 test"], check=True)
        manifest = {
            "implementation_authority_after_merge": "granted_for_exact_g3_resource_inventory_only",
            "implementation_path_policy": {
                "allowed_prefixes": ["apps/g3-resource-inventory/","contracts/g3-resource-inventory/","implementation/g3-resource-inventory/","tests/g3/","tools/g3/"],
                "allowed_exact_paths": [".github/workflows/g3-resource-inventory-runtime.yml"],
                "semantic_scan_prefixes": ["apps/g3-resource-inventory/","contracts/g3-resource-inventory/","implementation/g3-resource-inventory/","tests/g3/","tools/g3/"],
                "forbidden_path_tokens": ["metric","problem","health","alert","classification","taxonomy","topology","replacement","cutover"],
                "forbidden_code_markers": ["metric_definition","metric_current_state","problem_state","health_projection","canonical_device_class","create table monitoring.","src/jlmirror_monitoring","sql/wave4"],
                "implementation_claim_path": "implementation/g3-resource-inventory/IMPLEMENTATION_CLAIM.json",
                "implementation_pr_head_prefix": "impl/g3-resource-inventory",
                "implementation_pr_required_label": "jlmirror-slice:g3-resource-inventory"
            }
        }
        p = root / "implementation/g3-resource-inventory-authorization/AUTHORIZATION_MANIFEST.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(manifest), encoding="utf-8")
        shared = root / "src/jlmirror_monitoring/shared.py"
        shared.parent.mkdir(parents=True, exist_ok=True)
        shared.write_text("CANONICAL = True\n", encoding="utf-8")
        subprocess.run(["git","-C",str(root),"add","."],check=True)
        subprocess.run(["git","-C",str(root),"commit","-qm","base"],check=True)
        base = subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()

        destination = root / "apps/g3-resource-inventory/stolen_shared.py"
        destination.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git","-C",str(root),"mv","src/jlmirror_monitoring/shared.py","apps/g3-resource-inventory/stolen_shared.py"],check=True)
        claim = root / "implementation/g3-resource-inventory/IMPLEMENTATION_CLAIM.json"
        claim.parent.mkdir(parents=True, exist_ok=True)
        claim.write_text(json.dumps({"schema_version":1,"authorization_id":"g3.resource-inventory@1","slice_id":"g3.resource-inventory@1"}),encoding="utf-8")
        subprocess.run(["git","-C",str(root),"add","."],check=True)
        subprocess.run(["git","-C",str(root),"commit","-qm","candidate"],check=True)
        head = subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
        cp = subprocess.run([
            "python3", str(VALIDATOR),
            "--repo-root", str(root),
            "--base", base,
            "--head", head,
            "--head-ref", "impl/g3-resource-inventory-test",
            "--labels-json", '["jlmirror-slice:g3-resource-inventory"]',
            "--head-repo", "SupportingBasesOfficial/ProjectJLMirror",
            "--base-repo", "SupportingBasesOfficial/ProjectJLMirror"
        ],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        if cp.returncode == 0 or "src/jlmirror_monitoring/shared.py" not in cp.stderr:
            raise AssertionError(f"shared-substrate rename unexpectedly accepted\nstdout={cp.stdout}\nstderr={cp.stderr}")


def main() -> int:
    run_case({"apps/g3-resource-inventory/read.py":"RESOURCE_KIND = 'host'\n"}, expect_ok=True)
    run_case({"sql/g3/parallel.sql":"create table monitoring.resource_shadow(id text);\n"}, expect_ok=False)
    run_case({"apps/g3-resource-inventory/metric_view.py":"metric_definition = 'forbidden'\n"}, expect_ok=False)
    run_case({"apps/g3-resource-inventory/device.py":"canonical_device_class = 'server'\n"}, expect_ok=False)
    run_rename_case()
    print("g3_scope_falsification=PASS path_widening=blocked rename_escape=blocked g4=blocked classification=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
