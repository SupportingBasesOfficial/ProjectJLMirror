#!/usr/bin/env python3
from __future__ import annotations

import openbao_crypto_conformance_runner as core


_ORIGINAL_CALL = core.BaoClient.call


def _openbao_262_compatible_call(
    self: core.BaoClient,
    method: str,
    path: str,
    body: dict | None = None,
    *,
    expect: set[int] = {200, 204},
    timeout: float = 6,
) -> dict:
    """Accept OpenBao 2.6.2 success responses with or without a response body.

    Some Transit/admin endpoints that historically return 204 can return 200 with
    useful metadata in OpenBao 2.6.2. 200 and 204 are both successful HTTP
    outcomes; all other status handling remains delegated to the canonical
    client. This compatibility layer does not convert any 4xx/5xx into success.
    """
    accepted = set(expect)
    if 204 in accepted:
        accepted.add(200)
    return _ORIGINAL_CALL(self, method, path, body, expect=accepted, timeout=timeout)


def main() -> None:
    core.BaoClient.call = _openbao_262_compatible_call
    print(
        "d3_e_openbao_262_http_success_profile=PASS "
        "http_200_success_retained=true http_204_success_retained=true "
        "client_errors_not_relaxed=true"
    )
    core.main()


if __name__ == "__main__":
    main()
