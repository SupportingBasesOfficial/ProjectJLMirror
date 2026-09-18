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
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
POSTGRES_IMAGE = "postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280"
CONTAINER = "jlmirror-g2-browser-postgres"
DATABASE = "jlmirror"
PASSWORD = "jlmirror-g2-test-password"


def browser() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    raise RuntimeError("headless Chrome/Chromium is required")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run(command: list[str], *, input_text: str | None = None, env=None) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "command failed rc=" + str(completed.returncode) + "\n" + completed.stderr[-3000:]
        )
    return completed


def pg(sql: str) -> str:
    return run([
        "docker", "exec", CONTAINER, "psql", "-Atq", "-v", "ON_ERROR_STOP=1",
        "-U", "postgres", "-d", DATABASE, "-c", sql,
    ]).stdout.strip()


def start_postgres() -> None:
    subprocess.run(["docker", "rm", "-f", CONTAINER], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run(["docker", "pull", POSTGRES_IMAGE])
    run([
        "docker", "run", "-d", "--rm", "--name", CONTAINER,
        "-e", "POSTGRES_PASSWORD=" + PASSWORD,
        "-e", "POSTGRES_DB=" + DATABASE,
        POSTGRES_IMAGE,
    ])
    stable = 0
    for _ in range(90):
        probe = subprocess.run(
            ["docker", "exec", CONTAINER, "psql", "-Atq", "-U", "postgres", "-d", DATABASE, "-c", "SELECT 1"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        if probe.returncode == 0 and probe.stdout.strip() == "1":
            stable += 1
            if stable >= 3:
                break
        else:
            stable = 0
        time.sleep(0.2)
    if stable < 3:
        raise AssertionError("Postgres did not become stable")

    migration_dir = ROOT / "sql" / "wave4"
    for name in (
        "001_monitoring_source_foundation.sql",
        "002_monitoring_source_audit_evidence.sql",
        "003_zabbix_initial_validation_worker.sql",
    ):
        run(
            ["docker", "exec", "-i", CONTAINER, "psql", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", DATABASE],
            input_text=(migration_dir / name).read_text(encoding="utf-8"),
        )


def wait_ready(url: str) -> None:
    context = ssl._create_unverified_context()
    for _ in range(120):
        try:
            with urllib.request.urlopen(url, context=context, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.1)
    raise AssertionError("G2 BFF did not become ready")


def run_browser(executable: str, *, profile: Path, url: str, marker: str) -> str:
    completed = run([
        executable,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--ignore-certificate-errors",
        "--allow-insecure-localhost",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--no-first-run",
        "--user-data-dir=" + str(profile),
        "--virtual-time-budget=9000",
        "--dump-dom",
        url,
    ])
    html = completed.stdout
    if 'data-e2e-result="' + marker + '"' not in html:
        raise AssertionError("missing browser marker " + marker + "; DOM tail=" + html[-3500:])
    for forbidden in ("access_token", "refresh_token", "api_token", "Authorization: Bearer"):
        if forbidden in html:
            raise AssertionError("browser DOM leaked forbidden marker: " + forbidden)
    return html


def main() -> int:
    executable = browser()
    start_postgres()
    try:
        with tempfile.TemporaryDirectory(prefix="jlmirror-g2-browser-") as tmp:
            temp = Path(tmp)
            cert = temp / "cert.pem"
            key = temp / "key.pem"
            run([
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                "-subj", "/CN=127.0.0.1",
                "-addext", "subjectAltName=IP:127.0.0.1",
                "-keyout", str(key), "-out", str(cert),
            ])

            env = dict(os.environ)
            parts = [str(ROOT / "src"), str(ROOT / "apps/g2-monitoring-source-onboarding")]
            if env.get("PYTHONPATH"):
                parts.append(env["PYTHONPATH"])
            env["PYTHONPATH"] = os.pathsep.join(parts)

            port = free_port()
            server = subprocess.Popen([
                sys.executable,
                "apps/g2-monitoring-source-onboarding/bff_server.py",
                "--host", "127.0.0.1",
                "--port", str(port),
                "--certfile", str(cert),
                "--keyfile", str(key),
                "--fixture",
                "--pg-container", CONTAINER,
                "--pg-database", DATABASE,
            ], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                base = "https://127.0.0.1:" + str(port)
                wait_ready(base + "/healthz")
                scenarios = (
                    ("success-a", "success", "g2-success-pass"),
                    ("success-replay", "success", "g2-success-pass"),
                    ("missing", "missing", "g2-missing-pass"),
                    ("revoked", "revoked", "g2-revoked-pass"),
                    ("cross", "cross-tenant", "g2-cross-tenant-pass"),
                )
                for profile_name, case_name, marker in scenarios:
                    run_browser(
                        executable,
                        profile=temp / ("profile-" + profile_name),
                        url=base + "/__fixture__/g2/login/start?case=" + case_name,
                        marker=marker,
                    )

                if pg("SELECT count(*) FROM monitoring.monitoring_source WHERE tenant_id='tenant-a';") != "2":
                    raise AssertionError("idempotent replay or denied paths created unexpected source rows")
                if pg("SELECT count(*) FROM monitoring.monitoring_source_validation_evidence WHERE tenant_id='tenant-a';") != "2":
                    raise AssertionError("durable validation evidence count is unexpected")
                forbidden_columns = pg(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_schema='monitoring' AND column_name IN ('api_token','password','secret');"
                )
                if forbidden_columns != "0":
                    raise AssertionError("provider secret material became ordinary Monitoring schema state")

                print(
                    "g2_browser_e2e=PASS success=PASS replay=PASS missing_scope=PASS "
                    "revoked=PASS cross_tenant=PASS postgres=PASS worker=accepted"
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
                    raise AssertionError("G2 BFF exited unexpectedly: " + stderr[-3000:])
    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
