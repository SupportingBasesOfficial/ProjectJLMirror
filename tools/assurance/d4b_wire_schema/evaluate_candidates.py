#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

ELIGIBLE = "eligible_for_evidence_execution"
MAX_MESSAGE_BYTES = 4096
MAX_JSON_DEPTH = 8
MAX_JSON_NUMBER_DIGITS = 20
MAX_JSON_SCALE = 18
MAX_JSON_MAGNITUDE = Decimal((1 << 63) - 1)
MAX_PROTO_FIELD_NUMBER = (1 << 29) - 1
MAX_PROTO_VARINT_VALUE = (1 << 64) - 1
PROTO_RESERVED_FIELD_RANGE = range(19000, 20000)
MAX_AVRO_FIELDS = 64
MAX_AVRO_NAME_BYTES = 128
MAX_AVRO_ALIASES_PER_FIELD = 16
MAX_AVRO_SCALAR_BYTES = MAX_MESSAGE_BYTES


class EvidenceViolation(ValueError):
    pass


class DuplicateMemberError(EvidenceViolation):
    pass


REVIEWED_SCHEMA_REFS: dict[str, frozenset[str]] = {
    "bounded_json_plus_json_schema_profile": frozenset({"json:event:v1"}),
    "protobuf_profile": frozenset({"proto:event:v1"}),
    "avro_profile": frozenset({"avro:event:v1", "avro:event:v2"}),
}


@dataclass(frozen=True)
class HistoricalEnvelope:
    candidate: str
    schema_ref: str
    original_bytes: bytes


def admit_transport_payload(raw: bytes, compression: str = "identity") -> bytes:
    if compression != "identity":
        raise EvidenceViolation("compressed payload rejected until a reviewed decompression profile is selected")
    if not isinstance(raw, bytes) or len(raw) > MAX_MESSAGE_BYTES:
        raise EvidenceViolation("message exceeds evidence byte bound")
    return raw


def resolve_reviewed_schema(candidate: str, configured_ref: str, untrusted_message_ref: str | None = None) -> str:
    if untrusted_message_ref is not None:
        raise EvidenceViolation("untrusted message content cannot select schema or executable code")
    allowed = REVIEWED_SCHEMA_REFS.get(candidate)
    if allowed is None or configured_ref not in allowed:
        raise EvidenceViolation("schema reference is not part of reviewed static evidence authority")
    return configured_ref


def read_historical_envelope(envelope: HistoricalEnvelope, candidate: str, schema_ref: str) -> bytes:
    if envelope.candidate != candidate or envelope.schema_ref != schema_ref:
        raise EvidenceViolation("historical profile/schema reinterpretation is forbidden")
    resolve_reviewed_schema(candidate, schema_ref)
    return bytes(envelope.original_bytes)


def _reject_duplicate_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateMemberError(f"duplicate JSON member {key!r}")
        out[key] = value
    return out


def _bounded_decimal(raw: str) -> Decimal:
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise EvidenceViolation("invalid JSON number") from exc
    if not value.is_finite():
        raise EvidenceViolation("non-finite JSON number")
    _, digits, exponent = value.as_tuple()
    if len(digits) > MAX_JSON_NUMBER_DIGITS or abs(exponent) > MAX_JSON_SCALE:
        raise EvidenceViolation("JSON number exceeds evidence precision/scale bound")
    if abs(value) > MAX_JSON_MAGNITUDE:
        raise EvidenceViolation("JSON number exceeds evidence magnitude bound")
    return value


def _depth(value: Any, current: int = 0) -> int:
    if isinstance(value, dict):
        return current + 1 if not value else max(_depth(v, current + 1) for v in value.values())
    if isinstance(value, list):
        return current + 1 if not value else max(_depth(v, current + 1) for v in value)
    return current


JSON_ALIAS_GROUPS = (
    frozenset({"tenant_id", "tenantId"}),
    frozenset({"event_type", "eventType"}),
)


