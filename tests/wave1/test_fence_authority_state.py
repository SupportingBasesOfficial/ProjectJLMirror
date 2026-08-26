from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.fencing import (  # noqa: E402
    EFFECT_ELIGIBLE_FENCE_AUTHORITY_STATE,
    FenceRecord,
    FenceToken,
    acquire_next_fence,
    admit_fenced_effect,
)
from jlmirror_authority.model import AdmissionDenied  # noqa: E402


class RecordingFenceAuthority:
    def __init__(self, state: str):
        self.record = FenceRecord("tenant:acme", 7, "gen-7", state)
        self.acquire_called = False

    def current(self, fence_scope_id):
        return self.record if fence_scope_id == self.record.fence_scope_id else None

    def acquire_successor(self, **kwargs):
        self.acquire_called = True
        return FenceRecord(
            kwargs["fence_scope_id"],
            kwargs["expected_predecessor_epoch"] + 1,
            kwargs["successor_generation_id"],
            kwargs["successor_state"],
        )


class FenceAuthorityStateTests(unittest.TestCase):
    def test_active_exact_fence_is_effect_eligible_only_through_current_authority(self):
        authority = RecordingFenceAuthority(EFFECT_ELIGIBLE_FENCE_AUTHORITY_STATE)
        admit_fenced_effect(
            token=FenceToken("tenant:acme", 7, "gen-7"),
            authority=authority,
        )

    def test_non_active_exact_fence_is_not_effect_authority(self):
        token = FenceToken("tenant:acme", 7, "gen-7")
        for state in ("quarantined", "retired", "unknown-canonical-state"):
            authority = RecordingFenceAuthority(state)
            with self.subTest(state=state), self.assertRaises(AdmissionDenied):
                admit_fenced_effect(token=token, authority=authority)

    def test_stale_token_is_denied_after_current_authority_advances(self):
        authority = RecordingFenceAuthority(EFFECT_ELIGIBLE_FENCE_AUTHORITY_STATE)
        stale = FenceToken("tenant:acme", 7, "gen-7")
        authority.record = FenceRecord("tenant:acme", 8, "gen-8", "active")
        with self.assertRaises(AdmissionDenied):
            admit_fenced_effect(token=stale, authority=authority)

    def test_non_active_predecessor_cannot_spawn_ordinary_successor(self):
        for state in ("quarantined", "retired", "unknown-canonical-state"):
            authority = RecordingFenceAuthority(state)
            with self.subTest(state=state), self.assertRaises(AdmissionDenied):
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
