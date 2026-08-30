#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from validate_post_d2_wave4_state import (
    FILES,
    MERGE_SHA,
    compute_surface_blobs,
    validate,
)


class PostD2Wave4StateGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for path in FILES.values():
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)

        (self.root / FILES["transition"]).write_text(
            "\n".join(
                [
                    MERGE_SHA,
                    "## Readiness propagation requirements",
                    "```text",
                    "open_rel_030_track_b = accepted",
                    "open_rel_030_profile = selected_and_conformed",
                    "customer_telemetry_slice = eligible_for_implementation_authorization",
                    "wave4_monitoring = eligible_for_separate_explicit_authorization",
                    "wave4_implementation_authorization = not_granted",
                    "production_authority = none",
                    "open_rel_020_production_state = open_c3",
                    "```",
                    "READY_TO_AUTHORIZE != AUTHORIZED_TO_IMPLEMENT",
                ]
            ),
            encoding="utf-8",
        )
        (self.root / FILES["open_register"]).write_text(
            f"`OPEN-REL-030` | C2 | **ACCEPTED / selected + conformed {MERGE_SHA} `OPEN-REL-020`",
            encoding="utf-8",
        )
        (self.root / FILES["blockers"]).write_text(
            "former `OPEN-REL-030` evidence blocker is **satisfied; "
            "`eligible_for_implementation_authorization`; not authorized to implement; `OPEN-REL-020`",
            encoding="utf-8",
        )
        (self.root / FILES["sequencing"]).write_text(
            "Track A accepted + Track B accepted\n"
            "eligible_for_separate_explicit_authorization\n"
            "READY_TO_AUTHORIZE != AUTHORIZED_TO_IMPLEMENT",
            encoding="utf-8",
        )
        (self.root / FILES["slice_manifest"]).write_text(
            "`impl.customer-telemetry@1` "
            "`eligible_for_implementation_authorization` for the accepted Track B profile merged by PR #40; "
            "accepted Monitoring/Zabbix subprofile is `eligible_for_implementation_authorization`; "
            "every other concrete provider/effectful subprofile remains `deferred_product_gated`",
            encoding="utf-8",
        )
        self.baseline = compute_surface_blobs(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _append(self, key: str, line: str) -> None:
        path = self.root / FILES[key]
        path.write_text(path.read_text(encoding="utf-8") + f"\n{line}", encoding="utf-8")

    def _validate(self) -> None:
        validate(self.root, expected_surface_blobs=self.baseline)

    def _rebaseline(self) -> None:
        self.baseline = compute_surface_blobs(self.root)

    def test_accepts_consistent_post_d2_state(self) -> None:
        self._validate()

    def test_every_governed_surface_is_content_addressed(self) -> None:
        for key in FILES:
            with self.subTest(key=key):
                original = (self.root / FILES[key]).read_text(encoding="utf-8")
                self._append(key, "editorial drift")
                with self.assertRaises(AssertionError):
                    self._validate()
                (self.root / FILES[key]).write_text(original, encoding="utf-8")

    def test_rejects_invalid_governed_blob_oid(self) -> None:
        baseline = dict(self.baseline)
        baseline["sequencing"] = "not-a-git-blob"
        with self.assertRaises(AssertionError):
            validate(self.root, expected_surface_blobs=baseline)

    def test_rejects_incomplete_governed_surface_baseline(self) -> None:
        baseline = dict(self.baseline)
        baseline.pop("open_register")
        with self.assertRaises(AssertionError):
            validate(self.root, expected_surface_blobs=baseline)

    def test_reviewed_rebaseline_can_accept_nonsemantic_editorial_change(self) -> None:
        self._append("sequencing", "Editorial note: D2 evidence remains canonical.")
        with self.assertRaises(AssertionError):
            self._validate()
        self._rebaseline()
        self._validate()

    def test_rejects_structured_wave4_grant_even_after_rebaseline(self) -> None:
        path = self.root / FILES["transition"]
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "wave4_implementation_authorization = not_granted",
                "wave4_implementation_authorization = granted",
            ),
            encoding="utf-8",
        )
        self._rebaseline()
        with self.assertRaises(AssertionError):
            self._validate()

    def test_rejects_structured_production_grant_even_after_rebaseline(self) -> None:
        path = self.root / FILES["transition"]
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "production_authority = none",
                "production_authority = granted",
            ),
            encoding="utf-8",
        )
        self._rebaseline()
        with self.assertRaises(AssertionError):
            self._validate()

    def test_rejects_structured_open_rel_020_closure_even_after_rebaseline(self) -> None:
        path = self.root / FILES["transition"]
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "open_rel_020_production_state = open_c3",
                "open_rel_020_production_state = closed",
            ),
            encoding="utf-8",
        )
        self._rebaseline()
        with self.assertRaises(AssertionError):
            self._validate()

    def test_rejects_duplicate_structured_authority_key_even_after_rebaseline(self) -> None:
        path = self.root / FILES["transition"]
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "production_authority = none\n",
                "production_authority = none\nproduction_authority = none\n",
            ),
            encoding="utf-8",
        )
        self._rebaseline()
        with self.assertRaises(AssertionError):
            self._validate()

    def test_rejects_machine_wave4_override_on_other_surface_after_rebaseline(self) -> None:
        self._append("open_register", "wave4_implementation_authorization = granted")
        self._rebaseline()
        with self.assertRaises(AssertionError):
            self._validate()

    def test_rejects_machine_production_override_on_other_surface_after_rebaseline(self) -> None:
        self._append("blockers", "production_authority = granted")
        self._rebaseline()
        with self.assertRaises(AssertionError):
            self._validate()

    def test_rejects_machine_open_rel_override_on_other_surface_after_rebaseline(self) -> None:
        self._append("open_register", "open_rel_020_production_state = closed")
        self._rebaseline()
        with self.assertRaises(AssertionError):
            self._validate()

    def test_rejects_stale_customer_telemetry_blocker_even_after_rebaseline(self) -> None:
        self._append(
            "blockers",
            "Blocked until `OPEN-REL-030` C2 durable acceptance/projection mechanism",
        )
        self._rebaseline()
        with self.assertRaises(AssertionError):
            self._validate()

    # Exact fresh Codex vectors on predecessor 38d4a4f6. These no longer depend on
    # language recognition: any unreviewed prose mutation changes the governed blob.
    def test_rejects_future_modifier_hiding_present_closure(self) -> None:
        self._append(
            "open_register",
            "OPEN-REL-020 may require review, but it is now closed",
        )
        with self.assertRaises(AssertionError):
            self._validate()

    def test_rejects_undecided_prefix_hiding_production_grant(self) -> None:
        self._append(
            "sequencing",
            "Whether Wave 4 is authorized remains undecided, but production deployment is approved and its timing remains undecided",
        )
        with self.assertRaises(AssertionError):
            self._validate()

    def test_rejects_noun_form_authority_grant(self) -> None:
        self._append("sequencing", "Wave 4 implementation has authority to proceed")
        with self.assertRaises(AssertionError):
            self._validate()

    def test_rejects_inverse_open_rel_020_not_open_claim(self) -> None:
        self._append("open_register", "OPEN-REL-020 is no longer open")
        with self.assertRaises(AssertionError):
            self._validate()

    # Representative predecessor vectors remain covered by the same closed-world rule.
    def test_rejects_trailing_question_bypass(self) -> None:
        self._append(
            "sequencing",
            "Wave 4 is authorized to implement. Is production ready?",
        )
        with self.assertRaises(AssertionError):
            self._validate()

    def test_rejects_adverb_qualified_grant(self) -> None:
        self._append("blockers", "Production deployment is explicitly approved")
        with self.assertRaises(AssertionError):
            self._validate()

    def test_rejects_colon_scope_bypass(self) -> None:
        self._append(
            "blockers",
            "Wave 4 is not authorized: production deployment is approved",
        )
        with self.assertRaises(AssertionError):
            self._validate()


if __name__ == "__main__":
    unittest.main()
