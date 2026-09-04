#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import struct
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
    schema_content_sha256: str | None = None


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


def make_historical_envelope(candidate: str, schema_ref: str, payload: bytes) -> HistoricalEnvelope:
    resolve_reviewed_schema(candidate, schema_ref)
    digest = _reviewed_avro_schema_content_digest(schema_ref) if candidate == "avro_profile" else None
    return HistoricalEnvelope(candidate, schema_ref, bytes(payload), digest)


def read_historical_envelope(envelope: HistoricalEnvelope, candidate: str, schema_ref: str) -> bytes:
    if envelope.candidate != candidate or envelope.schema_ref != schema_ref:
        raise EvidenceViolation("historical profile/schema reinterpretation is forbidden")
    resolve_reviewed_schema(candidate, schema_ref)
    if candidate == "avro_profile":
        expected = _reviewed_avro_schema_content_digest(schema_ref)
        if envelope.schema_content_sha256 != expected:
            raise EvidenceViolation("historical Avro schema content digest mismatch")
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
    if value.copy_abs() > MAX_JSON_MAGNITUDE:
        raise EvidenceViolation("JSON number exceeds evidence magnitude bound")
    return value


def _depth(value: Any, current: int = 0) -> int:
    if isinstance(value, dict):
        return current + 1 if not value else max(_depth(v, current + 1) for v in value.values())
    if isinstance(value, list):
        return current + 1 if not value else max(_depth(v, current + 1) for v in value)
    return current


def _validate_unicode_scalar_string(value: str, label: str) -> None:
    if not isinstance(value, str):
        raise EvidenceViolation(f"{label} must be a string")
    for ch in value:
        code = ord(ch)
        if 0xD800 <= code <= 0xDFFF:
            raise EvidenceViolation(f"{label} contains an unpaired surrogate")


