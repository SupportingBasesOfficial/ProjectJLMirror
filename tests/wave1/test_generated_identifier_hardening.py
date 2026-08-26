from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.model import Principal, PrincipalKind  # noqa: E402
from jlmirror_authority.session import issue_browser_session  # noqa: E402

NOW = datetime(2026, 8, 24, 11, 30, tzinfo=timezone.utc)


class CapturingAuthority:
    def __init__(self):
        self.record = None

    def create(self, record):
        self.record = record
        return True


class GeneratedIdentifierHardeningTests(unittest.TestCase):
    def test_random_generation_prefix_cannot_make_session_identifier_noncanonical(self):
        authority = CapturingAuthority()
        with patch(
            "jlmirror_authority.session.secrets.token_urlsafe",
            side_effect=["A" * 64, "_random-token-can-start-with-underscore"],
        ):
            handle = issue_browser_session(
                authority=authority,
                principal=Principal(
                    "user-1", PrincipalKind.HUMAN_BROWSER_SESSION, "identity-g1"
                ),
                now=NOW,
                lifetime=timedelta(minutes=5),
            )

        self.assertEqual(handle.value, "A" * 64)
        self.assertIsNotNone(authority.record)
        self.assertEqual(
            authority.record.session_generation,
            "session-_random-token-can-start-with-underscore",
        )
        self.assertEqual(
            authority.record.principal.credential_generation,
            authority.record.session_generation,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
