from __future__ import annotations

import time

import keycloak_mfa_step_up_probe as probe

_USED_COUNTERS: list[int] = []


def _fresh_single_use_totp(secret: str) -> str:
    """Issue only a non-replayed TOTP counter for the evidence browser flow."""

    while True:
        timestamp = int(time.time())
        counter = timestamp // 30
        remainder = 30 - (timestamp % 30)

        if _USED_COUNTERS and counter <= _USED_COUNTERS[-1]:
            time.sleep(remainder + 1)
            continue
        if remainder <= 3:
            time.sleep(remainder + 1)
            continue

        code = probe._totp(secret, now=timestamp)
        _USED_COUNTERS.append(counter)
        return code


def main() -> int:
    # Keycloak 26.7.2 defaults TOTP codes to single-use. The underlying probe
    # intentionally owns all OIDC/MFA semantics; this runner only guarantees
    # that enrollment and the subsequent real login exercise distinct TOTP
    # time counters instead of accidentally testing a provider-side replay.
    probe._stable_totp = _fresh_single_use_totp
    result = probe.main()

    if len(_USED_COUNTERS) != 2:
        raise AssertionError(
            f"expected exactly two TOTP uses (enroll/login), got {len(_USED_COUNTERS)}"
        )
    if _USED_COUNTERS[1] <= _USED_COUNTERS[0]:
        raise AssertionError("MFA login did not advance beyond enrollment TOTP counter")

    print(
        "d3_keycloak_totp_single_use_freshness=PASS "
        "enrollment_and_login_distinct_counters=true"
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
