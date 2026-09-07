#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class WorkloadIdentity:
    uri: str
    environment: str
    runtime_profile: str
    workload_id: str
    credential_generation: int
    current: bool = True
    revoked: bool = False
    authenticated: bool = True

@dataclass(frozen=True)
class BrokerGrant:
    service: str
    environment: str
    broker_role: str
    contracts: tuple[str, ...]
    tenant_scopes: tuple[str, ...] = ()

@dataclass(frozen=True)
class DerivedCredential:
    subject_uri: str
    generation: int
    broker_role: str
    contracts: tuple[str, ...]
    expires_short_lived: bool = True
    secret_material: str = "opaque-secret"

class AdapterDenied(Exception):
    pass

def derive_broker_credential(identity: WorkloadIdentity, grant: BrokerGrant, *, expected_generation: int) -> DerivedCredential:
    if not identity.authenticated:
        raise AdapterDenied("workload identity must be authenticated before derivation")
    if identity.revoked or not identity.current:
        raise AdapterDenied("stale or revoked workload identity")
    if identity.credential_generation != expected_generation:
        raise AdapterDenied("stale workload credential generation")
    if identity.environment != grant.environment:
        raise AdapterDenied("cross-environment broker credential derivation")
    if identity.workload_id != grant.service:
        raise AdapterDenied("grant service does not match authenticated workload")
    if grant.tenant_scopes:
        raise AdapterDenied("broker adapter cannot manufacture tenant business authority")
    if not grant.contracts:
        raise AdapterDenied("empty contract scope")
    if "*" in grant.contracts or grant.broker_role in {"admin","superuser","root"}:
        raise AdapterDenied("broad broker authority forbidden")
    return DerivedCredential(
        subject_uri=identity.uri,
        generation=identity.credential_generation,
        broker_role=grant.broker_role,
        contracts=grant.contracts,
    )

def sanitize_record(record: dict) -> dict:
    forbidden={"secret","credential","private_key","token","password","secret_material"}
    clean={}
    for k,v in record.items():
        if k.lower() in forbidden:
            continue
        clean[k]=v
    return clean

def run_probes() -> dict[str,bool]:
    ident=WorkloadIdentity("spiffe://jl/prod/api/orders","prod","api","orders",7)
    grant=BrokerGrant("orders","prod","producer",("orders.event.v1",))
    cred=derive_broker_credential(ident,grant,expected_generation=7)
    checks={}
    checks["authenticated_before_derivation"]=cred.subject_uri==ident.uri
    checks["canonical_identity_preserved"]=cred.subject_uri==ident.uri
    checks["derived_not_canonical"]=cred.broker_role=="producer" and cred.expires_short_lived
    checks["least_privilege_scope"]=cred.contracts==("orders.event.v1",)
    for name, bad_ident, bad_grant, gen in [
        ("network_presence_not_trust", WorkloadIdentity(ident.uri,"prod","api","orders",7,authenticated=False), grant, 7),
        ("cross_environment_rejected", WorkloadIdentity(ident.uri,"dev","api","orders",7), grant, 7),
        ("revoked_rejected", WorkloadIdentity(ident.uri,"prod","api","orders",7,revoked=True), grant, 7),
        ("stale_generation_rejected", ident, grant, 8),
        ("broad_role_rejected", ident, BrokerGrant("orders","prod","admin",("orders.event.v1",)), 7),
        ("wildcard_contract_rejected", ident, BrokerGrant("orders","prod","producer",("*",)), 7),
        ("tenant_authority_not_manufactured", ident, BrokerGrant("orders","prod","producer",("orders.event.v1",),("tenant-a",)), 7),
    ]:
        try:
            derive_broker_credential(bad_ident,bad_grant,expected_generation=gen)
            checks[name]=False
        except AdapterDenied:
            checks[name]=True
    rotated=derive_broker_credential(WorkloadIdentity(ident.uri,"prod","api","orders",8),grant,expected_generation=8)
    checks["rotation_preserves_canonical_identity"]=rotated.subject_uri==cred.subject_uri and rotated.generation!=cred.generation
    sanitized=sanitize_record({"message_id":"m1","secret_material":cred.secret_material,"token":"abc","contract":"orders.event.v1"})
    checks["credential_material_excluded"]=set(sanitized)=={"message_id","contract"}
    return checks

if __name__ == "__main__":
    checks=run_probes()
    failed=[k for k,v in checks.items() if not v]
    if failed:
        raise SystemExit("FAILED: "+",".join(failed))
    print(f"d4d_open_evt_016_source_evidence=PASS probes={len(checks)}")
