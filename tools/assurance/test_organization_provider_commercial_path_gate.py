#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def run(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        run(repo, "git", "init", "-q")
        run(repo, "git", "config", "user.email", "assurance@example.invalid")
        run(repo, "git", "config", "user.name", "JLMIRROR Assurance")

        old_path = Path("src/runtime.py")
        new_path = Path("governance/product-model/organization-provider-commercial/runtime.py")
        (repo / old_path).parent.mkdir(parents=True, exist_ok=True)
        (repo / old_path).write_text("runtime_authority = True\n", encoding="utf-8")
        run(repo, "git", "add", ".")
        run(repo, "git", "commit", "-qm", "base")
        base = run(repo, "git", "rev-parse", "HEAD").strip()

        (repo / new_path).parent.mkdir(parents=True, exist_ok=True)
        run(repo, "git", "mv", str(old_path), str(new_path))
        run(repo, "git", "commit", "-qm", "rename runtime into allowed governance prefix")

        unsafe = set(run(repo, "git", "diff", "--name-only", f"{base}...HEAD").splitlines())
        safe = set(run(repo, "git", "diff", "--no-renames", "--name-only", f"{base}...HEAD").splitlines())

        if str(old_path) in unsafe:
            raise SystemExit("precondition changed: default rename detection exposed old path")
        if str(new_path) not in unsafe:
            raise SystemExit("precondition changed: renamed destination missing")
        if str(old_path) not in safe or str(new_path) not in safe:
            raise SystemExit(
                "rename-safe path enumeration failed to expose both rename endpoints: "
                f"safe={sorted(safe)!r}"
            )

        print("organization_provider_commercial_rename_gate=PASS both_endpoints_visible")


if __name__ == "__main__":
    main()
