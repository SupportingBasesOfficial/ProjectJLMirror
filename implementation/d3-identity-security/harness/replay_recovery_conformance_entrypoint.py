#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

import replay_recovery_conformance_runner as core
import replay_recovery_strict_entrypoint as strict
from replay_recovery_port_probe import prove_port_single_winner
from replay_recovery_capability_binding import (
    capture_recovery_boundary_exact,
    recover_from_witness_exact,
)


class CrashDurableProviderState(strict.DurableProviderState):
    """Final source-evidence provider state with file+directory durability."""

    def _atomic_write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(str(path) + ".tmp")
        with tmp.open("w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        directory_fd = os.open(
            path.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)


def durable_provider_server() -> None:
    core.ProviderState = CrashDurableProviderState
    core.provider_server()


def start_provider() -> core.subprocess.Popen:
    proc = core.subprocess.Popen(
        [core.sys.executable, __file__, "--durable-provider-server"],
        stdout=core.subprocess.DEVNULL,
        stderr=core.subprocess.DEVNULL,
    )
    core.wait_provider()
    return proc


# Direct port concurrency remains a useful storage-boundary probe but cannot
# claim private_key_jwt/token-boundary evidence. The stronger proof is executed
# through two real HTTP token replicas in its own exact-head gate.
core.prove_single_winner = prove_port_single_winner

# Exact provider capability identity is canonical for both recovery capture and
# restore. Operation-id coincidence alone can never authorize reconciliation.
strict.capture_recovery_boundary_strict = capture_recovery_boundary_exact
strict.recover_from_witness_strict = recover_from_witness_exact

# The final executed provider path supersedes the weaker orderly-restart-only
# state publisher in the underlying strict layer. Child processes execute this
# entrypoint too, so every provider /send and /probe persists through fsync(file)
# + atomic rename + fsync(parent directory) before a response can be emitted.
strict.DurableProviderState = CrashDurableProviderState
strict.durable_provider_server = durable_provider_server
strict.start_provider = start_provider

from replay_recovery_strict_entrypoint import *  # noqa: E402,F401,F403

# Re-export the canonical functions for final hardening layers importing this
# module as their base.
capture_recovery_boundary_strict = capture_recovery_boundary_exact
recover_from_witness_strict = recover_from_witness_exact


def main() -> None:
    strict.main()


if __name__ == "__main__":
    if "--durable-provider-server" in core.sys.argv:
        durable_provider_server()
    else:
        main()
