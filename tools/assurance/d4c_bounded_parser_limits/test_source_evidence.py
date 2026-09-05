#!/usr/bin/env python3
from __future__ import annotations

import gzip
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from evaluate_candidates import (  # noqa: E402
    CANDIDATES,
    TEST_LIMIT_PROFILE,
    TEST_MAX_BATCH_ITEMS,
    TEST_MAX_COLLECTION_ITEMS,
    TEST_MAX_DECOMPRESSED_BYTES,
    TEST_MAX_NESTING_DEPTH,
    TEST_MAX_TOTAL_FIELDS,
    TEST_MAX_WIRE_BYTES,
    ProbeChunks,
    decode_and_validate,
    encoded,
    evaluate_all,
    policy_for,
)


class BoundedParserSourceTests(unittest.TestCase):
    def test_all_concrete_candidates_are_eligible(self):
        result = evaluate_all()
        self.assertEqual(set(result["candidate_results"]), set(CANDIDATES))
        self.assertEqual(set(result["candidate_results"].values()), {"eligible_for_evidence_execution"})
        self.assertTrue(all(all(checks.values()) for checks in result["checks"].values()))
        self.assertEqual(result["selection"], "not_selected")
        self.assertEqual(result["ledger_credit"], [])

    def test_declared_oversize_is_rejected_before_stream_iteration(self):
        for candidate in CANDIDATES:
            probe = ProbeChunks([b"{}"])
            result = decode_and_validate(candidate, probe, declared_length=policy_for(candidate).effective_wire_limit + 1)
            self.assertEqual(result["failure"]["code"], "wire_bytes_exceeded")
            self.assertEqual(probe.yielded, 0)

    def test_unknown_length_stream_cannot_cross_contract_budget(self):
        for candidate in CANDIDATES:
            probe = ProbeChunks([b"x" * (TEST_MAX_WIRE_BYTES - 1), b"xx"])
            result = decode_and_validate(candidate, probe, declared_length=None)
            self.assertFalse(result["accepted"])
            self.assertEqual(result["failure"]["code"], "wire_bytes_exceeded")

    def test_transport_limit_cannot_relax_contract_limit(self):
        candidate = "layered_transport_and_application_bounds_profile"
        self.assertGreater(policy_for(candidate).transport_limit, TEST_MAX_WIRE_BYTES)
        payload = b"{" + b" " * TEST_MAX_WIRE_BYTES + b"}"
        result = decode_and_validate(candidate, [payload], declared_length=len(payload))
        self.assertEqual(result["failure"]["code"], "wire_bytes_exceeded")

    def test_parser_nesting_is_rejected_before_recursive_json_decode(self):
        payload = b"[" * (TEST_MAX_NESTING_DEPTH + 100) + b"0" + b"]" * (TEST_MAX_NESTING_DEPTH + 100)
        self.assertLess(len(payload), TEST_MAX_WIRE_BYTES)
        for candidate in CANDIDATES:
            result = decode_and_validate(candidate, [payload], declared_length=len(payload))
            self.assertEqual(result["failure"]["code"], "nesting_depth_exceeded")
            self.assertFalse(result["failure"]["retryable"])

    def test_decompression_bomb_is_bounded_before_json_parse(self):
        plain = encoded({"data": "x" * (TEST_MAX_DECOMPRESSED_BYTES + 1024)})
        compressed = gzip.compress(plain)
        self.assertLess(len(compressed), TEST_MAX_WIRE_BYTES)
        for candidate in CANDIDATES:
            result = decode_and_validate(candidate, [compressed], declared_length=len(compressed), encoding="gzip")
            self.assertEqual(result["failure"]["code"], "decompressed_bytes_exceeded")
            self.assertFalse(result["failure"]["retryable"])

    def test_malformed_gzip_is_deterministic_nonretryable_failure(self):
        payload = b"not-a-gzip-stream"
        for candidate in CANDIDATES:
            first = decode_and_validate(candidate, [payload], declared_length=len(payload), encoding="gzip")
            second = decode_and_validate(candidate, [payload], declared_length=len(payload), encoding="gzip")
            self.assertEqual(first["failure"], second["failure"])
            self.assertEqual(first["failure"]["code"], "invalid_compressed_payload")
            self.assertFalse(first["failure"]["retryable"])

    def test_concatenated_gzip_member_is_rejected_without_processing_second_member(self):
        first = gzip.compress(encoded({"value": "ok"}))
        second = gzip.compress(b"x" * (TEST_MAX_DECOMPRESSED_BYTES + 1024))
        payload = first + second
        self.assertLess(len(payload), TEST_MAX_WIRE_BYTES)
        for candidate in CANDIDATES:
            result = decode_and_validate(candidate, [payload], declared_length=len(payload), encoding="gzip")
            self.assertEqual(result["failure"]["code"], "compressed_trailing_data")

    def test_duplicate_json_members_are_not_collapsed_before_field_guard(self):
        payload = b"{" + b",".join([b'\"dup\":0'] * (TEST_MAX_TOTAL_FIELDS + 1)) + b"}"
        self.assertLess(len(payload), TEST_MAX_WIRE_BYTES)
        for candidate in CANDIDATES:
            result = decode_and_validate(candidate, [payload], declared_length=len(payload))
            self.assertIn(result["failure"]["code"], {"duplicate_json_member", "total_fields_exceeded"})
            self.assertFalse(result["failure"]["retryable"])

    def test_batch_limit_is_deterministic_and_non_retryable(self):
        payload = encoded([{"i": i} for i in range(TEST_MAX_BATCH_ITEMS + 1)])
        for candidate in CANDIDATES:
            first = decode_and_validate(candidate, [payload], declared_length=len(payload))
            second = decode_and_validate(candidate, [payload], declared_length=len(payload))
            self.assertEqual(first["failure"], second["failure"])
            self.assertEqual(first["failure"]["code"], "batch_items_exceeded")
            self.assertFalse(first["failure"]["retryable"])

    def test_nested_collection_limit_is_independent_from_batch_limit(self):
        payload = encoded({"items": list(range(TEST_MAX_COLLECTION_ITEMS + 1))})
        for candidate in CANDIDATES:
            result = decode_and_validate(candidate, [payload], declared_length=len(payload))
            self.assertEqual(result["failure"]["code"], "collection_items_exceeded")

    def test_artifact_and_telemetry_are_reference_only_at_any_depth(self):
        for candidate in CANDIDATES:
            inline = encoded({"wrapper": {"kind": "artifact", "inline": "abc"}})
            rejected = decode_and_validate(candidate, [inline], declared_length=len(inline))
            self.assertEqual(rejected["failure"]["code"], "artifact_reference_required")
            artifact = encoded({"wrapper": {"kind": "artifact", "artifact_ref": "artifact://tenant/object"}})
            telemetry = encoded({"wrapper": {"kind": "raw_telemetry", "telemetry_ref": "telemetry://tenant/range"}})
            self.assertTrue(decode_and_validate(candidate, [artifact], declared_length=len(artifact))["accepted"])
            self.assertTrue(decode_and_validate(candidate, [telemetry], declared_length=len(telemetry))["accepted"])

    def test_numeric_profile_is_explicitly_fixture_only(self):
        self.assertEqual(TEST_LIMIT_PROFILE, "bounded_parser_fixture_only_noncanonical")
        self.assertNotIn("production", TEST_LIMIT_PROFILE)

    def test_equivalent_profile_stays_insufficient(self):
        result = evaluate_all()
        self.assertEqual(result["equivalent_reviewed_profile"], "insufficient_evidence")


if __name__ == "__main__":
    unittest.main(verbosity=2)
