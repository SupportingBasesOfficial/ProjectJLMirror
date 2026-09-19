from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g9-notification-delivery"))

from domain import AuthoritySnapshot,require_attempt_state,require_evidence,require_intent


class DomainTests(unittest.TestCase):
    def test_authority_is_current_and_identity_bound(self):
        good=AuthoritySnapshot("tenant-a","actor-a",True,"notification:write","policy-r1")
        good.validate(tenant_id="tenant-a",actor_principal_id="actor-a")
        with self.assertRaises(PermissionError):
            AuthoritySnapshot("tenant-a","actor-a",False,"x","r").validate(
                tenant_id="tenant-a",actor_principal_id="actor-a"
            )
        with self.assertRaises(PermissionError):
            good.validate(tenant_id="tenant-b",actor_principal_id="actor-a")

    def test_channel_and_state_sets_are_bounded(self):
        require_intent("alert_requires_attention","whatsapp_business@1")
        require_attempt_state("sent")
        require_evidence("delivered")
        with self.assertRaises(ValueError):
            require_intent("alert_requires_attention","other-channel")
        with self.assertRaises(ValueError):
            require_attempt_state("viewed")


if __name__=="__main__":
    unittest.main()
