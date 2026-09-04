#!/usr/bin/env python3
from __future__ import annotations

import decimal
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "assurance" / "d4b_wire_schema"))
import evaluate_candidates as evaluator
import validate_source_evidence as validator


def snapshot() -> dict[Path, object]:
    paths = (validator.MANIFEST, validator.PLAN, validator.LEDGER, validator.STATE)
    return {path: json.loads((ROOT / path).read_text(encoding="utf-8")) for path in paths}


def obj(data: dict[Path, object], path: Path) -> dict:
    value = data[path]
    assert isinstance(value, dict)
    return value


def mutate_and_validate(mutator) -> list[str]:
    data = snapshot()
    mutator(data)
    with TemporaryDirectory() as td:
        root = Path(td)
        for path, value in data.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, bytes):
                target.write_bytes(value)
            else:
                target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return validator.validate(root)


def must_fail(mutator, fragment: str) -> None:
    errors = mutate_and_validate(mutator)
    if not any(fragment in error for error in errors):
        raise AssertionError(f"expected {fragment!r}, got {errors!r}")


def inject_duplicate_selection(data: dict[Path, object]) -> None:
    raw = (ROOT / validator.MANIFEST).read_bytes()
    needle = b'  "selection_state": "not_selected",\n'
    if raw.count(needle) != 1:
        raise AssertionError("selection_state line not unique")
    data[validator.MANIFEST] = raw.replace(needle, b'  "selection_state": "selected",\n' + needle, 1)


