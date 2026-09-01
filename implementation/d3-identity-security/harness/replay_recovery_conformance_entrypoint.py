#!/usr/bin/env python3
from __future__ import annotations

import replay_recovery_conformance_runner as core
from replay_recovery_port_probe import prove_port_single_winner

# The core runner still provides generic primitives, but the canonical D3-E
# entrypoint deliberately does not let its direct-port concurrency helper claim
# private_key_jwt/token-boundary evidence. That stronger proof lives behind two
# real HTTP token replicas in private_key_jwt_token_boundary_conformance.py.
core.prove_single_winner = prove_port_single_winner

from replay_recovery_strict_entrypoint import *  # noqa: E402,F401,F403


if __name__ == "__main__":
    if "--durable-provider-server" in core.sys.argv:
        durable_provider_server()
    else:
        main()
