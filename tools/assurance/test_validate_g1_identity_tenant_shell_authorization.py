#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "assurance"))
import validate_g1_identity_tenant_shell_authorization as validator


def must_fail(mutator, fragment: str) -> None:
    data = copy.deepcopy(validator.load())
    mutator(data)
    try:
        validator.validate_manifest(data)
    except AssertionError as exc:
        if fragment not in str(exc):
            raise AssertionError(f"expected {fragment!r}, got {exc!r}")
        return
    raise AssertionError(f"mutation unexpectedly accepted: {fragment}")


def main() -> int:
    validator.validate()
    must_fail(lambda d: d.__setitem__("merge_authorization", "granted"), "merge authority escalation")
    must_fail(lambda d: d.__setitem__("production_authority", "granted"), "production authority escalation")
    must_fail(lambda d: d.__setitem__("frontend_authority", "generic_product_ui"), "frontend authority escalation")
    must_fail(lambda d: d["authorized_capability_scope"].append("g2_monitoring_source_onboarding"), "capability scope drift")
    must_fail(lambda d: d["required_invariants"].remove("client_tenant_id_not_tenant_authority"), "required invariant drift")
    must_fail(lambda d: d["authorized_g0_bootstrap_scope"].append("generic_shared_platform_framework"), "G0 bootstrap scope drift")
    must_fail(lambda d: d["consumed_existing_authority"].append("provider_native_identity_authority"), "consumed authority drift")
    must_fail(lambda d: d["authority_source_paths"].remove("implementation/wave-1/AUTHORITY_BOUNDARY.md"), "authority source corpus drift")
    must_fail(lambda d: d["explicitly_not_authorized"].remove("monitoring_product_ui"), "explicit exclusion drift")
    must_fail(lambda d: d.__setitem__("effective_rule", "effective_immediately"), "effective rule drift")
    must_fail(lambda d: d.__setitem__("historical_authority_rule", "rewrite_predecessors"), "historical authority rule drift")
    must_fail(lambda d: d.__setitem__("implementation_boundary_rule", "implementation_may_begin_before_merge"), "implementation boundary drift")
    must_fail(lambda d: d.__setitem__("schema_version", True), "schema_version drift")
    print("g1_identity_tenant_shell_authorization_falsification=PASS authority_escalation=blocked scope_expansion=blocked invariant_loss=blocked bootstrap_expansion=blocked authority_source_drift=blocked exclusion_removal=blocked successor_rule_weakening=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
