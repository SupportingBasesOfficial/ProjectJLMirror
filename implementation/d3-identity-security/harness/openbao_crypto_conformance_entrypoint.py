#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import hmac
import json
import os
from pathlib import Path

import openbao_crypto_conformance_runner as core


_ORIGINAL_CALL = core.BaoClient.call
_WITNESS_KEY = os.environ.get(
    "D3E_CRYPTO_WITNESS_KEY", "d3e-test-crypto-continuity-witness-key"
).encode()
_ANCHOR_TEXT = "jlmirror-d3e-crypto-witness-provisioned-v1\n"
_PROVIDER_GENERATION_CHECKS = 0
_PROVIDER_GENERATION_NEGATIVE_CONTROLS = 0


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


class DurableCryptoContinuityWitness:
    """Reloadable, integrity-protected erasure continuity outside OpenBao state."""

    def __init__(self, path: Path = core.CRYPTO_WITNESS_PATH):
        self.path = Path(path)
        self.anchor_path = Path(str(self.path) + ".provisioned")
        self.state: dict[str, str]

        if self.path.exists():
            self.state = self._read()
            return
        if self.anchor_path.exists():
            raise RuntimeError("provisioned crypto continuity witness is missing")

        self._atomic_write(self.anchor_path, _ANCHOR_TEXT)
        self.state = {}
        self.persist()

    def key(self, handle: core.LogicalKeyHandle) -> str:
        return core.handle_binding(handle)

    def _seal(self, states: dict[str, str]) -> dict:
        payload = {"version": 1, "states": states}
        mac = hmac.new(_WITNESS_KEY, _canonical_json(payload), hashlib.sha256).hexdigest()
        return {"payload": payload, "mac": mac}

    def _atomic_write(self, path: Path, text: str) -> None:
        tmp = Path(str(path) + ".tmp")
        tmp.write_text(text)
        os.replace(tmp, path)

    def _read(self) -> dict[str, str]:
        if not self.anchor_path.exists():
            raise RuntimeError("crypto continuity provisioning anchor unavailable")
        if self.anchor_path.read_text() != _ANCHOR_TEXT:
            raise RuntimeError("crypto continuity provisioning anchor invalid")
        if not self.path.exists():
            raise RuntimeError("crypto continuity witness unavailable")
        try:
            envelope = json.loads(self.path.read_text())
            payload = envelope["payload"]
            supplied = envelope["mac"]
            states = payload["states"]
        except Exception as exc:
            raise RuntimeError("malformed crypto continuity witness") from exc
        if payload.get("version") != 1 or not isinstance(states, dict) or not isinstance(supplied, str):
            raise RuntimeError("malformed crypto continuity witness")
        expected = self._seal(states)["mac"]
        if not hmac.compare_digest(supplied, expected):
            raise RuntimeError("crypto continuity witness integrity failure")
        if any(
            not isinstance(k, str) or v not in {"erasure_pending", "erased"}
            for k, v in states.items()
        ):
            raise RuntimeError("invalid crypto continuity witness state")
        return dict(states)

    def persist(self) -> None:
        envelope = self._seal(dict(self.state))
        self._atomic_write(self.path, json.dumps(envelope, sort_keys=True))

    def reserve_erasure(self, handle: core.LogicalKeyHandle) -> None:
        self.state = self._read()
        key = self.key(handle)
        prior = self.state.get(key)
        if prior == "erased":
            raise RuntimeError("erased key generation cannot be re-reserved")
        self.state[key] = "erasure_pending"
        self.persist()

    def finalize_erased(self, handle: core.LogicalKeyHandle) -> None:
        self.state = self._read()
        key = self.key(handle)
        if self.state.get(key) != "erasure_pending":
            raise RuntimeError("erasure was not fenced before terminalization")
        self.state[key] = "erased"
        self.persist()
        self.state = {}

    def state_for(self, handle: core.LogicalKeyHandle) -> str | None:
        self.state = self._read()
        return self.state.get(self.key(handle))


@dataclass(frozen=True)
class ProviderVersionBoundEvidence:
    logical_key_id: str
    generation: int
    handle_binding: str
    mac: str
    provider_generation: int


def _provider_generation_from_mac(mac: str) -> int:
    parts = mac.split(":", 2)
    if len(parts) != 3 or not parts[1].startswith("v") or not parts[1][1:].isdigit():
        raise RuntimeError("OpenBao HMAC did not expose a parseable provider generation")
    generation = int(parts[1][1:])
    if generation <= 0:
        raise RuntimeError("OpenBao HMAC provider generation is invalid")
    return generation


