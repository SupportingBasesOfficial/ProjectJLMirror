#!/usr/bin/env python3
from __future__ import annotations
import re
from dataclasses import dataclass, replace

class SecretBoundaryDenied(Exception):
    pass

@dataclass(frozen=True)
class SecretMaterial:
    handle: str
    generation: int

@dataclass(frozen=True)
class PayloadField:
    value: object
    classification: str

@dataclass(frozen=True)
class SecretReference:
    handle: str
    generation: int
    scope: str
    bearer_authority: bool = False

@dataclass(frozen=True)
class SecretAuthority:
    available: bool
    current_handle: str
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
VERIFICATION_REFERENCE_PREFIX = "verification-profile://"
AUDIT_REFERENCE_PREFIX = "secret-audit-ref://"
CANONICAL_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
CANONICAL_SCOPE = re.compile(r"^[a-z0-9][a-z0-9._-]*(/[a-z0-9][a-z0-9._-]*)+$")

def _contains_sensitive_material(values: dict[str, PayloadField]) -> bool:
    return any(
        field.classification in FORBIDDEN_PAYLOAD_CLASSIFICATIONS
        or isinstance(field.value, SecretMaterial)
        for field in values.values()
    )

def _validate_payload(values: dict[str, PayloadField]) -> None:
    classifications = {field.classification for field in values.values()}
    unknown = classifications - ALLOWED_PAYLOAD_CLASSIFICATIONS - FORBIDDEN_PAYLOAD_CLASSIFICATIONS
    if unknown:
        raise SecretBoundaryDenied("unknown payload classification")
    if _contains_sensitive_material(values):
        raise SecretBoundaryDenied("ordinary message payload cannot contain secret, credential, or key material")

def _validate_scope(scope: str) -> None:
    if not CANONICAL_SCOPE.fullmatch(scope):
        raise SecretBoundaryDenied("scope must be a canonical non-secret identifier")

def _validate_secret_reference_shape(reference: SecretReference) -> None:
    if reference.bearer_authority:
        raise SecretBoundaryDenied("secret reference cannot be bearer authority")
    if not reference.handle:
        raise SecretBoundaryDenied("secret reference handle required")
    if reference.generation <= 0:
        raise SecretBoundaryDenied("secret reference generation must be positive")
    _validate_scope(reference.scope)

def _audit_reference(reference: SecretReference) -> str:
    _validate_secret_reference_shape(reference)
    audit_ref = f"{AUDIT_REFERENCE_PREFIX}{reference.scope}/generation-{reference.generation}"
    if reference.handle == audit_ref or reference.handle in audit_ref:
        raise SecretBoundaryDenied("derived audit reference must not contain secret handle")
    return audit_ref

def _validate_verification_reference(reference: str, secret_ref: SecretReference | None) -> None:
    if not reference.startswith(VERIFICATION_REFERENCE_PREFIX):
        raise SecretBoundaryDenied("verification reference must use non-secret namespace")
    profile_id = reference[len(VERIFICATION_REFERENCE_PREFIX):]
    if not CANONICAL_ID.fullmatch(profile_id):
        raise SecretBoundaryDenied("verification profile identifier must be canonical")
    if secret_ref is not None and secret_ref.handle:
        if reference == secret_ref.handle or secret_ref.handle in reference:
            raise SecretBoundaryDenied("verification reference must not alias or embed secret handle")

def _validate_message_boundary(message: OrdinaryMessage) -> None:
    _validate_payload(message.payload)
    if message.secret_ref is not None:
        _validate_secret_reference_shape(message.secret_ref)
    _validate_verification_reference(message.verification_profile_ref, message.secret_ref)
    if message.verification_generation_ref <= 0:
        raise SecretBoundaryDenied("non-secret historical verification generation required")

def create_message(*, message_id: str, tenant_id: str, payload: dict[str, PayloadField], secret_ref: SecretReference | None, verification_profile_ref: str, verification_generation_ref: int) -> OrdinaryMessage:
    message = OrdinaryMessage(message_id, tenant_id, dict(payload), secret_ref, verification_profile_ref, verification_generation_ref)
    _validate_message_boundary(message)
    return message

def sanitize_record(message: OrdinaryMessage, *, record_kind: str) -> dict[str, object]:
    if record_kind not in {"inbox", "log", "trace", "quarantine"}:
        raise SecretBoundaryDenied("unsupported record kind")
    _validate_message_boundary(message)
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

