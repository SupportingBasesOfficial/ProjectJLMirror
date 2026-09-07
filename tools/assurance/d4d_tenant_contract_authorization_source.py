#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PlatformAuthorization:
    tenant_id: str
    service: str
    domain: str
    generation: int
    producer_contracts: tuple[str, ...]
    consumer_contracts: tuple[str, ...]
    current: bool = True
    revoked: bool = False

@dataclass(frozen=True)
class BrokerAuthorizationProjection:
    tenant_id: str
    service: str
    domain: str
    broker_role: str
    contract: str
    authority_generation: int
    authority_source: str = "current_platform_authority_projection"

class AuthorizationDenied(Exception):
    pass

def project_broker_authorization(
    authority: PlatformAuthorization,
    *,
    role: str,
    tenant_id: str,
    service: str,
    domain: str,
    contract: str,
    expected_generation: int,
) -> BrokerAuthorizationProjection:
    if role not in {"producer", "consumer"}:
        raise AuthorizationDenied("unsupported broker role")
    if authority.revoked or not authority.current:
        raise AuthorizationDenied("platform authorization is not current")
    if authority.generation != expected_generation:
        raise AuthorizationDenied("stale authorization generation")
    if authority.tenant_id != tenant_id:
        raise AuthorizationDenied("cross-tenant broker authorization forbidden")
    if authority.service != service or authority.domain != domain:
        raise AuthorizationDenied("service or domain authorization mismatch")
    if not contract or contract == "*":
        raise AuthorizationDenied("wildcard or empty contract scope forbidden")
    allowed = authority.producer_contracts if role == "producer" else authority.consumer_contracts
    if "*" in allowed:
        raise AuthorizationDenied("broad platform grant cannot project wildcard broker authority")
    if contract not in allowed:
        raise AuthorizationDenied("contract is outside current platform authority")
    return BrokerAuthorizationProjection(
        tenant_id=tenant_id,
        service=service,
        domain=domain,
        broker_role=role,
        contract=contract,
        authority_generation=authority.generation,
    )

def projection_is_current(projection: BrokerAuthorizationProjection, authority: PlatformAuthorization) -> bool:
    if authority.revoked or not authority.current:
        return False
    if projection.authority_source != "current_platform_authority_projection":
        return False
    if projection.broker_role not in {"producer", "consumer"}:
        return False
    if projection.authority_generation != authority.generation:
        return False
    if (projection.tenant_id, projection.service, projection.domain) != (authority.tenant_id, authority.service, authority.domain):
        return False
    allowed = authority.producer_contracts if projection.broker_role == "producer" else authority.consumer_contracts
    return "*" not in allowed and projection.contract in allowed

def reconcile_projection(projection: BrokerAuthorizationProjection, authority: PlatformAuthorization) -> BrokerAuthorizationProjection | None:
    if authority.revoked or not authority.current:
        return None
    if projection.authority_source != "current_platform_authority_projection":
        return None
    if projection.broker_role not in {"producer", "consumer"}:
        return None
    if (projection.tenant_id, projection.service, projection.domain) != (authority.tenant_id, authority.service, authority.domain):
        return None
    allowed = authority.producer_contracts if projection.broker_role == "producer" else authority.consumer_contracts
    if "*" in allowed or projection.contract not in allowed:
        return None
    return BrokerAuthorizationProjection(
        tenant_id=projection.tenant_id,
        service=projection.service,
        domain=projection.domain,
        broker_role=projection.broker_role,
        contract=projection.contract,
        authority_generation=authority.generation,
    )

