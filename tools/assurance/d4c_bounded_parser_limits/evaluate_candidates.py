#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import zlib
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

CANDIDATES = (
    "contract_bound_application_limits_with_transport_precheck",
    "bounded_envelope_codec_profile",
    "layered_transport_and_application_bounds_profile",
)

TEST_LIMIT_PROFILE = "bounded_parser_fixture_only_noncanonical"
TEST_MAX_WIRE_BYTES = 4096
TEST_MAX_DECOMPRESSED_BYTES = 8192
TEST_MAX_BATCH_ITEMS = 4
TEST_MAX_NESTING_DEPTH = 6
TEST_MAX_STRING_CHARS = 128
TEST_MAX_COLLECTION_ITEMS = 16
TEST_MAX_TOTAL_FIELDS = 32


class LimitViolation(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = False


class ProbeChunks:
    def __init__(self, chunks: Iterable[bytes]) -> None:
        self._chunks = list(chunks)
        self.yielded = 0

    def __iter__(self):
        for chunk in self._chunks:
            self.yielded += 1
            yield chunk


@dataclass(frozen=True)
class CandidatePolicy:
    name: str
    transport_limit: int

    @property
    def effective_wire_limit(self) -> int:
        return min(self.transport_limit, TEST_MAX_WIRE_BYTES)


def policy_for(candidate: str) -> CandidatePolicy:
    if candidate not in CANDIDATES:
        raise ValueError(candidate)
    if candidate == "layered_transport_and_application_bounds_profile":
        return CandidatePolicy(candidate, TEST_MAX_WIRE_BYTES * 4)
    return CandidatePolicy(candidate, TEST_MAX_WIRE_BYTES)


def bounded_read(chunks: Iterable[bytes], *, declared_length: int | None, policy: CandidatePolicy) -> bytes:
    limit = policy.effective_wire_limit
    if declared_length is not None:
        if type(declared_length) is not int or declared_length < 0:
            raise LimitViolation("invalid_declared_length")
        if declared_length > limit:
            raise LimitViolation("wire_bytes_exceeded")
    out = bytearray()
    for chunk in chunks:
        if not isinstance(chunk, (bytes, bytearray)):
            raise LimitViolation("invalid_wire_chunk")
        remaining = limit - len(out)
        if len(chunk) > remaining:
            raise LimitViolation("wire_bytes_exceeded")
        out.extend(chunk)
    if declared_length is not None and len(out) != declared_length:
        raise LimitViolation("declared_length_mismatch")
    return bytes(out)


def bounded_gzip_decode(data: bytes) -> bytes:
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    out = bytearray()
    pending = data
    try:
        while pending:
            remaining = TEST_MAX_DECOMPRESSED_BYTES - len(out)
            if remaining < 0:
                raise LimitViolation("decompressed_bytes_exceeded")
            piece = decoder.decompress(pending, remaining + 1)
            out.extend(piece)
            if len(out) > TEST_MAX_DECOMPRESSED_BYTES:
                raise LimitViolation("decompressed_bytes_exceeded")
            pending = decoder.unconsumed_tail
            if not pending:
                break
        remaining = TEST_MAX_DECOMPRESSED_BYTES - len(out)
        tail = decoder.flush(remaining + 1)
        out.extend(tail)
    except zlib.error as exc:
        raise LimitViolation("invalid_compressed_payload") from exc
    if len(out) > TEST_MAX_DECOMPRESSED_BYTES:
        raise LimitViolation("decompressed_bytes_exceeded")
    if not decoder.eof:
        raise LimitViolation("invalid_compressed_payload")
    if decoder.unused_data:
        raise LimitViolation("compressed_trailing_data")
    return bytes(out)


def precheck_json_nesting(payload: bytes) -> None:
    depth = 0
    in_string = False
    escaped = False
    for byte in payload:
        if in_string:
            if escaped:
                escaped = False
            elif byte == 0x5C:
                escaped = True
            elif byte == 0x22:
                in_string = False
            continue
        if byte == 0x22:
            in_string = True
        elif byte in (0x7B, 0x5B):
            depth += 1
            if depth > TEST_MAX_NESTING_DEPTH:
                raise LimitViolation("nesting_depth_exceeded")
        elif byte in (0x7D, 0x5D):
            depth -= 1


def strict_json_loads(payload: bytes) -> Any:
    parsed_fields = 0

    def strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        nonlocal parsed_fields
        if len(pairs) > TEST_MAX_COLLECTION_ITEMS:
            raise LimitViolation("collection_items_exceeded")
        parsed_fields += len(pairs)
        if parsed_fields > TEST_MAX_TOTAL_FIELDS:
            raise LimitViolation("total_fields_exceeded")
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise LimitViolation("duplicate_json_member")
            if len(key) > TEST_MAX_STRING_CHARS:
                raise LimitViolation("field_name_invalid_or_exceeded")
            out[key] = value
        return out

    def reject_constant(_: str) -> None:
        raise LimitViolation("invalid_json_constant")

    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=strict_pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise LimitViolation("invalid_json")


def validate_structure(value: Any) -> None:
    stack: List[tuple[Any, int]] = [(value, 1)]
    total_fields = 0
    while stack:
        node, depth = stack.pop()
        if depth > TEST_MAX_NESTING_DEPTH:
            raise LimitViolation("nesting_depth_exceeded")
        if isinstance(node, str):
            if len(node) > TEST_MAX_STRING_CHARS:
                raise LimitViolation("string_chars_exceeded")
            continue
        if isinstance(node, dict):
            if len(node) > TEST_MAX_COLLECTION_ITEMS:
                raise LimitViolation("collection_items_exceeded")
            total_fields += len(node)
            if total_fields > TEST_MAX_TOTAL_FIELDS:
                raise LimitViolation("total_fields_exceeded")
            for key, child in node.items():
                if len(key) > TEST_MAX_STRING_CHARS:
                    raise LimitViolation("field_name_invalid_or_exceeded")
                stack.append((child, depth + 1))
            continue
        if isinstance(node, list):
            if len(node) > TEST_MAX_COLLECTION_ITEMS:
                raise LimitViolation("collection_items_exceeded")
            for child in node:
                stack.append((child, depth + 1))
            continue
        if node is None or isinstance(node, (bool, int, float)):
            continue
        raise LimitViolation("unsupported_value_type")


def validate_specialized_planes(value: Any) -> None:
    stack: List[Any] = [value]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            kind = node.get("kind")
            if kind == "artifact":
                if "inline" in node or not isinstance(node.get("artifact_ref"), str) or not node["artifact_ref"]:
                    raise LimitViolation("artifact_reference_required")
            if kind == "raw_telemetry":
                if "inline" in node or not isinstance(node.get("telemetry_ref"), str) or not node["telemetry_ref"]:
                    raise LimitViolation("telemetry_reference_required")
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def decode_and_validate(
    candidate: str,
    chunks: Iterable[bytes],
    *,
    declared_length: int | None,
    encoding: str = "identity",
) -> Dict[str, Any]:
    policy = policy_for(candidate)
    events: list[dict[str, Any]] = []
    try:
        wire = bounded_read(chunks, declared_length=declared_length, policy=policy)
        if encoding == "gzip":
            payload = bounded_gzip_decode(wire)
        elif encoding == "identity":
            payload = wire
        else:
            raise LimitViolation("unsupported_content_encoding")
        precheck_json_nesting(payload)
        value = strict_json_loads(payload)
        if isinstance(value, list) and len(value) > TEST_MAX_BATCH_ITEMS:
            raise LimitViolation("batch_items_exceeded")
        validate_structure(value)
        validate_specialized_planes(value)
        return {"accepted": True, "failure": None, "events": events, "limit_profile": TEST_LIMIT_PROFILE}
    except LimitViolation as exc:
        event = {"code": exc.code, "retryable": False, "candidate": candidate}
        events.append(event)
        return {"accepted": False, "failure": event, "events": events, "limit_profile": TEST_LIMIT_PROFILE}


def encoded(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def check_candidate(candidate: str) -> Dict[str, bool]:
    policy = policy_for(candidate)
    valid = encoded({"kind": "event", "value": "ok"})
    normal = decode_and_validate(candidate, [valid], declared_length=len(valid))

    declared_probe = ProbeChunks([b"{}"])
    declared = decode_and_validate(candidate, declared_probe, declared_length=policy.effective_wire_limit + 1)

    unknown_probe = ProbeChunks([b"x" * (TEST_MAX_WIRE_BYTES - 1), b"xx"])
    unknown = decode_and_validate(candidate, unknown_probe, declared_length=None)

    batch = encoded([{"i": i} for i in range(TEST_MAX_BATCH_ITEMS + 1)])
    batch_result = decode_and_validate(candidate, [batch], declared_length=len(batch))

    deep_raw = b"[" * (TEST_MAX_NESTING_DEPTH + 20) + b"0" + b"]" * (TEST_MAX_NESTING_DEPTH + 20)
    deep_result = decode_and_validate(candidate, [deep_raw], declared_length=len(deep_raw))

    nested_collection = encoded({"items": list(range(TEST_MAX_COLLECTION_ITEMS + 1))})
    nested_collection_result = decode_and_validate(candidate, [nested_collection], declared_length=len(nested_collection))

    long_string = encoded({"s": "x" * (TEST_MAX_STRING_CHARS + 1)})
    string_result = decode_and_validate(candidate, [long_string], declared_length=len(long_string))

    many_fields_value = {
        "a": {f"a{i}": i for i in range(TEST_MAX_COLLECTION_ITEMS)},
        "b": {f"b{i}": i for i in range(TEST_MAX_COLLECTION_ITEMS)},
        "c": {"c0": 0},
    }
    many_fields = encoded(many_fields_value)
    fields_result = decode_and_validate(candidate, [many_fields], declared_length=len(many_fields))

    duplicate_members = b'{"dup":0,"dup":1}'
    duplicate_result = decode_and_validate(candidate, [duplicate_members], declared_length=len(duplicate_members))

    bomb_plain = encoded({"data": "x" * (TEST_MAX_DECOMPRESSED_BYTES + 512)})
    bomb = gzip.compress(bomb_plain)
    bomb_result = decode_and_validate(candidate, [bomb], declared_length=len(bomb), encoding="gzip")

    malformed_gzip = b"not-a-gzip-stream"
    malformed_result = decode_and_validate(candidate, [malformed_gzip], declared_length=len(malformed_gzip), encoding="gzip")

    first_member = gzip.compress(encoded({"value": "ok"}))
    second_member = gzip.compress(b"x" * (TEST_MAX_DECOMPRESSED_BYTES + 512))
    concatenated = first_member + second_member
    concatenated_result = decode_and_validate(candidate, [concatenated], declared_length=len(concatenated), encoding="gzip")

    artifact_inline = encoded({"kind": "artifact", "inline": "abc"})
    artifact_inline_result = decode_and_validate(candidate, [artifact_inline], declared_length=len(artifact_inline))
    nested_artifact_inline = encoded({"wrapper": {"kind": "artifact", "inline": "abc"}})
    nested_artifact_inline_result = decode_and_validate(candidate, [nested_artifact_inline], declared_length=len(nested_artifact_inline))
    artifact_ref = encoded({"wrapper": {"kind": "artifact", "artifact_ref": "artifact://tenant/object"}})
    artifact_ref_result = decode_and_validate(candidate, [artifact_ref], declared_length=len(artifact_ref))
    telemetry_ref = encoded({"wrapper": {"kind": "raw_telemetry", "telemetry_ref": "telemetry://tenant/range"}})
    telemetry_ref_result = decode_and_validate(candidate, [telemetry_ref], declared_length=len(telemetry_ref))

    oversized_contract = b"{" + b" " * TEST_MAX_WIRE_BYTES + b"}"
    weak_transport_result = decode_and_validate(candidate, [oversized_contract], declared_length=len(oversized_contract))

    deterministic_1 = decode_and_validate(candidate, [batch], declared_length=len(batch))
    deterministic_2 = decode_and_validate(candidate, [batch], declared_length=len(batch))

    return {
        "valid_payload_admitted": normal["accepted"] is True,
        "declared_oversize_rejected_before_stream_consumption": declared["failure"]["code"] == "wire_bytes_exceeded" and declared_probe.yielded == 0,
        "unknown_length_stream_remains_bounded": unknown["failure"]["code"] == "wire_bytes_exceeded" and unknown_probe.yielded <= 2,
        "batch_size_bound": batch_result["failure"]["code"] == "batch_items_exceeded",
        "parser_nesting_prechecked_before_json_decode": deep_result["failure"]["code"] == "nesting_depth_exceeded",
        "collection_size_bound": nested_collection_result["failure"]["code"] == "collection_items_exceeded",
        "string_bound": string_result["failure"]["code"] == "string_chars_exceeded",
        "field_count_bound": fields_result["failure"]["code"] == "total_fields_exceeded",
        "duplicate_json_members_rejected_before_collapse": duplicate_result["failure"]["code"] == "duplicate_json_member",
        "decompression_output_bound": bomb_result["failure"]["code"] == "decompressed_bytes_exceeded",
        "malformed_gzip_is_bounded_failure": malformed_result["failure"]["code"] == "invalid_compressed_payload" and malformed_result["failure"]["retryable"] is False,
        "compressed_trailing_member_rejected": concatenated_result["failure"]["code"] == "compressed_trailing_data",
        "artifact_reference_required_at_any_depth": artifact_inline_result["failure"]["code"] == "artifact_reference_required" and nested_artifact_inline_result["failure"]["code"] == "artifact_reference_required" and artifact_ref_result["accepted"] is True,
        "raw_telemetry_reference_supported_at_any_depth": telemetry_ref_result["accepted"] is True,
        "transport_cannot_weaken_contract_limit": weak_transport_result["failure"]["code"] == "wire_bytes_exceeded",
        "limit_failures_deterministic": deterministic_1["failure"]["code"] == deterministic_2["failure"]["code"] == "batch_items_exceeded",
        "limit_failures_non_retryable": deterministic_1["failure"]["retryable"] is False and deterministic_2["failure"]["retryable"] is False,
        "fixture_profile_is_noncanonical": TEST_LIMIT_PROFILE.endswith("_noncanonical"),
    }


def evaluate_all() -> Dict[str, Any]:
    checks = {candidate: check_candidate(candidate) for candidate in CANDIDATES}
    results = {
        candidate: "eligible_for_evidence_execution" if all(candidate_checks.values()) else "insufficient_evidence"
        for candidate, candidate_checks in checks.items()
    }
    return {
        "schema_version": 1,
        "source_decision": "OPEN-EVT-010",
        "evidence_id": "bounded_message_batch_compression_and_parser_limits",
        "limit_profile": TEST_LIMIT_PROFILE,
        "candidate_results": results,
        "equivalent_reviewed_profile": "insufficient_evidence",
        "checks": checks,
        "selection": "not_selected",
        "selection_authority": "not_granted",
        "ledger_credit": [],
        "current_run_auto_credit": False,
    }


def main() -> int:
    result = evaluate_all()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if set(result["candidate_results"].values()) == {"eligible_for_evidence_execution"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
