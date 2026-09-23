from __future__ import annotations

from pathlib import Path
import json
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE_TAG="python:3.13-slim-bookworm"
IMAGE="jlmirror-g8-runtime-proof:local"
CONTAINER="jlmirror-g8-runtime-proof"


def run(command:list[str],*,check:bool=True)->subprocess.CompletedProcess:
    cp=subprocess.run(command,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if check and cp.returncode!=0:
        raise AssertionError("command failed\n"+cp.stdout[-2500:]+cp.stderr[-2500:])
    return cp


def resolve_digest()->str:
    run(["docker","pull",BASE_TAG])
    digests=json.loads(run(["docker","image","inspect",BASE_TAG,"--format","{{json .RepoDigests}}"]).stdout.strip())
    matches=[x for x in digests if x.startswith("python@sha256:")]
    if len(matches)!=1:
        raise AssertionError("expected one immutable Python RepoDigest")
    return matches[0]


def main()->int:
    digest=resolve_digest()
    subprocess.run(["docker","rm","-f",CONTAINER],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(["docker","image","rm","-f",IMAGE],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        run([
            "docker","build","--pull=false","--build-arg","BASE_IMAGE="+digest,
            "-f","apps/g8-human-operations/Dockerfile.runtime-proof",
            "-t",IMAGE,".",
        ])
        uid="65532:65532"
        cp=run([
            "docker","run","--name",CONTAINER,
            "--user",uid,"--network","none","--read-only",
            "--tmpfs","/tmp:rw,noexec,nosuid,size=16m",
            "--cap-drop","ALL","--security-opt","no-new-privileges",
            IMAGE,"--self-check",
        ])
        if "g8_worker_boot=PASS" not in cp.stdout:
            raise AssertionError("G8 worker self-check drift")
        inspect=run([
            "docker","inspect",CONTAINER,"--format",
            "{{.HostConfig.ReadonlyRootfs}}|{{json .HostConfig.CapDrop}}|"
            "{{json .HostConfig.SecurityOpt}}|{{.Config.User}}|{{.HostConfig.NetworkMode}}",
        ]).stdout.strip()
        if not inspect.startswith("true|") or "ALL" not in inspect or "no-new-privileges" not in inspect:
            raise AssertionError("G8 container hardening drift")
        if "|"+uid+"|" not in inspect or not inspect.endswith("|none"):
            raise AssertionError("G8 container user/network drift")
        print("g8_container_proof=PASS readonly=PASS cap_drop=ALL no_new_privileges=PASS network=none non_root="+uid)
        return 0
    finally:
        subprocess.run(["docker","rm","-f",CONTAINER],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(["docker","image","rm","-f",IMAGE],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__=="__main__":
    raise SystemExit(main())
