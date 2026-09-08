#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
import re

TRACEPARENT_RE = re.compile(r"^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")
SENSITIVE_MARKERS = ("authorization", "cookie", "secret", "password", "credential", "api_key", "apikey", "token")
MAX_TRACESTATE_LEN = 512
MAX_ATTRS = 16
MAX_ATTR_KEY = 64
MAX_ATTR_VALUE = 128

@dataclass(frozen=True)
class BusinessEnvelope:
    tenant_id: str
    message_id: str
    idempotency_key: str
    ordering_key: str
    payload: str
    delivery_semantics: str

@dataclass(frozen=True)
class TraceContext:
    traceparent: str | None
    tracestate: str | None
    attributes: tuple[tuple[str, str], ...] = ()

@dataclass(frozen=True)
class ObservedMessage:
    envelope: BusinessEnvelope
    trace: TraceContext

class TraceContextRejected(Exception):
    pass

def _valid_traceparent(value: str) -> bool:
    if not TRACEPARENT_RE.fullmatch(value):
        return False
    version, trace_id, parent_id, _flags = value.split("-")
    return version != "ff" and trace_id != "0" * 32 and parent_id != "0" * 16

def _bounded_tracestate(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) > MAX_TRACESTATE_LEN or "\n" in value or "\r" in value:
        raise TraceContextRejected("tracestate out of bounds")
    return value

def _is_sensitive_attribute(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SENSITIVE_MARKERS)

def _redact_attributes(attributes: dict[str, str]) -> tuple[tuple[str, str], ...]:
    if len(attributes) > MAX_ATTRS:
        raise TraceContextRejected("too many trace attributes")
    clean: list[tuple[str, str]] = []
    for key, value in attributes.items():
        if not isinstance(key, str) or not isinstance(value, str) or not key or len(key) > MAX_ATTR_KEY or len(value) > MAX_ATTR_VALUE:
            raise TraceContextRejected("trace attribute out of bounds")
        clean.append((key, "[REDACTED]" if _is_sensitive_attribute(key) else value))
    return tuple(sorted(clean))

def normalize_trace_context(traceparent: str | None, tracestate: str | None, attributes: dict[str, str] | None = None) -> TraceContext:
    attrs = _redact_attributes(attributes or {})
    if traceparent is None:
        if tracestate is not None:
            raise TraceContextRejected("tracestate requires traceparent")
        return TraceContext(None, None, attrs)
    if not _valid_traceparent(traceparent):
        raise TraceContextRejected("malformed traceparent")
    return TraceContext(traceparent, _bounded_tracestate(tracestate), attrs)

def process_message(envelope: BusinessEnvelope, *, traceparent: str | None, tracestate: str | None = None, attributes: dict[str, str] | None = None) -> ObservedMessage:
    trace = normalize_trace_context(traceparent, tracestate, attributes)
    return ObservedMessage(envelope=envelope, trace=trace)

def business_semantics(observed: ObservedMessage) -> tuple[str, str, str, str, str, str]:
    e = observed.envelope
    return (e.tenant_id, e.message_id, e.idempotency_key, e.ordering_key, e.payload, e.delivery_semantics)

def can_correlate(left: ObservedMessage, right: ObservedMessage) -> bool:
    if left.envelope.tenant_id != right.envelope.tenant_id:
        return False
    if not left.trace.traceparent or not right.trace.traceparent:
        return False
    return left.trace.traceparent.split("-")[1] == right.trace.traceparent.split("-")[1]

def run_probes() -> dict[str, bool]:
    env = BusinessEnvelope("tenant-a", "msg-1", "idem-1", "order-1", "payload-v1", "at_least_once")
    valid = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    same_trace_other_parent = "00-4bf92f3577b34da6a3ce929d0e0e4736-1111111111111111-01"

    observed = process_message(env, traceparent=valid, tracestate="vendor=value", attributes={"component": "consumer", "http.request.header.authorization": "Bearer super-secret", "db.api_token": "opaque-secret"})
    no_trace = process_message(env, traceparent=None)
    attrs = dict(observed.trace.attributes)

    checks: dict[str, bool] = {
        "trace_context_is_observability_only": business_semantics(observed) == business_semantics(no_trace),
        "trace_context_not_tenant_authority": observed.envelope.tenant_id == "tenant-a",
        "trace_context_not_idempotency_authority": observed.envelope.idempotency_key == "idem-1",
        "trace_context_not_ordering_authority": observed.envelope.ordering_key == "order-1",
        "trace_context_not_message_identity_authority": observed.envelope.message_id == "msg-1",
        "trace_context_not_delivery_authority": observed.envelope.delivery_semantics == "at_least_once",
        "valid_traceparent_accepted": observed.trace.traceparent == valid,
        "bounded_tracestate_accepted": observed.trace.tracestate == "vendor=value",
        "sensitive_trace_attribute_redacted": attrs["http.request.header.authorization"] == "[REDACTED]" and attrs["db.api_token"] == "[REDACTED]",
        "non_sensitive_trace_attribute_preserved": attrs["component"] == "consumer",
        "missing_trace_context_preserves_business_and_delivery_semantics": business_semantics(no_trace) == business_semantics(observed),
    }

    malformed_cases = [
        "zz-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        "00-00000000000000000000000000000000-00f067aa0ba902b7-01",
        "00-4bf92f3577b34da6a3ce929d0e0e4736-0000000000000000-01",
        "ff-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    ]
    for idx, candidate in enumerate(malformed_cases, start=1):
        try:
            process_message(env, traceparent=candidate)
            checks[f"malformed_traceparent_{idx}_rejected"] = False
        except TraceContextRejected:
            checks[f"malformed_traceparent_{idx}_rejected"] = True

    try:
        process_message(env, traceparent=None, tracestate="vendor=value")
        checks["orphan_tracestate_rejected"] = False
    except TraceContextRejected:
        checks["orphan_tracestate_rejected"] = True

    try:
        process_message(env, traceparent=valid, tracestate="x" * (MAX_TRACESTATE_LEN + 1))
        checks["oversized_tracestate_rejected"] = False
    except TraceContextRejected:
        checks["oversized_tracestate_rejected"] = True

    try:
        process_message(env, traceparent=valid, attributes={f"k{i}": "v" for i in range(MAX_ATTRS + 1)})
        checks["excess_trace_attributes_rejected"] = False
    except TraceContextRejected:
        checks["excess_trace_attributes_rejected"] = True

    tenant_a_2 = process_message(BusinessEnvelope("tenant-a", "msg-2", "idem-2", "order-2", "payload-v2", "at_least_once"), traceparent=same_trace_other_parent)
    tenant_b = process_message(BusinessEnvelope("tenant-b", "msg-3", "idem-3", "order-3", "payload-v3", "at_least_once"), traceparent=same_trace_other_parent)
    checks["same_tenant_trace_correlation_allowed"] = can_correlate(observed, tenant_a_2)
    checks["cross_tenant_trace_correlation_blocked"] = not can_correlate(observed, tenant_b)

    altered_trace = process_message(env, traceparent=same_trace_other_parent, tracestate=None)
    checks["trace_change_does_not_change_business_or_delivery_semantics"] = business_semantics(altered_trace) == business_semantics(observed)

    return checks

if __name__ == "__main__":
    checks = run_probes()
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise SystemExit("FAILED: " + ",".join(failed))
    print(f"d4d_open_evt_018_trace_context_source=PASS probes={len(checks)}")
