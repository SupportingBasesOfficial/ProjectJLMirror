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
                    "open_rel_030_track_b = accepted",
                    "open_rel_030_profile = selected_and_conformed",
                    "customer_telemetry_slice = eligible_for_implementation_authorization",
                    "wave4_monitoring = eligible_for_separate_explicit_authorization",
                    "wave4_implementation_authorization = not_granted",
                    "production_authority = none",
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

    def test_accepts_consistent_post_d2_state(self) -> None:
        validate(self.root)

    def test_rejects_stale_customer_telemetry_blocker(self) -> None:
        path = self.root / FILES["blockers"]
        path.write_text(
            path.read_text(encoding="utf-8")
            + "\nBlocked until `OPEN-REL-030` C2 durable acceptance/projection mechanism",
            encoding="utf-8",
        )
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_implicit_wave4_authorization_in_transition(self) -> None:
        path = self.root / FILES["transition"]
        path.write_text(
            path.read_text(encoding="utf-8")
            + "\nwave4_implementation_authorization = granted",
            encoding="utf-8",
        )
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_rejects_implicit_wave4_authorization_in_open_register(self) -> None:
        path = self.root / FILES["open_register"]
        path.write_text(
            path.read_text(encoding="utf-8")
            + "\nwave4_implementation_authorization = granted",
            encoding="utf-8",
        )
        with self.assertRaises(AssertionError):
            validate(self.root)


if __name__ == "__main__":
    unittest.main()