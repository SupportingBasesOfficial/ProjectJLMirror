from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def _assert_frontend_boundary() -> None:
    text = (ROOT / "apps/g1-identity-tenant-shell/frontend/index.html").read_text(encoding="utf-8")
    forbidden = (
        "localStorage",
        "sessionStorage",
        "refresh_token",
        "access_token",
        "Authorization: Bearer",
    )
    for marker in forbidden:
        if marker in text:
            raise AssertionError(f"protected shell frontend contains forbidden credential surface: {marker}")
    for state in ("ready", "unauthenticated", "forbidden", "revoked", "unavailable"):
        if state not in text:
            raise AssertionError(f"protected shell frontend missing state: {state}")


def main() -> int:
    _assert_frontend_boundary()
    env = dict(os.environ)
    pythonpath = [str(ROOT / "src")]
    existing = env.get("PYTHONPATH")
    if existing:
        pythonpath.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            str(ROOT / "tests/g1"),
            "-p",
            "test_*.py",
            "-v",
        ],
        cwd=ROOT,
        env=env,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
