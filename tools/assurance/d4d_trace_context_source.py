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
    traceparent: str
    mac_hex: str

class TenantScopeAuthority:
    def __init__(self, verification_key: bytes):
        if not isinstance(verification_key, bytes) or len(verification_key) < 32:
            raise ValueError("tenant scope authority requires at least 256 bits")
        self._key = verification_key

    @staticmethod
    def _payload(tenant_id: str, traceparent: str) -> bytes:
        return f"jlmirror-tenant-trace-scope-v1\0{tenant_id}\0{traceparent}".encode("utf-8")

    def issue(self, tenant_id: str, traceparent: str) -> TenantScopeProof:
        if not _valid_traceparent(traceparent):
            raise TraceContextRejected("cannot attest malformed traceparent")
        mac_hex = hmac.new(self._key, self._payload(tenant_id, traceparent), hashlib.sha256).hexdigest()
        return TenantScopeProof(tenant_id, traceparent, mac_hex)

    def verifies(self, proof: object, traceparent: str) -> bool:
        if not isinstance(proof, TenantScopeProof):
            return False
        if proof.traceparent != traceparent or not re.fullmatch(r"[0-9a-f]{64}", proof.mac_hex):
            return False
        expected = hmac.new(self._key, self._payload(proof.tenant_id, proof.traceparent), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, proof.mac_hex)

@dataclass(frozen=True)
class ObservedMessage:
    envelope: BusinessEnvelope
    trace: TraceContext
    trace_context_disposition: str = "accepted"

class TraceContextRejected(Exception):
    pass

