#!/usr/bin/env python3
from __future__ import annotations

# Canonical D3-E recovery entrypoint. The implementation lives in the strict
# module so every caller—including the final hardening layer—uses exact
# provider-capability binding rather than the superseded permissive path.
from replay_recovery_strict_entrypoint import *  # noqa: F401,F403


if __name__ == "__main__":
    if "--durable-provider-server" in core.sys.argv:
        durable_provider_server()
    else:
        main()
