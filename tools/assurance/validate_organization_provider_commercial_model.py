#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/03-domains/organization-operating-model-contract.md"
MANIFEST = ROOT / "governance/product-model/organization-provider-commercial/DECISION_MANIFEST.json"
STATE = ROOT / "governance/product-model/organization-provider-commercial/STATE.md"
COMPAT = ROOT / "governance/product-model/organization-provider-commercial/MONITORING_COMPATIBILITY.md"
ADR = ROOT / "adr/ADR-021-organization-provider-commercial-operating-model.md"
DECISION_INDEX = ROOT / "docs/06-architecture/decision-index.md"
WORKFLOW = ROOT / ".github/workflows/organization-provider-commercial-model.yml"

EXPECTED_BASE = "8e2265a4ee2810ea701166228e8f44ad3bc0d894"
EXPECTED_SOURCE_HEAD = "ba2817a7586ed43b18eb72a139f1eba8ffeadfa0"
EXPECTED_SQUASH = "8c9eb94ebe76a56db85dd1ecbd3e0f8569edfb62"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    contract = CONTRACT.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    state = STATE.read_text(encoding="utf-8")
    compat = COMPAT.read_text(encoding="utf-8")
    adr = ADR.read_text(encoding="utf-8")
    decision_index = DECISION_INDEX.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    require(manifest["decision_id"] == "organization-provider-commercial-model@1", "unexpected decision_id")
    require(manifest["status"] == "separately_accepted", "accepted state drift")
    require(manifest["canonical_base"] == EXPECTED_BASE, "canonical base drift")
    require(manifest["accepted_source_head"] == EXPECTED_SOURCE_HEAD, "accepted source head drift")
    require(manifest["accepted_squash_sha"] == EXPECTED_SQUASH, "accepted squash drift")
    require(f"main@{EXPECTED_BASE}" in state, "STATE canonical base mismatch")
    require(EXPECTED_SOURCE_HEAD in state, "STATE source head mismatch")
    require(EXPECTED_SQUASH in state, "STATE accepted squash mismatch")
    require("SEPARATELY_ACCEPTED" in state, "STATE is not separately accepted")
    require(
        manifest["decision_record"] == "adr/ADR-021-organization-provider-commercial-operating-model.md",
        "ADR binding drift",
    )
    require("**Status:** accepted" in adr, "ADR-021 is not accepted")
    require(EXPECTED_SOURCE_HEAD in adr and EXPECTED_SQUASH in adr, "ADR acceptance provenance mismatch")
    require("| ADR-021 | Organization, provider and commercial operating model | accepted |" in decision_index, "ADR-021 missing from decision index")

    require(manifest["runtime_implementation_authority"] == "not_granted_by_this_gate", "runtime authority granted")
    require(manifest["frontend_authority"] == "not_granted_by_this_gate", "frontend authority granted")
    require(manifest["production_authority"] == "none", "production authority granted")
    require(manifest["historical_wave4_authority_rewritten"] is False, "historical Wave 4 truth rewritten")
    require(
        manifest["monitoring_compatibility_overlay"]
        == "governance/product-model/organization-provider-commercial/MONITORING_COMPATIBILITY.md",
        "Monitoring compatibility overlay not bound",
    )

    decisions = manifest["decisions"]
    require(decisions["organization_model"] == "stable_entity_with_contextual_relationships_not_rigid_type", "organization model drift")
    require(decisions["tenant_model"] == "one_monitored_customer_organization_boundary_per_tenant", "tenant model drift")
    require(decisions["msp_customer_isolation"] == "distinct_customer_tenants_with_delegated_authority", "MSP isolation drift")
    require(decisions["provider_instance_model"] == "one_physical_provider_instance_may_serve_many_tenants", "provider instance model drift")
    require(decisions["provider_visibility_vs_platform_authority"] == "independent_layers", "provider/platform authority conflated")
    require(decisions["ownership_ambiguity"] == "fail_closed_reconciliation_required", "ownership conflict no longer fail-closed")
    require(decisions["contract_entitlement_permission_usage"] == "independent_concepts", "commercial/authority concepts conflated")
    require(decisions["platform_cross_tenant_access"] == "explicit_privileged_attributable_audited_authority", "platform cross-tenant governance weakened")
    require(
        decisions["accepted_monitoring_source_compatibility"]
        == "tenant_source_may_reference_shared_provider_instance_without_transferring_provider_ownership_or_weakening_tenant_identity_scope",
        "Monitoring Source compatibility drift",
    )

    required_contract_phrases = [
        "Organization is not a rigid organization type",
        "Tenant remains an isolation boundary",
        "Delegation does not merge tenants",
        "Provider visibility is not JLMIRROR authorization",
        "One physical provider instance MAY therefore participate",
        "ProviderScopeTenantBinding",
        "ownership_conflict",
        "Entitlement != Permission",
        "Tenant Admin != Provider Admin",
        "Display/TV access SHOULD be represented by an independently attributable non-human display/device principal",
        "Organization 360 traceability requirement",
        "This contract does not grant implementation, frontend, production, billing-price, or provider-write authority by itself",
    ]
    for phrase in required_contract_phrases:
        require(phrase in contract, f"missing canonical contract phrase: {phrase}")

    required_state_phrases = [
        "SEPARATELY_ACCEPTED",
        "No provider validation/ingestion successor slice should assume `1 Monitoring Source = 1 physical provider = 1 organization`",
        "does **not**",
        "authorize the Zabbix validation worker",
        "grant production authority",
    ]
    for phrase in required_state_phrases:
        require(phrase in state, f"missing state boundary: {phrase}")

    required_compat_phrases = [
        "every tenant owns the physical Zabbix installation it reads from",
        "Multiple tenant-scoped Monitoring Sources/bindings MAY reference the same `ProviderInstance`",
        "The accepted `observation_identity_scope = (tenant_id, monitoring_source_id, \"zabbix\", zabbix_instance_generation)` remains valid",
        "Both Monitoring Sources may resolve to the same provider endpoint while remaining distinct tenant authorities and identity scopes",
        "The accepted rule that an ordinary Monitoring Source base-URL edit requires the explicit source-instance replacement workflow remains intact",
    ]
    for phrase in required_compat_phrases:
        require(phrase in compat, f"missing Monitoring compatibility invariant: {phrase}")

    require("git diff --no-renames --name-only" in workflow, "rename-safe path gate not enforced")
    require("Falsify rename path-gate bypass" in workflow, "rename-bypass regression test not wired")

    deferred = set(manifest["explicitly_deferred"])
    for required in {
        "exact_commercial_prices",
        "production_quotas_and_capacity_numerics",
        "frontend_navigation_and_information_architecture",
        "provider_write_back",
        "production_deployment",
    }:
        require(required in deferred, f"missing deferred boundary: {required}")

    print(
        "organization_provider_commercial_model=PASS "
        "state=separately_accepted provenance=pinned runtime=not_granted production=none"
    )


if __name__ == "__main__":
    main()
