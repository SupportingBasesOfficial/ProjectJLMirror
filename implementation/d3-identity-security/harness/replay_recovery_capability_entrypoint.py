#!/usr/bin/env python3
"""Canonical entrypoint for standalone D3-E recovery-capability probes.

The capability test module intentionally contains no provider-runtime authority.
This entrypoint first loads the crash-durable canonical runtime, exact provider
capability semantics, and retryable recovery transition, then executes the
standalone negative controls through those bindings.
"""
from __future__ import annotations

import replay_recovery_conformance_entrypoint as canonical
import replay_recovery_capability_binding as capability
import replay_recovery_provider_capability_hardening as provider_capability
import replay_recovery_transition_hardening as transition

# Every provider child used by the standalone probes now starts through the
# canonical entrypoint whose state publication is fsync(file)+rename+fsync(dir).
capability.strict.DurableProviderState = canonical.CrashDurableProviderState
capability.strict.durable_provider_server = canonical.durable_provider_server
capability.strict.start_provider = canonical.start_provider

# Install the safe retryable witness-open/database-closed handoff semantics.
capability._enter_recovery_quarantine = transition._enter_recovery_quarantine_retryable
capability.recover_from_witness_exact = transition.recover_from_witness_retryable


def main() -> None:
    capability.main()


if __name__ == "__main__":
    main()
