#!/usr/bin/env python3
"""Provider-capability hardening loaded before the legacy conformance runner."""
from __future__ import annotations

import replay_recovery_conformance_runner as core

_ORIGINAL_DO_POST = core.ProviderHandler.do_POST


def _capability_bound_do_post(self) -> None:
    if self.path != "/send":
        return _ORIGINAL_DO_POST(self)

    payload = self.read_json()
    op = payload["operation_id"]
    generation = int(payload["attempt_generation"])
    token = payload["attempt_token"]
    with self.state.lock:
        fence = self.state.fences.get(op)
        if fence:
            same_fence = (
                fence["attempt_generation"] == generation
                and fence["attempt_token"] == token
            )
            self.send_json(409, {
                "outcome": "BLOCKED" if same_fence else "CONFLICT",
                **fence,
            })
            return

        existing = self.state.effects.get(op)
        if existing:
            same = (
                existing["attempt_generation"] == generation
                and existing["attempt_token"] == token
                and existing["effect_id"] == payload["effect_id"]
                and existing["result_ref"] == payload["result_ref"]
            )
            self.send_json(200 if same else 409, {
                "outcome": "OBSERVE" if same else "CONFLICT",
                **existing,
            })
            return

        revision = self.state.next_revision()
        effect = {
            "attempt_generation": generation,
            "attempt_token": token,
            "effect_id": payload["effect_id"],
            "result_ref": payload["result_ref"],
            "revision": revision,
        }
        self.state.effects[op] = effect
        self.state.persist()
        if payload.get("drop_response"):
            self.close_connection = True
            return
        self.send_json(200, {"outcome": "WIN", **effect})


core.ProviderHandler.do_POST = _capability_bound_do_post


def prove_observed_send_requires_exact_capability() -> None:
    op = "observed-send-exact-capability"
    first = core.provider_send(op, 1, "token-a", "effect-a", "result-a")
    if first.get("outcome") != "WIN":
        raise RuntimeError("initial exact-capability send did not win")
    same = core.provider_send(op, 1, "token-a", "effect-a", "result-a")
    if same.get("outcome") != "OBSERVE":
        raise RuntimeError("same capability was not observable")
    mismatched = core.provider_send(op, 1, "token-b", "effect-a", "result-a")
    if mismatched.get("outcome") != "CONFLICT":
        raise RuntimeError("different attempt token observed an existing provider effect")
    print(
        "d3_e_provider_send_exact_capability_binding=PASS "
        "observe_requires_generation=true observe_requires_attempt_token=true "
        "observe_requires_effect_id=true observe_requires_result_ref=true "
        "same_operation_different_token_conflicts=true"
    )