def resolve_secret(*, reference: SecretReference, authority: SecretAuthority, requested_scope: str, authorized: bool, audit_sink: list[dict[str, object]]) -> SecretMaterial:
    _validate_secret_reference_shape(reference)
    if not authority.available:
        raise SecretBoundaryDenied("secret authority unavailable: fail closed")
    if authority.authority_source != "secret_or_kms_authority":
        raise SecretBoundaryDenied("invalid secret authority source")
    if reference.handle != authority.current_handle:
        raise SecretBoundaryDenied("unknown or revoked secret handle")
    if reference.generation != authority.current_generation:
        raise SecretBoundaryDenied("stale or unknown secret generation")
    if not authorized or requested_scope != reference.scope or requested_scope not in authority.allowed_scopes:
        raise SecretBoundaryDenied("secret resolution is not narrowly authorized")
    audit_ref = _audit_reference(reference)
    audit_sink.append({"scope": requested_scope, "reference": audit_ref, "generation": reference.generation, "resolved": True, "secret_handle_logged": False, "secret_material_logged": False})
    return SecretMaterial(reference.handle, reference.generation)

def erase_and_minimize(message: OrdinaryMessage) -> HistoricalEvidence:
    _validate_message_boundary(message)
    return HistoricalEvidence(message.message_id, message.tenant_id, message.verification_profile_ref, message.verification_generation_ref, False, False, False)

def historical_reference_can_resolve_secret(evidence: HistoricalEvidence, authority: SecretAuthority, *, scope: str) -> bool:
    try:
        resolve_secret(
            reference=SecretReference(evidence.verification_profile_ref, evidence.verification_generation_ref, scope),
            authority=authority,
            requested_scope=scope,
            authorized=True,
            audit_sink=[],
        )
        return True
    except SecretBoundaryDenied:
        return False

def duplicate_sensitive_effect_eligible(evidence: HistoricalEvidence, *, expected_tenant: str, expected_profile: str, known_generations: tuple[int, ...]) -> bool:
    return (
        evidence.tenant_id == expected_tenant
        and evidence.verification_profile_ref == expected_profile
        and evidence.verification_generation_ref in known_generations
        and evidence.verification_profile_ref.startswith(VERIFICATION_REFERENCE_PREFIX)
        and bool(CANONICAL_ID.fullmatch(evidence.verification_profile_ref[len(VERIFICATION_REFERENCE_PREFIX):]))
        and not evidence.secret_material_present
        and not evidence.credential_material_present
        and not evidence.secret_reference_present
    )

def _expect_denied(checks: dict[str, bool], name: str, fn) -> None:
    try:
        fn()
        checks[name] = False
    except SecretBoundaryDenied:
        checks[name] = True