def _valid_traceparent(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if not TRACEPARENT_RE.fullmatch(value):
        return False
    version, trace_id, parent_id, _flags = value.split("-")
    return version != "ff" and trace_id != "0" * 32 and parent_id != "0" * 16

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

def _validate_attribute_profile(key: str, value: str, context: PropagationContext) -> None:
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

def _redact_attributes(attributes: object, context: PropagationContext | None) -> tuple[tuple[str, str], ...]:
    if not isinstance(attributes, dict):
        raise TraceContextRejected("trace attributes must be an object")
    if len(attributes) > MAX_ATTRS:
        raise TraceContextRejected("too many trace attributes")
    if attributes and not isinstance(context, PropagationContext):
        raise TraceContextRejected("propagation context required for trace attributes")
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
    digest = hashlib.sha256(f"jlmirror-trace-scope-v2\0{tenant_id}\0{label}\0{value}".encode("utf-8")).hexdigest()[:length]
    if set(digest) == {"0"}:
        return "1" + digest[1:]
    return digest

def _scope_trace_to_tenant(trace: TraceContext, tenant_id: str) -> TraceContext:
    if not trace.traceparent:
        return trace
    version, trace_id, parent_id, flags = trace.traceparent.split("-")
    scoped_trace_id = _tenant_scoped_hex(tenant_id, "trace-id", trace_id, 32)
    scoped_parent_id = _tenant_scoped_hex(tenant_id, "parent-id", parent_id, 16)
    return TraceContext(
        f"{version}-{scoped_trace_id}-{scoped_parent_id}-{flags}",
        None,
        trace.attributes,
    )

def issue_tenant_scope_proof(observed: ObservedMessage, authority: TenantScopeAuthority) -> TenantScopeProof:
    if not observed.trace.traceparent or observed.trace_context_disposition not in {"accepted_tenant_scoped", "accepted_authenticated_tenant_scope", "accepted_rescoped_tenant_boundary"}:
        raise TraceContextRejected("only accepted tenant-scoped context may be attested")
    return authority.issue(observed.envelope.tenant_id, observed.trace.traceparent)

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
                trace = TraceContext(normalized.traceparent, None, normalized.attributes)
                disposition = "accepted_authenticated_tenant_scope"
            else:
                trace = _scope_trace_to_tenant(normalized, envelope.tenant_id)
                disposition = "accepted_rescoped_tenant_boundary"
        else:
            trace = _scope_trace_to_tenant(normalized, envelope.tenant_id)
            disposition = "accepted_tenant_scoped"
    except TraceContextRejected:
        trace = TraceContext(None, None, ())
        disposition = "discarded_invalid_observability_context"
    return ObservedMessage(envelope=envelope, trace=trace, trace_context_disposition=disposition)

def business_semantics(observed: ObservedMessage) -> tuple[str, str, str, str, str, str]:
    e = observed.envelope
    return (e.tenant_id, e.message_id, e.idempotency_key, e.ordering_key, e.payload, e.delivery_semantics)

def can_correlate(left: ObservedMessage, right: ObservedMessage) -> bool:
    if left.envelope.tenant_id != right.envelope.tenant_id:
        return False
    if not left.trace.traceparent or not right.trace.traceparent:
        return False
    return left.trace.traceparent.split("-")[1] == right.trace.traceparent.split("-")[1]

def _rejected(callable_) -> bool:
    try:
        callable_()
        return False
    except TraceContextRejected:
        return True

def _isolated_from_business(envelope: BusinessEnvelope, observed: ObservedMessage) -> bool:
    return (
        observed.envelope == envelope
        and business_semantics(observed) == (
            envelope.tenant_id,
            envelope.message_id,
            envelope.idempotency_key,
            envelope.ordering_key,
            envelope.payload,
            envelope.delivery_semantics,
        )
        and observed.trace == TraceContext(None, None, ())
        and observed.trace_context_disposition == "discarded_invalid_observability_context"
    )

def run_probes() -> dict[str, bool]:
    env = BusinessEnvelope("tenant-a", "msg-1", "idem-1", "order-1", "payload-v1", "at_least_once")
    valid = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    same_trace_other_parent = "00-4bf92f3577b34da6a3ce929d0e0e4736-1111111111111111-01"
    consumer_context = PropagationContext("consumer", "authenticated_internal", "internal", "local_async_boundary", False)
    scope_authority = TenantScopeAuthority(b"d4d-open-evt-018-test-scope-key-0001")
    wrong_scope_authority = TenantScopeAuthority(b"d4d-open-evt-018-wrong-scope-key-01")

    observed = process_message(env, traceparent=valid, tracestate="vendor=value", attributes={"component": "consumer", "phase": "receive"}, propagation_context=consumer_context)
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
    checks["malformed_traceparent_does_not_abort_business_processing"] = _isolated_from_business(env, malformed_traceparent_observed)
    checks["malformed_tracestate_does_not_abort_business_processing"] = _isolated_from_business(env, malformed_tracestate_observed)
    checks["malformed_attribute_does_not_abort_business_processing"] = _isolated_from_business(env, malformed_attribute_observed)

    tenant_a_2 = process_message(BusinessEnvelope("tenant-a", "msg-2", "idem-2", "order-2", "payload-v2", "at_least_once"), traceparent=same_trace_other_parent)
    tenant_b = process_message(BusinessEnvelope("tenant-b", "msg-3", "idem-3", "order-3", "payload-v3", "at_least_once"), traceparent=same_trace_other_parent)
    tenant_a_same_input = process_message(BusinessEnvelope("tenant-a", "msg-4", "idem-4", "order-4", "payload-v4", "at_least_once"), traceparent=valid, tracestate="vendor=global-correlation-123")
    tenant_b_same_input = process_message(BusinessEnvelope("tenant-b", "msg-5", "idem-5", "order-5", "payload-v5", "at_least_once"), traceparent=valid, tracestate="vendor=global-correlation-123")
    proof_a = issue_tenant_scope_proof(observed, scope_authority)
    second_same_tenant_hop = process_message(BusinessEnvelope("tenant-a", "msg-6", "idem-6", "order-6", "payload-v6", "at_least_once"), traceparent=observed.trace.traceparent, scope_proof=proof_a, scope_authority=scope_authority)
    cross_tenant_from_scoped = process_message(BusinessEnvelope("tenant-b", "msg-7", "idem-7", "order-7", "payload-v7", "at_least_once"), traceparent=observed.trace.traceparent, scope_proof=proof_a, scope_authority=scope_authority)
    raw_replayed_same_tenant = process_message(BusinessEnvelope("tenant-a", "msg-8", "idem-8", "order-8", "payload-v8", "at_least_once"), traceparent=observed.trace.traceparent)
    forged_proof = wrong_scope_authority.issue("tenant-a", observed.trace.traceparent)
    forged_scope = process_message(BusinessEnvelope("tenant-a", "msg-9", "idem-9", "order-9", "payload-v9", "at_least_once"), traceparent=observed.trace.traceparent, scope_proof=forged_proof, scope_authority=scope_authority)
    collision_a = process_message(BusinessEnvelope("tenant-27417", "msg-10", "idem-10", "order-10", "payload-v10", "at_least_once"), traceparent=valid)
    collision_proof = issue_tenant_scope_proof(collision_a, scope_authority)
    collision_b = process_message(BusinessEnvelope("tenant-33720", "msg-11", "idem-11", "order-11", "payload-v11", "at_least_once"), traceparent=collision_a.trace.traceparent, scope_proof=collision_proof, scope_authority=scope_authority)

    checks["same_tenant_trace_correlation_allowed"] = can_correlate(observed, tenant_a_2)
    checks["cross_tenant_trace_correlation_blocked"] = not can_correlate(observed, tenant_b)
    checks["same_input_trace_id_is_stable_within_tenant"] = observed.trace.traceparent is not None and tenant_a_same_input.trace.traceparent is not None and observed.trace.traceparent.split("-")[1] == tenant_a_same_input.trace.traceparent.split("-")[1]
    checks["same_input_trace_id_is_different_across_tenants"] = observed.trace.traceparent is not None and tenant_b_same_input.trace.traceparent is not None and observed.trace.traceparent.split("-")[1] != tenant_b_same_input.trace.traceparent.split("-")[1]
    checks["copied_tracestate_is_not_exported_across_tenants"] = tenant_a_same_input.trace.tracestate is None and tenant_b_same_input.trace.tracestate is None
    checks["authenticated_scope_preserves_same_tenant_multi_hop_trace"] = observed.trace.traceparent is not None and second_same_tenant_hop.trace.traceparent == observed.trace.traceparent and second_same_tenant_hop.trace_context_disposition == "accepted_authenticated_tenant_scope" and can_correlate(observed, second_same_tenant_hop)
    checks["authenticated_scope_is_rescoped_at_different_tenant_boundary"] = observed.trace.traceparent is not None and cross_tenant_from_scoped.trace.traceparent is not None and cross_tenant_from_scoped.trace.traceparent != observed.trace.traceparent and cross_tenant_from_scoped.trace_context_disposition == "accepted_rescoped_tenant_boundary" and not can_correlate(observed, cross_tenant_from_scoped)
    checks["raw_scoped_bytes_are_not_scope_authority"] = observed.trace.traceparent is not None and raw_replayed_same_tenant.trace.traceparent is not None and raw_replayed_same_tenant.trace.traceparent != observed.trace.traceparent
    checks["forged_scope_proof_is_rejected_without_business_abort"] = _isolated_from_business(forged_scope.envelope, forged_scope)
    checks["known_short_marker_collision_cannot_bypass_tenant_rescoping"] = collision_a.trace.traceparent is not None and collision_b.trace.traceparent is not None and collision_b.trace.traceparent != collision_a.trace.traceparent and collision_b.trace_context_disposition == "accepted_rescoped_tenant_boundary"

    altered_trace = process_message(env, traceparent=same_trace_other_parent, tracestate=None)
    checks["trace_change_does_not_change_business_or_delivery_semantics"] = business_semantics(altered_trace) == business_semantics(observed)

    return checks

if __name__ == "__main__":
    checks = run_probes()
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise SystemExit("FAILED: " + ",".join(failed))
    print(f"d4d_open_evt_018_trace_context_source=PASS probes={len(checks)}")