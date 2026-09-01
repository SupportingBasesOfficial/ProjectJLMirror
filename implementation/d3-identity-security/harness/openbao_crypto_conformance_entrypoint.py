#!/usr/bin/env python3
from __future__ import annotations

import _openbao_crypto_conformance_base as base
import openbao_crypto_conformance_runner as core


_ORIGINAL_INITIALIZE_SOURCE = core.initialize_source
_ORIGINAL_ISSUE = base._issue_provider_version_bound
_CAPTURED_ROOT_TOKEN: str | None = None
_LAST_ISSUE: tuple[core.KeyAuthorityPort, core.LogicalKeyHandle, bytes, int] | None = None

# These aliases are intentionally overridable by the final hardening layer.
# main() copies their current values into the preserved implementation before
# execution so monkey-patched monotonic continuity evidence remains effective.
DurableCryptoContinuityWitness = base.DurableCryptoContinuityWitness
_prove_witness_restart_and_corruption_fail_closed = base._prove_witness_restart_and_corruption_fail_closed


def _capture_initialize_source() -> tuple[str, str]:
    global _CAPTURED_ROOT_TOKEN
    unseal_key, root_token = _ORIGINAL_INITIALIZE_SOURCE()
    _CAPTURED_ROOT_TOKEN = root_token
    return unseal_key, root_token


def _tracked_issue(
    self: core.KeyAuthorityPort, *, handle: core.LogicalKeyHandle, content: bytes
) -> base.ProviderVersionBoundEvidence:
    global _LAST_ISSUE
    evidence = _ORIGINAL_ISSUE(self, handle=handle, content=content)
    _LAST_ISSUE = (self, handle, content, evidence.provider_generation)
    return evidence


def _prove_provider_generation_binding_exercised() -> None:
    if base._PROVIDER_GENERATION_CHECKS <= 0:
        raise AssertionError("historical verification never exercised provider-generation binding")
    if base._PROVIDER_GENERATION_NEGATIVE_CONTROLS != base._PROVIDER_GENERATION_CHECKS:
        raise AssertionError("provider-generation mismatch negative control did not accompany verification")
    if _CAPTURED_ROOT_TOKEN is None or _LAST_ISSUE is None:
        raise AssertionError("real OpenBao issuance authority was not captured for native-rotation control")

    port, handle, content, authorized_generation = _LAST_ISSUE
    if port.state(handle) != "current":
        raise AssertionError("native-rotation control did not retain a current logical generation")
    provider_ref = port.adapter.ref(handle)
    trusted_before = base._authorized_provider_generation(handle, provider_ref)
    if trusted_before != authorized_generation:
        raise AssertionError("captured provider generation diverged from trusted authority before rotation")

    root = core.BaoClient(core.SOURCE_ADDR, _CAPTURED_ROOT_TOKEN)
    root.call("POST", f"transit/keys/{base.quote(provider_ref, safe='')}/rotate", {}, expect={200, 204})
    metadata = root.call("GET", f"transit/keys/{base.quote(provider_ref, safe='')}", expect={200})
    latest = metadata.get("data", {}).get("latest_version")
    if type(latest) is not int or latest <= trusted_before:
        raise AssertionError("real OpenBao native rotation did not advance provider generation")

    try:
        port.issue(handle=handle, content=content + b"-after-native-rotation")
    except RuntimeError as exc:
        if "immutable during ordinary issuance" not in str(exc):
            raise
    else:
        raise AssertionError("ordinary issuance self-authorized a rotated provider generation")

    retained = base._authorized_provider_generation(handle, provider_ref)
    if retained != trusted_before:
        raise AssertionError("failed issuance rewrote trusted provider-generation authority")

    print(
        "d3_e_provider_generation_binding=PASS "
        "provider_version_parsed_from_hmac=true evidence_records_provider_generation=true "
        "trusted_postgresql_provider_generation_authority=true "
        "embedded_generation_equals_authorized_generation=true stale_native_generation_rejected=true "
        "native_openbao_rotation_exercised=true ordinary_issue_path_exercised=true "
        "ordinary_issuance_cannot_rewrite_authorized_generation=true "
        "native_rotation_cannot_self_authorize=true governed_rotation_required_for_generation_change=true "
        "trusted_generation_retained_after_rejected_issue=true "
        "mismatch_rejected_before_evidence_return=true separate_provider_ref_per_logical_generation=true"
    )


def main() -> None:
    # Preserve overrides installed by openbao_crypto_final_entrypoint.py instead
    # of bypassing them when delegating into the preserved implementation.
    base.DurableCryptoContinuityWitness = DurableCryptoContinuityWitness
    base._prove_witness_restart_and_corruption_fail_closed = (
        _prove_witness_restart_and_corruption_fail_closed
    )
    core.initialize_source = _capture_initialize_source
    base._issue_provider_version_bound = _tracked_issue
    base._prove_provider_generation_binding_exercised = _prove_provider_generation_binding_exercised
    base.main()


if __name__ == "__main__":
    main()
