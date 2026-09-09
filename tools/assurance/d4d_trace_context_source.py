#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import re

TRACEPARENT_RE = re.compile(r"^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")
TRACESTATE_KEY_RE = re.compile(r"^[a-z][a-z0-9_\-*/]{0,31}$")
TRACESTATE_VALUE_RE = re.compile(r"^[\x21-\x2b\x2d-\x3c\x3e-\x7e](?:[\x20-\x2b\x2d-\x3c\x3e-\x7e]{0,254}[\x21-\x2b\x2d-\x3c\x3e-\x7e])?$")
MAX_TRACESTATE_LEN = 512
MAX_TRACESTATE_MEMBERS = 32
MAX_ATTRS = 16
MAX_ATTR_KEY = 64
MAX_ATTR_VALUE = 128
MAX_SCOPE_TENANT_ID_CHARS = 128
MAX_PROPAGATION_CONTEXT_FIELD_CHARS = 64

ATTRIBUTE_PROFILES = {
    "component": {
        "allowed_values": {"producer", "consumer", "dispatcher", "broker_adapter"},
        "allowed_sources": {"producer", "consumer", "dispatcher", "broker_adapter"},
        "allowed_trust_levels": {"authenticated_internal"},
        "allowed_classifications": {"internal"},
        "allowed_hop_scopes": {"local_async_boundary"},
        "may_leave_jlmirror": False,
    },
    "phase": {
        "allowed_values": {"receive", "validate", "dispatch", "ack", "retry"},
        "allowed_sources": {"producer", "consumer", "dispatcher", "broker_adapter"},
        "allowed_trust_levels": {"authenticated_internal"},
        "allowed_classifications": {"internal"},
        "allowed_hop_scopes": {"local_async_boundary"},
        "may_leave_jlmirror": False,
    },
}


@dataclass(frozen=True)
class BusinessEnvelope:
    tenant_id: str
    message_id: str
    idempotency_key: str
    ordering_key: str
    payload: str
    delivery_semantics: str


@dataclass(frozen=True)
class PropagationContext:
    source: str
    trust_level: str
    classification: str
    hop_scope: str
    leaving_jlmirror: bool = False


@dataclass(frozen=True)
class TraceContext:
    traceparent: str | None
    tracestate: str | None
    attributes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class TenantScopeProof:
    tenant_id: str
    trace_id: str
    parent_id: str
    mac_hex: str


@dataclass(frozen=True)
class ObservedMessage:
    envelope: BusinessEnvelope
    trace: TraceContext
    trace_context_disposition: str = "accepted"
    scope_proof: TenantScopeProof | None = None


class TraceContextRejected(Exception):
    pass


def _valid_traceparent(value: object) -> bool:
    if not isinstance(value, str) or not TRACEPARENT_RE.fullmatch(value):
        return False
    version, trace_id, parent_id, _flags = value.split("-")
    return version == "00" and trace_id != "0" * 32 and parent_id != "0" * 16


def _utf8_encodable(value: str) -> bool:
    try:
        value.encode("utf-8")
        return True
    except UnicodeEncodeError:
        return False


def _valid_scope_tenant_id(value: object) -> bool:
    return isinstance(value, str) and 0 < len(value) <= MAX_SCOPE_TENANT_ID_CHARS and _utf8_encodable(value)


def _valid_trace_id(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value) is not None and value != "0" * 32


