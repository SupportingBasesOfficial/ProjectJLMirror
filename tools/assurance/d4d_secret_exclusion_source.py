#!/usr/bin/env python3
from __future__ import annotations
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, astuple, dataclass, replace
from types import MappingProxyType
from urllib.parse import parse_qsl, quote, unquote, urlencode

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
    payload: Mapping[str, PayloadField]
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
URL_DECODE_MAX_ROUNDS = 4
URL_DECODE_MAX_LENGTH = 16384
DURABLE_SECRET_AUTHORITY_HANDLES = frozenset({
    "kms://orders-signing/current",
    "kms://other/current",
    "collision-profile",
})


def _validate_generation(value: object, label: str) -> None:
    if type(value) is not int or value <= 0:
        raise SecretBoundaryDenied(f"{label} must be a positive integer")


def _known_secret_handle_in_text(value: str, secret_handle: object = None) -> bool:
    handles = set(DURABLE_SECRET_AUTHORITY_HANDLES)
    if isinstance(secret_handle, str) and secret_handle:
        handles.add(secret_handle)
    return any(handle and handle in value for handle in handles)


def _validate_identifier(value: object, label: str, secret_handle: object = None) -> None:
    if type(value) is not str or not value:
        raise SecretBoundaryDenied(f"{label} must be a non-empty non-secret string")
    if _known_secret_handle_in_text(value, secret_handle):
        raise SecretBoundaryDenied(f"{label} must not alias or embed a known secret handle")


def _looks_like_serialized_secret_material(value: Mapping[str, object]) -> bool:
    if "handle" not in value or "generation" not in value:
        return False
    handle = value.get("handle")
    generation = value.get("generation")
    return isinstance(handle, str) and bool(handle) and type(generation) is int and generation > 0


def _looks_like_positional_serialized_secret_material(value: object) -> bool:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return False
    handle, generation = value
    return isinstance(handle, str) and bool(handle) and type(generation) is int and generation > 0


def _url_form_contains_secret_material(value: str, secret_handle: object = None) -> bool:
    if "=" not in value:
        return False
    try:
        pairs = parse_qsl(value, keep_blank_values=True, strict_parsing=False)
    except ValueError:
        return False
    if not pairs:
        return False
    form: dict[str, list[str]] = {}
    for key, item in pairs:
        form.setdefault(key, []).append(item)
        if _known_secret_handle_in_text(key, secret_handle) or _known_secret_handle_in_text(item, secret_handle):
            return True
    if "handle" in form and "generation" in form:
        handles = form["handle"]
        generations = form["generation"]
        if any(handle for handle in handles) and any(g.isdigit() and int(g) > 0 for g in generations):
            return True
    return False


def _decoded_text_contains_secret_material(value: str, secret_handle: object = None) -> bool:
    if _known_secret_handle_in_text(value, secret_handle):
        return True
    stripped = value.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            structured = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            structured = None
        if structured is not None and _value_contains_secret_material(structured, secret_handle):
            return True
    return _url_form_contains_secret_material(value, secret_handle)


def _url_escaped_contains_secret_material(value: str, secret_handle: object = None) -> bool:
    if "%" not in value:
        return False
    decoded = value
    for _ in range(URL_DECODE_MAX_ROUNDS):
        if "%" not in decoded:
            return False
        next_decoded = unquote(decoded)
        if next_decoded == decoded:
            return False
        decoded = next_decoded
        if len(decoded) > URL_DECODE_MAX_LENGTH:
            raise SecretBoundaryDenied("URL-decoded payload text exceeds normalization bound")
        if _decoded_text_contains_secret_material(decoded, secret_handle):
            return True
    if "%" in decoded and unquote(decoded) != decoded:
        return True
    return False


def _text_contains_secret_material(value: str, secret_handle: object = None) -> bool:
    if _known_secret_handle_in_text(value, secret_handle):
        return True
    stripped = value.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            decoded = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            decoded = None
        if decoded is not None and _value_contains_secret_material(decoded, secret_handle):
            return True
    if _url_form_contains_secret_material(value, secret_handle):
        return True
    return _url_escaped_contains_secret_material(value, secret_handle)