def _validate_json_unicode_scalars(value: Any) -> None:
    if isinstance(value, str):
        _validate_unicode_scalar_string(value, "JSON string")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_unicode_scalars(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_unicode_scalar_string(key, "JSON object key")
            _validate_json_unicode_scalars(item)


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
    except RecursionError as exc:
        raise EvidenceViolation("JSON nesting exceeds parser recursion safety bound") from exc
    if not isinstance(value, dict):
        raise EvidenceViolation("JSON top level must be object")
    try:
        depth = _depth(value)
        _validate_json_unicode_scalars(value)
    except RecursionError as exc:
        raise EvidenceViolation("JSON nesting exceeds traversal recursion safety bound") from exc
    if depth > MAX_JSON_DEPTH:
        raise EvidenceViolation("JSON nesting exceeds evidence depth bound")
    for aliases in JSON_ALIAS_GROUPS:
        if len(aliases.intersection(value)) > 1:
            raise EvidenceViolation("protected JSON alias collision")
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
    body = "".join(str(d) for d in digits)
    if exponent >= 0:
        body += "0" * exponent
    else:
        point = len(body) + exponent
        body = body[:point] + "." + body[point:] if point > 0 else "0." + "0" * (-point) + body
    return ("-" if sign else "") + body


def _canonical_json_value(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, str):
        _validate_unicode_scalar_string(value, "JSON string")
        return ("string", value)
    if isinstance(value, Decimal):
        return ("number", _canonical_decimal_text(value))
    if isinstance(value, list):
        return ("array", tuple(_canonical_json_value(v) for v in value))
    if isinstance(value, dict):
        for key in value:
            _validate_unicode_scalar_string(key, "JSON object key")
        return ("object", tuple((k, _canonical_json_value(value[k])) for k in sorted(value)))
    raise EvidenceViolation("unsupported JSON runtime mapping type")


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
                raise EvidenceViolation("non-minimal protobuf varint")
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
        number, wire_type = tag >> 3, tag & 7
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
            raw_value, offset = raw[offset:end], end
        elif wire_type == 2:
            length, after_len = _read_varint(raw, offset)
            end = after_len + length
            if length > MAX_MESSAGE_BYTES or end > len(raw):
                raise EvidenceViolation("protobuf length field exceeds bound or is truncated")
            raw_value, offset = raw[after_len:end], end
        elif wire_type == 5:
            end = offset + 4
            if end > len(raw):
                raise EvidenceViolation("truncated protobuf fixed32")
            raw_value, offset = raw[offset:end], end
        else:
            raise EvidenceViolation("protobuf groups/unsupported wire types forbidden")
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
    if any(counts.get(n, 0) > 1 for n in PROTO_PROTECTED_SINGULAR):
        raise EvidenceViolation("protected protobuf singular duplicated")
    if any(counts.get(n, 0) > 1 for n in PROTO_PROTECTED_ONEOF):
        raise EvidenceViolation("protected protobuf oneof member duplicated")
    if sum(1 for n in PROTO_PROTECTED_ONEOF if counts.get(n, 0)) > 1:
        raise EvidenceViolation("protected protobuf oneof collision")
    by_number = {f.number: f for f in fields if f.number in PROTO_PROTECTED_SINGULAR}
    for required in (1, 2):
        field = by_number.get(required)
        if field is None or field.wire_type != 2 or not field.raw_value:
            raise EvidenceViolation("required protobuf field missing or invalid")
    severity = by_number.get(6)
    if severity is not None and (severity.wire_type != 2 or severity.raw_value not in PROTO_SEVERITIES):
        raise EvidenceViolation("protobuf severity invalid")
    unknown = b"".join(f.raw_segment for f in fields if f.number not in PROTO_KNOWN_FIELDS)
    return fields, unknown


def protobuf_semantic_equivalence(raw: bytes) -> tuple[tuple[int, tuple[tuple[int, bytes], ...]], ...]:
    fields, _ = validate_protobuf_profile(raw)
    grouped: dict[int, list[tuple[int, bytes]]] = {}
    for field in fields:
        grouped.setdefault(field.number, []).append((field.wire_type, field.raw_value))
    return tuple((number, tuple(grouped[number])) for number in sorted(grouped))


AVRO_PRIMITIVES = frozenset({"null", "boolean", "int", "long", "float", "double", "bytes", "string"})
AVRO_PROMOTIONS: dict[str, frozenset[str]] = {
    "null": frozenset({"null"}), "boolean": frozenset({"boolean"}),
    "int": frozenset({"int", "long", "float", "double"}),
    "long": frozenset({"long", "float", "double"}),
    "float": frozenset({"float", "double"}), "double": frozenset({"double"}),
    "bytes": frozenset({"bytes", "string"}), "string": frozenset({"string", "bytes"}),
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


@dataclass(frozen=True)
class AvroUnionDatum:
    branch_index: int
    value: Any


REVIEWED_AVRO_EVENT_V1 = AvroRecordSchema("Event", (AvroFieldSpec("tenant_id", ("string",)), AvroFieldSpec("event_type", ("string",))))
REVIEWED_AVRO_EVENT_V2 = AvroRecordSchema("Event", (
    AvroFieldSpec("tenant_id", ("string",)), AvroFieldSpec("event_type", ("string",)),
    AvroFieldSpec("severity", ("string", "null"), default_present=True, default="info"),
))
REVIEWED_AVRO_SCHEMAS = {"avro:event:v1": REVIEWED_AVRO_EVENT_V1, "avro:event:v2": REVIEWED_AVRO_EVENT_V2}


def _schema_digest_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        if isinstance(value, str):
            _validate_unicode_scalar_string(value, "Avro schema default string")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EvidenceViolation("non-finite Avro schema default cannot be digested")
        return {"float_hex": value.hex()}
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    raise EvidenceViolation("unsupported Avro schema default for content digest")


def _utf8_bytes(value: str, label: str) -> bytes:
    _validate_unicode_scalar_string(value, f"Avro {label}")
    try:
        return value.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise EvidenceViolation(f"Avro {label} must be valid UTF-8") from exc


def _avro_schema_content_digest(schema: AvroRecordSchema) -> str:
    structural = {
        "name": schema.name,
        "fields": [
            {
                "name": field.name,
                "avro_types": list(field.avro_types),
                "aliases": list(field.aliases),
                "default_present": field.default_present,
                "default": _schema_digest_value(field.default) if field.default_present else None,
            }
            for field in schema.fields
        ],
    }
    serialized = json.dumps(structural, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(_utf8_bytes(serialized, "schema digest content")).hexdigest()


def _reviewed_avro_schema_content_digest(schema_ref: str) -> str:
    schema = REVIEWED_AVRO_SCHEMAS.get(schema_ref)
    if schema is None:
        raise EvidenceViolation("reviewed Avro schema ref has no structural content")
    return _avro_schema_content_digest(schema)


def _bounded_avro_name(value: str, label: str) -> None:
    if not isinstance(value, str) or not value or len(_utf8_bytes(value, label)) > MAX_AVRO_NAME_BYTES:
        raise EvidenceViolation(f"Avro {label} exceeds evidence bound")


def _int_to_f32_exact(value: int) -> float:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvidenceViolation("exact integer-to-float32 helper requires integer")
    if value == 0:
        return 0.0
    sign = 1 if value < 0 else 0
    magnitude = -value if value < 0 else value
    exponent = magnitude.bit_length() - 1
    if exponent > 127:
        raise EvidenceViolation("Avro float exceeds IEEE-754 single-precision bound")
    if exponent <= 23:
        significand = magnitude << (23 - exponent)
    else:
        shift = exponent - 23
        significand, remainder = divmod(magnitude, 1 << shift)
        half = 1 << (shift - 1)
        if remainder > half or (remainder == half and (significand & 1)):
            significand += 1
            if significand == (1 << 24):
                significand >>= 1
                exponent += 1
                if exponent > 127:
                    raise EvidenceViolation("Avro float exceeds IEEE-754 single-precision bound")
    mantissa = significand - (1 << 23)
    bits = (sign << 31) | ((exponent + 127) << 23) | mantissa
    return struct.unpack(">f", struct.pack(">I", bits))[0]


def _quantize_f32(value: Any) -> float:
    if isinstance(value, bool):
        raise EvidenceViolation("Avro float mismatch")
    if isinstance(value, int):
        return _int_to_f32_exact(value)
    if not isinstance(value, float):
        raise EvidenceViolation("Avro float mismatch")
    try:
        if not math.isfinite(value):
            raise EvidenceViolation("Avro float must be finite")
        quantized = struct.unpack(">f", struct.pack(">f", value))[0]
    except (OverflowError, ValueError, struct.error) as exc:
        raise EvidenceViolation("Avro float exceeds IEEE-754 single-precision bound") from exc
    if not math.isfinite(quantized):
        raise EvidenceViolation("Avro float quantization produced non-finite value")
    return quantized


def _materialize_avro_type(value: Any, avro_type: str) -> Any:
    if avro_type == "null":
        if value is not None: raise EvidenceViolation("Avro null mismatch")
        return None
    if avro_type == "boolean":
        if not isinstance(value, bool): raise EvidenceViolation("Avro boolean mismatch")
        return value
    if avro_type == "int":
        if not isinstance(value, int) or isinstance(value, bool) or not (-(1 << 31) <= value <= (1 << 31) - 1): raise EvidenceViolation("Avro int mismatch")
        return value
    if avro_type == "long":
        if not isinstance(value, int) or isinstance(value, bool) or not (-(1 << 63) <= value <= (1 << 63) - 1): raise EvidenceViolation("Avro long mismatch")
        return value
    if avro_type == "float":
        if not isinstance(value, (int, float)) or isinstance(value, bool): raise EvidenceViolation("Avro float mismatch")
        return _quantize_f32(value)
    if avro_type == "double":
        if not isinstance(value, (int, float)) or isinstance(value, bool): raise EvidenceViolation("Avro double mismatch")
        try: numeric = float(value)
        except (OverflowError, ValueError) as exc: raise EvidenceViolation("Avro double overflow") from exc
        if not math.isfinite(numeric): raise EvidenceViolation("Avro double must be finite")
        return numeric
    if avro_type == "bytes":
        if not isinstance(value, bytes) or len(value) > MAX_AVRO_SCALAR_BYTES: raise EvidenceViolation("Avro bytes mismatch")
        return value
    if avro_type == "string":
        if not isinstance(value, str): raise EvidenceViolation("Avro string mismatch")
        if len(_utf8_bytes(value, "string datum")) > MAX_AVRO_SCALAR_BYTES: raise EvidenceViolation("Avro string mismatch")
        return value
    raise EvidenceViolation("unsupported Avro primitive")


def _avro_value_matches_type(value: Any, avro_type: str) -> bool:
    try:
        _materialize_avro_type(value, avro_type)
        return True
    except EvidenceViolation:
        return False


def _resolve_avro_writer_value(value: Any, writer_types: tuple[str, ...]) -> tuple[str, Any]:
    if isinstance(value, AvroUnionDatum):
        if len(writer_types) <= 1:
            raise EvidenceViolation("Avro union branch marker supplied for non-union field")
        if not isinstance(value.branch_index, int) or isinstance(value.branch_index, bool) or not (0 <= value.branch_index < len(writer_types)):
            raise EvidenceViolation("Avro union branch index invalid")
        writer_type = writer_types[value.branch_index]
        return writer_type, _materialize_avro_type(value.value, writer_type)
    matches = [writer_type for writer_type in writer_types if _avro_value_matches_type(value, writer_type)]
    if not matches:
        raise EvidenceViolation("Avro datum does not match writer type")
    if len(matches) > 1:
        raise EvidenceViolation("Avro union branch is ambiguous without decoded branch index")
    writer_type = matches[0]
    return writer_type, _materialize_avro_type(value, writer_type)


def _avro_effective_writer_type(value: Any, writer_types: tuple[str, ...]) -> str:
    return _resolve_avro_writer_value(value, writer_types)[0]


def _avro_reader_type_for_writer(writer_type: str, reader_types: tuple[str, ...]) -> str:
    for reader_type in reader_types:
        if reader_type in AVRO_PROMOTIONS[writer_type]:
            return reader_type
    raise EvidenceViolation("Avro writer value has no compatible reader type")


def _promote_avro_value(value: Any, writer_type: str, reader_type: str) -> Any:
    writer_value = _materialize_avro_type(value, writer_type)
    if writer_type == reader_type:
        return writer_value
    if writer_type == "int" and reader_type == "long":
        return writer_value
    if reader_type == "float" and writer_type in {"int", "long"}:
        return _int_to_f32_exact(writer_value)
    if reader_type == "double" and writer_type in {"int", "long", "float"}:
        try: promoted = float(writer_value)
        except (OverflowError, ValueError) as exc: raise EvidenceViolation("Avro double promotion overflow") from exc
        if not math.isfinite(promoted): raise EvidenceViolation("Avro double promotion non-finite")
        return promoted
    if writer_type == "bytes" and reader_type == "string":
        try: promoted = writer_value.decode("utf-8", "strict")
        except UnicodeDecodeError as exc: raise EvidenceViolation("Avro bytes-to-string requires UTF-8") from exc
        return _materialize_avro_type(promoted, "string")
    if writer_type == "string" and reader_type == "bytes":
        return _materialize_avro_type(_utf8_bytes(writer_value, "string promotion"), "bytes")
    raise EvidenceViolation(f"unsupported Avro promotion {writer_type}->{reader_type}")


def validate_avro_schema(schema: AvroRecordSchema) -> None:
    _bounded_avro_name(schema.name, "record name")
    if len(schema.fields) > MAX_AVRO_FIELDS: raise EvidenceViolation("Avro field count exceeds bound")
    names: set[str] = set(); aliases: dict[str, str] = {}
    for field in schema.fields:
        _bounded_avro_name(field.name, "field name")
        if field.name in names: raise EvidenceViolation("duplicate Avro field")
        names.add(field.name)
        if not field.avro_types or len(set(field.avro_types)) != len(field.avro_types) or any(t not in AVRO_PRIMITIVES for t in field.avro_types): raise EvidenceViolation("invalid Avro type declaration")
        if field.default_present and not _avro_value_matches_type(field.default, field.avro_types[0]): raise EvidenceViolation("Avro default mismatch")
        if len(field.aliases) > MAX_AVRO_ALIASES_PER_FIELD: raise EvidenceViolation("Avro alias count exceeds bound")
        for alias in field.aliases:
            _bounded_avro_name(alias, "field alias")
            if alias == field.name or (alias in aliases and aliases[alias] != field.name): raise EvidenceViolation("ambiguous Avro alias")
            aliases[alias] = field.name
    if names.intersection(aliases): raise EvidenceViolation("Avro field/alias collision")


def resolve_reviewed_avro_schema(schema_ref: str, schema: AvroRecordSchema) -> AvroRecordSchema:
    resolve_reviewed_schema("avro_profile", schema_ref)
    if REVIEWED_AVRO_SCHEMAS.get(schema_ref) != schema: raise EvidenceViolation("Avro ref/schema content mismatch")
    validate_avro_schema(schema)
    return schema


def resolve_avro_record(writer: AvroRecordSchema, reader: AvroRecordSchema, datum: dict[str, Any]) -> dict[str, tuple[str, Any]]:
    validate_avro_schema(writer); validate_avro_schema(reader)
    if writer.name != reader.name: raise EvidenceViolation("Avro record identity mismatch")
    if not isinstance(datum, dict) or len(datum) > MAX_AVRO_FIELDS: raise EvidenceViolation("Avro datum width exceeds bound")
    writer_fields = {f.name: f for f in writer.fields}; datum_names = set(datum)
    if datum_names - set(writer_fields): raise EvidenceViolation("datum contains unknown writer field")
    if set(writer_fields) - datum_names: raise EvidenceViolation("datum omits writer-declared field")
    writer_materialized: dict[str, tuple[str, Any]] = {}
    for name, field in writer_fields.items():
        writer_materialized[name] = _resolve_avro_writer_value(datum[name], field.avro_types)
    resolved: dict[str, tuple[str, Any]] = {}
    for target in reader.fields:
        source_names = (target.name,) + target.aliases
        writer_matches = [n for n in source_names if n in writer_fields]
        if len(writer_matches) > 1: raise EvidenceViolation("Avro alias collision in writer schema")
        if writer_matches:
            source_name = writer_matches[0]
            writer_type, writer_value = writer_materialized[source_name]
            reader_type = _avro_reader_type_for_writer(writer_type, target.avro_types)
            promoted = _promote_avro_value(writer_value, writer_type, reader_type)
            resolved[target.name] = (reader_type, _materialize_avro_type(promoted, reader_type))
        elif target.default_present:
            resolved[target.name] = (target.avro_types[0], _materialize_avro_type(target.default, target.avro_types[0]))
        else:
            raise EvidenceViolation("Avro reader field missing without default")
    return resolved


def validate_avro_contract(value: dict[str, tuple[str, Any]]) -> None:
    for required in ("tenant_id", "event_type"):
        item = value.get(required)
        if item is None or item[0] != "string" or not isinstance(item[1], str) or not item[1]: raise EvidenceViolation("Avro Event required field invalid")
    if "severity" in value:
        t, v = value["severity"]
        if t == "null" and v is None: return
        if t == "string" and v in ("info", "warning", "critical"): return
        raise EvidenceViolation("Avro severity invalid")


def avro_semantic_equivalence(writer: AvroRecordSchema, reader: AvroRecordSchema, datum: dict[str, Any]) -> tuple[tuple[str, tuple[str, Any]], ...]:
    resolved = resolve_avro_record(writer, reader, datum)
    if reader.name == "Event": validate_avro_contract(resolved)
    return tuple((name, resolved[name]) for name in sorted(resolved))


def reviewed_avro_semantic_equivalence(writer_ref: str, writer: AvroRecordSchema, reader_ref: str, reader: AvroRecordSchema, datum: dict[str, Any]) -> tuple[tuple[str, tuple[str, Any]], ...]:
    resolve_reviewed_avro_schema(writer_ref, writer); resolve_reviewed_avro_schema(reader_ref, reader)
    return avro_semantic_equivalence(writer, reader, datum)


def prove_static_schema_and_history(candidate: str, schema_ref: str, payload: bytes) -> None:
    resolve_reviewed_schema(candidate, schema_ref)
    try: resolve_reviewed_schema(candidate, schema_ref, untrusted_message_ref="https://attacker.invalid/schema")
    except EvidenceViolation: pass
    else: raise AssertionError("dynamic schema selection accepted")
    envelope = make_historical_envelope(candidate, schema_ref, payload)
    if read_historical_envelope(envelope, candidate, schema_ref) != payload: raise AssertionError("historical bytes changed")
    other = "protobuf_profile" if candidate != "protobuf_profile" else "avro_profile"; other_ref = next(iter(REVIEWED_SCHEMA_REFS[other]))
    try: read_historical_envelope(envelope, other, other_ref)
    except EvidenceViolation: pass
    else: raise AssertionError("historical cross-profile reinterpretation accepted")


def prove_identity_only_transport() -> None:
    admit_transport_payload(b"bounded")
    try: admit_transport_payload(b"compressed", compression="gzip")
    except EvidenceViolation: pass
    else: raise AssertionError("compressed payload accepted")


def prove_json_profile() -> None:
    prove_static_schema_and_history("bounded_json_plus_json_schema_profile", "json:event:v1", b"historical-json")
    a = b'{"tenant_id":"t1","event_type":"alarm","severity":null,"payload":{"x":1.0}}'; b = b'{"payload":{"x":1e0},"event_type":"alarm","tenant_id":"t1","severity":null}'
    if canonical_json_equivalence(a) != canonical_json_equivalence(b): raise AssertionError("JSON numeric equivalence drift")
    if canonical_json_equivalence(b'{"tenant_id":"t1","event_type":"alarm","payload":{"x":-0.0}}') != canonical_json_equivalence(b'{"tenant_id":"t1","event_type":"alarm","payload":{"x":0}}'): raise AssertionError("JSON zero drift")
    da = b'{"tenant_id":"t1","event_type":"alarm","payload":{"x":9007199254740992.0}}'; db = b'{"tenant_id":"t1","event_type":"alarm","payload":{"x":9007199254740993.0}}'
    if canonical_json_equivalence(da) == canonical_json_equivalence(db): raise AssertionError("distinct decimals collapsed")
    for vector in (b'{"tenant_id":"t1","tenant_id":"t2","event_type":"alarm"}', b'{"tenant_id":"t1","tenantId":"t1","event_type":"alarm"}', b'{"tenant_id":"t1","event_type":"alarm","extra":1}', b'{"tenant_id":"t1","event_type":"alarm","severity":"unknown"}', b'{"tenant_id":"t1","event_type":"alarm","payload":9223372036854775808}', b'{"tenant_id":"t1","event_type":"alarm","payload":1e-999}', b'{"tenant_id":"\\ud800","event_type":"alarm"}', b'{"tenant_id":"t1","event_type":"alarm","payload":{"\\ud800":1}}'):
        try: canonical_json_equivalence(vector)
        except EvidenceViolation: continue
        raise AssertionError("JSON forbidden vector accepted")
    deeply_nested = b'{"tenant_id":"t1","event_type":"alarm","payload":' + (b'[' * 900) + b'0' + (b']' * 900) + b'}'
    if len(deeply_nested) > MAX_MESSAGE_BYTES: raise AssertionError("deep JSON falsification vector exceeds transport fixture bound")
    try: canonical_json_equivalence(deeply_nested)
    except EvidenceViolation: pass
    except RecursionError as exc: raise AssertionError("JSON recursion escaped fail-closed boundary") from exc
    else: raise AssertionError("deep JSON recursion vector accepted")


def prove_protobuf_profile() -> None:
    prove_static_schema_and_history("protobuf_profile", "proto:event:v1", b"historical-protobuf")
    tenant, event, severity = proto_field(1,b"t1"), proto_field(2,b"alarm"), proto_field(6,b"warning")
    ra, rb, unknown = proto_field(5,b"a"), proto_field(5,b"b"), proto_field(100,b"future")
    raw_a = tenant+event+severity+ra+rb+unknown; raw_b = unknown+event+tenant+severity+ra+rb
    _, preserved = validate_protobuf_profile(raw_a)
    if preserved != unknown or protobuf_semantic_equivalence(raw_a) != protobuf_semantic_equivalence(raw_b): raise AssertionError("protobuf forward/equivalence failure")
    if protobuf_semantic_equivalence(tenant+event+ra+rb) == protobuf_semantic_equivalence(tenant+event+rb+ra): raise AssertionError("protobuf repeated order erased")
    for vector in (tenant+tenant+event, tenant+event+proto_field(3,b"a")+proto_field(3,b"b"), tenant+event+proto_field(3,b"a")+proto_field(4,b"b"), tenant+event+proto_field(6,b"unknown"), event):
        try: validate_protobuf_profile(vector)
        except EvidenceViolation: continue
        raise AssertionError("protobuf invalid vector accepted")
    try: validate_protobuf_profile(bytes([0x8A,0x00,0x02])+b"t1"+event)
    except EvidenceViolation: pass
    else: raise AssertionError("nonminimal varint accepted")
    try: scan_bounded_protobuf(_encode_varint(7<<3)+(bytes([0x80])*9)+bytes([0x02]))
    except EvidenceViolation: pass
    else: raise AssertionError("uint64 overflow accepted")


def prove_avro_profile() -> None:
    prove_static_schema_and_history("avro_profile", "avro:event:v1", b"historical-avro"); admit_transport_payload(b"avro")
    writer_v1, reader_v2 = REVIEWED_AVRO_EVENT_V1, REVIEWED_AVRO_EVENT_V2
    resolve_reviewed_avro_schema("avro:event:v1", writer_v1); resolve_reviewed_avro_schema("avro:event:v2", reader_v2)
    historical = make_historical_envelope("avro_profile", "avro:event:v1", b"historical-avro")
    rebound = AvroRecordSchema("Event", writer_v1.fields + (AvroFieldSpec("rebound", ("string",), default_present=True, default="x"),))
    original_schema = REVIEWED_AVRO_SCHEMAS["avro:event:v1"]
    try:
        REVIEWED_AVRO_SCHEMAS["avro:event:v1"] = rebound
        try: read_historical_envelope(historical, "avro_profile", "avro:event:v1")
        except EvidenceViolation: pass
        else: raise AssertionError("historical Avro envelope accepted same-ref schema-content rebind")
    finally:
        REVIEWED_AVRO_SCHEMAS["avro:event:v1"] = original_schema
    mutated = AvroRecordSchema("Event", writer_v1.fields+(AvroFieldSpec("injected",("string",),default_present=True,default="x"),))
    try: resolve_reviewed_avro_schema("avro:event:v1", mutated)
    except EvidenceViolation: pass
    else: raise AssertionError("Avro ref/content swap accepted")
    datum = {"tenant_id":"t1","event_type":"alarm"}
    expected = (("event_type",("string","alarm")),("severity",("string","info")),("tenant_id",("string","t1")))
    if reviewed_avro_semantic_equivalence("avro:event:v1",writer_v1,"avro:event:v2",reader_v2,datum) != expected: raise AssertionError("reviewed Avro resolution drift")
    try: reviewed_avro_semantic_equivalence("avro:event:v2",reader_v2,"avro:event:v2",reader_v2,datum)
    except EvidenceViolation: pass
    else: raise AssertionError("writer field omission fabricated by reader default")
    writer_projection = AvroRecordSchema("Projection", (AvroFieldSpec("kept", ("string",)), AvroFieldSpec("writer_only", ("string",))))
    reader_projection = AvroRecordSchema("Projection", (AvroFieldSpec("kept", ("string",)),))
    for invalid_writer_only in ("x" * (MAX_AVRO_SCALAR_BYTES + 1), object()):
        try: avro_semantic_equivalence(writer_projection, reader_projection, {"kept":"ok", "writer_only":invalid_writer_only})
        except EvidenceViolation: pass
        else: raise AssertionError("writer-only Avro datum bypassed writer type/bound validation")
    nullable = AvroRecordSchema("Event",(AvroFieldSpec("tenant_id",("string",)),AvroFieldSpec("event_type",("string",)),AvroFieldSpec("severity",("null","string"),default_present=True,default=None)))
    if ("severity",("null",None)) not in avro_semantic_equivalence(nullable,nullable,{"tenant_id":"t1","event_type":"alarm","severity":None}): raise AssertionError("nullable semantics lost")
    invalid_event = AvroRecordSchema("Event",(AvroFieldSpec("value",("string",)),))
    try: avro_semantic_equivalence(invalid_event,invalid_event,{"value":"x"})
    except EvidenceViolation: pass
    else: raise AssertionError("Event invariants bypassed")
    incompatible = AvroRecordSchema("Event",(AvroFieldSpec("tenant_id",("boolean",)),AvroFieldSpec("event_type",("string",))))
    try: resolve_avro_record(incompatible,reader_v2,{"tenant_id":True,"event_type":"alarm"})
    except EvidenceViolation: pass
    else: raise AssertionError("Avro incompatible types accepted")
    int_writer = AvroRecordSchema("Metric",(AvroFieldSpec("value",("int",)),)); double_reader = AvroRecordSchema("Metric",(AvroFieldSpec("value",("double",)),)); double_writer = AvroRecordSchema("Metric",(AvroFieldSpec("value",("double",)),))
    if avro_semantic_equivalence(int_writer,double_reader,{"value":1}) != avro_semantic_equivalence(double_writer,double_reader,{"value":1.0}): raise AssertionError("double promotion drift")
    float_reader = AvroRecordSchema("Metric",(AvroFieldSpec("value",("float",)),)); float_writer = AvroRecordSchema("Metric",(AvroFieldSpec("value",("float",)),))
    if avro_semantic_equivalence(int_writer,float_reader,{"value":16777217}) != avro_semantic_equivalence(float_writer,float_reader,{"value":16777217.0}): raise AssertionError("float32 promotion width drift")
    expected_f32 = struct.unpack(">f", struct.pack(">f", 16777217.0))[0]
    if avro_semantic_equivalence(int_writer,float_reader,{"value":16777217}) != (("value",("float",expected_f32)),): raise AssertionError("Avro float not single precision")
    long_writer = AvroRecordSchema("Metric", (AvroFieldSpec("value", ("long",)),))
    double_round_vector = 4611686293305294849
    expected_direct = 4611686568183267328.0
    if avro_semantic_equivalence(long_writer, float_reader, {"value": double_round_vector}) != (("value", ("float", expected_direct)),): raise AssertionError("Avro long-to-float double rounding drift")
    union_writer = AvroRecordSchema("UnionMetric", (AvroFieldSpec("value", ("float", "double")),))
    union_reader = AvroRecordSchema("UnionMetric", (AvroFieldSpec("value", ("double",)),))
    try: avro_semantic_equivalence(union_writer, union_reader, {"value": 16777217.0})
    except EvidenceViolation: pass
    else: raise AssertionError("ambiguous Avro union inferred branch from Python runtime value")
    union_float = avro_semantic_equivalence(union_writer, union_reader, {"value": AvroUnionDatum(0, 16777217.0)})
    union_double = avro_semantic_equivalence(union_writer, union_reader, {"value": AvroUnionDatum(1, 16777217.0)})
    if union_float != (("value", ("double", 16777216.0)),): raise AssertionError("Avro float union branch was not preserved before widening")
    if union_double != (("value", ("double", 16777217.0)),): raise AssertionError("Avro double union branch was not preserved")
    if union_float == union_double: raise AssertionError("distinct Avro union branches collapsed")
    selected_union_writer = AvroRecordSchema("Selected", (AvroFieldSpec("value", ("string", "int")),))
    selected_union_reader = AvroRecordSchema("Selected", (AvroFieldSpec("value", ("long",)),))
    if avro_semantic_equivalence(selected_union_writer, selected_union_reader, {"value": AvroUnionDatum(1, 7)}) != (("value", ("long", 7)),): raise AssertionError("unselected incompatible Avro union branch blocked selected compatible branch")
    try: avro_semantic_equivalence(selected_union_writer, selected_union_reader, {"value": AvroUnionDatum(0, "x")})
    except EvidenceViolation: pass
    else: raise AssertionError("selected incompatible Avro union branch was accepted")
    for invalid_float in (True, "1.0"):
        try: avro_semantic_equivalence(float_writer,float_reader,{"value":invalid_float})
        except EvidenceViolation: pass
        else: raise AssertionError("Avro float accepted non-numeric runtime mapping")
    string_writer = AvroRecordSchema("Text", (AvroFieldSpec("value", ("string",)),))
    try: avro_semantic_equivalence(string_writer, string_writer, {"value": "\ud800"})
    except EvidenceViolation: pass
    except UnicodeEncodeError as exc: raise AssertionError("Avro invalid UTF-8 string escaped fail-closed boundary") from exc
    else: raise AssertionError("Avro invalid UTF-8 string accepted")
    try: avro_semantic_equivalence(double_writer,double_reader,{"value":10**10000})
    except EvidenceViolation: pass
    else: raise AssertionError("Avro double overflow not fail-closed")
    bytes_writer = AvroRecordSchema("Text",(AvroFieldSpec("value",("bytes",)),)); string_reader = AvroRecordSchema("Text",(AvroFieldSpec("value",("string",)),))
    if avro_semantic_equivalence(bytes_writer,string_reader,{"value":b"hello"}) != (("value",("string","hello")),): raise AssertionError("bytes/string promotion drift")
    try: avro_semantic_equivalence(bytes_writer,string_reader,{"value":b"\xff"})
    except EvidenceViolation: pass
    else: raise AssertionError("invalid UTF-8 promotion accepted")
    try: resolve_avro_record(writer_v1,reader_v2,{"tenant_id":"x"*(MAX_AVRO_SCALAR_BYTES+1),"event_type":"alarm"})
    except EvidenceViolation: pass
    else: raise AssertionError("oversized Avro scalar accepted")
    missing_reader = AvroRecordSchema("Event",reader_v2.fields+(AvroFieldSpec("region",("string",)),))
    try: resolve_avro_record(writer_v1,missing_reader,datum)
    except EvidenceViolation: pass
    else: raise AssertionError("missing reader default accepted")
    ambiguous = AvroRecordSchema("Event",(AvroFieldSpec("tenant_id",("string",),aliases=("tenant",)),AvroFieldSpec("event_type",("string",),aliases=("tenant",))))
    try: validate_avro_schema(ambiguous)
    except EvidenceViolation: pass
    else: raise AssertionError("Avro alias ambiguity accepted")


def evaluate() -> dict[str, str]:
    prove_identity_only_transport(); prove_json_profile(); prove_protobuf_profile(); prove_avro_profile()
    return {"bounded_json_plus_json_schema_profile": ELIGIBLE, "protobuf_profile": ELIGIBLE, "avro_profile": ELIGIBLE}


def main() -> int:
    results = evaluate()
    print("d4b_wire_schema_candidate_source=PASS candidates=3 concrete_eligible=3 identity_only_transport=bounded dynamic_schema_selection=blocked historical_profile_reinterpretation=blocked json_duplicates=blocked json_alias_collision=blocked json_unicode_scalars=fail_closed json_numeric_mapping=context_independent json_magnitude=context_independent json_depth_recursion=fail_closed json_distinct_decimals=preserved json_bounds=proven protobuf_nonminimal_varint=blocked protobuf_uint64_overflow=blocked protobuf_protected_duplicates=blocked protobuf_oneof_duplicate=blocked protobuf_presence_enum=explicit protobuf_unknown_bytes=preserved protobuf_byte_order=noncanonical protobuf_repeated_order=preserved avro_schema_ref_content=binding_exact avro_historical_schema_digest=sha256_bound avro_writer_fields=required avro_writer_only_fields=validated avro_union_branch=explicit avro_selected_union_branch=authoritative avro_string_utf8=fail_closed avro_float_overflow=fail_closed avro_float_width=ieee754_binary32 avro_long_to_float=direct_round_to_binary32 avro_float_runtime_mapping=type_strict avro_writer_reader_resolution=explicit avro_type_compatibility=selected_branch avro_promotions=reader_canonicalized avro_event_contract=scoped avro_datum_bounds=proven avro_nullable_enum=explicit avro_alias_ambiguity=blocked selection=not_selected ledger_credit=0")
    for candidate, result in sorted(results.items()): print(f"candidate={candidate} result={result}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
