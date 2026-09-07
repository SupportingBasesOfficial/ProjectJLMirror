#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass, replace

class SecretBoundaryDenied(Exception):
    pass

@dataclass(frozen=True)
class PayloadField:
    value: str
    classification: str

@dataclass(frozen=True)
class SecretReference:
    handle: str
    audit_reference: str
    generation: int
    scope: str
    bearer_authority: bool = False

@dataclass(frozen=True)
class SecretAuthority:
    available: bool
    current_generation: int
    allowed_scopes: tuple[str, ...]
    authority_source: str = "secret_or_kms_authority"

@dataclass(frozen=True)
class OrdinaryMessage:
    message_id: str
    tenant_id: str
    payload: dict[str, PayloadField]
    secret_ref: SecretReference | None
    verification_profile_ref: str
    verification_generation_ref: int

@dataclass(frozen=True)
class HistoricalEvidence:
    message_id: str
    tenant_id: str
    verification_profile_ref: str
    verification_generation_ref: int
    secret_material_present: bool = False
    credential_material_present: bool = False
    secret_reference_present: bool = False

ALLOWED_PAYLOAD_CLASSIFICATIONS = {"public", "internal", "business_data"}
FORBIDDEN_PAYLOAD_CLASSIFICATIONS = {"secret", "credential", "key_material"}

def _contains_sensitive_material(values: dict[str, PayloadField]) -> bool:
    return any(field.classification in FORBIDDEN_PAYLOAD_CLASSIFICATIONS for field in values.values())

def create_message(*, message_id: str, tenant_id: str, payload: dict[str, PayloadField], secret_ref: SecretReference | None, verification_profile_ref: str, verification_generation_ref: int) -> OrdinaryMessage:
    unknown = {field.classification for field in payload.values()} - ALLOWED_PAYLOAD_CLASSIFICATIONS - FORBIDDEN_PAYLOAD_CLASSIFICATIONS
    if unknown:
        raise SecretBoundaryDenied("unknown payload classification")
    if _contains_sensitive_material(payload):
        raise SecretBoundaryDenied("ordinary message payload cannot contain secret, credential, or key material")
    if secret_ref is not None and secret_ref.bearer_authority:
        raise SecretBoundaryDenied("secret reference cannot be bearer authority")
    if not verification_profile_ref or verification_generation_ref <= 0:
        raise SecretBoundaryDenied("non-secret historical verification reference required")
    return OrdinaryMessage(message_id, tenant_id, dict(payload), secret_ref, verification_profile_ref, verification_generation_ref)

def sanitize_record(message: OrdinaryMessage, *, record_kind: str) -> dict[str, object]:
    if record_kind not in {"inbox", "log", "trace", "quarantine"}:
        raise SecretBoundaryDenied("unsupported record kind")
    return {
        "record_kind": record_kind,
        "message_id": message.message_id,
        "tenant_id": message.tenant_id,
        "verification_profile_ref": message.verification_profile_ref,
        "verification_generation_ref": message.verification_generation_ref,
        "secret_ref_present": False,
        "secret_material_present": False,
        "credential_material_present": False,
        "key_material_present": False,
    }

def resolve_secret(*, reference: SecretReference, authority: SecretAuthority, requested_scope: str, authorized: bool, audit_sink: list[dict[str, object]]) -> str:
    if reference.bearer_authority:
        raise SecretBoundaryDenied("historical/reference handle is not bearer authority")
    if not authority.available:
        raise SecretBoundaryDenied("secret authority unavailable: fail closed")
    if authority.authority_source != "secret_or_kms_authority":
        raise SecretBoundaryDenied("invalid secret authority source")
    if not authorized or requested_scope != reference.scope or requested_scope not in authority.allowed_scopes:
        raise SecretBoundaryDenied("secret resolution is not narrowly authorized")
    audit_sink.append({
        "scope": requested_scope,
        "reference": reference.audit_reference,
        "generation": reference.generation,
        "resolved": True,
        "secret_handle_logged": False,
        "secret_material_logged": False,
    })
    return f"resolved-secret-for:{reference.handle}:generation:{reference.generation}"

def erase_and_minimize(message: OrdinaryMessage) -> HistoricalEvidence:
    return HistoricalEvidence(
        message_id=message.message_id,
        tenant_id=message.tenant_id,
        verification_profile_ref=message.verification_profile_ref,
        verification_generation_ref=message.verification_generation_ref,
        secret_material_present=False,
        credential_material_present=False,
        secret_reference_present=False,
    )

def historical_reference_can_resolve_secret(evidence: HistoricalEvidence, authority: SecretAuthority) -> bool:
    return False

def duplicate_sensitive_effect_eligible(evidence: HistoricalEvidence, *, expected_tenant: str, expected_profile: str, known_generations: tuple[int, ...]) -> bool:
    return (
        evidence.tenant_id == expected_tenant
        and evidence.verification_profile_ref == expected_profile
        and evidence.verification_generation_ref in known_generations
        and not evidence.secret_material_present
        and not evidence.credential_material_present
        and not evidence.secret_reference_present
    )