def run_probes() -> dict[str, bool]:
    current = PlatformAuthorization(
        tenant_id="tenant-a",
        service="orders",
        domain="commerce",
        generation=11,
        producer_contracts=("orders.created.v1", "orders.updated.v1"),
        consumer_contracts=("payments.confirmed.v1",),
    )
    producer = project_broker_authorization(
        current, role="producer", tenant_id="tenant-a", service="orders", domain="commerce",
        contract="orders.created.v1", expected_generation=11,
    )
    consumer = project_broker_authorization(
        current, role="consumer", tenant_id="tenant-a", service="orders", domain="commerce",
        contract="payments.confirmed.v1", expected_generation=11,
    )
    checks: dict[str, bool] = {
        "producer_contract_scoped": producer.contract == "orders.created.v1" and producer.broker_role == "producer",
        "consumer_tenant_service_domain_scoped": consumer.tenant_id == "tenant-a" and consumer.service == "orders" and consumer.domain == "commerce",
        "broker_policy_is_platform_projection": producer.authority_source == "current_platform_authority_projection",
        "current_projection_valid": projection_is_current(producer, current),
    }

    denied_cases = [
        ("cross_tenant_produce_rejected", dict(role="producer", tenant_id="tenant-b", service="orders", domain="commerce", contract="orders.created.v1", expected_generation=11), current),
        ("cross_tenant_consume_rejected", dict(role="consumer", tenant_id="tenant-b", service="orders", domain="commerce", contract="payments.confirmed.v1", expected_generation=11), current),
        ("producer_contract_outside_scope_rejected", dict(role="producer", tenant_id="tenant-a", service="orders", domain="commerce", contract="orders.deleted.v1", expected_generation=11), current),
        ("consumer_contract_outside_scope_rejected", dict(role="consumer", tenant_id="tenant-a", service="orders", domain="commerce", contract="refunds.created.v1", expected_generation=11), current),
        ("stale_generation_rejected", dict(role="producer", tenant_id="tenant-a", service="orders", domain="commerce", contract="orders.created.v1", expected_generation=10), current),
        ("revoked_authority_rejected", dict(role="producer", tenant_id="tenant-a", service="orders", domain="commerce", contract="orders.created.v1", expected_generation=11), PlatformAuthorization("tenant-a","orders","commerce",11,("orders.created.v1",),("payments.confirmed.v1",),revoked=True)),
        ("wildcard_request_rejected", dict(role="producer", tenant_id="tenant-a", service="orders", domain="commerce", contract="*", expected_generation=11), current),
        ("broad_grant_rejected", dict(role="producer", tenant_id="tenant-a", service="orders", domain="commerce", contract="orders.created.v1", expected_generation=11), PlatformAuthorization("tenant-a","orders","commerce",11,("*",),("payments.confirmed.v1",))),
        ("service_mismatch_rejected", dict(role="consumer", tenant_id="tenant-a", service="billing", domain="commerce", contract="payments.confirmed.v1", expected_generation=11), current),
        ("domain_mismatch_rejected", dict(role="consumer", tenant_id="tenant-a", service="orders", domain="security", contract="payments.confirmed.v1", expected_generation=11), current),
    ]
    for name, kwargs, authority in denied_cases:
        try:
            project_broker_authorization(authority, **kwargs)
            checks[name] = False
        except AuthorizationDenied:
            checks[name] = True

    rotated = PlatformAuthorization(
        tenant_id="tenant-a", service="orders", domain="commerce", generation=12,
        producer_contracts=("orders.created.v1",), consumer_contracts=("payments.confirmed.v1",),
    )
    checks["stale_projection_blocked_after_generation_change"] = not projection_is_current(producer, rotated)
    reconciled = reconcile_projection(producer, rotated)
    checks["projection_reconciles_from_current_platform_authority"] = reconciled is not None and reconciled.authority_generation == 12 and projection_is_current(reconciled, rotated)
    narrowed = PlatformAuthorization(
        tenant_id="tenant-a", service="orders", domain="commerce", generation=12,
        producer_contracts=("orders.updated.v1",), consumer_contracts=("payments.confirmed.v1",),
    )
    checks["revoked_contract_removed_on_reconciliation"] = reconcile_projection(producer, narrowed) is None

    forged_role = BrokerAuthorizationProjection("tenant-a","orders","commerce","admin","payments.confirmed.v1",11)
    checks["forged_broker_role_not_current"] = not projection_is_current(forged_role, current)
    checks["forged_broker_role_not_reconcilable"] = reconcile_projection(forged_role, current) is None
    broker_native = BrokerAuthorizationProjection("tenant-a","orders","commerce","producer","orders.created.v1",11,"broker_native_policy")
    checks["broker_native_projection_cannot_bootstrap_reconciliation"] = reconcile_projection(broker_native, current) is None
    return checks

if __name__ == "__main__":
    checks = run_probes()
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise SystemExit("FAILED: " + ",".join(failed))
    print(f"d4d_open_evt_016_tenant_contract_authorization_source=PASS probes={len(checks)}")