def parse_bounded_json(raw: bytes) -> dict[str, Any]:
    raw = admit_transport_payload(raw)
    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_reject_duplicate_members,
            parse_int=_bounded_decimal,
            parse_float=_bounded_decimal,
            parse_constant=lambda token: (_ for _ in ()).throw(EvidenceViolation(f"forbidden JSON constant {token}")),
        )
    except UnicodeDecodeError as exc:
        raise EvidenceViolation("JSON must be UTF-8") from exc
    if not isinstance(value, dict):
        raise EvidenceViolation("JSON top level must be object")
    if _depth(value) > MAX_JSON_DEPTH:
        raise EvidenceViolation("JSON nesting exceeds evidence depth bound")
    for aliases in JSON_ALIAS_GROUPS:
        present = aliases.intersection(value)
        if len(present) > 1:
            raise EvidenceViolation(f"protected JSON alias collision: {sorted(present)}")
    return value


def validate_json_contract(value: dict[str, Any]) -> None:
    permitted = {"tenant_id", "event_type", "payload", "severity"}
    if set(value) - permitted:
        raise EvidenceViolation("JSON additional properties forbidden by evidence profile")
    for required in ("tenant_id", "event_type"):
        if required not in value or not isinstance(value[required], str) or value[required] == "":
            raise EvidenceViolation(f"JSON field {required} must be present non-empty string")
    if "severity" in value and value["severity"] not in ("info", "warning", "critical", None):
        raise EvidenceViolation("JSON enum/null semantics violated")


def _canonical_decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    sign, raw_digits, exponent = value.as_tuple()
    digits = list(raw_digits)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exponent += 1
    body = "".join(str(digit) for digit in digits)
    if exponent >= 0:
        body = body + ("0" * exponent)
    else:
        point = len(body) + exponent
        if point > 0:
            body = body[:point] + "." + body[point:]
        else:
            body = "0." + ("0" * (-point)) + body
    return ("-" if sign else "") + body


def _canonical_json_value(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, str):
        return ("string", value)
    if isinstance(value, Decimal):
        return ("number", _canonical_decimal_text(value))
    if isinstance(value, list):
        return ("array", tuple(_canonical_json_value(item) for item in value))
    if isinstance(value, dict):
        return ("object", tuple((key, _canonical_json_value(value[key])) for key in sorted(value)))
    raise EvidenceViolation(f"unsupported JSON runtime mapping type: {type(value).__name__}")


def canonical_json_equivalence(raw: bytes) -> tuple[Any, ...]:
    value = parse_bounded_json(raw)
    validate_json_contract(value)
    return _canonical_json_value(value)


@dataclass(frozen=True)
class ProtoField:
    number: int
    wire_type: int
    raw_value: bytes
    raw_segment: bytes


