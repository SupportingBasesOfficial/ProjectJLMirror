#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("validate_wave4_monitoring_authorization.py")
spec = importlib.util.spec_from_file_location("wave4_auth", MODULE_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def expect_failure(mutator, expected: str) -> None:
    data = mod.load()
    candidate = copy.deepcopy(data)
    mutator(candidate)
    try:
        mod.validate_manifest(candidate)
    except AssertionError as exc:
        if expected not in str(exc):
            raise AssertionError(f"expected {expected!r}, got {str(exc)!r}") from exc
        return
    raise AssertionError(f"mutation unexpectedly passed: {expected}")


def falsify_hidden_implementation_under_authorization_path() -> None:
    changed = sorted(mod.ALLOWED_PR_PATHS | {
        "implementation/wave-4-monitoring-authorization/frontend/app.py"
    })
    try:
        mod.validate_changed_paths(changed)
    except AssertionError as exc:
        if "authorization PR touched forbidden path" not in str(exc):
            raise AssertionError(f"unexpected hidden-path failure: {exc}") from exc
        return
    raise AssertionError("hidden implementation under authorization directory unexpectedly passed")


def main() -> int:
    mod.validate()

    expect_failure(lambda d: d.__setitem__("authorized_product_vertical", "all_products"), "product vertical drift")
    expect_failure(lambda d: d.__setitem__("production_authority", "granted"), "production authority escalation")
    expect_failure(lambda d: d.__setitem__("c3_production_state", "closed"), "C3 production state escalation")
    expect_failure(lambda d: d.__setitem__("frontend_authority", "granted"), "frontend authority escalation")
    expect_failure(lambda d: d.__setitem__("merge_authorization", "granted"), "merge authority escalation")
    expect_failure(lambda d: d.__setitem__("canonical_effect_after_merge", "authorized_all_wave4_products"), "canonical effect drift")

    def add_alerting_slice(d):
        d["authorized_slices"].append({"slice_id": "impl.alerting@1", "scope": "all"})
    expect_failure(add_alerting_slice, "authorized slices drift")

    def widen_provider(d):
        d["authorized_slices"][1]["scope"] = "all_providers"
    expect_failure(widen_provider, "authorized slices drift")

    def widen_capability(d):
        d["authorized_capability_scope"].append("alerting_lifecycle_and_acknowledgement")
    expect_failure(widen_capability, "authorized capability scope drift")

    def widen_contract_surface(d):
        d["authorized_contract_surfaces"].append("docs/03-domains/alerting-domain-contract.md")
    expect_failure(widen_contract_surface, "authorized contract surface drift")

    def drop_frontend_guard(d):
        d["explicitly_not_authorized"].remove("frontend_route_generation_from_backend_shape")
    expect_failure(drop_frontend_guard, "explicit exclusion drift")

    def drop_realtime_guard(d):
        d["explicitly_not_authorized"].remove("browser_realtime_activation")
    expect_failure(drop_realtime_guard, "explicit exclusion drift")

    def change_predecessor(d):
        d["required_predecessor_authority"]["d4_eventing_async"] = "scoped"
    expect_failure(change_predecessor, "predecessor authority drift")

    falsify_hidden_implementation_under_authorization_path()

    print("wave4_monitoring_authorization_falsification=PASS cases=14 hidden_implementation_path=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