def prove_behavior_falsifications() -> None:
    try:
        evaluator.admit_transport_payload(b"compressed", compression="gzip")
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("compressed input accepted without selected decompression profile")

    try:
        evaluator.resolve_reviewed_schema("protobuf_profile", "proto:event:v1", untrusted_message_ref="https://attacker.invalid/schema")
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("untrusted message schema selection accepted")

    historical = evaluator.HistoricalEnvelope("bounded_json_plus_json_schema_profile", "json:event:v1", b"old")
    try:
        evaluator.read_historical_envelope(historical, "protobuf_profile", "proto:event:v1")
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("historical cross-profile reinterpretation accepted")

    for raw in (
        b'{"tenant_id":"t1","tenant_id":"t2","event_type":"alarm"}',
        b'{"tenant_id":"t1","tenantId":"t1","event_type":"alarm"}',
    ):
        try:
            evaluator.canonical_json_equivalence(raw)
        except evaluator.EvidenceViolation:
            pass
        else:
            raise AssertionError("JSON ambiguity accepted")

    too_deep = b'{"tenant_id":"t1","event_type":"alarm","payload":{"a":{"b":{"c":{"d":{"e":{"f":{"g":{"h":1}}}}}}}}}'
    try:
        evaluator.canonical_json_equivalence(too_deep)
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("JSON excessive nesting accepted")

    if evaluator.canonical_json_equivalence(b'{"tenant_id":"t1","event_type":"alarm","payload":{"x":1.0}}') != evaluator.canonical_json_equivalence(b'{"event_type":"alarm","payload":{"x":1e0},"tenant_id":"t1"}'):
        raise AssertionError("JSON numeric spelling changed canonical semantics")
    distinct_a = b'{"tenant_id":"t1","event_type":"alarm","payload":{"x":9007199254740992.0}}'
    distinct_b = b'{"tenant_id":"t1","event_type":"alarm","payload":{"x":9007199254740993.0}}'
    if evaluator.canonical_json_equivalence(distinct_a) == evaluator.canonical_json_equivalence(distinct_b):
        raise AssertionError("distinct bounded JSON decimals collapsed")
    with decimal.localcontext() as ctx:
        ctx.prec = 10
        if evaluator.canonical_json_equivalence(distinct_a) == evaluator.canonical_json_equivalence(distinct_b):
            raise AssertionError("ambient Decimal context collapsed distinct bounded decimals")
        if evaluator.canonical_json_equivalence(b'{"tenant_id":"t1","event_type":"alarm","payload":{"x":1.2300}}') != evaluator.canonical_json_equivalence(b'{"tenant_id":"t1","event_type":"alarm","payload":{"x":1.23}}'):
            raise AssertionError("ambient Decimal context changed exact canonical spelling")

    tenant = evaluator.proto_field(1, b"t1")
    event = evaluator.proto_field(2, b"alarm")
    for vector in (
        tenant + tenant + event,
        tenant + event + evaluator.proto_field(3, b"a") + evaluator.proto_field(3, b"b"),
        tenant + event + evaluator.proto_field(3, b"a") + evaluator.proto_field(4, b"b"),
    ):
        try:
            evaluator.validate_protobuf_profile(vector)
        except evaluator.EvidenceViolation:
            continue
        raise AssertionError("protobuf duplicate/oneof ambiguity accepted")

    nonminimal_tag = bytes([0x8A, 0x00, 0x02]) + b"t1" + event
    try:
        evaluator.validate_protobuf_profile(nonminimal_tag)
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("protobuf non-minimal tag varint accepted")

    overflow_scalar = evaluator._encode_varint(7 << 3) + (bytes([0x80]) * 9) + bytes([0x02])
    try:
        evaluator.scan_bounded_protobuf(overflow_scalar)
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("protobuf uint64-overflow varint accepted")

    for invalid in (event, tenant + event + evaluator.proto_field(6, b"invalid")):
        try:
            evaluator.validate_protobuf_profile(invalid)
        except evaluator.EvidenceViolation:
            pass
        else:
            raise AssertionError("protobuf required/enum semantics weakened")

    unknown = evaluator.proto_field(123, b"future")
    _, preserved = evaluator.validate_protobuf_profile(tenant + event + unknown)
    if preserved != unknown:
        raise AssertionError("protobuf unknown bytes changed")
    if evaluator.protobuf_semantic_equivalence(tenant + event + unknown) != evaluator.protobuf_semantic_equivalence(unknown + event + tenant):
        raise AssertionError("protobuf semantic equivalence depends on distinct-field order")

    repeated_a = evaluator.proto_field(5, b"a")
    repeated_b = evaluator.proto_field(5, b"b")
    if evaluator.protobuf_semantic_equivalence(tenant + event + repeated_a + repeated_b) == evaluator.protobuf_semantic_equivalence(tenant + event + repeated_b + repeated_a):
        raise AssertionError("protobuf repeated occurrence order was erased")

    mutated_reviewed = evaluator.AvroRecordSchema(
        "Event",
        evaluator.REVIEWED_AVRO_EVENT_V1.fields + (evaluator.AvroFieldSpec("injected", ("string",), default_present=True, default="x"),),
    )
    try:
        evaluator.resolve_reviewed_avro_schema("avro:event:v1", mutated_reviewed)
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("reviewed Avro ref accepted different schema content")

    try:
        evaluator.reviewed_avro_semantic_equivalence(
            "avro:event:v2",
            evaluator.REVIEWED_AVRO_EVENT_V2,
            "avro:event:v2",
            evaluator.REVIEWED_AVRO_EVENT_V2,
            {"tenant_id": "t1", "event_type": "alarm"},
        )
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("reader default fabricated a writer-declared Avro field")

    writer = evaluator.AvroRecordSchema(
        "Event",
        (
            evaluator.AvroFieldSpec("tenant_id", ("string",)),
            evaluator.AvroFieldSpec("event_type", ("string",)),
        ),
    )
    ambiguous = evaluator.AvroRecordSchema(
        "Event",
        (
            evaluator.AvroFieldSpec("tenant_id", ("string",), aliases=("legacy",)),
            evaluator.AvroFieldSpec("event_type", ("string",), aliases=("legacy",)),
        ),
    )
    try:
        evaluator.validate_avro_schema(ambiguous)
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("Avro ambiguous alias accepted")

    reader = evaluator.AvroRecordSchema("Event", writer.fields + (evaluator.AvroFieldSpec("region", ("string",)),))
    try:
        evaluator.resolve_avro_record(writer, reader, {"tenant_id": "t1", "event_type": "alarm"})
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("Avro reader-only field without default accepted")

    string_reader = evaluator.AvroRecordSchema(
        "Event",
        (
            evaluator.AvroFieldSpec("tenant_id", ("string",)),
            evaluator.AvroFieldSpec("event_type", ("string",)),
        ),
    )
    boolean_writer = evaluator.AvroRecordSchema(
        "Event",
        (
            evaluator.AvroFieldSpec("tenant_id", ("boolean",)),
            evaluator.AvroFieldSpec("event_type", ("string",)),
        ),
    )
    try:
        evaluator.resolve_avro_record(boolean_writer, string_reader, {"tenant_id": True, "event_type": "alarm"})
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("Avro incompatible field types accepted")

    int_writer = evaluator.AvroRecordSchema("Metric", (evaluator.AvroFieldSpec("value", ("int",)),))
    double_reader = evaluator.AvroRecordSchema("Metric", (evaluator.AvroFieldSpec("value", ("double",)),))
    double_writer = evaluator.AvroRecordSchema("Metric", (evaluator.AvroFieldSpec("value", ("double",)),))
    if evaluator.avro_semantic_equivalence(int_writer, double_reader, {"value": 1}) != evaluator.avro_semantic_equivalence(double_writer, double_reader, {"value": 1.0}):
        raise AssertionError("Avro numeric promotion failed to materialize reader representation")

    float_reader = evaluator.AvroRecordSchema("Metric", (evaluator.AvroFieldSpec("value", ("float",)),))
    float_writer = evaluator.AvroRecordSchema("Metric", (evaluator.AvroFieldSpec("value", ("float",)),))
    promoted_float = evaluator.avro_semantic_equivalence(int_writer, float_reader, {"value": 16777217})
    native_float = evaluator.avro_semantic_equivalence(float_writer, float_reader, {"value": 16777216.0})
    if promoted_float != native_float or promoted_float != (("value", ("float", 16777216.0)),):
        raise AssertionError("Avro float equivalence did not materialize IEEE-754 binary32 reader width")
    if evaluator.avro_semantic_equivalence(float_writer, float_reader, {"value": 16777217.0}) != native_float:
        raise AssertionError("Avro writer float was not quantized to IEEE-754 binary32 before equivalence")

    try:
        evaluator.avro_semantic_equivalence(double_writer, double_reader, {"value": 10**10000})
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("Avro oversized float/double input did not fail closed")

    bytes_writer = evaluator.AvroRecordSchema("Text", (evaluator.AvroFieldSpec("value", ("bytes",)),))
    text_reader = evaluator.AvroRecordSchema("Text", (evaluator.AvroFieldSpec("value", ("string",)),))
    if evaluator.avro_semantic_equivalence(bytes_writer, text_reader, {"value": b"hello"}) != (("value", ("string", "hello")),):
        raise AssertionError("Avro bytes-to-string promotion failed to materialize reader representation")
    try:
        evaluator.avro_semantic_equivalence(bytes_writer, text_reader, {"value": b"\xff"})
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("Avro invalid UTF-8 bytes-to-string promotion accepted")

    try:
        evaluator.resolve_avro_record(writer, string_reader, {"tenant_id": "x" * (evaluator.MAX_AVRO_SCALAR_BYTES + 1), "event_type": "alarm"})
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("Avro oversized scalar accepted")

    too_many_fields = tuple(evaluator.AvroFieldSpec(f"f{i}", ("string",)) for i in range(evaluator.MAX_AVRO_FIELDS + 1))
    try:
        evaluator.validate_avro_schema(evaluator.AvroRecordSchema("TooWide", too_many_fields))
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("Avro oversized schema field inventory accepted")

    nullable_schema = evaluator.AvroRecordSchema(
        "Event",
        (
            evaluator.AvroFieldSpec("tenant_id", ("string",)),
            evaluator.AvroFieldSpec("event_type", ("string",)),
            evaluator.AvroFieldSpec("severity", ("null", "string"), default_present=True, default=None),
        ),
    )
    encoded = evaluator.avro_semantic_equivalence(nullable_schema, nullable_schema, {"tenant_id": "t1", "event_type": "alarm", "severity": None})
    if ("severity", ("null", None)) not in encoded:
        raise AssertionError("Avro nullable enum semantics lost")


