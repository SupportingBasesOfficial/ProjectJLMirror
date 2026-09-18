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

ROOT=Path(__file__).resolve().parents[2]


def browser()->str:
    for name in ("google-chrome","google-chrome-stable","chromium","chromium-browser"):
        found=shutil.which(name)
        if found:
            return found
    raise RuntimeError("headless Chrome/Chromium is required")


def free_port()->int:
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1",0))
        return int(sock.getsockname()[1])


def run(command:list[str],*,env=None)->subprocess.CompletedProcess:
    completed=subprocess.run(
        command,cwd=ROOT,env=env,text=True,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,
    )
    if completed.returncode!=0:
        raise AssertionError("command failed rc="+str(completed.returncode)+"\n"+completed.stderr[-3000:])
    return completed


def wait_ready(url:str)->None:
    context=ssl._create_unverified_context()
    for _ in range(120):
        try:
            with urllib.request.urlopen(url,context=context,timeout=1) as response:
                if response.status==200:
                    return
        except Exception:
            time.sleep(0.1)
    raise AssertionError("G5 BFF did not become ready")


def run_browser(executable:str,*,profile:Path,url:str,marker:str,server_log:Path)->str:
    completed=run([
        executable,
        "--headless=new","--no-sandbox","--disable-gpu",
        "--ignore-certificate-errors","--allow-insecure-localhost",
        "--disable-background-networking","--disable-component-update",
        "--disable-default-apps","--no-first-run",
        "--user-data-dir="+str(profile),
        "--virtual-time-budget=9000","--dump-dom",url,
    ])
    html=completed.stdout
    if 'data-e2e-result="'+marker+'"' not in html:
        log_tail=server_log.read_text(encoding="utf-8",errors="replace")[-5000:] if server_log.exists() else ""
        raise AssertionError(
            "missing browser marker "+marker
            +"; DOM head="+html[:2500]
            +"; DOM tail="+html[-2500:]
            +"; BFF log tail="+log_tail
        )
    for forbidden in ("access_token","refresh_token","api_token","Authorization: Bearer"):
        if forbidden in html:
            raise AssertionError("browser DOM leaked forbidden marker: "+forbidden)
    return html


def main()->int:
    executable=browser()
    with tempfile.TemporaryDirectory(prefix="jlmirror-g5-browser-") as tmp:
        temp=Path(tmp)
        cert=temp/"cert.pem"
        key=temp/"key.pem"
        run([
            "openssl","req","-x509","-newkey","rsa:2048","-nodes","-days","1",
            "-subj","/CN=127.0.0.1","-addext","subjectAltName=IP:127.0.0.1",
            "-keyout",str(key),"-out",str(cert),
        ])

        env=dict(os.environ)
        parts=[str(ROOT/"src"),str(ROOT/"apps/g5-problem-health")]
        if env.get("PYTHONPATH"):
            parts.append(env["PYTHONPATH"])
        env["PYTHONPATH"]=os.pathsep.join(parts)

        port=free_port()
        server_log=temp/"g5-bff.log"
        server_log_handle=server_log.open("w",encoding="utf-8")
        server=subprocess.Popen([
            sys.executable,"apps/g5-problem-health/bff_server.py",
            "--host","127.0.0.1","--port",str(port),
            "--certfile",str(cert),"--keyfile",str(key),
            "--fixture","--fixture-memory",
        ],cwd=ROOT,env=env,stdout=server_log_handle,stderr=server_log_handle,text=True)

        try:
            base="https://127.0.0.1:"+str(port)
            wait_ready(base+"/healthz")
            for profile_name,case_name,marker in (
                ("active","active","g5-active-pass"),
                ("resolved","resolved","g5-resolved-pass"),
                ("health","health","g5-health-pass"),
                ("revoked","revoked","g5-revoked-pass"),
                ("cross","cross-tenant","g5-cross-tenant-pass"),
            ):
                run_browser(
                    executable,
                    profile=temp/("profile-"+profile_name),
                    url=base+"/__fixture__/g5/login/start?case="+case_name,
                    marker=marker,
                    server_log=server_log,
                )
            print(
                "g5_browser_e2e=PASS active=PASS resolved=PASS health=PASS "
                "revoked=PASS cross_tenant=PASS provider_metadata_list_isolation=PASS"
            )
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            server_log_handle.close()
            if server.returncode not in (0,-15):
                logs=server_log.read_text(encoding="utf-8",errors="replace") if server_log.exists() else ""
                raise AssertionError("G5 BFF exited unexpectedly: "+logs[-3000:])
    return 0


if __name__=="__main__":
    raise SystemExit(main())
