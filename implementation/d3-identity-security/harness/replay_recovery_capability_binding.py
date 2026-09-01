#!/usr/bin/env python3
"""Import-stable shim for D3-E recovery capability logic.

Library imports receive the implementation symbols unchanged. Direct execution
is routed through the canonical durable runtime entrypoint so standalone gates
cannot accidentally start the weaker provider path.
"""
from replay_recovery_capability_impl import *  # noqa: F401,F403

if __name__ == "__main__":
    import replay_recovery_capability_entrypoint as _entry
    _entry.main()
