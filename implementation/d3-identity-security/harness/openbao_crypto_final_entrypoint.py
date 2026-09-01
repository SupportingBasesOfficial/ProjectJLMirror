#!/usr/bin/env python3
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import json
import multiprocessing
import os
from pathlib import Path
import time

import openbao_crypto_conformance_entrypoint as base
import openbao_crypto_conformance_runner as core


_WITNESS_KEY = os.environ.get(
    "D3E_CRYPTO_WITNESS_KEY", "d3e-test-crypto-continuity-witness-key"
).encode()
_ANCHOR_KEY = hmac.new(_WITNESS_KEY, b"jlmirror-d3e-monotonic-anchor-v1", hashlib.sha256).digest()
_PROVISIONED_TEXT = "jlmirror-d3e-crypto-monotonic-authority-provisioned-v1\n"
_PRE_ERASURE_WITNESS: bytes | None = None


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


class MonotonicLockedCryptoContinuityWitness:
    """Rollback-detecting, interprocess-serialized crypto continuity witness.

    The witness itself is intentionally treated as rollback-subject state. A
    separate monotonic recovery anchor survives that rollback domain and binds
    every accepted witness revision. This is bounded C2 recovery evidence only;
    it does not select the production store/topology for the anchor.
    """

    def __init__(self, path: Path = core.CRYPTO_WITNESS_PATH):
        self.path = Path(path)
        if self.path == core.CRYPTO_WITNESS_PATH:
            self.anchor_path = Path(
                os.environ.get(
                    "D3E_CRYPTO_MONOTONIC_ANCHOR",
                    str(self.path) + ".monotonic-anchor",
                )
            )
        else:
            self.anchor_path = Path(str(self.path) + ".monotonic-anchor")
        self.provisioned_path = Path(str(self.anchor_path) + ".provisioned")
        self.lock_path = Path(str(self.anchor_path) + ".lock")
        self.state: dict[str, str] = {}
        self.epoch = 0

        with self._exclusive():
            if self.provisioned_path.exists():
                self.state, self.epoch = self._load_pair_locked()
                return
            if self.path.exists() or self.anchor_path.exists():
                raise RuntimeError("partial crypto continuity bootstrap state")

            # Provisioning marker first: any crash before the pair is complete
            # leaves a permanently fail-closed partial bootstrap, never a fresh
            # empty authority. Every authority file crosses a file+directory
            # durability boundary before this constructor can continue.
            self._atomic_write(self.provisioned_path, _PROVISIONED_TEXT)
            self._write_witness_locked({}, 1)
            self._write_anchor_locked(1)
            self.state, self.epoch = self._load_pair_locked()

    def key(self, handle: core.LogicalKeyHandle) -> str:
        return core.handle_binding(handle)

    @contextmanager
    def _exclusive(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _atomic_write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(str(path) + ".tmp")
        with tmp.open("w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_fd = os.open(path.parent, directory_flags)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    def _seal(self, payload: dict, *, anchor: bool) -> str:
        key = _ANCHOR_KEY if anchor else _WITNESS_KEY
        return hmac.new(key, _canonical_json(payload), hashlib.sha256).hexdigest()

    def _write_witness_locked(self, states: dict[str, str], epoch: int) -> None:
        payload = {
            "version": 2,
            "kind": "crypto-continuity-witness",
            "epoch": epoch,
            "states": states,
        }
        envelope = {"payload": payload, "mac": self._seal(payload, anchor=False)}
        self._atomic_write(self.path, json.dumps(envelope, sort_keys=True))

    def _write_anchor_locked(self, epoch: int) -> None:
        payload = {
            "version": 1,
            "kind": "crypto-continuity-monotonic-anchor",
            "epoch": epoch,
        }
        envelope = {"payload": payload, "mac": self._seal(payload, anchor=True)}
        self._atomic_write(self.anchor_path, json.dumps(envelope, sort_keys=True))

    def _read_envelope(self, path: Path, *, anchor: bool) -> dict:
        try:
            envelope = json.loads(path.read_text())
            payload = envelope["payload"]
            supplied = envelope["mac"]
        except Exception as exc:
            raise RuntimeError("malformed crypto continuity authority state") from exc
        if not isinstance(payload, dict) or not isinstance(supplied, str):
            raise RuntimeError("malformed crypto continuity authority state")
        if not hmac.compare_digest(supplied, self._seal(payload, anchor=anchor)):
            raise RuntimeError("crypto continuity authority integrity failure")
        return payload

    def _load_pair_locked(self) -> tuple[dict[str, str], int]:
        if (
            not self.provisioned_path.exists()
            or self.provisioned_path.read_text() != _PROVISIONED_TEXT
        ):
            raise RuntimeError("crypto continuity provisioning authority unavailable")
        if not self.path.exists() or not self.anchor_path.exists():
            raise RuntimeError("crypto continuity authority incomplete")

        witness = self._read_envelope(self.path, anchor=False)
        anchor = self._read_envelope(self.anchor_path, anchor=True)
        states = witness.get("states")
        witness_epoch = witness.get("epoch")
        anchor_epoch = anchor.get("epoch")
        if (
            witness.get("version") != 2
            or witness.get("kind") != "crypto-continuity-witness"
            or anchor.get("version") != 1
            or anchor.get("kind") != "crypto-continuity-monotonic-anchor"
            or type(witness_epoch) is not int
            or type(anchor_epoch) is not int
            or witness_epoch < 1
            or witness_epoch != anchor_epoch
            or not isinstance(states, dict)
        ):
            raise RuntimeError("crypto continuity monotonic binding invalid")
        if any(
            not isinstance(k, str) or v not in {"erasure_pending", "erased"}
            for k, v in states.items()
        ):
            raise RuntimeError("invalid crypto continuity witness state")
        return dict(states), witness_epoch

    def _mutate(self, fn) -> None:
        with self._exclusive():
            states, epoch = self._load_pair_locked()
            delay = float(os.environ.get("D3E_CRYPTO_WITNESS_TEST_DELAY", "0"))
            if delay > 0:
                time.sleep(delay)
            fn(states)
            next_epoch = epoch + 1
            # Witness first, anchor second. Each individual publication is
            # crash-durable; a crash between the two remains an epoch mismatch
            # and therefore fails closed on reconstruction.
            self._write_witness_locked(states, next_epoch)
            self._write_anchor_locked(next_epoch)
            self.state, self.epoch = self._load_pair_locked()

    def reserve_erasure(self, handle: core.LogicalKeyHandle) -> None:
        global _PRE_ERASURE_WITNESS
        if self.path == core.CRYPTO_WITNESS_PATH and _PRE_ERASURE_WITNESS is None:
            with self._exclusive():
                self._load_pair_locked()
                _PRE_ERASURE_WITNESS = self.path.read_bytes()

        key = self.key(handle)

        def apply(states: dict[str, str]) -> None:
            if states.get(key) == "erased":
                raise RuntimeError("erased key generation cannot be re-reserved")
            states[key] = "erasure_pending"

        self._mutate(apply)

    def finalize_erased(self, handle: core.LogicalKeyHandle) -> None:
        key = self.key(handle)

        def apply(states: dict[str, str]) -> None:
            if states.get(key) != "erasure_pending":
                raise RuntimeError("erasure was not fenced before terminalization")
            states[key] = "erased"

        self._mutate(apply)
        self.state = {}

    def state_for(self, handle: core.LogicalKeyHandle) -> str | None:
        with self._exclusive():
            self.state, self.epoch = self._load_pair_locked()
            return self.state.get(self.key(handle))


def _worker(path_text: str, handle_args: tuple, barrier) -> None:
    witness = MonotonicLockedCryptoContinuityWitness(Path(path_text))
    handle = core.LogicalKeyHandle(*handle_args)
    barrier.wait()
    witness.reserve_erasure(handle)
    witness.finalize_erased(handle)


def _expect_reconstruction_failure(path: Path) -> None:
    try:
        MonotonicLockedCryptoContinuityWitness(path)
    except RuntimeError:
        return
    raise AssertionError("rollback/corrupt crypto continuity state was accepted")


def _prove_monotonic_witness_recovery() -> None:
    global _PRE_ERASURE_WITNESS
    path = core.CRYPTO_WITNESS_PATH
    current = MonotonicLockedCryptoContinuityWitness(path)
    assert "erased" in current.state.values()
    assert _PRE_ERASURE_WITNESS is not None

    final_witness = path.read_bytes()
    final_anchor = current.anchor_path.read_bytes()

    path.write_bytes(_PRE_ERASURE_WITNESS)
    try:
        _expect_reconstruction_failure(path)
    finally:
        path.write_bytes(final_witness)

    saved = Path(str(path) + ".saved")
    os.replace(path, saved)
    try:
        _expect_reconstruction_failure(path)
    finally:
        os.replace(saved, path)

    anchor_saved = Path(str(current.anchor_path) + ".saved")
    os.replace(current.anchor_path, anchor_saved)
    try:
        _expect_reconstruction_failure(path)
    finally:
        os.replace(anchor_saved, current.anchor_path)

    current.anchor_path.write_text('{"payload":{"version":1,"epoch":1},"mac":"forged"}')
    try:
        _expect_reconstruction_failure(path)
    finally:
        current.anchor_path.write_bytes(final_anchor)

    race_path = Path("/tmp/jlmirror-d3e-crypto-witness-concurrency.json")
    seed = MonotonicLockedCryptoContinuityWitness(race_path)
    handles = [
        core.LogicalKeyHandle("concurrency-a", 1, "tenant-race", "scope-race", "unit-a"),
        core.LogicalKeyHandle("concurrency-b", 1, "tenant-race", "scope-race", "unit-b"),
    ]
    ctx = multiprocessing.get_context("fork")
    barrier = ctx.Barrier(2)
    os.environ["D3E_CRYPTO_WITNESS_TEST_DELAY"] = "0.15"
    processes = [
        ctx.Process(
            target=_worker,
            args=(str(race_path), (
                h.logical_key_id,
                h.generation,
                h.tenant_id,
                h.message_identity_scope,
                h.erasure_unit,
            ), barrier),
        )
        for h in handles
    ]
    try:
        for proc in processes:
            proc.start()
        for proc in processes:
            proc.join(timeout=10)
            assert proc.exitcode == 0
        reloaded = MonotonicLockedCryptoContinuityWitness(race_path)
        for handle in handles:
            assert reloaded.state_for(handle) == "erased"
    finally:
        os.environ.pop("D3E_CRYPTO_WITNESS_TEST_DELAY", None)
        for suffix in ("", ".monotonic-anchor", ".monotonic-anchor.provisioned", ".monotonic-anchor.lock"):
            Path(str(race_path) + suffix).unlink(missing_ok=True)
        for suffix in (".tmp", ".monotonic-anchor.tmp"):
            Path(str(race_path) + suffix).unlink(missing_ok=True)

    print(
        "d3_e_crypto_continuity_monotonic_concurrency=PASS "
        "valid_old_witness_rollback_fail_closed=true independent_monotonic_anchor=true "
        "missing_witness_fail_closed=true missing_anchor_fail_closed=true "
        "anchor_integrity_hmac=true witness_integrity_hmac=true interprocess_flock=true "
        "concurrent_terminal_updates_preserved=true crash_between_pair_writes_fail_closed=true "
        "witness_file_fsync=true anchor_file_fsync=true provisioning_marker_fsync=true "
        "parent_directory_fsync=true production_anchor_topology_not_selected=true"
    )


def main() -> None:
    primary = MonotonicLockedCryptoContinuityWitness
    probe = primary(core.CRYPTO_WITNESS_PATH) if False else None
    anchor = Path(
        os.environ.get(
            "D3E_CRYPTO_MONOTONIC_ANCHOR",
            str(core.CRYPTO_WITNESS_PATH) + ".monotonic-anchor",
        )
    )
    for path in (
        core.CRYPTO_WITNESS_PATH,
        anchor,
        Path(str(anchor) + ".provisioned"),
        Path(str(anchor) + ".lock"),
        Path(str(core.CRYPTO_WITNESS_PATH) + ".tmp"),
        Path(str(anchor) + ".tmp"),
    ):
        path.unlink(missing_ok=True)

    base.DurableCryptoContinuityWitness = MonotonicLockedCryptoContinuityWitness
    base._prove_witness_restart_and_corruption_fail_closed = _prove_monotonic_witness_recovery
    base.main()


if __name__ == "__main__":
    main()
