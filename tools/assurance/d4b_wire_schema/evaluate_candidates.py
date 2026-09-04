#!/usr/bin/env python3
from __future__ import annotations

import json
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
PROTO_RESERVED_FIELD_RANGE = range(19000, 20000)


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
    sign, digits, exponent = value.as_tuple()
    del sign
    if len(digits) > MAX_JSON_NUMBER_DIGITS or abs(exponent) > MAX_JSON_SCALE:
        raise EvidenceViolation("JSON number exceeds evidence precision/scale bound")
    if abs(value) > MAX_JSON_MAGNITUDE:
        raise EvidenceViolation("JSON number exceeds evidence magnitude bound")
    return value


def _depth(value: Any, current: int = 0) -> int:
    if isinstance(value, dict):
        if not value:
            return current + 1
        return max(_depth(v, current + 1) for v in value.values())
    if isinstance(value, list):
        if not value:
            return current + 1
        return max(_depth(v, current + 1) for v in value)
    return current


JSON_ALIAS_GROUPS = (
    frozenset({"tenant_id", "tenantId"}),
    frozenset({"event_type", "eventType"}),
)


def parse_bounded_json(raw: bytes) -> dict[str, Any]:
    raw = admit_transport_payload(raw)
    try:
        text = raw.decode("utf-8", "strict")
        value = json.loads(
            text,
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
        if required not in value:
            raise EvidenceViolation(f"missing required JSON field {required}")
        if not isinstance(value[required], str) or value[required] == "":
            raise EvidenceViolation(f"JSON field {required} must be non-empty string")
    if "severity" in value and value["severity"] not in ("info", "warning", "critical", None):
        raise EvidenceViolation("JSON enum/null semantics violated")


def _canonical_json_value(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, str):
        return ("string", value)
    if isinstance(value, Decimal):
        if value == 0:
            number = "0"
        else:
            number = format(value.normalize(), "f")
        return ("number", number)
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
    if value < 0:
        raise ValueError("varint evidence helper requires non-negative value")
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
        if not (byte & 0x80):
            encoded = raw[start:offset]
            if encoded != _encode_varint(value):
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


@dataclass(frozen=True)
class AvroFieldSpec:
    name: str
    aliases: tuple[str, ...] = ()
    default_present: bool = False
    default: Any = None


@dataclass(frozen=True)
class AvroRecordSchema:
    name: str
    fields: tuple[AvroFieldSpec, ...]


def validate_avro_schema(schema: AvroRecordSchema) -> None:
    names: set[str] = set()
    aliases: dict[str, str] = {}
    for field in schema.fields:
        if field.name in names:
            raise EvidenceViolation(f"duplicate Avro field name {field.name}")
        names.add(field.name)
        for alias in field.aliases:
            if alias == field.name:
                raise EvidenceViolation("Avro field alias cannot duplicate its canonical name in evidence profile")
            owner = aliases.get(alias)
            if owner is not None and owner != field.name:
                raise EvidenceViolation(f"ambiguous Avro field alias {alias}")
            aliases[alias] = field.name
    if names.intersection(aliases):
        raise EvidenceViolation("Avro canonical field/alias collision")


def resolve_avro_record(writer: AvroRecordSchema, reader: AvroRecordSchema, datum: dict[str, Any]) -> dict[str, Any]:
    validate_avro_schema(writer)
    validate_avro_schema(reader)
    if writer.name != reader.name:
        raise EvidenceViolation("Avro writer/reader record identity mismatch")
    writer_names = {field.name for field in writer.fields}
    if set(datum) - writer_names:
        raise EvidenceViolation("datum contains field absent from pinned Avro writer schema")

    resolved: dict[str, Any] = {}
    for target in reader.fields:
        source_names = (target.name,) + target.aliases
        present = [name for name in source_names if name in datum and name in writer_names]
        if len(present) > 1:
            raise EvidenceViolation(f"Avro protected alias collision in datum for {target.name}")
        if present:
            resolved[target.name] = datum[present[0]]
        elif target.default_present:
            resolved[target.name] = target.default
        else:
            raise EvidenceViolation(f"Avro reader field {target.name} missing and has no default")
    return resolved


def validate_avro_contract(value: dict[str, Any]) -> None:
    for required in ("tenant_id", "event_type"):
        if not isinstance(value.get(required), str) or value[required] == "":
            raise EvidenceViolation(f"Avro required field {required} invalid")
    if "severity" in value and value["severity"] not in ("info", "warning", "critical", None):
        raise EvidenceViolation("Avro nullable enum semantics violated")


def avro_semantic_equivalence(writer: AvroRecordSchema, reader: AvroRecordSchema, datum: dict[str, Any]) -> bytes:
    resolved = resolve_avro_record(writer, reader, datum)
    validate_avro_contract(resolved)
    return json.dumps(resolved, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


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
    negative_zero = b'{"tenant_id":"t1","event_type":"alarm","payload":{"x":-0.0}}'
    positive_zero = b'{"tenant_id":"t1","event_type":"alarm","payload":{"x":0}}'
    if canonical_json_equivalence(negative_zero) != canonical_json_equivalence(positive_zero):
        raise AssertionError("JSON numeric zero semantics vary by runtime spelling")
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
    for vector in (
        tenant + tenant + event,
        tenant + event + proto_field(3, b"a") + proto_field(4, b"b"),
        tenant + event + proto_field(6, b"unknown"),
        event,
    ):
        try:
            validate_protobuf_profile(vector)
        except EvidenceViolation:
            continue
        raise AssertionError("protobuf profile accepted invalid protected field semantics")

    # Non-minimal tag varint for field 1 (canonical 0x0a encoded as 0x8a 0x00) must fail.
    nonminimal_tag = bytes([0x8A, 0x00, 0x02]) + b"t1" + event
    try:
        validate_protobuf_profile(nonminimal_tag)
    except EvidenceViolation:
        pass
    else:
        raise AssertionError("protobuf non-minimal varint was accepted")


def prove_avro_profile() -> None:
    prove_static_schema_and_history("avro_profile", "avro:event:v1", b"historical-avro")
    admit_transport_payload(b"avro-binary-fixture")
    writer_v1 = AvroRecordSchema("Event", (AvroFieldSpec("tenant_id"), AvroFieldSpec("event_type")))
    reader_v2 = AvroRecordSchema(
        "Event",
        (
            AvroFieldSpec("tenant_id"),
            AvroFieldSpec("event_type"),
            AvroFieldSpec("severity", default_present=True, default="info"),
        ),
    )
    datum = {"tenant_id": "t1", "event_type": "alarm"}
    expected = b'{"event_type":"alarm","severity":"info","tenant_id":"t1"}'
    if avro_semantic_equivalence(writer_v1, reader_v2, datum) != expected:
        raise AssertionError("Avro writer-reader resolution is not deterministic")

    writer_v2 = reader_v2
    nullable = {"tenant_id": "t1", "event_type": "alarm", "severity": None}
    if b'"severity":null' not in avro_semantic_equivalence(writer_v2, reader_v2, nullable):
        raise AssertionError("Avro nullable enum semantics were not preserved")

    missing_required_reader = AvroRecordSchema("Event", reader_v2.fields + (AvroFieldSpec("region"),))
    try:
        resolve_avro_record(writer_v1, missing_required_reader, datum)
    except EvidenceViolation:
        pass
    else:
        raise AssertionError("Avro reader accepted missing field without default")

    ambiguous_reader = AvroRecordSchema(
        "Event",
        (
            AvroFieldSpec("tenant_id", aliases=("tenant",)),
            AvroFieldSpec("event_type", aliases=("tenant",)),
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
        "json_duplicates=blocked json_alias_collision=blocked json_numeric_mapping=canonical json_bounds=proven "
        "protobuf_nonminimal_varint=blocked protobuf_protected_duplicates=blocked protobuf_presence_enum=explicit "
        "protobuf_unknown_bytes=preserved protobuf_byte_order=noncanonical protobuf_repeated_order=preserved "
        "avro_writer_reader_resolution=explicit avro_nullable_enum=explicit avro_alias_ambiguity=blocked "
        "selection=not_selected ledger_credit=0"
    )
    for candidate, result in sorted(results.items()):
        print(f"candidate={candidate} result={result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