def main() -> int:
    if evaluator.evaluate() != validator.EXPECTED_RESULTS:
        raise AssertionError("candidate evaluator result drift")
    errors = validator.validate(ROOT)
    if errors:
        raise AssertionError(f"canonical source evidence invalid: {errors!r}")

    must_fail(lambda d: obj(d, validator.MANIFEST).__setitem__("candidate", "protobuf_profile"), "source manifest exact key schema drift")
    must_fail(inject_duplicate_selection, "duplicate JSON member 'selection_state'")
    must_fail(lambda d: obj(d, validator.MANIFEST).__setitem__("selection_state", "selected"), "must not select D4-B wire profile")
    must_fail(lambda d: obj(d, validator.MANIFEST).__setitem__("selection_authority", "granted"), "selection authority escalation")
    must_fail(lambda d: obj(d, validator.MANIFEST).__setitem__("current_run_auto_credit", True), "must not auto-credit ledger")
    must_fail(lambda d: obj(d, validator.MANIFEST)["ledger_credit"].append("canonical_bounded_serialization_profile"), "must not auto-credit ledger")
    must_fail(lambda d: obj(d, validator.MANIFEST)["candidate_results"].__setitem__("protobuf_profile", "selected"), "concrete candidate result inventory drift")
    must_fail(lambda d: obj(d, validator.MANIFEST).__setitem__("equivalent_reviewed_profile", "eligible_for_evidence_execution"), "equivalent candidate class must remain unevaluated")
    must_fail(lambda d: obj(d, validator.MANIFEST)["required_proofs"].pop(), "required proof inventory drift")
    must_fail(lambda d: obj(d, validator.MANIFEST)["candidate_profile_requirements"]["bounded_json_plus_json_schema_profile"].remove("decimal_canonicalization_is_context_independent_and_constructed_from_exact_decimal_tuple"), "candidate requirement drift for bounded_json_plus_json_schema_profile")
    must_fail(lambda d: obj(d, validator.MANIFEST)["candidate_profile_requirements"]["protobuf_profile"].remove("protected_oneof_duplicate_occurrences_and_cross_member_collisions_fail_closed_before_generated_binding_resolution"), "candidate requirement drift for protobuf_profile")
    must_fail(lambda d: obj(d, validator.MANIFEST)["candidate_profile_requirements"]["avro_profile"].remove("reviewed_avro_schema_reference_is_bound_to_exact_reviewed_schema_content_before_resolution"), "candidate requirement drift for avro_profile")
    must_fail(lambda d: obj(d, validator.MANIFEST)["candidate_profile_requirements"]["avro_profile"].remove("writer_declared_fields_must_be_present_in_datum_and_reader_defaults_apply_only_when_field_is_absent_from_writer_schema"), "candidate requirement drift for avro_profile")
    must_fail(lambda d: obj(d, validator.MANIFEST)["candidate_profile_requirements"]["avro_profile"].remove("avro_float_writer_and_reader_values_are_materialized_at_ieee754_binary32_width_before_equivalence"), "candidate requirement drift for avro_profile")
    must_fail(lambda d: obj(d, validator.MANIFEST)["candidate_profile_requirements"]["avro_profile"].remove("float_double_admission_and_promotion_overflow_fail_closed_as_evidence_violation"), "candidate requirement drift for avro_profile")
    must_fail(lambda d: obj(d, validator.MANIFEST)["candidate_profile_requirements"]["avro_profile"].remove("allowed_writer_reader_promotions_are_applied_to_reader_representation_before_equivalence"), "candidate requirement drift for avro_profile")
    must_fail(lambda d: obj(d, validator.MANIFEST)["candidate_profile_requirements"]["avro_profile"].remove("datum_processing_is_bounded_and_canonicalized_structurally_without_unrestricted_recursive_json_serialization"), "candidate requirement drift for avro_profile")
    must_fail(lambda d: obj(d, validator.MANIFEST)["official_source_facts"].pop(), "official source fact inventory drift")
    must_fail(lambda d: obj(d, validator.MANIFEST)["source_assertions"].remove("avro_reviewed_schema_reference_is_structurally_bound_to_exact_reviewed_schema_content"), "source assertion inventory drift")
    must_fail(lambda d: obj(d, validator.MANIFEST)["source_assertions"].remove("avro_writer_declared_fields_cannot_be_fabricated_from_reader_defaults"), "source assertion inventory drift")
    must_fail(lambda d: obj(d, validator.MANIFEST)["source_assertions"].remove("avro_float_reader_and_writer_semantics_are_canonicalized_at_ieee754_binary32_width"), "source assertion inventory drift")
    must_fail(lambda d: obj(d, validator.MANIFEST)["source_assertions"].remove("avro_float_double_overflow_is_caught_and_fails_closed"), "source assertion inventory drift")
    must_fail(lambda d: obj(d, validator.MANIFEST)["source_assertions"].remove("json_numeric_normalization_is_bounded_decimal_context_independent_and_runtime_independent_within_the_evidence_profile"), "source assertion inventory drift")
    must_fail(lambda d: obj(d, validator.MANIFEST)["source_assertions"].remove("avro_allowed_promotions_materialize_reader_representation_before_semantic_equivalence"), "source assertion inventory drift")
    must_fail(lambda d: obj(d, validator.MANIFEST)["source_assertions"].remove("avro_schema_and_datum_resource_bounds_are_enforced_before_structural_equivalence"), "source assertion inventory drift")
    must_fail(lambda d: obj(d, validator.LEDGER).__setitem__("candidate", "protobuf_profile"), "D4-B ledger selection drift")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("gate_state", "accepted"), "D4 gate escalation")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("canonical_product_implementation_authority", "granted"), "Product authority escalation")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("wave4_implementation_authority", "granted"), "Wave4 authority escalation")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("production_authority", "granted"), "production authority escalation")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("c3_numeric_topology_authority", "selected"), "C3 authority escalation")

    prove_behavior_falsifications()
    print(
        "d4b_wire_schema_source_falsification=PASS duplicate_json=blocked hidden_selection=blocked "
        "auto_credit=blocked candidate_promotion=blocked proof_weakening=blocked source_fact_drift=blocked "
        "compression_without_profile=blocked dynamic_schema_selection=blocked historical_cross_profile=blocked "
        "json_bounds=blocked json_numeric_runtime_drift=blocked json_decimal_context_drift=blocked "
        "protobuf_nonminimal_varint=blocked protobuf_uint64_overflow=blocked protobuf_last_wins_override=blocked "
        "protobuf_oneof_same_member_duplicate=blocked protobuf_presence_enum_weakening=blocked "
        "protobuf_unknown_preservation=proven protobuf_byte_order_authority=blocked protobuf_repeated_order_loss=blocked "
        "avro_schema_ref_content_swap=blocked avro_writer_field_omission=blocked avro_float_width=binary32 avro_float_overflow=blocked "
        "avro_alias_ambiguity=blocked avro_missing_default=blocked avro_type_incompatibility=blocked "
        "avro_promotion_representation=proven avro_invalid_utf8_promotion=blocked avro_scalar_bound=blocked "
        "avro_schema_width_bound=blocked avro_nullable_semantics=proven ledger_selection=blocked d4_authority_escalation=blocked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