def _encode_varint(value: int) -> bytes:
    if value < 0 or value > MAX_PROTO_VARINT_VALUE:
        raise ValueError("varint evidence helper requires uint64 value")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _read_varint(raw: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    start = offset
    while offset < len(raw) and offset - start < 10:
        byte = raw[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if value > MAX_PROTO_VARINT_VALUE:
            raise EvidenceViolation("protobuf varint exceeds uint64 bound")
        if not (byte & 0x80):
            if raw[start:offset] != _encode_varint(value):
                raise EvidenceViolation("non-minimal protobuf varint is forbidden by canonical evidence profile")
            return value, offset
        shift += 7
    raise EvidenceViolation("invalid or overlong protobuf varint")


def proto_field(number: int, payload: bytes) -> bytes:
    if number <= 0 or number > MAX_PROTO_FIELD_NUMBER or number in PROTO_RESERVED_FIELD_RANGE:
        raise ValueError("invalid or reserved protobuf field number")
    return _encode_varint((number << 3) | 2) + _encode_varint(len(payload)) + payload


def scan_bounded_protobuf(raw: bytes) -> list[ProtoField]:
    raw = admit_transport_payload(raw)
    fields: list[ProtoField] = []
    offset = 0
    while offset < len(raw):
        start = offset
        tag, offset = _read_varint(raw, offset)
        number = tag >> 3
        wire_type = tag & 0x07
        if number <= 0 or number > MAX_PROTO_FIELD_NUMBER or number in PROTO_RESERVED_FIELD_RANGE:
            raise EvidenceViolation("invalid or reserved protobuf field number")
        if wire_type == 0:
            _, end = _read_varint(raw, offset)
            raw_value = raw[offset:end]
            offset = end
        elif wire_type == 1:
            end = offset + 8
            if end > len(raw):
                raise EvidenceViolation("truncated protobuf fixed64")
            raw_value = raw[offset:end]
            offset = end
        elif wire_type == 2:
            length, after_len = _read_varint(raw, offset)
            end = after_len + length
            if length > MAX_MESSAGE_BYTES or end > len(raw):
                raise EvidenceViolation("protobuf length-delimited field exceeds bound or is truncated")
            raw_value = raw[after_len:end]
            offset = end
        elif wire_type == 5:
            end = offset + 4
            if end > len(raw):
                raise EvidenceViolation("truncated protobuf fixed32")
            raw_value = raw[offset:end]
            offset = end
        else:
            raise EvidenceViolation("protobuf groups/unsupported wire types forbidden by evidence profile")
        fields.append(ProtoField(number, wire_type, raw_value, raw[start:offset]))
    return fields


PROTO_PROTECTED_SINGULAR = frozenset({1, 2, 6})
PROTO_PROTECTED_ONEOF = frozenset({3, 4})
PROTO_REPEATED_FIELDS = frozenset({5})
PROTO_KNOWN_FIELDS = PROTO_PROTECTED_SINGULAR | PROTO_PROTECTED_ONEOF | PROTO_REPEATED_FIELDS
PROTO_SEVERITIES = frozenset({b"info", b"warning", b"critical"})


def validate_protobuf_profile(raw: bytes) -> tuple[list[ProtoField], bytes]:
    fields = scan_bounded_protobuf(raw)
    counts: dict[int, int] = {}
    for field in fields:
        counts[field.number] = counts.get(field.number, 0) + 1
    duplicates = sorted(number for number in PROTO_PROTECTED_SINGULAR if counts.get(number, 0) > 1)
    if duplicates:
        raise EvidenceViolation(f"protected protobuf singular field duplicated: {duplicates}")
    duplicate_oneof = sorted(number for number in PROTO_PROTECTED_ONEOF if counts.get(number, 0) > 1)
    if duplicate_oneof:
        raise EvidenceViolation(f"protected protobuf oneof member duplicated: {duplicate_oneof}")
    oneof_present = sorted(number for number in PROTO_PROTECTED_ONEOF if counts.get(number, 0) > 0)
    if len(oneof_present) > 1:
        raise EvidenceViolation(f"protected protobuf oneof collision: {oneof_present}")
    by_number = {field.number: field for field in fields if field.number in PROTO_PROTECTED_SINGULAR}
    for required in (1, 2):
        field = by_number.get(required)
        if field is None or field.wire_type != 2 or field.raw_value == b"":
            raise EvidenceViolation(f"required protobuf field {required} missing or invalid")
    severity = by_number.get(6)
    if severity is not None and (severity.wire_type != 2 or severity.raw_value not in PROTO_SEVERITIES):
        raise EvidenceViolation("protobuf optional severity enum invalid; null is represented only by absence")
    unknown = b"".join(field.raw_segment for field in fields if field.number not in PROTO_KNOWN_FIELDS)
    return fields, unknown


def protobuf_semantic_equivalence(raw: bytes) -> tuple[tuple[int, tuple[tuple[int, bytes], ...]], ...]:
    fields, _ = validate_protobuf_profile(raw)
    grouped: dict[int, list[tuple[int, bytes]]] = {}
    for field in fields:
        grouped.setdefault(field.number, []).append((field.wire_type, field.raw_value))
    return tuple((number, tuple(grouped[number])) for number in sorted(grouped))


AVRO_PRIMITIVES = frozenset({"null", "boolean", "int", "long", "float", "double", "bytes", "string"})
AVRO_PROMOTIONS: dict[str, frozenset[str]] = {
    "null": frozenset({"null"}),
    "boolean": frozenset({"boolean"}),
    "int": frozenset({"int", "long", "float", "double"}),
    "long": frozenset({"long", "float", "double"}),
    "float": frozenset({"float", "double"}),
    "double": frozenset({"double"}),
    "bytes": frozenset({"bytes", "string"}),
    "string": frozenset({"string", "bytes"}),
}


@dataclass(frozen=True)
class AvroFieldSpec:
    name: str
    avro_types: tuple[str, ...] = ("string",)
    aliases: tuple[str, ...] = ()
    default_present: bool = False
    default: Any = None


@dataclass(frozen=True)
class AvroRecordSchema:
    name: str
    fields: tuple[AvroFieldSpec, ...]


def _bounded_avro_name(value: str, label: str) -> None:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > MAX_AVRO_NAME_BYTES:
        raise EvidenceViolation(f"Avro {label} exceeds evidence name bound")


def _avro_value_matches_type(value: Any, avro_type: str) -> bool:
    if avro_type == "null":
        return value is None
    if avro_type == "boolean":
        return isinstance(value, bool)
    if avro_type == "int":
        return isinstance(value, int) and not isinstance(value, bool) and -(1 << 31) <= value <= (1 << 31) - 1
    if avro_type == "long":
        return isinstance(value, int) and not isinstance(value, bool) and -(1 << 63) <= value <= (1 << 63) - 1
    if avro_type in {"float", "double"}:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
    if avro_type == "bytes":
        return isinstance(value, bytes) and len(value) <= MAX_AVRO_SCALAR_BYTES
    if avro_type == "string":
        return isinstance(value, str) and len(value.encode("utf-8")) <= MAX_AVRO_SCALAR_BYTES
    return False


def _avro_types_compatible(writer_types: tuple[str, ...], reader_types: tuple[str, ...]) -> bool:
    return all(any(reader in AVRO_PROMOTIONS[writer] for reader in reader_types) for writer in writer_types)


def _avro_effective_writer_type(value: Any, writer_types: tuple[str, ...]) -> str:
    for writer_type in writer_types:
        if _avro_value_matches_type(value, writer_type):
            return writer_type
    raise EvidenceViolation("Avro datum does not match any bounded writer type")


def _avro_reader_type_for_writer(writer_type: str, reader_types: tuple[str, ...]) -> str:
    for reader_type in reader_types:
        if reader_type in AVRO_PROMOTIONS[writer_type]:
            return reader_type
    raise EvidenceViolation("Avro writer value has no compatible reader type")


def _promote_avro_value(value: Any, writer_type: str, reader_type: str) -> Any:
    if writer_type == reader_type or (writer_type == "int" and reader_type == "long"):
        return value
    if writer_type in {"int", "long", "float"} and reader_type in {"float", "double"}:
        promoted = float(value)
        if not math.isfinite(promoted):
            raise EvidenceViolation("Avro numeric promotion produced non-finite reader value")
        return promoted
    if writer_type == "bytes" and reader_type == "string":
        try:
            promoted = value.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise EvidenceViolation("Avro bytes-to-string promotion requires valid UTF-8") from exc
        if len(promoted.encode("utf-8")) > MAX_AVRO_SCALAR_BYTES:
            raise EvidenceViolation("Avro promoted string exceeds evidence bound")
        return promoted
    if writer_type == "string" and reader_type == "bytes":
        promoted = value.encode("utf-8")
        if len(promoted) > MAX_AVRO_SCALAR_BYTES:
            raise EvidenceViolation("Avro promoted bytes exceed evidence bound")
        return promoted
    raise EvidenceViolation(f"unsupported Avro promotion {writer_type}->{reader_type}")


def validate_avro_schema(schema: AvroRecordSchema) -> None:
    _bounded_avro_name(schema.name, "record name")
    if len(schema.fields) > MAX_AVRO_FIELDS:
        raise EvidenceViolation("Avro field count exceeds evidence bound")
    names: set[str] = set()
    aliases: dict[str, str] = {}
    for field in schema.fields:
        _bounded_avro_name(field.name, "field name")
        if field.name in names:
            raise EvidenceViolation(f"duplicate Avro field name {field.name}")
        names.add(field.name)
        if not field.avro_types or len(set(field.avro_types)) != len(field.avro_types) or any(t not in AVRO_PRIMITIVES for t in field.avro_types):
            raise EvidenceViolation(f"invalid Avro type declaration for {field.name}")
        if field.default_present and not _avro_value_matches_type(field.default, field.avro_types[0]):
            raise EvidenceViolation(f"Avro default for {field.name} must match first declared type and evidence bounds")
        if len(field.aliases) > MAX_AVRO_ALIASES_PER_FIELD:
            raise EvidenceViolation(f"Avro alias count exceeds evidence bound for {field.name}")
        for alias in field.aliases:
            _bounded_avro_name(alias, "field alias")
            if alias == field.name:
                raise EvidenceViolation("Avro field alias cannot duplicate its canonical name in evidence profile")
            owner = aliases.get(alias)
            if owner is not None and owner != field.name:
                raise EvidenceViolation(f"ambiguous Avro field alias {alias}")
            aliases[alias] = field.name
    if names.intersection(aliases):
        raise EvidenceViolation("Avro canonical field/alias collision")


def resolve_avro_record(writer: AvroRecordSchema, reader: AvroRecordSchema, datum: dict[str, Any]) -> dict[str, tuple[str, Any]]:
    validate_avro_schema(writer)
    validate_avro_schema(reader)
    if writer.name != reader.name:
        raise EvidenceViolation("Avro writer/reader record identity mismatch")
    if not isinstance(datum, dict) or len(datum) > MAX_AVRO_FIELDS:
        raise EvidenceViolation("Avro datum field count exceeds evidence bound")
    writer_fields = {field.name: field for field in writer.fields}
    if set(datum) - set(writer_fields):
        raise EvidenceViolation("datum contains field absent from pinned Avro writer schema")
    resolved: dict[str, tuple[str, Any]] = {}
    for target in reader.fields:
        source_names = (target.name,) + target.aliases
        present = [name for name in source_names if name in datum and name in writer_fields]
        if len(present) > 1:
            raise EvidenceViolation(f"Avro protected alias collision in datum for {target.name}")
        if present:
            source_name = present[0]
            source = writer_fields[source_name]
            if not _avro_types_compatible(source.avro_types, target.avro_types):
                raise EvidenceViolation(f"Avro writer/reader type incompatibility for {target.name}")
            value = datum[source_name]
            writer_type = _avro_effective_writer_type(value, source.avro_types)
            reader_type = _avro_reader_type_for_writer(writer_type, target.avro_types)
            promoted = _promote_avro_value(value, writer_type, reader_type)
            if not _avro_value_matches_type(promoted, reader_type):
                raise EvidenceViolation(f"Avro promoted value violates reader type/bounds for {target.name}")
            resolved[target.name] = (reader_type, promoted)
        elif target.default_present:
            resolved[target.name] = (target.avro_types[0], target.default)
        else:
            raise EvidenceViolation(f"Avro reader field {target.name} missing and has no default")
    return resolved


def validate_avro_contract(value: dict[str, tuple[str, Any]]) -> None:
    for required in ("tenant_id", "event_type"):
        resolved = value.get(required)
        if resolved is None or resolved[0] != "string" or not isinstance(resolved[1], str) or resolved[1] == "":
            raise EvidenceViolation(f"Avro required field {required} invalid")
    if "severity" in value:
        severity_type, severity_value = value["severity"]
        if severity_type == "null":
            if severity_value is not None:
                raise EvidenceViolation("Avro nullable severity null branch invalid")
        elif severity_type == "string":
            if severity_value not in ("info", "warning", "critical"):
                raise EvidenceViolation("Avro nullable severity enum invalid")
        else:
            raise EvidenceViolation("Avro nullable severity resolved to unsupported reader type")


def avro_semantic_equivalence(writer: AvroRecordSchema, reader: AvroRecordSchema, datum: dict[str, Any]) -> tuple[tuple[str, tuple[str, Any]], ...]:
    resolved = resolve_avro_record(writer, reader, datum)
    validate_avro_contract(resolved)
    return tuple((name, resolved[name]) for name in sorted(resolved))


def prove_static_schema_and_history(candidate: str, schema_ref: str, payload: bytes) -> None:
    resolve_reviewed_schema(candidate, schema_ref)
    try:
        resolve_reviewed_schema(candidate, schema_ref, untrusted_message_ref="https://attacker.invalid/schema")
    except EvidenceViolation:
        pass
    else:
        raise AssertionError(f"{candidate} accepted untrusted dynamic schema selection")
    envelope = HistoricalEnvelope(candidate, schema_ref, payload)
    if read_historical_envelope(envelope, candidate, schema_ref) != payload:
        raise AssertionError(f"{candidate} historical bytes changed")
    other = "protobuf_profile" if candidate != "protobuf_profile" else "avro_profile"
    other_ref = next(iter(REVIEWED_SCHEMA_REFS[other]))
    try:
        read_historical_envelope(envelope, other, other_ref)
    except EvidenceViolation:
        pass
    else:
        raise AssertionError(f"{candidate} historical payload was reinterpreted through another profile")


def prove_identity_only_transport() -> None:
    admit_transport_payload(b"bounded")
    try:
        admit_transport_payload(b"compressed", compression="gzip")
    except EvidenceViolation:
        pass
    else:
        raise AssertionError("compressed payload accepted without selected bounded decompression profile")


def prove_json_profile() -> None:
    prove_static_schema_and_history("bounded_json_plus_json_schema_profile", "json:event:v1", b"historical-json")
    good_a = b'{"tenant_id":"t1","event_type":"alarm","severity":null,"payload":{"x":1.0}}'
    good_b = b'{"payload":{"x":1e0},"event_type":"alarm","tenant_id":"t1","severity":null}'
    if canonical_json_equivalence(good_a) != canonical_json_equivalence(good_b):
        raise AssertionError("JSON semantic equivalence is not deterministic across numeric spellings")
    if canonical_json_equivalence(b'{"tenant_id":"t1","event_type":"alarm","payload":{"x":-0.0}}') != canonical_json_equivalence(b'{"tenant_id":"t1","event_type":"alarm","payload":{"x":0}}'):
        raise AssertionError("JSON numeric zero semantics vary by runtime spelling")
    distinct_a = b'{"tenant_id":"t1","event_type":"alarm","payload":{"x":9007199254740992.0}}'
    distinct_b = b'{"tenant_id":"t1","event_type":"alarm","payload":{"x":9007199254740993.0}}'
    if canonical_json_equivalence(distinct_a) == canonical_json_equivalence(distinct_b):
        raise AssertionError("distinct bounded JSON decimals collapsed during normalization")
    forbidden = (
        b'{"tenant_id":"t1","tenant_id":"t2","event_type":"alarm"}',
        b'{"tenant_id":"t1","tenantId":"t1","event_type":"alarm"}',
        b'{"tenant_id":"t1","event_type":"alarm","extra":1}',
        b'{"tenant_id":"t1","event_type":"alarm","severity":"unknown"}',
        b'{"tenant_id":"t1","event_type":"alarm","payload":9223372036854775808}',
        b'{"tenant_id":"t1","event_type":"alarm","payload":1e-999}',
    )
    for vector in forbidden:
        try:
            canonical_json_equivalence(vector)
        except (EvidenceViolation, DuplicateMemberError):
            continue
        raise AssertionError(f"JSON evidence profile accepted forbidden vector {vector!r}")


def prove_protobuf_profile() -> None:
    prove_static_schema_and_history("protobuf_profile", "proto:event:v1", b"historical-protobuf")
    tenant = proto_field(1, b"t1")
    event = proto_field(2, b"alarm")
    severity = proto_field(6, b"warning")
    repeated_a = proto_field(5, b"a")
    repeated_b = proto_field(5, b"b")
    unknown = proto_field(100, b"future")
    raw_a = tenant + event + severity + repeated_a + repeated_b + unknown
    raw_b = unknown + event + tenant + severity + repeated_a + repeated_b
    fields, preserved_unknown = validate_protobuf_profile(raw_a)
    if not fields or preserved_unknown != unknown:
        raise AssertionError("protobuf unknown field bytes were not preserved")
    if protobuf_semantic_equivalence(raw_a) != protobuf_semantic_equivalence(raw_b):
        raise AssertionError("protobuf semantic equivalence depends on distinct-field serialization order")
    if protobuf_semantic_equivalence(tenant + event + repeated_a + repeated_b) == protobuf_semantic_equivalence(tenant + event + repeated_b + repeated_a):
        raise AssertionError("protobuf repeated-field order was erased by semantic normalization")
    invalid_vectors = (
        tenant + tenant + event,
        tenant + event + proto_field(3, b"a") + proto_field(3, b"b"),
        tenant + event + proto_field(3, b"a") + proto_field(4, b"b"),
        tenant + event + proto_field(6, b"unknown"),
        event,
    )
    for vector in invalid_vectors:
        try:
            validate_protobuf_profile(vector)
        except EvidenceViolation:
            continue
        raise AssertionError("protobuf profile accepted invalid protected field semantics")
    nonminimal_tag = bytes([0x8A, 0x00, 0x02]) + b"t1" + event
    try:
        validate_protobuf_profile(nonminimal_tag)
    except EvidenceViolation:
        pass
    else:
        raise AssertionError("protobuf non-minimal varint was accepted")
    overflow_scalar = _encode_varint(7 << 3) + (bytes([0x80]) * 9) + bytes([0x02])
    try:
        scan_bounded_protobuf(overflow_scalar)
    except EvidenceViolation:
        pass
    else:
        raise AssertionError("protobuf uint64-overflow varint was accepted")


def prove_avro_profile() -> None:
    prove_static_schema_and_history("avro_profile", "avro:event:v1", b"historical-avro")
    admit_transport_payload(b"avro-binary-fixture")
    writer_v1 = AvroRecordSchema(
        "Event",
        (
            AvroFieldSpec("tenant_id", ("string",)),
            AvroFieldSpec("event_type", ("string",)),
        ),
    )
    reader_v2 = AvroRecordSchema(
        "Event",
        (
            AvroFieldSpec("tenant_id", ("string",)),
            AvroFieldSpec("event_type", ("string",)),
            AvroFieldSpec("severity", ("string", "null"), default_present=True, default="info"),
        ),
    )
    datum = {"tenant_id": "t1", "event_type": "alarm"}
    expected = (
        ("event_type", ("string", "alarm")),
        ("severity", ("string", "info")),
        ("tenant_id", ("string", "t1")),
    )
    if avro_semantic_equivalence(writer_v1, reader_v2, datum) != expected:
        raise AssertionError("Avro writer-reader resolution is not deterministic")
    nullable_schema = AvroRecordSchema(
        "Event",
        (
            AvroFieldSpec("tenant_id", ("string",)),
            AvroFieldSpec("event_type", ("string",)),
            AvroFieldSpec("severity", ("null", "string"), default_present=True, default=None),
        ),
    )
    nullable_equivalence = avro_semantic_equivalence(nullable_schema, nullable_schema, {"tenant_id": "t1", "event_type": "alarm", "severity": None})
    if ("severity", ("null", None)) not in nullable_equivalence:
        raise AssertionError("Avro nullable enum semantics were not preserved")
    incompatible_writer = AvroRecordSchema(
        "Event",
        (
            AvroFieldSpec("tenant_id", ("boolean",)),
            AvroFieldSpec("event_type", ("string",)),
        ),
    )
    try:
        resolve_avro_record(incompatible_writer, reader_v2, {"tenant_id": True, "event_type": "alarm"})
    except EvidenceViolation:
        pass
    else:
        raise AssertionError("Avro incompatible writer/reader field types were accepted")
    int_writer = AvroRecordSchema("Metric", (AvroFieldSpec("value", ("int",)),))
    double_reader = AvroRecordSchema("Metric", (AvroFieldSpec("value", ("double",)),))
    double_writer = AvroRecordSchema("Metric", (AvroFieldSpec("value", ("double",)),))
    if avro_semantic_equivalence(int_writer, double_reader, {"value": 1}) != avro_semantic_equivalence(double_writer, double_reader, {"value": 1.0}):
        raise AssertionError("Avro numeric promotion did not canonicalize to reader representation")
    bytes_writer = AvroRecordSchema("Text", (AvroFieldSpec("value", ("bytes",)),))
    string_reader = AvroRecordSchema("Text", (AvroFieldSpec("value", ("string",)),))
    if avro_semantic_equivalence(bytes_writer, string_reader, {"value": b"hello"}) != (("value", ("string", "hello")),):
        raise AssertionError("Avro bytes-to-string promotion did not produce reader representation")
    try:
        avro_semantic_equivalence(bytes_writer, string_reader, {"value": b"\xff"})
    except EvidenceViolation:
        pass
    else:
        raise AssertionError("Avro invalid UTF-8 bytes-to-string promotion was accepted")
    try:
        resolve_avro_record(writer_v1, reader_v2, {"tenant_id": "x" * (MAX_AVRO_SCALAR_BYTES + 1), "event_type": "alarm"})
    except EvidenceViolation:
        pass
    else:
        raise AssertionError("Avro oversized scalar was accepted")
    missing_required_reader = AvroRecordSchema("Event", reader_v2.fields + (AvroFieldSpec("region", ("string",)),))
    try:
        resolve_avro_record(writer_v1, missing_required_reader, datum)
    except EvidenceViolation:
        pass
    else:
        raise AssertionError("Avro reader accepted missing field without default")
    ambiguous_reader = AvroRecordSchema(
        "Event",
        (
            AvroFieldSpec("tenant_id", ("string",), aliases=("tenant",)),
            AvroFieldSpec("event_type", ("string",), aliases=("tenant",)),
        ),
    )
    try:
        validate_avro_schema(ambiguous_reader)
    except EvidenceViolation:
        pass
    else:
        raise AssertionError("Avro ambiguous aliases were accepted")


def evaluate() -> dict[str, str]:
    prove_identity_only_transport()
    prove_json_profile()
    prove_protobuf_profile()
    prove_avro_profile()
    return {
        "bounded_json_plus_json_schema_profile": ELIGIBLE,
        "protobuf_profile": ELIGIBLE,
        "avro_profile": ELIGIBLE,
    }


def main() -> int:
    results = evaluate()
    print(
        "d4b_wire_schema_candidate_source=PASS candidates=3 concrete_eligible=3 "
        "identity_only_transport=bounded dynamic_schema_selection=blocked historical_profile_reinterpretation=blocked "
        "json_duplicates=blocked json_alias_collision=blocked json_numeric_mapping=context_independent json_distinct_decimals=preserved "
        "json_bounds=proven protobuf_nonminimal_varint=blocked protobuf_uint64_overflow=blocked "
        "protobuf_protected_duplicates=blocked protobuf_oneof_duplicate=blocked protobuf_presence_enum=explicit "
        "protobuf_unknown_bytes=preserved protobuf_byte_order=noncanonical protobuf_repeated_order=preserved "
        "avro_writer_reader_resolution=explicit avro_type_compatibility=checked avro_promotions=reader_canonicalized avro_datum_bounds=proven "
        "avro_nullable_enum=explicit avro_alias_ambiguity=blocked selection=not_selected ledger_credit=0"
    )
    for candidate, result in sorted(results.items()):
        print(f"candidate={candidate} result={result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())