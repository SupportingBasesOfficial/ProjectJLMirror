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
CONTAINER = "jlmirror-g3-browser-postgres"
DATABASE = "jlmirror"
PASSWORD = "jlmirror-g3-test-password"


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
        "004_monitoring_boundary_hardening.sql",
        "005_zabbix_host_inventory.sql",
        "006_zabbix_host_inventory_boundary_hardening.sql",
        "007_zabbix_host_inventory_integrity_hardening.sql",
        "008_zabbix_host_inventory_poll_ordering_hardening.sql",
    ):
        run(
            ["docker", "exec", "-i", CONTAINER, "psql", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", DATABASE],
            input_text=(migration_dir / name).read_text(encoding="utf-8"),
        )

    pg(
        "CREATE ROLE wave4_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;"
        "GRANT USAGE ON SCHEMA monitoring TO wave4_runtime;"
        "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA monitoring TO wave4_runtime;"
        "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA monitoring TO wave4_runtime;"
    )

    fp = "a" * 64
    scope = '{"host_group_refs":["10","20"]}'
    pg(
        "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; "
        "SELECT * FROM monitoring.create_zabbix_source("
        f"'tenant-a','create-a','{fp}','source-a','generation-a','binding-a','validation-a',"
        "'audit-a','principal-a','human_browser_session','credential-generation-a','authz-a',"
        "'correlation-a','Company A Zabbix','provider-instance:a','https://zabbix.example.test/zabbix',"
        f"'credential-binding:a','{scope}'::jsonb); COMMIT;"
    )
    pg(
        "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; "
        "SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation("
        "'tenant-a','validation-a','validation-claim-a'); "
        "SELECT monitoring.complete_zabbix_initial_validation("
        "'tenant-a','validation-a','validation-claim-a','validation-evidence-a','binding-a',"
        "'provider-instance:a','current','succeeded',NULL,'[\"10\",\"20\"]'::jsonb,'[]'::jsonb,"
        "'egress-validation-a','credential-generation-a'); COMMIT;"
    )

    host1 = {
        "monitoring_resource_id": "resource-101",
        "provider_evidence_id": "provider-evidence-101-a",
        "hostid": "101",
        "display_name": "Core Switch",
        "evidence_fingerprint": "1" * 64,
        "normalized_evidence": {
            "technical_name": "core-sw-01",
            "display_name": "Core Switch",
            "inventory": {"vendor": "Cisco", "model": "C9300"},
            "interfaces": [],
            "groups": [{"ref": "10", "name": "Network"}],
            "templates": [],
            "tags": [],
        },
    }
    host2 = {
        "monitoring_resource_id": "resource-102",
        "provider_evidence_id": "provider-evidence-102-a",
        "hostid": "102",
        "display_name": "Application Server",
        "evidence_fingerprint": "2" * 64,
        "normalized_evidence": {
            "technical_name": "app-01",
            "display_name": "Application Server",
            "inventory": {"vendor": "Dell", "model": "PowerEdge"},
            "interfaces": [],
            "groups": [{"ref": "20", "name": "Servers"}],
            "templates": [],
            "tags": [],
        },
    }
    payload = __import__("json").dumps([host1, host2], separators=(",", ":"))
    pg(
        "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; "
        "SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-a','inventory-a'); "
        "SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory("
        "'tenant-a','inventory-a','claim-inventory-a'); "
        "SELECT monitoring.complete_zabbix_host_inventory("
        "'tenant-a','inventory-a','claim-inventory-a','snapshot-a','binding-a','provider-instance:a',"
        f"'current','succeeded',NULL,true,'{payload}'::jsonb,'egress-a','credential-generation-a'); COMMIT;"
    )

    count = pg(
        "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; "
        "SELECT count(*) FROM monitoring.monitoring_resource WHERE presence_state='present'; COMMIT;"
    ).splitlines()[-1]
    if count != "2":
        raise AssertionError("fixture did not materialize two canonical resources")


def wait_ready(url: str) -> None:
    context = ssl._create_unverified_context()
    for _ in range(120):
        try:
            with urllib.request.urlopen(url, context=context, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.1)
    raise AssertionError("G3 BFF did not become ready")


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
        with tempfile.TemporaryDirectory(prefix="jlmirror-g3-browser-") as tmp:
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
            parts = [str(ROOT / "src"), str(ROOT / "apps/g3-resource-inventory")]
            if env.get("PYTHONPATH"):
                parts.append(env["PYTHONPATH"])
            env["PYTHONPATH"] = os.pathsep.join(parts)

            port = free_port()
            server = subprocess.Popen([
                sys.executable,
                "apps/g3-resource-inventory/bff_server.py",
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
                for profile_name, case_name, marker in (
                    ("success", "success", "g3-success-pass"),
                    ("detail", "detail", "g3-detail-pass"),
                    ("revoked", "revoked", "g3-revoked-pass"),
                    ("cross", "cross-tenant", "g3-cross-tenant-pass"),
                ):
                    run_browser(
                        executable,
                        profile=temp / ("profile-" + profile_name),
                        url=base + "/__fixture__/g3/login/start?case=" + case_name,
                        marker=marker,
                    )

                tenant_a = pg(
                    "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; "
                    "SELECT count(*) FROM monitoring.monitoring_resource; COMMIT;"
                ).splitlines()[-1]
                tenant_b = pg(
                    "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-b'; "
                    "SELECT count(*) FROM monitoring.monitoring_resource; COMMIT;"
                ).splitlines()[-1]
                if tenant_a != "2" or tenant_b != "0":
                    raise AssertionError("tenant-isolated canonical resource counts drifted")

                print(
                    "g3_browser_e2e=PASS list=PASS detail=PASS revoked=PASS "
                    "cross_tenant=PASS postgres=PASS canonical_identity=PASS"
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
                    raise AssertionError("G3 BFF exited unexpectedly: " + stderr[-3000:])
    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
