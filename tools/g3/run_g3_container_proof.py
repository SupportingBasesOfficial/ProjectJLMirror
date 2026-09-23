from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
BASE_TAG = "python:3.13-slim-bookworm"
IMAGE = "jlmirror-g3-runtime-proof:local"
CONTAINER = "jlmirror-g3-runtime-proof"


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    if check and completed.returncode != 0:
        raise AssertionError("command failed rc=" + str(completed.returncode) + "\n" + completed.stderr[-3000:])
    return completed


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def resolve_digest() -> str:
    run(["docker", "pull", BASE_TAG])
    digests = json.loads(run([
        "docker", "image", "inspect", BASE_TAG, "--format", "{{json .RepoDigests}}"
    ]).stdout.strip())
    candidates = [value for value in digests if value.startswith("python@sha256:")]
    if len(candidates) != 1:
        raise AssertionError("expected one immutable Python RepoDigest")
    return candidates[0]


def generate_tls(temp: Path) -> tuple[Path, Path]:
    openssl = shutil.which("openssl")
    if openssl is None:
        raise AssertionError("openssl is required")
    cert = temp / "cert.pem"
    key = temp / "key.pem"
    run([
        openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
        "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1",
        "-keyout", str(key), "-out", str(cert),
    ])
    return cert, key


def request(url: str) -> tuple[int, str]:
    context = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, context=context, timeout=2) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def wait_ready(url: str) -> str:
    for _ in range(120):
        state = run(["docker", "inspect", CONTAINER, "--format", "{{.State.Status}}|{{.State.ExitCode}}"], check=False)
        if state.returncode == 0 and state.stdout.strip().startswith("exited|"):
            logs = run(["docker", "logs", CONTAINER], check=False)
            raise AssertionError("G3 container exited before readiness\n" + logs.stderr[-3000:] + logs.stdout[-3000:])
        try:
            status, body = request(url)
            if status == 200:
                return body
        except Exception:
            pass
        time.sleep(0.1)
    raise AssertionError("G3 container did not become ready")


def main() -> int:
    digest = resolve_digest()
    port = free_port()
    subprocess.run(["docker", "rm", "-f", CONTAINER], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["docker", "image", "rm", "-f", IMAGE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with tempfile.TemporaryDirectory(prefix="jlmirror-g3-container-") as tmp:
            temp = Path(tmp)
            cert, key = generate_tls(temp)
            run([
                "docker", "build", "--pull=false", "--build-arg", "BASE_IMAGE=" + digest,
                "-f", "apps/g3-resource-inventory/Dockerfile.runtime-proof",
                "-t", IMAGE, ".",
            ])
            image_id = run(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"]).stdout.strip()
            if not image_id.startswith("sha256:"):
                raise AssertionError("container image id is not content-addressed")

            run([
                "docker", "run", "-d", "--name", CONTAINER,
                "--user", str(os.getuid()) + ":" + str(os.getgid()),
                "--network", "host", "--read-only",
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
                "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "-v", str(cert) + ":/run/jlmirror/cert.pem:ro",
                "-v", str(key) + ":/run/jlmirror/key.pem:ro",
                IMAGE,
                "--host", "127.0.0.1", "--port", str(port),
                "--certfile", "/run/jlmirror/cert.pem", "--keyfile", "/run/jlmirror/key.pem",
            ])

            base = "https://127.0.0.1:" + str(port)
            body = wait_ready(base + "/")
            if 'id="g3-inventory"' not in body:
                raise AssertionError("readiness response drift")
            status, fixture_body = request(base + "/__fixture__/g3/login/start?case=success")
            if status != 404 or fixture_body != '{"state":"unavailable"}':
                raise AssertionError("container boot unexpectedly exposed fixture-only G3 surface")

            running = run([
                "docker", "inspect", CONTAINER, "--format",
                "{{.State.Running}}|{{.HostConfig.ReadonlyRootfs}}|{{json .HostConfig.CapDrop}}|"
                "{{json .HostConfig.SecurityOpt}}|{{.Config.User}}",
            ]).stdout.strip()
            expected_user = str(os.getuid()) + ":" + str(os.getgid())
            if not running.startswith("true|true|"):
                raise AssertionError("container runtime hardening drift")
            if "ALL" not in running or "no-new-privileges" not in running:
                raise AssertionError("container privilege hardening drift")
            if not running.endswith("|" + expected_user):
                raise AssertionError("container did not run as the bounded non-root proof user")

            print(
                "g3_container_proof=PASS base_digest=" + digest.split("@", 1)[1]
                + " image_id=" + image_id
                + " https_boot=PASS fixture_isolation=PASS readonly=PASS cap_drop=ALL"
                + " no_new_privileges=PASS non_root_user=" + expected_user
            )
    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["docker", "image", "rm", "-f", IMAGE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