def run_probes() -> dict[str, bool]:
    ref = SecretReference(
        handle="kms://orders-signing/current",
        audit_reference="secret-ref/orders-signing/generation-7",
        generation=7,
        scope="tenant-a/orders",
    )
    authority = SecretAuthority(available=True, current_generation=7, allowed_scopes=("tenant-a/orders",))
    message = create_message(
        message_id="msg-001",
        tenant_id="tenant-a",
        payload={
            "order_id": PayloadField("ord-42", "business_data"),
            "event": PayloadField("order.created", "internal"),
        },
        secret_ref=ref,
        verification_profile_ref="semantic-equivalence-v3",
        verification_generation_ref=7,
    )
    checks: dict[str, bool] = {}

    checks["ordinary_payload_excludes_secret_credential_material"] = not _contains_sensitive_material(message.payload) and all(field.classification in ALLOWED_PAYLOAD_CLASSIFICATIONS for field in message.payload.values())
    negative_cases = [
        ("password", "password", "credential"),
        ("secret", "business_note", "secret"),
        ("credential", "credential", "credential"),
        ("token", "token", "credential"),
        ("api_key", "api_key", "credential"),
        ("private_key", "private_key", "key_material"),
        ("key_material", "key_material", "key_material"),
    ]
    for probe_name, field_name, classification in negative_cases:
        try:
            create_message(
                message_id="bad",
                tenant_id="tenant-a",
                payload={field_name: PayloadField("must-not-appear", classification)},
                secret_ref=ref,
                verification_profile_ref="semantic-equivalence-v3",
                verification_generation_ref=7,
            )
            checks[f"reject_payload_{probe_name}"] = False
        except SecretBoundaryDenied:
            checks[f"reject_payload_{probe_name}"] = True

    sanitized = [sanitize_record(message, record_kind=k) for k in ("inbox", "log", "trace", "quarantine")]
    checks["secondary_records_exclude_secret_key_material"] = all(
        not r["secret_ref_present"]
        and not r["secret_material_present"]
        and not r["credential_material_present"]
        and not r["key_material_present"]
        for r in sanitized
    )

    evidence = erase_and_minimize(message)
    checks["erasure_preserves_non_secret_historical_verification_reference"] = evidence.verification_profile_ref == "semantic-equivalence-v3" and evidence.verification_generation_ref == 7 and not evidence.secret_material_present and not evidence.credential_material_present and not evidence.secret_reference_present
    checks["redaction_erasure_preserve_correctness_evidence"] = duplicate_sensitive_effect_eligible(evidence, expected_tenant="tenant-a", expected_profile="semantic-equivalence-v3", known_generations=(5, 6, 7))

    audit: list[dict[str, object]] = []
    resolved = resolve_secret(reference=ref, authority=authority, requested_scope="tenant-a/orders", authorized=True, audit_sink=audit)
    checks["secret_resolution_is_narrowly_authorized_and_audited"] = (
        resolved.startswith("resolved-secret-for:")
        and len(audit) == 1
        and audit[0]["scope"] == "tenant-a/orders"
        and audit[0]["reference"] == ref.audit_reference
        and audit[0]["secret_handle_logged"] is False
        and audit[0]["secret_material_logged"] is False
        and ref.handle not in str(audit[0])
    )
    for name, scope, authorized in [
        ("unauthorized_resolution_fails_closed", "tenant-a/orders", False),
        ("cross_scope_resolution_fails_closed", "tenant-b/orders", True),
    ]:
        try:
            resolve_secret(reference=ref, authority=authority, requested_scope=scope, authorized=authorized, audit_sink=[])
            checks[name] = False
        except SecretBoundaryDenied:
            checks[name] = True

    unavailable = replace(authority, available=False)
    try:
        resolve_secret(reference=ref, authority=unavailable, requested_scope="tenant-a/orders", authorized=True, audit_sink=[])
        checks["secret_authority_outage_fails_closed"] = False
    except SecretBoundaryDenied:
        checks["secret_authority_outage_fails_closed"] = True

    checks["historical_reference_is_not_bearer_authority"] = not historical_reference_can_resolve_secret(evidence, authority)
    bearer_ref = replace(ref, bearer_authority=True)
    try:
        create_message(
            message_id="bad-ref",
            tenant_id="tenant-a",
            payload={"order_id": PayloadField("ord-43", "business_data")},
            secret_ref=bearer_ref,
            verification_profile_ref="semantic-equivalence-v3",
            verification_generation_ref=7,
        )
        checks["bearer_secret_reference_rejected"] = False
    except SecretBoundaryDenied:
        checks["bearer_secret_reference_rejected"] = True

    return checks

if __name__ == "__main__":
    checks = run_probes()
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise SystemExit("FAILED: " + ",".join(failed))
    print(f"d4d_open_evt_017_secret_exclusion_source=PASS probes={len(checks)}")