def run_probes() -> dict[str, bool]:
    ref = SecretReference("kms://orders-signing/current", 7, "tenant-a/orders")
    authority = SecretAuthority(True, ref.handle, 7, ("tenant-a/orders",))
    verification_ref = "verification-profile://semantic-equivalence-v3"
    safe_payload = {"order_id": PayloadField("ord-42", "business_data"), "event": PayloadField("order.created", "internal")}
    message = create_message(message_id="msg-001", tenant_id="tenant-a", payload=safe_payload, secret_ref=ref, verification_profile_ref=verification_ref, verification_generation_ref=7)
    checks: dict[str, bool] = {}

    checks["ordinary_payload_excludes_secret_credential_material"] = not _contains_sensitive_material(message.payload) and all(field.classification in ALLOWED_PAYLOAD_CLASSIFICATIONS for field in message.payload.values())
    for probe_name, field_name, classification in [
        ("password", "password", "credential"), ("secret", "business_note", "secret"), ("credential", "credential", "credential"),
        ("token", "token", "credential"), ("api_key", "api_key", "credential"), ("private_key", "private_key", "key_material"), ("key_material", "key_material", "key_material")]:
        _expect_denied(checks, f"reject_payload_{probe_name}", lambda field_name=field_name, classification=classification: create_message(message_id="bad", tenant_id="tenant-a", payload={field_name: PayloadField("must-not-appear", classification)}, secret_ref=ref, verification_profile_ref=verification_ref, verification_generation_ref=7))

    _expect_denied(checks,"reject_payload_unknown_classification",lambda:create_message(message_id="bad-unknown-classification",tenant_id="tenant-a",payload={"note":PayloadField("opaque","unclassified")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"secret_reference_empty_handle_rejected",lambda:create_message(message_id="bad-empty-handle",tenant_id="tenant-a",payload=safe_payload,secret_ref=replace(ref,handle=""),verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"secret_reference_nonpositive_generation_rejected",lambda:create_message(message_id="bad-secret-generation",tenant_id="tenant-a",payload=safe_payload,secret_ref=replace(ref,generation=0),verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"secret_reference_invalid_scope_rejected",lambda:create_message(message_id="bad-secret-scope",tenant_id="tenant-a",payload=safe_payload,secret_ref=replace(ref,scope="tenant-a"),verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"verification_generation_nonpositive_rejected",lambda:create_message(message_id="bad-verification-generation",tenant_id="tenant-a",payload=safe_payload,secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=0))

    wrong_namespace_but_canonical_suffix=("x"*len(VERIFICATION_REFERENCE_PREFIX))+"valid-profile"
    _expect_denied(checks,"verification_reference_namespace_rejected",lambda:create_message(message_id="bad-verification-namespace",tenant_id="tenant-a",payload=safe_payload,secret_ref=ref,verification_profile_ref=wrong_namespace_but_canonical_suffix,verification_generation_ref=7))
    _expect_denied(checks,"verification_reference_noncanonical_id_rejected",lambda:create_message(message_id="bad-verification-id",tenant_id="tenant-a",payload=safe_payload,secret_ref=ref,verification_profile_ref="verification-profile://bad/id",verification_generation_ref=7))

    direct_collision_ref=replace(ref,handle="verification-profile://collision-profile")
    _expect_denied(checks,"verification_reference_alias_secret_handle_rejected",lambda:create_message(message_id="bad-verification-alias",tenant_id="tenant-a",payload=safe_payload,secret_ref=direct_collision_ref,verification_profile_ref=direct_collision_ref.handle,verification_generation_ref=7))
    embedded_collision_ref=replace(ref,handle="collision-handle-7")
    _expect_denied(checks,"verification_reference_embedding_secret_handle_rejected",lambda:create_message(message_id="bad-verification-embed",tenant_id="tenant-a",payload=safe_payload,secret_ref=embedded_collision_ref,verification_profile_ref="verification-profile://prefix-collision-handle-7-suffix",verification_generation_ref=7))

    checks["audit_reference_is_derived_non_secret"]=_audit_reference(ref)=="secret-audit-ref://tenant-a/orders/generation-7" and ref.handle not in _audit_reference(ref)
    scope_collision_ref=replace(ref,handle="tenant-a/orders",scope="tenant-a/orders")
    scope_collision_authority=replace(authority,current_handle=scope_collision_ref.handle)
    _expect_denied(checks,"secret_handle_scope_rejected",lambda:resolve_secret(reference=scope_collision_ref,authority=scope_collision_authority,requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"unsupported_record_kind_rejected",lambda:sanitize_record(message,record_kind="debug_dump"))

    reconstructed_collision_ref=replace(ref,handle="verification-profile://reconstructed-collision")
    reconstructed_aliased_message=OrdinaryMessage("reconstructed-alias","tenant-a",dict(safe_payload),reconstructed_collision_ref,reconstructed_collision_ref.handle,7)
    _expect_denied(checks,"sanitize_reconstructed_alias_rejected",lambda:sanitize_record(reconstructed_aliased_message,record_kind="inbox"))
    _expect_denied(checks,"erase_reconstructed_alias_rejected",lambda:erase_and_minimize(reconstructed_aliased_message))

    reconstructed_secret_payload=OrdinaryMessage("reconstructed-secret-payload","tenant-a",{"note":PayloadField("must-not-survive","secret")},ref,verification_ref,7)
    _expect_denied(checks,"sanitize_reconstructed_secret_payload_rejected",lambda:sanitize_record(reconstructed_secret_payload,record_kind="inbox"))
    _expect_denied(checks,"erase_reconstructed_secret_payload_rejected",lambda:erase_and_minimize(reconstructed_secret_payload))

    reconstructed_bad_verification_generation=OrdinaryMessage("reconstructed-bad-verification-generation","tenant-a",dict(safe_payload),ref,verification_ref,0)
    _expect_denied(checks,"sanitize_reconstructed_nonpositive_verification_generation_rejected",lambda:sanitize_record(reconstructed_bad_verification_generation,record_kind="inbox"))
    _expect_denied(checks,"erase_reconstructed_nonpositive_verification_generation_rejected",lambda:erase_and_minimize(reconstructed_bad_verification_generation))

    sanitized=[sanitize_record(message,record_kind=k) for k in ("inbox","log","trace","quarantine")]
    checks["secondary_records_exclude_secret_key_material"]=all(not r["secret_ref_present"] and not r["secret_material_present"] and not r["credential_material_present"] and not r["key_material_present"] and ref.handle not in str(r) for r in sanitized)

    evidence=erase_and_minimize(message)
    checks["erasure_preserves_non_secret_historical_verification_reference"]=evidence.verification_profile_ref==verification_ref and evidence.verification_generation_ref==7 and ref.handle not in evidence.verification_profile_ref and not evidence.secret_material_present and not evidence.credential_material_present and not evidence.secret_reference_present
    checks["redaction_erasure_preserve_correctness_evidence"]=duplicate_sensitive_effect_eligible(evidence,expected_tenant="tenant-a",expected_profile=verification_ref,known_generations=(5,6,7))

    audit=[]
    resolved=resolve_secret(reference=ref,authority=authority,requested_scope="tenant-a/orders",authorized=True,audit_sink=audit)
    checks["secret_resolution_is_narrowly_authorized_and_audited"]=isinstance(resolved,SecretMaterial) and resolved.handle==ref.handle and resolved.generation==7 and len(audit)==1 and audit[0]["scope"]=="tenant-a/orders" and audit[0]["reference"]==_audit_reference(ref) and audit[0]["secret_handle_logged"] is False and audit[0]["secret_material_logged"] is False and ref.handle not in str(audit[0])
    _expect_denied(checks,"resolved_secret_material_rejected_under_business_classification",lambda:create_message(message_id="bad-resolved-secret",tenant_id="tenant-a",payload={"note":PayloadField(resolved,"business_data")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))

    _expect_denied(checks,"unauthorized_resolution_fails_closed",lambda:resolve_secret(reference=ref,authority=authority,requested_scope="tenant-a/orders",authorized=False,audit_sink=[]))
    _expect_denied(checks,"cross_scope_resolution_fails_closed",lambda:resolve_secret(reference=ref,authority=authority,requested_scope="tenant-b/orders",authorized=True,audit_sink=[]))
    scope_mismatch_authority=replace(authority,allowed_scopes=("tenant-a/orders","tenant-b/orders"))
    _expect_denied(checks,"reference_scope_mismatch_fails_closed",lambda:resolve_secret(reference=ref,authority=scope_mismatch_authority,requested_scope="tenant-b/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"scope_not_allowlisted_fails_closed",lambda:resolve_secret(reference=ref,authority=replace(authority,allowed_scopes=()),requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"secret_authority_outage_fails_closed",lambda:resolve_secret(reference=ref,authority=replace(authority,available=False),requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"invalid_secret_authority_source_rejected",lambda:resolve_secret(reference=ref,authority=replace(authority,authority_source="ordinary_payload_authority"),requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"unknown_secret_handle_resolution_fails_closed",lambda:resolve_secret(reference=replace(ref,handle="kms://orders-signing/unknown"),authority=authority,requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"stale_generation_resolution_fails_closed",lambda:resolve_secret(reference=replace(ref,generation=6),authority=authority,requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"unknown_generation_resolution_fails_closed",lambda:resolve_secret(reference=replace(ref,generation=99),authority=authority,requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))

    checks["historical_reference_is_not_bearer_authority"]=not historical_reference_can_resolve_secret(evidence,authority,scope="tenant-a/orders")
    bearer_ref=replace(ref,bearer_authority=True)
    _expect_denied(checks,"bearer_secret_reference_rejected",lambda:create_message(message_id="bad-ref",tenant_id="tenant-a",payload=safe_payload,secret_ref=bearer_ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"resolve_bearer_secret_reference_rejected",lambda:resolve_secret(reference=bearer_ref,authority=authority,requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    return checks

if __name__=="__main__":
    checks=run_probes()
    failed=[name for name,ok in checks.items() if not ok]
    if failed: raise SystemExit("FAILED: "+",".join(failed))
    print(f"d4d_open_evt_017_secret_exclusion_source=PASS probes={len(checks)}")