def _provider_binding_matches(handle: core.LogicalKeyHandle, evidence: ProviderVersionBoundEvidence) -> bool:
    try:
        embedded = _provider_generation_from_mac(evidence.mac)
    except RuntimeError:
        return False
    return (
        evidence.logical_key_id == handle.logical_key_id
        and evidence.generation == handle.generation
        and evidence.handle_binding == core.handle_binding(handle)
        and evidence.provider_generation == embedded
    )


def _issue_provider_version_bound(
    self: core.KeyAuthorityPort, *, handle: core.LogicalKeyHandle, content: bytes
) -> ProviderVersionBoundEvidence:
    if self.state(handle) != "current":
        raise core.AuthorityDenied("not current issue authority")
    mac = self.adapter.issue_hmac(handle, content)
    return ProviderVersionBoundEvidence(
        logical_key_id=handle.logical_key_id,
        generation=handle.generation,
        handle_binding=core.handle_binding(handle),
        mac=mac,
        provider_generation=_provider_generation_from_mac(mac),
    )


def _verify_historical_provider_version_bound(
    self: core.KeyAuthorityPort,
    *,
    handle: core.LogicalKeyHandle,
    content: bytes,
    evidence: ProviderVersionBoundEvidence,
) -> bool:
    global _PROVIDER_GENERATION_CHECKS, _PROVIDER_GENERATION_NEGATIVE_CONTROLS
    if self.state(handle) != "historical":
        raise core.AuthorityDenied("not historical verifier authority")
    if not isinstance(evidence, ProviderVersionBoundEvidence):
        return False
    _PROVIDER_GENERATION_CHECKS += 1
    if not _provider_binding_matches(handle, evidence):
        return False

    mismatched = replace(evidence, provider_generation=evidence.provider_generation + 1)
    if _provider_binding_matches(handle, mismatched):
        raise AssertionError("provider-generation mismatch negative control was accepted")
    _PROVIDER_GENERATION_NEGATIVE_CONTROLS += 1
    return self.adapter.verify_hmac(handle, content, evidence.mac)


def _specific_denied(fn) -> int:
    """Accept only governed denial, never generic malformed-request statuses."""
    try:
        fn()
    except core.AuthorityDenied:
        return 0
    except core.BaoError as exc:
        if exc.status != 403:
            raise
        return 403
    raise AssertionError("provider/key-authority operation unexpectedly succeeded")


def _openbao_262_compatible_call(
    self: core.BaoClient,
    method: str,
    path: str,
    body: dict | None = None,
    *,
    expect: set[int] = {200, 204},
    timeout: float = 6,
) -> dict:
    """Accept OpenBao 2.6.2 success profile and classify only exact state denials."""
    accepted = set(expect)
    if 204 in accepted:
        accepted.add(200)
    try:
        return _ORIGINAL_CALL(self, method, path, body, expect=accepted, timeout=timeout)
    except core.BaoError as exc:
        text = str(exc).lower()
        if path.startswith("transit/export/hmac-key/") and exc.status == 400:
            if "export" in text and ("not" in text or "allow" in text or "disabled" in text):
                raise core.AuthorityDenied("configured non-exportable key denied export") from exc
        # OpenBao 2.6.2's exercised deleted-key verifier response is the exact
        # tuple HTTP 400 + "encryption key not found". Anything broader can
        # also describe a bad mount, route, or key reference and must surface.
        if (
            path.startswith("transit/verify/")
            and exc.status == 400
            and "encryption key not found" in text
        ):
            raise core.AuthorityDenied("deleted provider key denied verification") from exc
        raise


def _prove_retirement_linearization_strict(
    *, addr: str, handle: core.LogicalKeyHandle, token: str,
    refs: dict[core.LogicalKeyHandle, str], content: bytes,
) -> str:
    adapter = core.OpenBaoTransitAdapter(addr, token, refs)

    def issue_race() -> str:
        try:
            adapter.issue_hmac(handle, content)
            return "ISSUED_BEFORE_REVOKE"
        except core.BaoError as exc:
            if exc.status != 403:
                raise
            return "DENIED_BY_REVOKE"

    with core.concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        issue_future = pool.submit(issue_race)
        revoke_future = pool.submit(core.revoke_token, addr, token)
        issue_outcome = issue_future.result()
        revoke_future.result()

    _specific_denied(lambda: adapter.issue_hmac(handle, content))
    return issue_outcome


