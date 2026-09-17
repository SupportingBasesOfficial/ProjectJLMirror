from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def _assert_frontend_boundary() -> None:
    index = (ROOT / "apps/g1-identity-tenant-shell/frontend/index.html").read_text(encoding="utf-8")
    module = (ROOT / "apps/g1-identity-tenant-shell/frontend/shell-state.mjs").read_text(encoding="utf-8")
    app = (ROOT / "apps/g1-identity-tenant-shell/frontend/app.mjs").read_text(encoding="utf-8")
    text = index + "\n" + module + "\n" + app
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
    for state in ("loading", "ready", "unauthenticated", "forbidden", "revoked", "unavailable"):
        if state not in text:
            raise AssertionError(f"protected shell frontend missing state: {state}")


def _assert_fixture_isolation() -> None:
    source = (ROOT / "apps/g1-identity-tenant-shell/bff_server.py").read_text(encoding="utf-8")
    required = (
        "FixtureOidc() if fixture_enabled else DisabledOidc()",
        "FixtureTenantAdmission() if fixture_enabled else DisabledTenantAdmission()",
        "if not self.server.fixture_enabled:",
    )
    for marker in required:
        if marker not in source:
            raise AssertionError(f"G1 BFF fixture isolation missing: {marker}")


def _run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> int:
    _assert_frontend_boundary()
    _assert_fixture_isolation()
    env = dict(os.environ)
    pythonpath = [str(ROOT / "src")]
    existing = env.get("PYTHONPATH")
    if existing:
        pythonpath.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)

    _run(
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
        env=env,
    )
    _run(["node", "--test", "tests/g1/protected_shell_presentation.test.mjs"])
    _run(["bash", "tools/g1/run_identity_tenant_shell_postgres_conformance.sh"])
    _run([sys.executable, "tools/g1/run_identity_tenant_shell_browser_e2e.py"], env=env)
    print("g1_identity_tenant_shell_runtime=PASS unit=PASS presentation=PASS postgres=PASS browser_e2e=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
