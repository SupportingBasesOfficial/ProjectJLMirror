from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.fencing import (  # noqa: E402
    FenceRecord,
    acquire_next_fence,
)
from jlmirror_authority.model import AdmissionDenied  # noqa: E402


class WrongScopeAuthority:
    def __init__(self):
        self.acquire_called = False

    def current(self, fence_scope_id):
        return FenceRecord(
            fence_scope_id="tenant:other",
            current_fence_epoch=7,
            current_generation_id="gen-7",
            authority_state="active",
        )

    def acquire_successor(self, **kwargs):
        self.acquire_called = True
        return FenceRecord(
            fence_scope_id=kwargs["fence_scope_id"],
            current_fence_epoch=kwargs["expected_predecessor_epoch"] + 1,
            current_generation_id=kwargs["successor_generation_id"],
            authority_state=kwargs["successor_state"],
        )


class FenceScopeBindingTests(unittest.TestCase):
    def test_wrong_scope_predecessor_is_rejected_before_successor_cas(self):
        authority = WrongScopeAuthority()
        with self.assertRaises(AdmissionDenied):
            acquire_next_fence(
                authority=authority,
                fence_scope_id="tenant:acme",
                expected_predecessor_epoch=7,
                expected_predecessor_generation_id="gen-7",
                successor_generation_id="gen-8",
            )
        self.assertFalse(authority.acquire_called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
