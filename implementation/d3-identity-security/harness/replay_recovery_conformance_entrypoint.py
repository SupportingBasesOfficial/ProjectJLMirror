#!/usr/bin/env python3
from __future__ import annotations

import replay_recovery_conformance_runner as core
import replay_recovery_strict_entrypoint as strict
from replay_recovery_port_probe import prove_port_single_winner
from replay_recovery_capability_binding import (
    capture_recovery_boundary_exact,
    recover_from_witness_exact,
)

# Direct port concurrency remains a useful storage-boundary probe but cannot
# claim private_key_jwt/token-boundary evidence. The stronger proof is executed
# through two real HTTP token replicas in its own exact-head gate.
core.prove_single_winner = prove_port_single_winner

# Exact provider capability identity is canonical for both recovery capture and
# restore. Operation-id coincidence alone can never authorize reconciliation.
strict.capture_recovery_boundary_strict = capture_recovery_boundary_exact
strict.recover_from_witness_strict = recover_from_witness_exact

from replay_recovery_strict_entrypoint import *  # noqa: E402,F401,F403

# Re-export the canonical functions for final hardening layers importing this
# module as their base.
capture_recovery_boundary_strict = capture_recovery_boundary_exact
recover_from_witness_strict = recover_from_witness_exact


def main() -> None:
    strict.main()


if __name__ == "__main__":
    if "--durable-provider-server" in core.sys.argv:
        strict.durable_provider_server()
    else:
        main()
