#!/usr/bin/env python3
"""Import-stable shim for D3-E recovery capability logic.

Library imports receive the implementation symbols unchanged, including the
internal helper API consumed by later exact-head hardening layers. Direct
execution is routed through the canonical durable runtime entrypoint so
standalone gates cannot accidentally start the weaker provider path.
"""
import replay_recovery_capability_impl as _impl
from replay_recovery_capability_impl import *  # noqa: F401,F403

# Python star-import intentionally excludes underscore-prefixed names. These
# helpers are an explicit internal contract used by transition/final hardening
# layers, so re-export them deliberately rather than relying on incidental
# module globals.
_exact_probe = _impl._exact_probe
_unique_captured_capability = _impl._unique_captured_capability
_issued_operation_ids = _impl._issued_operation_ids
_completed_terminal_fields = _impl._completed_terminal_fields
_require_completed_terminal_binding = _impl._require_completed_terminal_binding
_require_prepared_absence_binding = _impl._require_prepared_absence_binding
_enter_recovery_quarantine = _impl._enter_recovery_quarantine
_validate_restored_redrive_capabilities = _impl._validate_restored_redrive_capabilities
_restore_consumed = _impl._restore_consumed
_rehydrate_missing_row = _impl._rehydrate_missing_row
_restore_provider_outcomes = _impl._restore_provider_outcomes

if __name__ == "__main__":
    import replay_recovery_capability_entrypoint as _entry
    _entry.main()