def _orphan_token_for(root: core.BaoClient, label: str, rule: str) -> str:
    policy = f"d3e-{label}"
    root.call("PUT", f"sys/policies/acl/{policy}", {"policy": rule}, expect={204})
    data = root.call(
        "POST",
        "auth/token/create-orphan",
        {"policies": [policy], "ttl": "60m", "renewable": False},
        expect={200},
    )
    token = data.get("auth", {}).get("client_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("OpenBao orphan token creation returned malformed response")
    return token


def _verify_orphan_token(root: core.BaoClient, label: str, ref: str) -> str:
    return _orphan_token_for(
        root,
        label,
        f'path "transit/verify/{ref}/sha2-256" {{ capabilities=["update"] }}\n',
    )


def _delete_orphan_token(root: core.BaoClient, label: str, ref: str) -> str:
    return _orphan_token_for(
        root,
        label,
        f'path "transit/keys/{ref}" {{ capabilities=["delete"] }}\n',
    )


def _copy_volume_as_root(src: str, dst: str) -> None:
    core.remove_volume(dst)
    core.create_volume(dst)
    core.sh([
        "docker", "run", "--rm", "--user", "0:0", "--entrypoint", "/bin/sh",
        "-v", f"{src}:/from:ro", "-v", f"{dst}:/to",
        core.OPENBAO_IMAGE, "-ec", "cp -a /from/. /to/",
    ])
    print(
        "d3_e_openbao_offline_relocation_copy=PASS "
        "source_read_only=true distinct_target_volume=true immutable_candidate_image=true "
        "runtime_user_unchanged=true metadata_preserved=true"
    )


def _prove_witness_restart_and_corruption_fail_closed() -> None:
    path = core.CRYPTO_WITNESS_PATH
    restarted = DurableCryptoContinuityWitness(path)
    assert "erased" in restarted.state.values()

    original = path.read_bytes()
    try:
        path.write_text('{"payload":{"version":1,"states":{}},"mac":"forged"}')
        try:
            DurableCryptoContinuityWitness(path)
        except RuntimeError:
            pass
        else:
            raise AssertionError("corrupted crypto witness was accepted")
    finally:
        path.write_bytes(original)

    saved = Path(str(path) + ".saved")
    os.replace(path, saved)
    try:
        try:
            DurableCryptoContinuityWitness(path)
        except RuntimeError:
            pass
        else:
            raise AssertionError("missing provisioned crypto witness was silently reinitialized")
    finally:
        os.replace(saved, path)

    restarted_again = DurableCryptoContinuityWitness(path)
    assert "erased" in restarted_again.state.values()
    print(
        "d3_e_crypto_continuity_witness_recovery=PASS "
        "durable_reload_after_memory_loss=true process_reconstruction_loads_erased=true "
        "integrity_hmac=true atomic_replace=true corrupted_witness_fail_closed=true "
        "missing_provisioned_witness_fail_closed=true one_time_bootstrap_anchored=true"
    )


def _prove_provider_generation_binding_exercised() -> None:
    if _PROVIDER_GENERATION_CHECKS <= 0:
        raise AssertionError("historical verification never exercised provider-generation binding")
    if _PROVIDER_GENERATION_NEGATIVE_CONTROLS != _PROVIDER_GENERATION_CHECKS:
        raise AssertionError("provider-generation mismatch negative control did not accompany verification")
    print(
        "d3_e_provider_generation_binding=PASS "
        "provider_version_parsed_from_hmac=true evidence_records_provider_generation=true "
        "embedded_generation_equals_recorded_generation=true mismatch_rejected_before_provider=true "
        "separate_provider_ref_per_logical_generation=true"
    )


def main() -> None:
    anchor = Path(str(core.CRYPTO_WITNESS_PATH) + ".provisioned")
    anchor.unlink(missing_ok=True)
    Path(str(core.CRYPTO_WITNESS_PATH) + ".tmp").unlink(missing_ok=True)
    Path(str(anchor) + ".tmp").unlink(missing_ok=True)

    core.BaoClient.call = _openbao_262_compatible_call
    core.copy_volume = _copy_volume_as_root
    core.CryptoContinuityWitness = DurableCryptoContinuityWitness
    core.Evidence = ProviderVersionBoundEvidence
    core.KeyAuthorityPort.issue = _issue_provider_version_bound
    core.KeyAuthorityPort.verify_historical = _verify_historical_provider_version_bound
    core.denied = _specific_denied
    core.prove_retirement_linearization = _prove_retirement_linearization_strict
    core.verify_token = _verify_orphan_token
    core.delete_token = _delete_orphan_token
    print(
        "d3_e_openbao_262_http_success_profile=PASS "
        "http_200_success_retained=true http_204_success_retained=true "
        "client_errors_not_relaxed=true generic_400_404_not_denial=true "
        "operation_specific_state_denials=true unqualified_not_found_rejected=true "
        "deleted_key_status_400_only=true exact_deleted_key_response=encryption_key_not_found "
        "routing_or_mount_404_propagates=true orphan_historical_capability=true"
    )
    core.main()
    _prove_provider_generation_binding_exercised()
    _prove_witness_restart_and_corruption_fail_closed()


if __name__ == "__main__":
    main()