def _valid_parent_id(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{16}", value) is not None and value != "0" * 16


def _trace_id(traceparent: str) -> str:
    return traceparent.split("-")[1]


def _parent_id(traceparent: str) -> str:
    return traceparent.split("-")[2]


def _bounded_tracestate(value: object | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TraceContextRejected("tracestate must be a string")
    if len(value) > MAX_TRACESTATE_LEN or "\n" in value or "\r" in value:
        raise TraceContextRejected("tracestate out of bounds")
    members = value.split(",")
    if not members or len(members) > MAX_TRACESTATE_MEMBERS:
        raise TraceContextRejected("tracestate member count invalid")
    seen: set[str] = set()
    canonical: list[str] = []
    for member in members:
        if member.count("=") != 1:
            raise TraceContextRejected("malformed tracestate member")
        key, member_value = member.split("=", 1)
        if not TRACESTATE_KEY_RE.fullmatch(key) or not TRACESTATE_VALUE_RE.fullmatch(member_value):
            raise TraceContextRejected("non-canonical tracestate member")
        if key in seen:
            raise TraceContextRejected("duplicate tracestate key")
        seen.add(key)
        canonical.append(f"{key}={member_value}")
    return ",".join(canonical)


def _validate_propagation_context(context: object) -> PropagationContext:
    if not isinstance(context, PropagationContext):
        raise TraceContextRejected("propagation context object invalid")
    string_fields = (context.source, context.trust_level, context.classification, context.hop_scope)
    if any(not isinstance(field, str) or not field or len(field) > MAX_PROPAGATION_CONTEXT_FIELD_CHARS for field in string_fields):
        raise TraceContextRejected("propagation context string field invalid or out of bounds")
    if not isinstance(context.leaving_jlmirror, bool):
        raise TraceContextRejected("propagation context egress flag invalid")
    return context


def _validate_attribute_profile(key: str, value: str, context: PropagationContext) -> None:
    context = _validate_propagation_context(context)
    profile = ATTRIBUTE_PROFILES.get(key)
    if profile is None:
        raise TraceContextRejected("trace attribute is not allowlisted")
    if value not in profile["allowed_values"]:
        raise TraceContextRejected("trace attribute value outside semantic profile")
    if context.source not in profile["allowed_sources"]:
        raise TraceContextRejected("trace attribute source not allowed")
    if context.trust_level not in profile["allowed_trust_levels"]:
        raise TraceContextRejected("trace attribute trust level not allowed")
    if context.classification not in profile["allowed_classifications"]:
        raise TraceContextRejected("trace attribute classification not allowed")
    if context.hop_scope not in profile["allowed_hop_scopes"]:
        raise TraceContextRejected("trace attribute hop scope not allowed")
    if context.leaving_jlmirror and not profile["may_leave_jlmirror"]:
        raise TraceContextRejected("trace attribute may not leave JLMIRROR")
    if key == "component" and value != context.source:
        raise TraceContextRejected("component telemetry cannot impersonate another source")


def _validate_trace_context_object(trace: object, propagation_context: object | None = None) -> TraceContext:
    if not isinstance(trace, TraceContext):
        raise TraceContextRejected("trace context object invalid")
    if trace.traceparent is not None and not _valid_traceparent(trace.traceparent):
        raise TraceContextRejected("trace context traceparent invalid")
    if trace.tracestate is not None:
        if trace.traceparent is None:
            raise TraceContextRejected("trace context tracestate requires traceparent")
        if _bounded_tracestate(trace.tracestate) != trace.tracestate:
            raise TraceContextRejected("trace context tracestate non-canonical")
    if not isinstance(trace.attributes, tuple) or len(trace.attributes) > MAX_ATTRS:
        raise TraceContextRejected("trace context attributes container invalid")
    context: PropagationContext | None = None
    if trace.attributes:
        context = _validate_propagation_context(propagation_context)
    seen_keys: set[str] = set()
    for item in trace.attributes:
        if not isinstance(item, tuple) or len(item) != 2:
            raise TraceContextRejected("trace context attribute entry invalid")
        key, value = item
        if not isinstance(key, str) or not isinstance(value, str) or not key or len(key) > MAX_ATTR_KEY or len(value) > MAX_ATTR_VALUE:
            raise TraceContextRejected("trace context attribute out of bounds")
        if key in seen_keys:
            raise TraceContextRejected("duplicate trace context attribute")
        seen_keys.add(key)
        assert context is not None
        _validate_attribute_profile(key, value, context)
    if trace.attributes != tuple(sorted(trace.attributes)):
        raise TraceContextRejected("trace context attributes are not canonical")
    return trace


def _redact_attributes(attributes: object, context: PropagationContext | None) -> tuple[tuple[str, str], ...]:
    if not isinstance(attributes, dict):
        raise TraceContextRejected("trace attributes must be an object")
    if len(attributes) > MAX_ATTRS:
        raise TraceContextRejected("too many trace attributes")
    if attributes:
        context = _validate_propagation_context(context)
    clean: list[tuple[str, str]] = []
    for key, value in attributes.items():
        if not isinstance(key, str) or not isinstance(value, str) or not key or len(key) > MAX_ATTR_KEY or len(value) > MAX_ATTR_VALUE:
            raise TraceContextRejected("trace attribute out of bounds")
        assert context is not None
        _validate_attribute_profile(key, value, context)
        clean.append((key, value))
    return tuple(sorted(clean))


def normalize_trace_context(traceparent: object | None, tracestate: object | None, attributes: object | None = None, *, propagation_context: PropagationContext | None = None) -> TraceContext:
    attrs = _redact_attributes({} if attributes is None else attributes, propagation_context)
    if traceparent is None:
        if tracestate is not None:
            raise TraceContextRejected("tracestate requires traceparent")
        return TraceContext(None, None, attrs)
    if not _valid_traceparent(traceparent):
        raise TraceContextRejected("malformed traceparent")
    return TraceContext(traceparent, _bounded_tracestate(tracestate), attrs)


def _tenant_scoped_hex(tenant_id: str, label: str, value: str, length: int) -> str:
    if not _valid_scope_tenant_id(tenant_id):
        raise TraceContextRejected("tenant scope identity out of bounds or non-canonical")
    digest = hashlib.sha256(f"jlmirror-trace-scope-v4\0{tenant_id}\0{label}\0{value}".encode("utf-8")).hexdigest()[:length]
    return ("1" + digest[1:]) if set(digest) == {"0"} else digest


def _scope_trace_to_tenant(trace: object, tenant_id: object, propagation_context: object | None = None) -> TraceContext:
    trace = _validate_trace_context_object(trace, propagation_context)
    if not _valid_scope_tenant_id(tenant_id):
        raise TraceContextRejected("tenant scope identity invalid, non-canonical, or out of bounds")
    if not trace.traceparent:
        return trace
    assert isinstance(tenant_id, str)
    version, trace_id, parent_id, flags = trace.traceparent.split("-")
    return TraceContext(
        f"{version}-{_tenant_scoped_hex(tenant_id, 'trace-id', trace_id, 32)}-{_tenant_scoped_hex(tenant_id, 'parent-id', parent_id, 16)}-{flags}",
        None,
        trace.attributes,
    )


def _scope_authenticated_parent_to_tenant(trace: TraceContext, tenant_id: str, proof: TenantScopeProof) -> TraceContext:
    if not trace.traceparent or not _valid_scope_tenant_id(tenant_id):
        raise TraceContextRejected("authenticated tenant trace cannot scope malformed parent identity")
    version, trace_id, incoming_parent_id, flags = trace.traceparent.split("-")
    exported_parent_id = incoming_parent_id if incoming_parent_id == proof.parent_id else _tenant_scoped_hex(tenant_id, "parent-id", incoming_parent_id, 16)
    return TraceContext(f"{version}-{trace_id}-{exported_parent_id}-{flags}", None, trace.attributes)


class TenantScopeAuthority:
    def __init__(self, verification_key: bytes):
        if not isinstance(verification_key, bytes) or len(verification_key) < 32:
            raise ValueError("tenant scope authority requires at least 256 bits")
        self._key = verification_key

    @staticmethod
    def _payload(tenant_id: str, trace_id: str, parent_id: str) -> bytes:
        if not _valid_scope_tenant_id(tenant_id) or not _valid_trace_id(trace_id) or not _valid_parent_id(parent_id):
            raise TraceContextRejected("tenant scope proof identity invalid, non-canonical, or out of bounds")
        return f"jlmirror-tenant-trace-export-v4\0{tenant_id}\0{trace_id}\0{parent_id}".encode("utf-8")

    def _attest_scoped_traceparent(self, tenant_id: str, traceparent: str) -> TenantScopeProof:
        if not _valid_scope_tenant_id(tenant_id) or not _valid_traceparent(traceparent):
            raise TraceContextRejected("cannot attest malformed tenant-scoped traceparent")
        trace_id = _trace_id(traceparent)
        parent_id = _parent_id(traceparent)
        mac_hex = hmac.new(self._key, self._payload(tenant_id, trace_id, parent_id), hashlib.sha256).hexdigest()
        return TenantScopeProof(tenant_id, trace_id, parent_id, mac_hex)

    def scope_and_issue(self, tenant_id: object, trace: object, *, propagation_context: object | None = None) -> tuple[TraceContext, TenantScopeProof | None]:
        scoped = _scope_trace_to_tenant(trace, tenant_id, propagation_context)
        if not scoped.traceparent:
            return scoped, None
        assert isinstance(tenant_id, str)
        return scoped, self._attest_scoped_traceparent(tenant_id, scoped.traceparent)

    def verifies(self, proof: object, traceparent: object) -> bool:
        if not isinstance(proof, TenantScopeProof) or not _valid_traceparent(traceparent):
            return False
        if not _valid_scope_tenant_id(proof.tenant_id) or not _valid_trace_id(proof.trace_id) or not _valid_parent_id(proof.parent_id):
            return False
        if not isinstance(proof.mac_hex, str) or re.fullmatch(r"[0-9a-f]{64}", proof.mac_hex) is None:
            return False
        assert isinstance(traceparent, str)
        if proof.trace_id != _trace_id(traceparent):
            return False
        expected = hmac.new(self._key, self._payload(proof.tenant_id, proof.trace_id, proof.parent_id), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, proof.mac_hex)


def process_message(envelope: BusinessEnvelope, *, traceparent: object | None, tracestate: object | None = None, attributes: object | None = None, propagation_context: PropagationContext | None = None, scope_proof: object | None = None, scope_authority: TenantScopeAuthority | None = None) -> ObservedMessage:
    try:
        normalized = normalize_trace_context(traceparent, tracestate, attributes, propagation_context=propagation_context)
        if scope_proof is not None:
            if not isinstance(scope_authority, TenantScopeAuthority):
                raise TraceContextRejected("tenant scope proof requires verifier authority")
            if normalized.tracestate is not None:
                raise TraceContextRejected("attested tenant-scoped propagation cannot carry tracestate")
            if not normalized.traceparent or not scope_authority.verifies(scope_proof, normalized.traceparent):
                raise TraceContextRejected("tenant scope proof invalid")
            assert isinstance(scope_proof, TenantScopeProof)
            if scope_proof.tenant_id == envelope.tenant_id:
                trace = _scope_authenticated_parent_to_tenant(normalized, envelope.tenant_id, scope_proof)
                assert trace.traceparent is not None
                next_proof = scope_authority._attest_scoped_traceparent(envelope.tenant_id, trace.traceparent)
                disposition = "accepted_authenticated_tenant_scope"
            else:
                trace, next_proof = scope_authority.scope_and_issue(envelope.tenant_id, normalized, propagation_context=propagation_context)
                disposition = "accepted_rescoped_tenant_boundary"
        elif isinstance(scope_authority, TenantScopeAuthority):
            trace, next_proof = scope_authority.scope_and_issue(envelope.tenant_id, normalized, propagation_context=propagation_context)
            disposition = "accepted_tenant_scoped"
        else:
            trace = _scope_trace_to_tenant(normalized, envelope.tenant_id, propagation_context)
            next_proof = None
            disposition = "accepted_tenant_scoped"
    except TraceContextRejected:
        trace = TraceContext(None, None, ())
        next_proof = None
        disposition = "discarded_invalid_observability_context"
    return ObservedMessage(envelope, trace, disposition, next_proof)


def business_semantics(observed: ObservedMessage) -> tuple[str, str, str, str, str, str]:
    e = observed.envelope
    return (e.tenant_id, e.message_id, e.idempotency_key, e.ordering_key, e.payload, e.delivery_semantics)


def can_correlate(left: ObservedMessage, right: ObservedMessage) -> bool:
    return bool(left.envelope.tenant_id == right.envelope.tenant_id and left.trace.traceparent and right.trace.traceparent and _trace_id(left.trace.traceparent) == _trace_id(right.trace.traceparent))


def _rejected(callable_) -> bool:
    try:
        callable_()
        return False
    except TraceContextRejected:
        return True


def _isolated_from_business(envelope: BusinessEnvelope, observed: ObservedMessage) -> bool:
    return observed.envelope == envelope and business_semantics(observed) == (
        envelope.tenant_id, envelope.message_id, envelope.idempotency_key,
        envelope.ordering_key, envelope.payload, envelope.delivery_semantics,
    ) and observed.trace == TraceContext(None, None, ()) and observed.trace_context_disposition == "discarded_invalid_observability_context"


def run_probes() -> dict[str, bool]:
    env = BusinessEnvelope("tenant-a", "msg-1", "idem-1", "order-1", "payload-v1", "at_least_once")
    valid = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    future_version = "01-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    same_trace_other_parent = "00-4bf92f3577b34da6a3ce929d0e0e4736-1111111111111111-01"
    consumer_context = PropagationContext("consumer", "authenticated_internal", "internal", "local_async_boundary", False)
    scope_authority = TenantScopeAuthority(b"d4d-open-evt-018-test-scope-key-0001")
    wrong_scope_authority = TenantScopeAuthority(b"d4d-open-evt-018-wrong-scope-key-01")

    observed = process_message(env, traceparent=valid, tracestate="vendor=value", attributes={"component": "consumer", "phase": "receive"}, propagation_context=consumer_context, scope_authority=scope_authority)
    no_trace = process_message(env, traceparent=None)
    attrs = dict(observed.trace.attributes)
    strict_valid = normalize_trace_context(valid, "vendor=value", {"component": "consumer", "phase": "receive"}, propagation_context=consumer_context)

    checks: dict[str, bool] = {
        "trace_context_is_observability_only": business_semantics(observed) == business_semantics(no_trace),
        "trace_context_not_tenant_authority": observed.envelope.tenant_id == "tenant-a",
        "trace_context_not_idempotency_authority": observed.envelope.idempotency_key == "idem-1",
        "trace_context_not_ordering_authority": observed.envelope.ordering_key == "order-1",
        "trace_context_not_message_identity_authority": observed.envelope.message_id == "msg-1",
        "trace_context_not_delivery_authority": observed.envelope.delivery_semantics == "at_least_once",
        "valid_traceparent_accepted": strict_valid.traceparent == valid and observed.trace_context_disposition == "accepted_tenant_scoped",
        "accepted_traceparent_is_tenant_scoped": observed.trace.traceparent is not None and observed.trace.traceparent != valid and _valid_traceparent(observed.trace.traceparent),
        "bounded_canonical_tracestate_validated_on_ingress": strict_valid.tracestate == "vendor=value",
        "observable_export_discards_tracestate": observed.trace.tracestate is None,
        "allowlisted_trace_attributes_preserved": attrs == {"component": "consumer", "phase": "receive"},
        "missing_trace_context_preserves_business_and_delivery_semantics": business_semantics(no_trace) == business_semantics(observed),
    }

    malformed_cases: list[object] = [
        "zz-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        "00-00000000000000000000000000000000-00f067aa0ba902b7-01",
        "00-4bf92f3577b34da6a3ce929d0e0e4736-0000000000000000-01",
        "ff-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        42,
    ]
    for idx, candidate in enumerate(malformed_cases, start=1):
        checks[f"malformed_traceparent_{idx}_rejected"] = _rejected(lambda candidate=candidate: normalize_trace_context(candidate, None))
    checks["unsupported_traceparent_version_rejected"] = _rejected(lambda: normalize_trace_context(future_version, None))
    checks["orphan_tracestate_rejected"] = _rejected(lambda: normalize_trace_context(None, "vendor=value"))
    checks["non_string_tracestate_rejected"] = _rejected(lambda: normalize_trace_context(valid, 42))
    checks["oversized_tracestate_rejected"] = _rejected(lambda: normalize_trace_context(valid, "x" * (MAX_TRACESTATE_LEN + 1)))
    checks["malformed_tracestate_member_rejected"] = _rejected(lambda: normalize_trace_context(valid, "not valid, ="))
    checks["duplicate_tracestate_key_rejected"] = _rejected(lambda: normalize_trace_context(valid, "vendor=a,vendor=b"))
    too_many_members = ",".join(f"k{i}=v" for i in range(MAX_TRACESTATE_MEMBERS + 1))
    checks["excess_tracestate_members_rejected"] = _rejected(lambda: normalize_trace_context(valid, too_many_members))

    checks["excess_trace_attributes_rejected"] = _rejected(lambda: normalize_trace_context(valid, None, {f"k{i}": "v" for i in range(MAX_ATTRS + 1)}, propagation_context=consumer_context))
    checks["unknown_trace_attribute_rejected"] = _rejected(lambda: normalize_trace_context(valid, None, {"unknown": "benign"}, propagation_context=consumer_context))
    checks["sensitive_value_under_allowlisted_key_rejected"] = _rejected(lambda: normalize_trace_context(valid, None, {"component": "Bearer super-secret"}, propagation_context=consumer_context))
    checks["non_string_trace_attributes_rejected"] = _rejected(lambda: normalize_trace_context(valid, None, 42, propagation_context=consumer_context))
    checks["attribute_context_required"] = _rejected(lambda: normalize_trace_context(valid, None, {"component": "consumer"}))
    checks["component_source_impersonation_rejected"] = _rejected(lambda: normalize_trace_context(valid, None, {"component": "producer"}, propagation_context=consumer_context))
    checks["untrusted_attribute_source_rejected"] = _rejected(lambda: normalize_trace_context(valid, None, {"component": "consumer"}, propagation_context=PropagationContext("consumer", "untrusted_external", "internal", "local_async_boundary", False)))
    checks["protected_classification_attribute_rejected"] = _rejected(lambda: normalize_trace_context(valid, None, {"component": "consumer"}, propagation_context=PropagationContext("consumer", "authenticated_internal", "restricted", "local_async_boundary", False)))
    checks["wrong_hop_scope_attribute_rejected"] = _rejected(lambda: normalize_trace_context(valid, None, {"component": "consumer"}, propagation_context=PropagationContext("consumer", "authenticated_internal", "internal", "provider_egress", False)))
    checks["egress_attribute_rejected"] = _rejected(lambda: normalize_trace_context(valid, None, {"component": "consumer"}, propagation_context=PropagationContext("consumer", "authenticated_internal", "internal", "local_async_boundary", True)))

    malformed_traceparent_observed = process_message(env, traceparent=42)
    malformed_tracestate_observed = process_message(env, traceparent=valid, tracestate="not valid, =")
    malformed_attribute_observed = process_message(env, traceparent=valid, attributes={"component": "Bearer super-secret"}, propagation_context=consumer_context)
    malformed_contexts = {
        "source": PropagationContext(["consumer"], "authenticated_internal", "internal", "local_async_boundary", False),  # type: ignore[arg-type]
        "trust_level": PropagationContext("consumer", ["authenticated_internal"], "internal", "local_async_boundary", False),  # type: ignore[arg-type]
        "classification": PropagationContext("consumer", "authenticated_internal", ["internal"], "local_async_boundary", False),  # type: ignore[arg-type]
        "hop_scope": PropagationContext("consumer", "authenticated_internal", "internal", ["local_async_boundary"], False),  # type: ignore[arg-type]
        "leaving_jlmirror": PropagationContext("consumer", "authenticated_internal", "internal", "local_async_boundary", ["false"]),  # type: ignore[arg-type]
    }
    checks["malformed_traceparent_does_not_abort_business_processing"] = _isolated_from_business(env, malformed_traceparent_observed)
    checks["malformed_tracestate_does_not_abort_business_processing"] = _isolated_from_business(env, malformed_tracestate_observed)
    checks["malformed_attribute_does_not_abort_business_processing"] = _isolated_from_business(env, malformed_attribute_observed)
    for field, malformed_context in malformed_contexts.items():
        candidate = process_message(env, traceparent=valid, attributes={"component": "consumer"}, propagation_context=malformed_context)
        checks[f"malformed_propagation_context_{field}_does_not_abort_business_processing"] = _isolated_from_business(env, candidate)

    oversized_value = "x" * (MAX_PROPAGATION_CONTEXT_FIELD_CHARS + 1)
    oversized_contexts = {
        "source": PropagationContext(oversized_value, "authenticated_internal", "internal", "local_async_boundary", False),
        "trust_level": PropagationContext("consumer", oversized_value, "internal", "local_async_boundary", False),
        "classification": PropagationContext("consumer", "authenticated_internal", oversized_value, "local_async_boundary", False),
        "hop_scope": PropagationContext("consumer", "authenticated_internal", "internal", oversized_value, False),
    }
    for field, oversized_context in oversized_contexts.items():
        candidate = process_message(env, traceparent=valid, attributes={"component": "consumer"}, propagation_context=oversized_context)
        checks[f"oversized_propagation_context_{field}_does_not_abort_business_processing"] = _isolated_from_business(env, candidate)

    tenant_a_2 = process_message(BusinessEnvelope("tenant-a", "msg-2", "idem-2", "order-2", "payload-v2", "at_least_once"), traceparent=same_trace_other_parent, scope_authority=scope_authority)
    tenant_b = process_message(BusinessEnvelope("tenant-b", "msg-3", "idem-3", "order-3", "payload-v3", "at_least_once"), traceparent=same_trace_other_parent, scope_authority=scope_authority)
    tenant_a_same_input = process_message(BusinessEnvelope("tenant-a", "msg-4", "idem-4", "order-4", "payload-v4", "at_least_once"), traceparent=valid, tracestate="vendor=global-correlation-123", scope_authority=scope_authority)
    tenant_b_same_input = process_message(BusinessEnvelope("tenant-b", "msg-5", "idem-5", "order-5", "payload-v5", "at_least_once"), traceparent=valid, tracestate="vendor=global-correlation-123", scope_authority=scope_authority)
    assert observed.scope_proof is not None and observed.trace.traceparent is not None
    second_same_tenant_hop = process_message(BusinessEnvelope("tenant-a", "msg-6", "idem-6", "order-6", "payload-v6", "at_least_once"), traceparent=observed.trace.traceparent, scope_proof=observed.scope_proof, scope_authority=scope_authority)
    cross_tenant_from_scoped = process_message(BusinessEnvelope("tenant-b", "msg-7", "idem-7", "order-7", "payload-v7", "at_least_once"), traceparent=observed.trace.traceparent, scope_proof=observed.scope_proof, scope_authority=scope_authority)
    raw_replayed_same_tenant = process_message(BusinessEnvelope("tenant-a", "msg-8", "idem-8", "order-8", "payload-v8", "at_least_once"), traceparent=observed.trace.traceparent, scope_authority=scope_authority)
    _wrong_scoped, forged_proof = wrong_scope_authority.scope_and_issue("tenant-a", normalize_trace_context(observed.trace.traceparent, None))
    assert forged_proof is not None
    forged_scope = process_message(BusinessEnvelope("tenant-a", "msg-9", "idem-9", "order-9", "payload-v9", "at_least_once"), traceparent=observed.trace.traceparent, scope_proof=forged_proof, scope_authority=scope_authority)
    collision_a = process_message(BusinessEnvelope("tenant-27417", "msg-10", "idem-10", "order-10", "payload-v10", "at_least_once"), traceparent=valid, scope_authority=scope_authority)
    assert collision_a.scope_proof is not None and collision_a.trace.traceparent is not None
    collision_b = process_message(BusinessEnvelope("tenant-33720", "msg-11", "idem-11", "order-11", "payload-v11", "at_least_once"), traceparent=collision_a.trace.traceparent, scope_proof=collision_a.scope_proof, scope_authority=scope_authority)
    direct_scoped, direct_proof = scope_authority.scope_and_issue("tenant-a", normalize_trace_context(valid, None))

    version, scoped_trace_id, _old_parent_id, flags = observed.trace.traceparent.split("-")
    raw_child_parent = "2222222222222222"
    child_traceparent = f"{version}-{scoped_trace_id}-{raw_child_parent}-{flags}"
    child_hop = process_message(BusinessEnvelope("tenant-a", "msg-12", "idem-12", "order-12", "payload-v12", "at_least_once"), traceparent=child_traceparent, scope_proof=observed.scope_proof, scope_authority=scope_authority)
    assert child_hop.scope_proof is not None and child_hop.trace.traceparent is not None
    child_forward = process_message(BusinessEnvelope("tenant-a", "msg-12b", "idem-12b", "order-12b", "payload-v12b", "at_least_once"), traceparent=child_hop.trace.traceparent, scope_proof=child_hop.scope_proof, scope_authority=scope_authority)

    tenant_b_base = process_message(BusinessEnvelope("tenant-b", "msg-13", "idem-13", "order-13", "payload-v13", "at_least_once"), traceparent=valid, scope_authority=scope_authority)
    assert tenant_b_base.scope_proof is not None and tenant_b_base.trace.traceparent is not None
    version_b, scoped_trace_id_b, _old_parent_id_b, flags_b = tenant_b_base.trace.traceparent.split("-")
    tenant_b_child_raw = f"{version_b}-{scoped_trace_id_b}-{raw_child_parent}-{flags_b}"
    tenant_b_child = process_message(BusinessEnvelope("tenant-b", "msg-14", "idem-14", "order-14", "payload-v14", "at_least_once"), traceparent=tenant_b_child_raw, scope_proof=tenant_b_base.scope_proof, scope_authority=scope_authority)

    proof_parent = observed.scope_proof.parent_id
    malformed_proofs = {
        "tenant_id": TenantScopeProof(["tenant-a"], scoped_trace_id, proof_parent, observed.scope_proof.mac_hex),  # type: ignore[arg-type]
        "trace_id": TenantScopeProof("tenant-a", [scoped_trace_id], proof_parent, observed.scope_proof.mac_hex),  # type: ignore[arg-type]
        "parent_id": TenantScopeProof("tenant-a", scoped_trace_id, [proof_parent], observed.scope_proof.mac_hex),  # type: ignore[arg-type]
        "mac_hex": TenantScopeProof("tenant-a", scoped_trace_id, proof_parent, 42),  # type: ignore[arg-type]
    }
    for field, malformed_proof in malformed_proofs.items():
        candidate = process_message(BusinessEnvelope("tenant-a", f"msg-proof-{field}", f"idem-proof-{field}", f"order-proof-{field}", "payload-proof", "at_least_once"), traceparent=observed.trace.traceparent, scope_proof=malformed_proof, scope_authority=scope_authority)
        checks[f"malformed_scope_proof_{field}_does_not_abort_business_processing"] = _isolated_from_business(candidate.envelope, candidate)
    oversized_proof = TenantScopeProof("t" * (MAX_SCOPE_TENANT_ID_CHARS + 1), scoped_trace_id, proof_parent, observed.scope_proof.mac_hex)
    oversized_proof_observed = process_message(BusinessEnvelope("tenant-a", "msg-proof-oversized", "idem-proof-oversized", "order-proof-oversized", "payload-proof", "at_least_once"), traceparent=observed.trace.traceparent, scope_proof=oversized_proof, scope_authority=scope_authority)
    checks["oversized_scope_proof_tenant_id_does_not_abort_business_processing"] = _isolated_from_business(oversized_proof_observed.envelope, oversized_proof_observed)
    surrogate_proof = TenantScopeProof("\ud800", scoped_trace_id, proof_parent, observed.scope_proof.mac_hex)
    surrogate_proof_observed = process_message(BusinessEnvelope("tenant-a", "msg-proof-surrogate", "idem-proof-surrogate", "order-proof-surrogate", "payload-proof", "at_least_once"), traceparent=observed.trace.traceparent, scope_proof=surrogate_proof, scope_authority=scope_authority)
    checks["non_utf8_scope_proof_tenant_id_does_not_abort_business_processing"] = _isolated_from_business(surrogate_proof_observed.envelope, surrogate_proof_observed)

    malformed_scope_inputs = [
        ([], normalize_trace_context(valid, None), None),
        ("tenant-a", object(), None),
        ("tenant-a", TraceContext(42, None, ()), None),  # type: ignore[arg-type]
        ("tenant-a", TraceContext(valid, None, [["component", "consumer"]]), None),  # type: ignore[arg-type]
    ]
    checks["scope_and_issue_runtime_boundary_fail_closed"] = all(
        _rejected(lambda tenant_id=tenant_id, trace=trace, context=context: scope_authority.scope_and_issue(tenant_id, trace, propagation_context=context))
        for tenant_id, trace, context in malformed_scope_inputs
    )
    checks["scope_and_issue_rejects_oversized_tenant_id_before_hashing"] = _rejected(lambda: scope_authority.scope_and_issue("t" * (MAX_SCOPE_TENANT_ID_CHARS + 1), normalize_trace_context(valid, None)))
    checks["scope_and_issue_rejects_non_utf8_tenant_id_before_encoding"] = _rejected(lambda: scope_authority.scope_and_issue("\ud800", normalize_trace_context(valid, None)))

    direct_allowed = TraceContext(valid, None, (("component", "consumer"),))
    direct_unknown = TraceContext(valid, None, (("authorization", "Bearer secret"),))
    direct_sensitive = TraceContext(valid, None, (("component", "Bearer secret"),))
    direct_impersonated = TraceContext(valid, None, (("component", "producer"),))
    direct_duplicate = TraceContext(valid, None, (("phase", "receive"), ("phase", "validate")))
    direct_noncanonical_order = TraceContext(valid, None, (("phase", "receive"), ("component", "consumer")))
    checks["scope_and_issue_requires_context_for_attributes"] = _rejected(lambda: scope_authority.scope_and_issue("tenant-a", direct_allowed))
    checks["scope_and_issue_rejects_unallowlisted_attributes"] = _rejected(lambda: scope_authority.scope_and_issue("tenant-a", direct_unknown, propagation_context=consumer_context))
    checks["scope_and_issue_rejects_sensitive_allowlisted_value"] = _rejected(lambda: scope_authority.scope_and_issue("tenant-a", direct_sensitive, propagation_context=consumer_context))
    checks["scope_and_issue_rejects_component_source_impersonation"] = _rejected(lambda: scope_authority.scope_and_issue("tenant-a", direct_impersonated, propagation_context=consumer_context))
    checks["scope_and_issue_rejects_untrusted_attribute_context"] = _rejected(lambda: scope_authority.scope_and_issue("tenant-a", direct_allowed, propagation_context=PropagationContext("consumer", "untrusted_external", "internal", "local_async_boundary", False)))
    checks["scope_and_issue_rejects_duplicate_attribute_keys"] = _rejected(lambda: scope_authority.scope_and_issue("tenant-a", direct_duplicate, propagation_context=consumer_context))
    checks["scope_and_issue_rejects_noncanonical_attribute_order"] = _rejected(lambda: scope_authority.scope_and_issue("tenant-a", direct_noncanonical_order, propagation_context=consumer_context))

    checks["same_tenant_trace_correlation_allowed"] = can_correlate(observed, tenant_a_2)
    checks["cross_tenant_trace_correlation_blocked"] = not can_correlate(observed, tenant_b)
    checks["same_input_trace_id_is_stable_within_tenant"] = tenant_a_same_input.trace.traceparent is not None and _trace_id(observed.trace.traceparent) == _trace_id(tenant_a_same_input.trace.traceparent)
    checks["same_input_trace_id_is_different_across_tenants"] = tenant_b_same_input.trace.traceparent is not None and _trace_id(observed.trace.traceparent) != _trace_id(tenant_b_same_input.trace.traceparent)
    checks["copied_tracestate_is_not_exported_across_tenants"] = tenant_a_same_input.trace.tracestate is None and tenant_b_same_input.trace.tracestate is None
    checks["authenticated_scope_preserves_same_tenant_multi_hop_trace"] = second_same_tenant_hop.trace.traceparent is not None and _trace_id(second_same_tenant_hop.trace.traceparent) == _trace_id(observed.trace.traceparent) and second_same_tenant_hop.trace_context_disposition == "accepted_authenticated_tenant_scope" and can_correlate(observed, second_same_tenant_hop)
    checks["authenticated_exact_context_preserves_parent_id_without_rescoping"] = second_same_tenant_hop.trace.traceparent == observed.trace.traceparent and second_same_tenant_hop.scope_proof == observed.scope_proof
    checks["authenticated_scope_is_rescoped_at_different_tenant_boundary"] = cross_tenant_from_scoped.trace.traceparent is not None and cross_tenant_from_scoped.trace.traceparent != observed.trace.traceparent and cross_tenant_from_scoped.trace_context_disposition == "accepted_rescoped_tenant_boundary" and not can_correlate(observed, cross_tenant_from_scoped)
    checks["raw_scoped_bytes_are_not_scope_authority"] = raw_replayed_same_tenant.trace.traceparent is not None and raw_replayed_same_tenant.trace.traceparent != observed.trace.traceparent
    checks["forged_scope_proof_is_rejected_without_business_abort"] = _isolated_from_business(forged_scope.envelope, forged_scope)
    checks["known_short_marker_collision_cannot_bypass_tenant_rescoping"] = collision_b.trace.traceparent is not None and collision_b.trace.traceparent != collision_a.trace.traceparent and collision_b.trace_context_disposition == "accepted_rescoped_tenant_boundary"
    checks["scope_proof_issuance_scopes_before_attesting"] = direct_scoped.traceparent is not None and direct_scoped.traceparent != valid and direct_proof is not None and direct_proof.trace_id == _trace_id(direct_scoped.traceparent) and direct_proof.parent_id == _parent_id(direct_scoped.traceparent) and direct_proof.tenant_id == "tenant-a" and scope_authority.verifies(direct_proof, direct_scoped.traceparent)
    checks["authenticated_trace_identity_allows_child_span_parent_change"] = child_hop.trace.traceparent is not None and _trace_id(child_hop.trace.traceparent) == scoped_trace_id and _parent_id(child_hop.trace.traceparent) != raw_child_parent and child_hop.trace_context_disposition == "accepted_authenticated_tenant_scope" and child_hop.scope_proof is not None and child_hop.scope_proof.trace_id == scoped_trace_id and child_hop.scope_proof.parent_id == _parent_id(child_hop.trace.traceparent) and scope_authority.verifies(child_hop.scope_proof, child_hop.trace.traceparent) and can_correlate(observed, child_hop)
    checks["authenticated_child_parent_id_is_tenant_scoped_before_export"] = child_hop.trace.traceparent is not None and _parent_id(child_hop.trace.traceparent) == _tenant_scoped_hex("tenant-a", "parent-id", raw_child_parent, 16)
    checks["same_child_parent_id_is_different_across_tenants"] = child_hop.trace.traceparent is not None and tenant_b_child.trace.traceparent is not None and _parent_id(child_hop.trace.traceparent) != _parent_id(tenant_b_child.trace.traceparent) and _parent_id(tenant_b_child.trace.traceparent) != raw_child_parent
    checks["authenticated_child_export_is_idempotent_on_forwarding"] = child_forward.trace.traceparent == child_hop.trace.traceparent and child_forward.scope_proof == child_hop.scope_proof and child_forward.trace_context_disposition == "accepted_authenticated_tenant_scope"

    altered_trace = process_message(env, traceparent=same_trace_other_parent, tracestate=None, scope_authority=scope_authority)
    checks["trace_change_does_not_change_business_or_delivery_semantics"] = business_semantics(altered_trace) == business_semantics(observed)
    return checks


if __name__ == "__main__":
    checks = run_probes()
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise SystemExit("FAILED: " + ",".join(failed))
    print(f"d4d_open_evt_018_trace_context_source=PASS probes={len(checks)}")
