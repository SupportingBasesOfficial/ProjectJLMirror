#!/usr/bin/env python3
from __future__ import annotations

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
        evaluator.resolve_reviewed_schema(
            "protobuf_profile",
            "proto:event:v1",
            untrusted_message_ref="https://attacker.invalid/schema",
        )
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

    tenant = evaluator.proto_field(1, b"t1")
    event = evaluator.proto_field(2, b"alarm")
    try:
        evaluator.validate_protobuf_profile(tenant + tenant + event)
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("protobuf protected duplicate accepted")

    nonminimal_tag = bytes([0x8A, 0x00, 0x02]) + b"t1" + event
    try:
        evaluator.validate_protobuf_profile(nonminimal_tag)
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("protobuf non-minimal tag varint accepted")

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

    writer = evaluator.AvroRecordSchema("Event", (evaluator.AvroFieldSpec("tenant_id"), evaluator.AvroFieldSpec("event_type")))
    ambiguous = evaluator.AvroRecordSchema(
        "Event",
        (
            evaluator.AvroFieldSpec("tenant_id", aliases=("legacy",)),
            evaluator.AvroFieldSpec("event_type", aliases=("legacy",)),
        ),
    )
    try:
        evaluator.validate_avro_schema(ambiguous)
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("Avro ambiguous alias accepted")

    reader = evaluator.AvroRecordSchema("Event", writer.fields + (evaluator.AvroFieldSpec("region"),))
    try:
        evaluator.resolve_avro_record(writer, reader, {"tenant_id": "t1", "event_type": "alarm"})
    except evaluator.EvidenceViolation:
        pass
    else:
        raise AssertionError("Avro reader-only field without default accepted")

    nullable_schema = evaluator.AvroRecordSchema(
        "Event",
        (
            evaluator.AvroFieldSpec("tenant_id"),
            evaluator.AvroFieldSpec("event_type"),
            evaluator.AvroFieldSpec("severity", default_present=True, default=None),
        ),
    )
    encoded = evaluator.avro_semantic_equivalence(
        nullable_schema,
        nullable_schema,
        {"tenant_id": "t1", "event_type": "alarm", "severity": None},
    )
    if b'"severity":null' not in encoded:
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
    must_fail(lambda d: obj(d, validator.MANIFEST)["candidate_profile_requirements"]["protobuf_profile"].remove("bounded_wire_predecoder_rejects_nonminimal_varints_and_reserved_field_numbers"), "candidate requirement drift for protobuf_profile")
    must_fail(lambda d: obj(d, validator.MANIFEST)["candidate_profile_requirements"]["protobuf_profile"].remove("repeated_field_occurrence_order_is_preserved_within_each_field_number_during_semantic_normalization"), "candidate requirement drift for protobuf_profile")
    must_fail(lambda d: obj(d, validator.MANIFEST)["official_source_facts"].pop(), "official source fact inventory drift")
    must_fail(lambda d: obj(d, validator.MANIFEST)["source_assertions"].remove("historical_payload_profile_and_schema_binding_prevents_cross_profile_reinterpretation"), "source assertion inventory drift")
    must_fail(lambda d: obj(d, validator.MANIFEST)["source_assertions"].remove("unselected_compression_is_rejected_so_decompression_work_is_zero_and_bounded"), "source assertion inventory drift")
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
        "json_bounds=blocked json_numeric_runtime_drift=blocked protobuf_nonminimal_varint=blocked "
        "protobuf_last_wins_override=blocked protobuf_presence_enum_weakening=blocked protobuf_unknown_preservation=proven "
        "protobuf_byte_order_authority=blocked protobuf_repeated_order_loss=blocked "
        "avro_alias_ambiguity=blocked avro_missing_default=blocked avro_nullable_semantics=proven "
        "ledger_selection=blocked d4_authority_escalation=blocked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
