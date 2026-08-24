from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.model import Principal, PrincipalKind  # noqa: E402
from jlmirror_authority.session import (  # noqa: E402
    BrowserSessionHandle,
    issue_browser_session,
)

NOW = datetime(2026, 8, 24, 15, 30, tzinfo=timezone.utc)


class SessionAuthority:
    def __init__(self):
        self.records = {}

    def create(self, record):
        if record.handle_digest in self.records:
            return False
        self.records[record.handle_digest] = record
        return True

    def resolve(self, handle_digest):
        return self.records.get(handle_digest)

    def rotate(self, **kwargs):
        return False

    def retire(self, **kwargs):
        return False


class SessionCapabilityBoundaryTests(unittest.TestCase):
    def test_only_bounded_urlsafe_ascii_handles_are_canonical(self):
        BrowserSessionHandle("A" * 43)
        BrowserSessionHandle("a" * 128)
        BrowserSessionHandle("A_-0" * 16)

        invalid = (
            "A" * 42,
            "A" * 129,
            "A" * 63 + " ",
            "A" * 63 + "\n",
            "A" * 63 + "+",
            "A" * 63 + "/",
            "A" * 63 + "=",
            "A" * 63 + "é",
        )
        for value in invalid:
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                BrowserSessionHandle(value)

    def test_generated_handle_conforms_and_repr_remains_redacted(self):
        authority = SessionAuthority()
        handle = issue_browser_session(
            authority=authority,
            principal=Principal(
                "user-1",
                PrincipalKind.HUMAN_BROWSER_SESSION,
                "identity-login-g1",
            ),
            now=NOW,
            lifetime=timedelta(minutes=30),
        )
        self.assertGreaterEqual(len(handle.value), 43)
        self.assertLessEqual(len(handle.value), 128)
        self.assertTrue(all(c.isascii() and (c.isalnum() or c in "_-") for c in handle.value))
        self.assertNotIn(handle.value, repr(handle))


if __name__ == "__main__":
    unittest.main(verbosity=2)
