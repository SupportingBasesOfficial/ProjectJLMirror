from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request

from key_authority_conformance_core import (
    CONTAINER_NAME, OPENBAO_IMAGE, PORT, ConformanceError, KeyDomain, LifecycleRejected, _b64, _canon,
)

class OpenBaoController:
    def __init__(self, root: Path):
        self.root = root
        self.data_dir = root / "openbao-data"
        self.config_path = root / "openbao.hcl"
        self.addr = f"http://127.0.0.1:{PORT}"
        self.unseal_key: str | None = None
        self.root_token: str | None = None
        self.runtime_token: str | None = None
        self.data_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.data_dir, 0o777)
        self.config_path.write_text(
            'ui = false\ndisable_mlock = true\nstorage "file" {\n  path = "/openbao/file"\n}\nlistener "tcp" {\n  address = "0.0.0.0:8200"\n  tls_disable = 1\n}\n',
            encoding="utf-8",
        )

    def _docker(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["docker", *args], check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def start(self) -> None:
        self._docker("rm", "-f", CONTAINER_NAME, check=False)
        result = self._docker(
            "run", "-d", "--name", CONTAINER_NAME,
            "-p", f"127.0.0.1:{PORT}:8200",
            "-v", f"{self.config_path}:/openbao/config/d3e.hcl:ro",
            "-v", f"{self.data_dir}:/openbao/file",
            OPENBAO_IMAGE,
            "server", "-config=/openbao/config/d3e.hcl",
        )
        if not result.stdout.strip():
            raise ConformanceError("OpenBao container did not start")
        self._wait_http()

    def stop(self) -> None:
        self._docker("exec", CONTAINER_NAME, "sh", "-c", "chmod -R a+rwX /openbao/file", check=False)
        self._docker("rm", "-f", CONTAINER_NAME, check=False)

    def logs(self) -> str:
        return self._docker("logs", CONTAINER_NAME, check=False).stdout

    def _wait_http(self) -> None:
        deadline = time.time() + 30
        last: Exception | None = None
        while time.time() < deadline:
            try:
                req = urllib.request.Request(f"{self.addr}/v1/sys/health", method="GET")
                urllib.request.urlopen(req, timeout=1).read()
                return
            except urllib.error.HTTPError:
                return
            except Exception as exc:
                last = exc
                time.sleep(0.25)
        raise ConformanceError(f"OpenBao HTTP endpoint not ready: {last}\n{self.logs()}")

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        *,
        token: str | None = None,
        expected: tuple[int, ...] = (200, 204),
    ) -> dict[str, object]:
        data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        headers = {"Content-Type": "application/json"}
        use_token = token if token is not None else self.root_token
        if use_token:
            headers["X-Vault-Token"] = use_token
        req = urllib.request.Request(f"{self.addr}/v1/{path.lstrip('/')}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read()
                status = response.status
        except urllib.error.HTTPError as exc:
            body = exc.read()
            status = exc.code
        if status not in expected:
            text = body.decode("utf-8", "replace")
            raise ConformanceError(f"OpenBao {method} {path} returned HTTP {status}: {text[:500]}")
        if not body:
            return {}
        decoded = json.loads(body)
        if not isinstance(decoded, dict):
            raise ConformanceError("OpenBao response was not an object")
        return decoded

    def initialize(self) -> None:
        response = self.request(
            "POST", "sys/init", {"secret_shares": 1, "secret_threshold": 1}, token="", expected=(200,)
        )
        keys = response.get("keys_base64")
        root_token = response.get("root_token")
        if not isinstance(keys, list) or len(keys) != 1 or not isinstance(keys[0], str) or not isinstance(root_token, str):
            raise ConformanceError("unexpected OpenBao init response")
        self.unseal_key = keys[0]
        self.root_token = root_token
        self.unseal()

    def unseal(self) -> None:
        if not self.unseal_key:
            raise ConformanceError("missing unseal key")
        response = self.request("POST", "sys/unseal", {"key": self.unseal_key}, token="", expected=(200,))
        if response.get("sealed") is not False:
            raise ConformanceError("OpenBao did not unseal")

    def configure_transit_and_runtime_policy(self) -> None:
        self.request("POST", "sys/mounts/transit", {"type": "transit"}, expected=(204,))
        policy = '''
path "transit/hmac/*" { capabilities = ["update"] }
path "transit/verify/*" { capabilities = ["update"] }
path "transit/sign/*" { capabilities = ["update"] }
path "transit/keys/*" { capabilities = ["read"] }
'''.strip()
        self.request("PUT", "sys/policies/acl/d3e-runtime", {"policy": policy}, expected=(204,))
        token = self.request(
            "POST",
            "auth/token/create",
            {"policies": ["d3e-runtime"], "no_default_policy": True, "renewable": False},
            expected=(200,),
        )
        auth = token.get("auth")
        if not isinstance(auth, dict) or not isinstance(auth.get("client_token"), str):
            raise ConformanceError("runtime token creation failed")
        self.runtime_token = auth["client_token"]

    def snapshot_storage(self, destination: Path) -> None:
        self.stop()
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(self.data_dir, destination)
        self.start()
        self.unseal()

    def restore_storage(self, snapshot: Path) -> None:
        self.stop()
        if self.data_dir.exists():
            shutil.rmtree(self.data_dir)
        shutil.copytree(snapshot, self.data_dir)
        os.chmod(self.data_dir, 0o777)
        for path in self.data_dir.rglob("*"):
            try:
                os.chmod(path, 0o777 if path.is_dir() else 0o666)
            except PermissionError:
                pass
        self.start()
        self.unseal()


class OpenBaoAdmin:
    """Evidence setup/lifecycle authority; never handed to runtime cryptographic ports."""

    def __init__(self, controller: OpenBaoController):
        self.controller = controller

    def _metadata(self, provider_ref: str) -> dict[str, object]:
        result = self.controller.request("GET", f"transit/keys/{provider_ref}", expected=(200,))
        data = result.get("data")
        if not isinstance(data, dict):
            raise ConformanceError("missing OpenBao key metadata")
        return data

    def _assert_non_exportable(self, provider_ref: str) -> None:
        data = self._metadata(provider_ref)
        if data.get("exportable") is not False or data.get("allow_plaintext_backup") is not False:
            raise ConformanceError("provider key is exportable or allows plaintext backup")

    def provision_domain(self, domain: KeyDomain) -> str:
        ref = domain.provider_ref
        self.controller.request(
            "POST",
            f"transit/keys/{ref}",
            {"type": "hmac", "exportable": False, "allow_plaintext_backup": False},
            expected=(204,),
        )
        self._assert_non_exportable(ref)
        return ref

    @staticmethod
    def signing_ref_for_client(client_principal: str) -> str:
        client = _canon(client_principal, "client_principal")
        return "jlm-client-" + hashlib.sha256(client.encode()).hexdigest()

    def provision_signing_key(self, client_principal: str) -> str:
        ref = self.signing_ref_for_client(client_principal)
        self.controller.request(
            "POST",
            f"transit/keys/{ref}",
            {"type": "ed25519", "exportable": False, "allow_plaintext_backup": False},
            expected=(204,),
        )
        self._assert_non_exportable(ref)
        return ref

    def rotate(self, provider_ref: str) -> int:
        self.controller.request("POST", f"transit/keys/{provider_ref}/rotate", {}, expected=(204,))
        latest = self._metadata(provider_ref).get("latest_version")
        if not isinstance(latest, int):
            raise ConformanceError("invalid provider latest_version after rotate")
        return latest

    def set_minimum_version(self, provider_ref: str, generation: int) -> None:
        self.controller.request(
            "POST",
            f"transit/keys/{provider_ref}/config",
            {"min_decryption_version": generation, "min_encryption_version": generation},
            expected=(204,),
        )

    def create_historical_verifier_token(self, provider_ref: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9-]", "-", provider_ref)[:80]
        policy_name = f"d3e-historical-{safe}"
        policy = (
            f'path "transit/verify/{provider_ref}/*" {{ capabilities = ["update"] }}\n'
            f'path "transit/keys/{provider_ref}" {{ capabilities = ["read"] }}'
        )
        self.controller.request("PUT", f"sys/policies/acl/{policy_name}", {"policy": policy}, expected=(204,))
        token = self.controller.request(
            "POST",
            "auth/token/create",
            {"policies": [policy_name], "no_default_policy": True, "renewable": False},
            expected=(200,),
        )
        auth = token.get("auth")
        if not isinstance(auth, dict) or not isinstance(auth.get("client_token"), str):
            raise ConformanceError("historical verifier token creation failed")
        return auth["client_token"]


class OpenBaoRuntimeBackend:
    """Provider-neutral runtime adapter with a fixed least-privilege token and no admin methods."""

    def __init__(self, *, addr: str, token: str):
        self.addr = addr.rstrip("/")
        self._token = _canon(token, "runtime_token")

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        *,
        expected: tuple[int, ...] = (200, 204),
    ) -> dict[str, object]:
        data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        headers = {"Content-Type": "application/json", "X-Vault-Token": self._token}
        req = urllib.request.Request(f"{self.addr}/v1/{path.lstrip('/')}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read()
                status = response.status
        except urllib.error.HTTPError as exc:
            body = exc.read()
            status = exc.code
        if status not in expected:
            raise ConformanceError(
                f"OpenBao runtime {method} {path} returned HTTP {status}: {body.decode('utf-8', 'replace')[:400]}"
            )
        if not body:
            return {}
        decoded = json.loads(body)
        if not isinstance(decoded, dict):
            raise ConformanceError("OpenBao runtime response was not an object")
        return decoded

    def _metadata(self, provider_ref: str) -> dict[str, object]:
        result = self._request("GET", f"transit/keys/{provider_ref}", expected=(200,))
        data = result.get("data")
        if not isinstance(data, dict):
            raise ConformanceError("missing OpenBao key metadata")
        if data.get("exportable") is not False or data.get("allow_plaintext_backup") is not False:
            raise LifecycleRejected("runtime refuses exportable/plaintext-backup key authority")
        return data

    def binds_domain(self, *, provider_ref: str, domain: KeyDomain) -> bool:
        return hmac.compare_digest(provider_ref, domain.provider_ref)

    @staticmethod
    def signing_ref_for_client(client_principal: str) -> str:
        return OpenBaoAdmin.signing_ref_for_client(client_principal)

    def latest_generation(self, provider_ref: str) -> int:
        data = self._metadata(provider_ref)
        latest = data.get("latest_version")
        if not isinstance(latest, int) or latest <= 0:
            raise ConformanceError("invalid provider latest_version")
        return latest

    def hmac(self, *, provider_ref: str, generation: int, message: bytes) -> str:
        result = self._request(
            "POST", f"transit/hmac/{provider_ref}/sha2-256",
            {"input": _b64(message), "key_version": generation}, expected=(200,),
        )
        data = result.get("data")
        value = data.get("hmac") if isinstance(data, dict) else None
        if not isinstance(value, str) or _tagged_version(value) != generation:
            raise ConformanceError("missing/mismatched OpenBao HMAC")
        return value

    def verify_hmac(self, *, provider_ref: str, generation: int, message: bytes, mac_value: str) -> bool:
        if _tagged_version(mac_value) != generation:
            return False
        result = self._request(
            "POST", f"transit/verify/{provider_ref}/sha2-256",
            {"input": _b64(message), "hmac": mac_value}, expected=(200,),
        )
        data = result.get("data")
        return bool(data.get("valid")) if isinstance(data, dict) else False

    def sign(self, *, provider_ref: str, generation: int, message: bytes) -> str:
        result = self._request(
            "POST", f"transit/sign/{provider_ref}",
            {"input": _b64(message), "key_version": generation}, expected=(200,),
        )
        data = result.get("data")
        value = data.get("signature") if isinstance(data, dict) else None
        if not isinstance(value, str) or _tagged_version(value) != generation:
            raise ConformanceError("missing/mismatched OpenBao signature")
        return value

    def verify_signature(self, *, provider_ref: str, generation: int, message: bytes, signature: str) -> bool:
        if _tagged_version(signature) != generation:
            return False
        result = self._request(
            "POST", f"transit/verify/{provider_ref}",
            {"input": _b64(message), "signature": signature}, expected=(200,),
        )
        data = result.get("data")
        return bool(data.get("valid")) if isinstance(data, dict) else False


def _tagged_version(value: str) -> int:
    match = re.match(r"^(?:vault|ref):v([1-9][0-9]*):", value)
    if not match:
        raise ConformanceError("non-canonical provider cryptographic result")
    return int(match.group(1))
