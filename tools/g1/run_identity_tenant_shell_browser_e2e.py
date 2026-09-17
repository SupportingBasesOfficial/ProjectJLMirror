from __future__ import annotations

from pathlib import Path
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[2]


def _browser() -> str:
    for candidate in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("headless Chrome/Chromium is required for G1 browser E2E")


def _port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_ready(url: str) -> None:
    context = ssl._create_unverified_context()
    for _ in range(100):
        try:
            with urllib.request.urlopen(url, context=context, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("G1 BFF did not become ready")


def _assert_fixture_disabled(*, port: int, cert: Path, key: Path, env: dict[str, str]) -> None:
    server = subprocess.Popen(
        [
            sys.executable,
            "apps/g1-identity-tenant-shell/bff_server.py",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--certfile",
            str(cert),
            "--keyfile",
            str(key),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        base = f"https://127.0.0.1:{port}"
        _wait_ready(base + "/healthz")
        context = ssl._create_unverified_context()
        try:
            urllib.request.urlopen(
                base + "/__fixture__/login/start?target_tenant=tenant-a",
                context=context,
                timeout=2,
            )
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise AssertionError(f"fixture-disabled BFF returned unexpected status {exc.code}") from exc
        else:
            raise AssertionError("fixture login endpoint was reachable without --fixture")
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


def _run_browser(browser: str, *, profile: Path, url: str, marker: str) -> str:
    command = [
        browser,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--ignore-certificate-errors",
        "--allow-insecure-localhost",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--no-first-run",
        f"--user-data-dir={profile}",
        "--virtual-time-budget=3500",
        "--dump-dom",
        url,
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"browser scenario failed rc={completed.returncode}: {completed.stderr[-2000:]}"
        )
    html = completed.stdout
    if f'data-e2e-result="{marker}"' not in html:
        raise AssertionError(
            f"browser scenario missing marker {marker!r}; dom tail={html[-3000:]}"
        )
    for forbidden in ("access_token", "refresh_token", "Authorization: Bearer"):
        if forbidden in html:
            raise AssertionError(f"browser DOM leaked forbidden credential marker: {forbidden}")
    return html


def main() -> int:
    browser = _browser()
    env = dict(os.environ)
    pythonpath = [str(ROOT / "src")]
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)

    with tempfile.TemporaryDirectory(prefix="jlmirror-g1-browser-") as tmp:
        temp = Path(tmp)
        cert = temp / "cert.pem"
        key = temp / "key.pem"
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=127.0.0.1",
                "-addext",
                "subjectAltName=IP:127.0.0.1",
                "-keyout",
                str(key),
                "-out",
                str(cert),
            ],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        disabled_port = _port()
        _assert_fixture_disabled(port=disabled_port, cert=cert, key=key, env=env)

        port = _port()
        server = subprocess.Popen(
            [
                sys.executable,
                "apps/g1-identity-tenant-shell/bff_server.py",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--certfile",
                str(cert),
                "--keyfile",
                str(key),
                "--fixture",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            base = f"https://127.0.0.1:{port}"
            _wait_ready(base + "/healthz")
            scenarios = (
                ("allowed", "tenant-a", "allowed", "allowed-pass"),
                ("cross-tenant", "tenant-b", "allowed", "cross-tenant-pass"),
                ("revoked", "tenant-a", "revoked", "revoked-pass"),
                ("csrf-reject", "tenant-a", "allowed", "csrf-reject-pass"),
                ("logout", "tenant-a", "allowed", "logout-pass"),
            )
            for scenario, tenant, mode, marker in scenarios:
                profile = temp / f"profile-{scenario}"
                url = (
                    base
                    + "/__fixture__/login/start?"
                    + f"target_tenant={tenant}&scenario={scenario}&mode={mode}"
                )
                html = _run_browser(browser, profile=profile, url=url, marker=marker)
                if scenario == "cross-tenant" and ">tenant-b<" in html:
                    raise AssertionError("cross-tenant browser response disclosed requested tenant context")
            print(
                "g1_browser_e2e=PASS "
                "fixture_isolation=PASS allowed=PASS cross_tenant=PASS "
                "revoked=PASS csrf=PASS logout=PASS"
            )
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            if server.returncode not in (0, -15):
                stderr = server.stderr.read() if server.stderr else ""
                raise AssertionError(f"G1 BFF exited unexpectedly: {stderr[-2000:]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
