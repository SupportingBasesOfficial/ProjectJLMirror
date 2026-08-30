#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from validate_post_d2_wave4_state import FILES, MERGE_SHA, validate


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

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _append(self, key: str, line: str) -> None:
        path = self.root / FILES[key]
        path.write_text(path.read_text(encoding="utf-8") + f"\n{line}", encoding="utf-8")

    def test_accepts_consistent_post_d2_state(self) -> None:
        validate(self.root)

    def test_rejects_stale_customer_telemetry_blocker(self) -> None:
        self._append(
            "blockers",
            "Blocked until `OPEN-REL-030` C2 durable acceptance/projection mechanism",
        )
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_structured_wave4_authorization_grant(self) -> None:
        path = self.root / FILES["transition"]
        text = path.read_text(encoding="utf-8").replace(
            "wave4_implementation_authorization = not_granted",
            "wave4_implementation_authorization = granted",
        )
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_structured_production_authority_grant(self) -> None:
        path = self.root / FILES["transition"]
        text = path.read_text(encoding="utf-8").replace(
            "production_authority = none",
            "production_authority = granted",
        )
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_structured_open_rel_020_closure(self) -> None:
        path = self.root / FILES["transition"]
        text = path.read_text(encoding="utf-8").replace(
            "open_rel_020_production_state = open_c3",
            "open_rel_020_production_state = closed",
        )
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_duplicate_structured_authority_key(self) -> None:
        path = self.root / FILES["transition"]
        text = path.read_text(encoding="utf-8").replace(
            "production_authority = none\n",
            "production_authority = none\nproduction_authority = none\n",
        )
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_implicit_wave4_authorization_in_open_register(self) -> None:
        self._append("open_register", "wave4_implementation_authorization = granted")
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_natural_language_wave4_authorization(self) -> None:
        self._append("sequencing", "Wave 4 implementation is AUTHORIZED TO IMPLEMENT")
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_natural_language_provider_authorization(self) -> None:
        self._append(
            "slice_manifest",
            "accepted Monitoring/Zabbix subprofile is authorized to implement",
        )
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_production_authority_grant_in_current_surface(self) -> None:
        self._append("blockers", "production_authority = granted")
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_open_rel_020_closure_in_current_surface(self) -> None:
        self._append("blockers", "OPEN-REL-020 = CLOSED")
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_allows_explicit_negative_authority_language(self) -> None:
        self._append("sequencing", "Wave 4 remains not authorized to implement here")
        self._append("blockers", "This record does not authorize production deployment")
        validate(self.root)

    def test_rejects_safe_prefix_then_wave4_grant(self) -> None:
        self._append(
            "sequencing",
            "Wave 4 is eligible for review and is authorized to implement",
        )
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_negative_prefix_then_production_grant(self) -> None:
        self._append(
            "blockers",
            "Production is not ready, but is approved for deployment",
        )
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_wave4_may_now_proceed(self) -> None:
        self._append("sequencing", "Wave 4 implementation may now proceed")
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_production_deployment_permitted(self) -> None:
        self._append("blockers", "Production deployment is permitted")
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_open_rel_020_has_been_closed(self) -> None:
        self._append("open_register", "OPEN-REL-020 has been closed")
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_open_rel_020_is_complete(self) -> None:
        self._append("open_register", "OPEN-REL-020 is complete")
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_allows_authority_question_remains_undecided(self) -> None:
        self._append("sequencing", "Whether Wave 4 is authorized remains undecided")
        validate(self.root)

    def test_allows_authorized_only_after_explicit_gate(self) -> None:
        self._append(
            "sequencing",
            "Wave 4 is authorized only after a separate explicit gate",
        )
        validate(self.root)

    def test_allows_direct_authority_question(self) -> None:
        self._append("sequencing", "Is Wave 4 authorized?")
        validate(self.root)

    def test_allows_production_only_after_gate(self) -> None:
        self._append(
            "blockers",
            "Production deployment is permitted only after a separate production gate",
        )
        validate(self.root)


if __name__ == "__main__":
    unittest.main()