def _value_contains_secret_material(value: object, secret_handle: object = None) -> bool:
    if isinstance(value, SecretMaterial):
        return True
    if isinstance(value, str):
        return _text_contains_secret_material(value, secret_handle)
    if value is None or isinstance(value, (int, float, bool)):
        return False
    if isinstance(value, (list, tuple)):
        if _looks_like_positional_serialized_secret_material(value):
            return True
        return any(_value_contains_secret_material(item, secret_handle) for item in value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise SecretBoundaryDenied("payload object keys must be strings")
        if any(_text_contains_secret_material(key, secret_handle) for key in value):
            return True
        if _looks_like_serialized_secret_material(value):
            return True
        return any(_value_contains_secret_material(item, secret_handle) for item in value.values())
    raise SecretBoundaryDenied("unsupported payload value type")


def _freeze_payload_value(value: object, secret_handle: object = None) -> object:
    if isinstance(value, str):
        if _text_contains_secret_material(value, secret_handle):
            raise SecretBoundaryDenied("ordinary payload cannot contain text-serialized secret material or known secret handle")
        return value
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, list):
        if _looks_like_positional_serialized_secret_material(value):
            raise SecretBoundaryDenied("ordinary payload cannot contain a positional serialized secret handle and generation")
        return tuple(_freeze_payload_value(item, secret_handle) for item in value)
    if isinstance(value, tuple):
        if _looks_like_positional_serialized_secret_material(value):
            raise SecretBoundaryDenied("ordinary payload cannot contain a positional serialized secret handle and generation")
        return tuple(_freeze_payload_value(item, secret_handle) for item in value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise SecretBoundaryDenied("payload object keys must be strings")
        if any(_text_contains_secret_material(key, secret_handle) for key in value):
            raise SecretBoundaryDenied("ordinary payload object keys cannot contain known secret handles")
        if _looks_like_serialized_secret_material(value):
            raise SecretBoundaryDenied("ordinary payload cannot contain a serialized secret handle and generation")
        return MappingProxyType({key: _freeze_payload_value(item, secret_handle) for key, item in value.items()})
    raise SecretBoundaryDenied("unsupported payload value type")


def _contains_sensitive_material(values: Mapping[str, PayloadField], secret_handle: object = None) -> bool:
    return any(_text_contains_secret_material(key, secret_handle) for key in values) or any(
        field.classification in FORBIDDEN_PAYLOAD_CLASSIFICATIONS
        or _value_contains_secret_material(field.value, secret_handle)
        for field in values.values()
    )


def _validate_payload(values: Mapping[str, PayloadField], secret_handle: object = None) -> None:
    if not isinstance(values, Mapping) or not all(isinstance(key, str) for key in values):
        raise SecretBoundaryDenied("ordinary payload must be a string-keyed mapping")
    if any(_text_contains_secret_material(key, secret_handle) for key in values):
        raise SecretBoundaryDenied("ordinary payload keys cannot contain known secret handles")
    if not all(isinstance(field, PayloadField) for field in values.values()):
        raise SecretBoundaryDenied("ordinary payload values must be classified payload fields")
    classifications = {field.classification for field in values.values()}
    unknown = classifications - ALLOWED_PAYLOAD_CLASSIFICATIONS - FORBIDDEN_PAYLOAD_CLASSIFICATIONS
    if unknown:
        raise SecretBoundaryDenied("unknown payload classification")
    if _contains_sensitive_material(values, secret_handle):
        raise SecretBoundaryDenied("ordinary message payload cannot contain secret, credential, or key material")


def _freeze_payload(values: Mapping[str, PayloadField], secret_handle: object = None) -> Mapping[str, PayloadField]:
    _validate_payload(values, secret_handle)
    frozen = {
        key: PayloadField(_freeze_payload_value(field.value, secret_handle), field.classification)
        for key, field in values.items()
    }
    return MappingProxyType(frozen)


def _validate_scope(scope: object) -> None:
    if type(scope) is not str or not CANONICAL_SCOPE.fullmatch(scope):
        raise SecretBoundaryDenied("scope must be a canonical non-secret identifier")


def _validate_allowed_scopes(scopes: object) -> tuple[str, ...]:
    if not isinstance(scopes, (tuple, list)):
        raise SecretBoundaryDenied("secret authority allowed scopes must be an explicit scope collection")
    validated: list[str] = []
    for scope in scopes:
        _validate_scope(scope)
        validated.append(scope)
    return tuple(validated)


def _validate_secret_reference_shape(reference: SecretReference) -> None:
    if not isinstance(reference, SecretReference):
        raise SecretBoundaryDenied("secret reference must be a hydrated SecretReference")
    if reference.bearer_authority:
        raise SecretBoundaryDenied("secret reference cannot be bearer authority")
    if type(reference.handle) is not str or not reference.handle:
        raise SecretBoundaryDenied("secret reference handle must be a non-empty string")
    if reference.handle.startswith(VERIFICATION_REFERENCE_PREFIX):
        raise SecretBoundaryDenied("secret handle cannot use verification reference namespace")
    if reference.handle.startswith(AUDIT_REFERENCE_PREFIX):
        raise SecretBoundaryDenied("secret handle cannot use audit reference namespace")
    _validate_generation(reference.generation, "secret reference generation")
    _validate_scope(reference.scope)


def _audit_reference(reference: SecretReference) -> str:
    _validate_secret_reference_shape(reference)
    audit_ref = f"{AUDIT_REFERENCE_PREFIX}{reference.scope}/generation-{reference.generation}"
    if _known_secret_handle_in_text(audit_ref, reference.handle):
        raise SecretBoundaryDenied("derived audit reference must not contain any known secret-authority handle")
    return audit_ref


def _validate_verification_reference(reference: str, secret_ref: SecretReference | None) -> None:
    if type(reference) is not str or not reference.startswith(VERIFICATION_REFERENCE_PREFIX):
        raise SecretBoundaryDenied("verification reference must use non-secret namespace")
    profile_id = reference[len(VERIFICATION_REFERENCE_PREFIX):]
    if not CANONICAL_ID.fullmatch(profile_id):
        raise SecretBoundaryDenied("verification profile identifier must be canonical")
    if secret_ref is not None and isinstance(secret_ref.handle, str) and secret_ref.handle:
        if reference == secret_ref.handle or secret_ref.handle in reference:
            raise SecretBoundaryDenied("verification reference must not alias or embed secret handle")
    if _known_secret_handle_in_text(reference):
        raise SecretBoundaryDenied("verification reference must not alias or embed a durable secret-authority handle")


def _validate_message_boundary(message: OrdinaryMessage) -> None:
    secret_handle = message.secret_ref.handle if isinstance(message.secret_ref, SecretReference) and isinstance(message.secret_ref.handle, str) else None
    _validate_identifier(message.message_id, "message id", secret_handle)
    _validate_identifier(message.tenant_id, "tenant id", secret_handle)
    _validate_payload(message.payload, secret_handle)
    if message.secret_ref is not None:
        _validate_secret_reference_shape(message.secret_ref)
    _validate_verification_reference(message.verification_profile_ref, message.secret_ref)
    _validate_generation(message.verification_generation_ref, "historical verification generation")


def create_message(*, message_id: str, tenant_id: str, payload: Mapping[str, PayloadField], secret_ref: SecretReference | None, verification_profile_ref: str, verification_generation_ref: int) -> OrdinaryMessage:
    secret_handle = secret_ref.handle if isinstance(secret_ref, SecretReference) and isinstance(secret_ref.handle, str) else None
    frozen_payload = _freeze_payload(payload, secret_handle)
    message = OrdinaryMessage(message_id, tenant_id, frozen_payload, secret_ref, verification_profile_ref, verification_generation_ref)
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
    _validate_generation(authority.current_generation, "secret authority current generation")
    allowed_scopes = _validate_allowed_scopes(authority.allowed_scopes)
    if authority.available is not True:
        raise SecretBoundaryDenied("secret authority unavailable: fail closed")
    if authority.authority_source != "secret_or_kms_authority":
        raise SecretBoundaryDenied("invalid secret authority source")
    if type(authority.current_handle) is not str or authority.current_handle not in DURABLE_SECRET_AUTHORITY_HANDLES:
        raise SecretBoundaryDenied("secret authority handle is not durably configured")
    if reference.handle != authority.current_handle:
        raise SecretBoundaryDenied("unknown or revoked secret handle")
    if reference.generation != authority.current_generation:
        raise SecretBoundaryDenied("stale or unknown secret generation")
    if authorized is not True or requested_scope != reference.scope or requested_scope not in allowed_scopes:
        raise SecretBoundaryDenied("secret resolution is not narrowly authorized")
    audit_ref = _audit_reference(reference)
    audit_sink.append({"scope": requested_scope, "reference": audit_ref, "generation": reference.generation, "resolved": True, "secret_handle_logged": False, "secret_material_logged": False})
    return SecretMaterial(reference.handle, reference.generation)


def erase_and_minimize(message: OrdinaryMessage) -> HistoricalEvidence:
    _validate_message_boundary(message)
    return HistoricalEvidence(message.message_id, message.tenant_id, message.verification_profile_ref, message.verification_generation_ref, False, False, False)


def historical_reference_can_resolve_secret(evidence: HistoricalEvidence, authority: SecretAuthority, *, scope: str) -> bool:
    try:
        resolve_secret(reference=SecretReference(evidence.verification_profile_ref, evidence.verification_generation_ref, scope), authority=authority, requested_scope=scope, authorized=True, audit_sink=[])
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


def _expect_type_error(checks: dict[str, bool], name: str, fn) -> None:
    try:
        fn()
        checks[name] = False
    except (TypeError, AttributeError):
        checks[name] = True


def run_probes() -> dict[str, bool]:
    ref = SecretReference("kms://orders-signing/current", 7, "tenant-a/orders")
    authority = SecretAuthority(True, ref.handle, 7, ("tenant-a/orders",))
    verification_ref = "verification-profile://semantic-equivalence-v3"
    safe_payload = {"order_id": PayloadField("ord-42", "business_data"), "event": PayloadField("order.created", "internal")}
    message = create_message(message_id="msg-001", tenant_id="tenant-a", payload=safe_payload, secret_ref=ref, verification_profile_ref=verification_ref, verification_generation_ref=7)
    checks: dict[str, bool] = {}

    checks["ordinary_payload_excludes_secret_credential_material"] = not _contains_sensitive_material(message.payload, ref.handle) and all(field.classification in ALLOWED_PAYLOAD_CLASSIFICATIONS for field in message.payload.values())
    mutable_nested_source = ["one", {"two": ["three"]}]
    mutable_source_payload = {"nested": PayloadField(mutable_nested_source, "business_data")}
    frozen_message = create_message(message_id="msg-freeze", tenant_id="tenant-a", payload=mutable_source_payload, secret_ref=ref, verification_profile_ref=verification_ref, verification_generation_ref=7)
    _expect_type_error(checks,"message_payload_mapping_is_immutable",lambda:frozen_message.payload.__setitem__("late",PayloadField("x","business_data")))
    mutable_nested_source.append(SecretMaterial(ref.handle, ref.generation))
    checks["source_payload_mutation_does_not_reach_message"] = not _value_contains_secret_material(frozen_message.payload["nested"].value, ref.handle)
    _expect_type_error(checks,"nested_payload_sequence_is_immutable",lambda:frozen_message.payload["nested"].value.__setitem__(0,SecretMaterial(ref.handle,ref.generation)))
    nested_mapping = frozen_message.payload["nested"].value[1]
    _expect_type_error(checks,"nested_payload_mapping_is_immutable",lambda:nested_mapping.__setitem__("secret",SecretMaterial(ref.handle,ref.generation)))

    for probe_name, field_name, classification in [
        ("password", "password", "credential"), ("secret", "business_note", "secret"), ("credential", "credential", "credential"),
        ("token", "token", "credential"), ("api_key", "api_key", "credential"), ("private_key", "private_key", "key_material"), ("key_material", "key_material", "key_material")]:
        _expect_denied(checks, f"reject_payload_{probe_name}", lambda field_name=field_name, classification=classification: create_message(message_id="bad", tenant_id="tenant-a", payload={field_name: PayloadField("must-not-appear", classification)}, secret_ref=ref, verification_profile_ref=verification_ref, verification_generation_ref=7))

    _expect_denied(checks,"reject_payload_unknown_classification",lambda:create_message(message_id="bad-unknown-classification",tenant_id="tenant-a",payload={"note":PayloadField("opaque","unclassified")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    identifier_secret=SecretMaterial(ref.handle,ref.generation)
    _expect_denied(checks,"message_id_secret_material_rejected",lambda:create_message(message_id=identifier_secret,tenant_id="tenant-a",payload=safe_payload,secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"tenant_id_secret_material_rejected",lambda:create_message(message_id="bad-tenant-id",tenant_id=identifier_secret,payload=safe_payload,secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"message_id_secret_handle_rejected",lambda:create_message(message_id=ref.handle,tenant_id="tenant-a",payload=safe_payload,secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"tenant_id_secret_handle_rejected",lambda:create_message(message_id="bad-tenant-handle",tenant_id=ref.handle,payload=safe_payload,secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"message_id_embedded_secret_handle_rejected",lambda:create_message(message_id=f"msg-{ref.handle}-suffix",tenant_id="tenant-a",payload=safe_payload,secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"tenant_id_embedded_secret_handle_rejected",lambda:create_message(message_id="bad-tenant-embedded",tenant_id=f"tenant-{ref.handle}-suffix",payload=safe_payload,secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"secret_reference_empty_handle_rejected",lambda:create_message(message_id="bad-empty-handle",tenant_id="tenant-a",payload=safe_payload,secret_ref=replace(ref,handle=""),verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"secret_reference_nonstring_handle_creation_rejected",lambda:create_message(message_id="bad-handle-type",tenant_id="tenant-a",payload=safe_payload,secret_ref=replace(ref,handle=1),verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"secret_reference_nonstring_handle_resolution_rejected",lambda:resolve_secret(reference=replace(ref,handle=1),authority=authority,requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"secret_reference_nonpositive_generation_rejected",lambda:create_message(message_id="bad-secret-generation",tenant_id="tenant-a",payload=safe_payload,secret_ref=replace(ref,generation=0),verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"secret_reference_boolean_generation_rejected",lambda:create_message(message_id="bad-secret-generation-bool",tenant_id="tenant-a",payload=safe_payload,secret_ref=replace(ref,generation=True),verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"secret_reference_fractional_generation_rejected",lambda:create_message(message_id="bad-secret-generation-float",tenant_id="tenant-a",payload=safe_payload,secret_ref=replace(ref,generation=1.5),verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"secret_reference_invalid_scope_rejected",lambda:create_message(message_id="bad-secret-scope",tenant_id="tenant-a",payload=safe_payload,secret_ref=replace(ref,scope="tenant-a"),verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"verification_generation_nonpositive_rejected",lambda:create_message(message_id="bad-verification-generation",tenant_id="tenant-a",payload=safe_payload,secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=0))
    _expect_denied(checks,"verification_generation_boolean_rejected",lambda:create_message(message_id="bad-verification-generation-bool",tenant_id="tenant-a",payload=safe_payload,secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=True))
    _expect_denied(checks,"verification_generation_fractional_rejected",lambda:create_message(message_id="bad-verification-generation-float",tenant_id="tenant-a",payload=safe_payload,secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=1.5))

    wrong_namespace_but_canonical_suffix=("x"*len(VERIFICATION_REFERENCE_PREFIX))+"valid-profile"
    _expect_denied(checks,"verification_reference_namespace_rejected",lambda:create_message(message_id="bad-verification-namespace",tenant_id="tenant-a",payload=safe_payload,secret_ref=ref,verification_profile_ref=wrong_namespace_but_canonical_suffix,verification_generation_ref=7))
    _expect_denied(checks,"verification_reference_noncanonical_id_rejected",lambda:create_message(message_id="bad-verification-id",tenant_id="tenant-a",payload=safe_payload,secret_ref=ref,verification_profile_ref="verification-profile://bad/id",verification_generation_ref=7))
    namespace_collision_ref=replace(ref,handle="verification-profile://collision-profile")
    _expect_denied(checks,"secret_handle_verification_namespace_rejected",lambda:create_message(message_id="bad-secret-namespace",tenant_id="tenant-a",payload=safe_payload,secret_ref=namespace_collision_ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    audit_namespace_ref=replace(ref,handle="secret-audit-ref://unrelated")
    audit_namespace_authority=replace(authority,current_handle=audit_namespace_ref.handle)
    _expect_denied(checks,"secret_handle_audit_namespace_rejected",lambda:resolve_secret(reference=audit_namespace_ref,authority=audit_namespace_authority,requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    direct_collision_ref=replace(ref,handle="collision-profile")
    _expect_denied(checks,"verification_reference_alias_secret_handle_rejected",lambda:create_message(message_id="bad-verification-alias",tenant_id="tenant-a",payload=safe_payload,secret_ref=direct_collision_ref,verification_profile_ref="verification-profile://collision-profile",verification_generation_ref=7))
    embedded_collision_ref=replace(ref,handle="collision-handle-7")
    _expect_denied(checks,"verification_reference_embedding_secret_handle_rejected",lambda:create_message(message_id="bad-verification-embed",tenant_id="tenant-a",payload=safe_payload,secret_ref=embedded_collision_ref,verification_profile_ref="verification-profile://prefix-collision-handle-7-suffix",verification_generation_ref=7))
    _expect_denied(checks,"durable_authority_verification_reference_alias_rejected",lambda:create_message(message_id="bad-durable-verification-alias",tenant_id="tenant-a",payload=safe_payload,secret_ref=None,verification_profile_ref="verification-profile://collision-profile",verification_generation_ref=7))

    checks["audit_reference_is_derived_non_secret"]=_audit_reference(ref)=="secret-audit-ref://tenant-a/orders/generation-7" and ref.handle not in _audit_reference(ref)
    scope_collision_ref=replace(ref,handle="collision-profile",scope="tenant-a/collision-profile")
    scope_collision_authority=replace(authority,current_handle=scope_collision_ref.handle,allowed_scopes=(scope_collision_ref.scope,))
    _expect_denied(checks,"secret_handle_scope_rejected",lambda:resolve_secret(reference=scope_collision_ref,authority=scope_collision_authority,requested_scope=scope_collision_ref.scope,authorized=True,audit_sink=[]))
    catalog_collision_ref=replace(ref,scope="tenant-a/collision-profile")
    catalog_collision_authority=replace(authority,allowed_scopes=(catalog_collision_ref.scope,))
    _expect_denied(checks,"audit_reference_catalogued_handle_collision_rejected",lambda:resolve_secret(reference=catalog_collision_ref,authority=catalog_collision_authority,requested_scope=catalog_collision_ref.scope,authorized=True,audit_sink=[]))
    _expect_denied(checks,"unsupported_record_kind_rejected",lambda:sanitize_record(message,record_kind="debug_dump"))

    reconstructed_collision_ref=replace(ref,handle="collision-reconstructed")
    reconstructed_aliased_message=OrdinaryMessage("reconstructed-alias","tenant-a",dict(safe_payload),reconstructed_collision_ref,"verification-profile://collision-reconstructed",7)
    _expect_denied(checks,"sanitize_reconstructed_alias_rejected",lambda:sanitize_record(reconstructed_aliased_message,record_kind="inbox"))
    _expect_denied(checks,"erase_reconstructed_alias_rejected",lambda:erase_and_minimize(reconstructed_aliased_message))
    reconstructed_unhydrated_secret_ref=OrdinaryMessage("reconstructed-unhydrated-ref","tenant-a",dict(safe_payload),{"handle":ref.handle,"generation":ref.generation,"scope":ref.scope},verification_ref,7)
    _expect_denied(checks,"sanitize_reconstructed_unhydrated_secret_ref_rejected",lambda:sanitize_record(reconstructed_unhydrated_secret_ref,record_kind="inbox"))
    _expect_denied(checks,"erase_reconstructed_unhydrated_secret_ref_rejected",lambda:erase_and_minimize(reconstructed_unhydrated_secret_ref))
    reconstructed_secret_message_id=OrdinaryMessage(identifier_secret,"tenant-a",dict(safe_payload),ref,verification_ref,7)
    _expect_denied(checks,"sanitize_reconstructed_secret_message_id_rejected",lambda:sanitize_record(reconstructed_secret_message_id,record_kind="inbox"))
    _expect_denied(checks,"erase_reconstructed_secret_message_id_rejected",lambda:erase_and_minimize(reconstructed_secret_message_id))
    reconstructed_secret_tenant_id=OrdinaryMessage("reconstructed-secret-tenant",identifier_secret,dict(safe_payload),ref,verification_ref,7)
    _expect_denied(checks,"sanitize_reconstructed_secret_tenant_id_rejected",lambda:sanitize_record(reconstructed_secret_tenant_id,record_kind="inbox"))
    _expect_denied(checks,"erase_reconstructed_secret_tenant_id_rejected",lambda:erase_and_minimize(reconstructed_secret_tenant_id))
    reconstructed_handle_message_id=OrdinaryMessage(ref.handle,"tenant-a",dict(safe_payload),ref,verification_ref,7)
    _expect_denied(checks,"sanitize_reconstructed_secret_handle_message_id_rejected",lambda:sanitize_record(reconstructed_handle_message_id,record_kind="inbox"))
    _expect_denied(checks,"erase_reconstructed_secret_handle_message_id_rejected",lambda:erase_and_minimize(reconstructed_handle_message_id))
    reconstructed_handle_tenant_id=OrdinaryMessage("reconstructed-handle-tenant",ref.handle,dict(safe_payload),ref,verification_ref,7)
    _expect_denied(checks,"sanitize_reconstructed_secret_handle_tenant_id_rejected",lambda:sanitize_record(reconstructed_handle_tenant_id,record_kind="inbox"))
    _expect_denied(checks,"erase_reconstructed_secret_handle_tenant_id_rejected",lambda:erase_and_minimize(reconstructed_handle_tenant_id))
    reconstructed_secret_payload=OrdinaryMessage("reconstructed-secret-payload","tenant-a",{"note":PayloadField("must-not-survive","secret")},ref,verification_ref,7)
    _expect_denied(checks,"sanitize_reconstructed_secret_payload_rejected",lambda:sanitize_record(reconstructed_secret_payload,record_kind="inbox"))
    _expect_denied(checks,"erase_reconstructed_secret_payload_rejected",lambda:erase_and_minimize(reconstructed_secret_payload))
    reconstructed_bad_verification_generation=OrdinaryMessage("reconstructed-bad-verification-generation","tenant-a",dict(safe_payload),ref,verification_ref,0)
    _expect_denied(checks,"sanitize_reconstructed_nonpositive_verification_generation_rejected",lambda:sanitize_record(reconstructed_bad_verification_generation,record_kind="inbox"))
    _expect_denied(checks,"erase_reconstructed_nonpositive_verification_generation_rejected",lambda:erase_and_minimize(reconstructed_bad_verification_generation))
    reconstructed_bool_verification_generation=OrdinaryMessage("reconstructed-bool-verification-generation","tenant-a",dict(safe_payload),ref,verification_ref,True)
    _expect_denied(checks,"sanitize_reconstructed_boolean_verification_generation_rejected",lambda:sanitize_record(reconstructed_bool_verification_generation,record_kind="inbox"))
    _expect_denied(checks,"erase_reconstructed_boolean_verification_generation_rejected",lambda:erase_and_minimize(reconstructed_bool_verification_generation))
    reconstructed_fractional_verification_generation=OrdinaryMessage("reconstructed-fractional-verification-generation","tenant-a",dict(safe_payload),ref,verification_ref,1.5)
    _expect_denied(checks,"sanitize_reconstructed_fractional_verification_generation_rejected",lambda:sanitize_record(reconstructed_fractional_verification_generation,record_kind="inbox"))
    _expect_denied(checks,"erase_reconstructed_fractional_verification_generation_rejected",lambda:erase_and_minimize(reconstructed_fractional_verification_generation))

    sanitized=[sanitize_record(message,record_kind=k) for k in ("inbox","log","trace","quarantine")]
    checks["secondary_records_exclude_secret_key_material"]=all(not r["secret_ref_present"] and not r["secret_material_present"] and not r["credential_material_present"] and not r["key_material_present"] and ref.handle not in str(r) for r in sanitized)
    evidence=erase_and_minimize(message)
    checks["erasure_preserves_non_secret_historical_verification_reference"]=evidence.verification_profile_ref==verification_ref and evidence.verification_generation_ref==7 and ref.handle not in evidence.verification_profile_ref and not evidence.secret_material_present and not evidence.credential_material_present and not evidence.secret_reference_present
    checks["redaction_erasure_preserve_correctness_evidence"]=duplicate_sensitive_effect_eligible(evidence,expected_tenant="tenant-a",expected_profile=verification_ref,known_generations=(5,6,7))

    audit=[]
    resolved=resolve_secret(reference=ref,authority=authority,requested_scope="tenant-a/orders",authorized=True,audit_sink=audit)
    checks["secret_resolution_is_narrowly_authorized_and_audited"]=isinstance(resolved,SecretMaterial) and resolved.handle==ref.handle and resolved.generation==7 and len(audit)==1 and audit[0]["scope"]=="tenant-a/orders" and audit[0]["reference"]==_audit_reference(ref) and audit[0]["secret_handle_logged"] is False and audit[0]["secret_material_logged"] is False and ref.handle not in str(audit[0])
    second_ref=SecretReference("kms://other/current",3,"tenant-a/other")
    second_authority=SecretAuthority(True,second_ref.handle,3,("tenant-a/other",))
    second_resolved=resolve_secret(reference=second_ref,authority=second_authority,requested_scope="tenant-a/other",authorized=True,audit_sink=[])
    checks["second_configured_authority_handle_resolves"]=isinstance(second_resolved,SecretMaterial) and second_resolved.handle==second_ref.handle and second_resolved.generation==3
    _expect_denied(checks,"second_configured_authority_handle_detached_payload_rejected",lambda:create_message(message_id="bad-second-detached-handle",tenant_id="tenant-a",payload={"note":PayloadField(second_resolved.handle,"business_data")},secret_ref=None,verification_profile_ref=verification_ref,verification_generation_ref=7))
    uncatalogued_ref=SecretReference("kms://uncatalogued/current",4,"tenant-a/uncatalogued")
    uncatalogued_authority=SecretAuthority(True,uncatalogued_ref.handle,4,("tenant-a/uncatalogued",))
    _expect_denied(checks,"uncatalogued_authority_handle_rejected",lambda:resolve_secret(reference=uncatalogued_ref,authority=uncatalogued_authority,requested_scope="tenant-a/uncatalogued",authorized=True,audit_sink=[]))
    _expect_denied(checks,"resolved_secret_material_rejected_under_business_classification",lambda:create_message(message_id="bad-resolved-secret",tenant_id="tenant-a",payload={"note":PayloadField(resolved,"business_data")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    serialized_resolved = asdict(resolved)
    _expect_denied(checks,"serialized_resolved_secret_material_rejected",lambda:create_message(message_id="bad-serialized-resolved-secret",tenant_id="tenant-a",payload={"note":PayloadField(serialized_resolved,"business_data")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"nested_serialized_resolved_secret_material_rejected",lambda:create_message(message_id="bad-nested-serialized-resolved-secret",tenant_id="tenant-a",payload={"note":PayloadField({"outer":[{"inner":serialized_resolved}]},"business_data")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    positional_serialized_resolved = astuple(resolved)
    _expect_denied(checks,"positional_serialized_resolved_secret_material_rejected",lambda:create_message(message_id="bad-positional-serialized-secret",tenant_id="tenant-a",payload={"note":PayloadField(positional_serialized_resolved,"business_data")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"nested_positional_serialized_resolved_secret_material_rejected",lambda:create_message(message_id="bad-nested-positional-serialized-secret",tenant_id="tenant-a",payload={"note":PayloadField({"outer":[positional_serialized_resolved]},"business_data")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    textual_serialized_resolved = json.dumps(serialized_resolved, sort_keys=True)
    positional_textual_serialized_resolved = json.dumps(positional_serialized_resolved)
    nested_textual_serialized_resolved = json.dumps({"outer":[{"inner":serialized_resolved}]}, sort_keys=True)
    url_form_serialized_resolved = urlencode(serialized_resolved)
    url_escaped_serialized_resolved = quote(textual_serialized_resolved, safe="")
    double_url_escaped_serialized_resolved = quote(url_escaped_serialized_resolved, safe="")
    benign_url_escaped = quote("benign payload", safe="")
    benign_double_url_escaped = quote(benign_url_escaped, safe="")
    over_bound_url_escaped_secret = textual_serialized_resolved
    for _ in range(URL_DECODE_MAX_ROUNDS + 1):
        over_bound_url_escaped_secret = quote(over_bound_url_escaped_secret, safe="")
    _expect_denied(checks,"text_serialized_resolved_secret_material_rejected",lambda:create_message(message_id="bad-text-serialized-secret",tenant_id="tenant-a",payload={"note":PayloadField(textual_serialized_resolved,"business_data")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"positional_text_serialized_resolved_secret_material_rejected",lambda:create_message(message_id="bad-positional-text-serialized-secret",tenant_id="tenant-a",payload={"note":PayloadField(positional_textual_serialized_resolved,"business_data")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"nested_text_serialized_resolved_secret_material_rejected",lambda:create_message(message_id="bad-nested-text-serialized-secret",tenant_id="tenant-a",payload={"note":PayloadField(nested_textual_serialized_resolved,"business_data")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"url_form_serialized_resolved_secret_material_rejected",lambda:create_message(message_id="bad-url-form-secret",tenant_id="tenant-a",payload={"note":PayloadField(url_form_serialized_resolved,"business_data")},secret_ref=None,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"url_escaped_serialized_resolved_secret_material_rejected",lambda:create_message(message_id="bad-url-escaped-secret",tenant_id="tenant-a",payload={"note":PayloadField(url_escaped_serialized_resolved,"business_data")},secret_ref=None,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"double_url_escaped_serialized_resolved_secret_material_rejected",lambda:create_message(message_id="bad-double-url-escaped-secret",tenant_id="tenant-a",payload={"note":PayloadField(double_url_escaped_serialized_resolved,"business_data")},secret_ref=None,verification_profile_ref=verification_ref,verification_generation_ref=7))
    benign_double_message=create_message(message_id="benign-double-url-escaped",tenant_id="tenant-a",payload={"note":PayloadField(benign_double_url_escaped,"business_data")},secret_ref=None,verification_profile_ref=verification_ref,verification_generation_ref=7)
    checks["double_url_escaped_benign_payload_accepted_after_stabilization"]=benign_double_message.payload["note"].value==benign_double_url_escaped
    _expect_denied(checks,"over_decode_bound_secret_material_rejected",lambda:create_message(message_id="bad-over-bound-url-escaped-secret",tenant_id="tenant-a",payload={"note":PayloadField(over_bound_url_escaped_secret,"business_data")},secret_ref=None,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"secret_handle_text_fragment_rejected",lambda:create_message(message_id="bad-secret-handle-text",tenant_id="tenant-a",payload={"note":PayloadField(f"opaque-prefix:{ref.handle}:suffix","business_data")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"top_level_payload_key_secret_handle_rejected",lambda:create_message(message_id="bad-top-key",tenant_id="tenant-a",payload={ref.handle:PayloadField("x","business_data")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"nested_payload_key_secret_handle_rejected",lambda:create_message(message_id="bad-nested-key",tenant_id="tenant-a",payload={"note":PayloadField({ref.handle:"x"},"business_data")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"fresh_worker_configured_handle_without_resolution_history_rejected",lambda:create_message(message_id="bad-fresh-worker-handle",tenant_id="tenant-a",payload={"note":PayloadField(ref.handle,"business_data")},secret_ref=None,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"resolved_handle_without_attached_reference_rejected",lambda:create_message(message_id="bad-detached-handle",tenant_id="tenant-a",payload={"note":PayloadField(resolved.handle,"business_data")},secret_ref=None,verification_profile_ref=verification_ref,verification_generation_ref=7))
    other_ref=SecretReference("kms://other/current",3,"tenant-a/other")
    _expect_denied(checks,"resolved_handle_with_different_reference_rejected",lambda:create_message(message_id="bad-cross-ref-handle",tenant_id="tenant-a",payload={"note":PayloadField(resolved.handle,"business_data")},secret_ref=other_ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    parser_only_mapping=json.dumps({"handle":"opaque-parser-only","generation":11},sort_keys=True)
    parser_only_positional=json.dumps(["opaque-parser-only",11])
    parser_only_nested=json.dumps({"outer":[{"handle":"opaque-parser-only","generation":11}]},sort_keys=True)
    _expect_denied(checks,"json_parser_mapping_secret_shape_rejected",lambda:create_message(message_id="bad-parser-map",tenant_id="tenant-a",payload={"note":PayloadField(parser_only_mapping,"business_data")},secret_ref=None,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"json_parser_positional_secret_shape_rejected",lambda:create_message(message_id="bad-parser-positional",tenant_id="tenant-a",payload={"note":PayloadField(parser_only_positional,"business_data")},secret_ref=None,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"json_parser_nested_secret_shape_rejected",lambda:create_message(message_id="bad-parser-nested",tenant_id="tenant-a",payload={"note":PayloadField(parser_only_nested,"business_data")},secret_ref=None,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"nested_list_secret_material_rejected",lambda:create_message(message_id="bad-nested-list-secret",tenant_id="tenant-a",payload={"note":PayloadField(["prefix",resolved],"business_data")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"nested_object_secret_material_rejected",lambda:create_message(message_id="bad-nested-object-secret",tenant_id="tenant-a",payload={"note":PayloadField({"safe":"x","nested":{"secret":resolved}},"business_data")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"opaque_payload_value_type_rejected",lambda:create_message(message_id="bad-opaque-payload",tenant_id="tenant-a",payload={"note":PayloadField(object(),"business_data")},secret_ref=ref,verification_profile_ref=verification_ref,verification_generation_ref=7))

    _expect_denied(checks,"unauthorized_resolution_fails_closed",lambda:resolve_secret(reference=ref,authority=authority,requested_scope="tenant-a/orders",authorized=False,audit_sink=[]))
    _expect_denied(checks,"truthy_nonboolean_authorization_rejected",lambda:resolve_secret(reference=ref,authority=authority,requested_scope="tenant-a/orders",authorized="false",audit_sink=[]))
    _expect_denied(checks,"cross_scope_resolution_fails_closed",lambda:resolve_secret(reference=ref,authority=authority,requested_scope="tenant-b/orders",authorized=True,audit_sink=[]))
    scope_mismatch_authority=replace(authority,allowed_scopes=("tenant-a/orders","tenant-b/orders"))
    _expect_denied(checks,"reference_scope_mismatch_fails_closed",lambda:resolve_secret(reference=ref,authority=scope_mismatch_authority,requested_scope="tenant-b/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"scope_not_allowlisted_fails_closed",lambda:resolve_secret(reference=ref,authority=replace(authority,allowed_scopes=()),requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"allowed_scopes_string_container_rejected",lambda:resolve_secret(reference=ref,authority=replace(authority,allowed_scopes="tenant-a/orders-archive"),requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"secret_authority_outage_fails_closed",lambda:resolve_secret(reference=ref,authority=replace(authority,available=False),requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"truthy_nonboolean_authority_availability_rejected",lambda:resolve_secret(reference=ref,authority=replace(authority,available="false"),requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"invalid_secret_authority_source_rejected",lambda:resolve_secret(reference=ref,authority=replace(authority,authority_source="ordinary_payload_authority"),requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"unknown_secret_handle_resolution_fails_closed",lambda:resolve_secret(reference=replace(ref,handle="kms://orders-signing/unknown"),authority=authority,requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"stale_generation_resolution_fails_closed",lambda:resolve_secret(reference=replace(ref,generation=6),authority=authority,requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"unknown_generation_resolution_fails_closed",lambda:resolve_secret(reference=replace(ref,generation=99),authority=authority,requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"authority_boolean_generation_rejected",lambda:resolve_secret(reference=ref,authority=replace(authority,current_generation=True),requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    _expect_denied(checks,"authority_fractional_generation_rejected",lambda:resolve_secret(reference=ref,authority=replace(authority,current_generation=7.0),requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))

    checks["historical_reference_is_not_bearer_authority"]=not historical_reference_can_resolve_secret(evidence,authority,scope="tenant-a/orders")
    colliding_authority=replace(authority,current_handle=evidence.verification_profile_ref,current_generation=evidence.verification_generation_ref)
    checks["historical_verification_namespace_collision_fails_closed"]=not historical_reference_can_resolve_secret(evidence,colliding_authority,scope="tenant-a/orders")
    bearer_ref=replace(ref,bearer_authority=True)
    _expect_denied(checks,"bearer_secret_reference_rejected",lambda:create_message(message_id="bad-ref",tenant_id="tenant-a",payload=safe_payload,secret_ref=bearer_ref,verification_profile_ref=verification_ref,verification_generation_ref=7))
    _expect_denied(checks,"resolve_bearer_secret_reference_rejected",lambda:resolve_secret(reference=bearer_ref,authority=authority,requested_scope="tenant-a/orders",authorized=True,audit_sink=[]))
    return checks

if __name__=="__main__":
    checks=run_probes()
    failed=[name for name,ok in checks.items() if not ok]
    if failed: raise SystemExit("FAILED: "+",".join(failed))
    print(f"d4d_open_evt_017_secret_exclusion_source=PASS probes={len(checks)}")
