#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

import replay_recovery_conformance_runner as core
import replay_recovery_strict_entrypoint as strict
from replay_recovery_port_probe import prove_port_single_winner
from replay_recovery_capability_binding import capture_recovery_boundary_exact


class CrashDurableProviderState(strict.DurableProviderState):
    """Final source-evidence provider state with file+directory durability."""
    def _atomic_write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(str(path) + ".tmp")
        with tmp.open("w") as stream:
            stream.write(text); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try: os.fsync(directory_fd)
        finally: os.close(directory_fd)


def durable_provider_server() -> None:
    core.ProviderState = CrashDurableProviderState
    core.provider_server()


def start_provider() -> core.subprocess.Popen:
    proc = core.subprocess.Popen([core.sys.executable, __file__, "--durable-provider-server"], stdout=core.subprocess.DEVNULL, stderr=core.subprocess.DEVNULL)
    core.wait_provider(); return proc


core.prove_single_winner = prove_port_single_winner
strict.capture_recovery_boundary_strict = capture_recovery_boundary_exact
strict.DurableProviderState = CrashDurableProviderState
strict.durable_provider_server = durable_provider_server
strict.start_provider = start_provider

import replay_recovery_capability_binding as capability  # noqa: E402
capability.strict.DurableProviderState = CrashDurableProviderState
capability.strict.durable_provider_server = durable_provider_server
capability.strict.start_provider = start_provider

# Load the exact-capability send patch and retryable reopen transition before
# exporting the final recovery function to the strict execution layer.
import replay_recovery_provider_capability_hardening as provider_capability  # noqa: E402,F401
import replay_recovery_transition_hardening as transition  # noqa: E402

strict.recover_from_witness_strict = transition.recover_from_witness_retryable
capability.recover_from_witness_exact = transition.recover_from_witness_retryable

from replay_recovery_strict_entrypoint import *  # noqa: E402,F401,F403

capture_recovery_boundary_strict = capture_recovery_boundary_exact
recover_from_witness_strict = transition.recover_from_witness_retryable


def main() -> None:
    strict.main()
    # These negative controls execute against the same durable provider and
    # recovery authority used by the canonical gate.
    provider = start_provider()
    try:
        provider_capability.prove_observed_send_requires_exact_capability()
    finally:
        strict.stop_provider(provider)
    transition.prove_partial_reopen_is_retryable()


if __name__ == "__main__":
    if "--durable-provider-server" in core.sys.argv:
        durable_provider_server()
    else:
        main()
