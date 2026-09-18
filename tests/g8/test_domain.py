from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g8-human-operations"))

from domain import AuthoritySnapshot,require_action,require_responsibility,require_visibility


class DomainTests(unittest.TestCase):
    def test_current_authority_is_required_and_identity_bound(self):
        good=AuthoritySnapshot("tenant-a","actor-a",True,"human-operations:write","policy-r1")
        good.validate(tenant_id="tenant-a",actor_principal_id="actor-a")
        with self.assertRaises(PermissionError):
            AuthoritySnapshot("tenant-a","actor-a",False,"x","r1").validate(
                tenant_id="tenant-a",actor_principal_id="actor-a"
            )
        with self.assertRaises(PermissionError):
            good.validate(tenant_id="tenant-b",actor_principal_id="actor-a")

    def test_bounded_semantics(self):
        require_responsibility("technical_responsible","manual")
        require_action("investigate_alert")
        require_visibility("customer","platform_native_authenticated_view@1")
        with self.assertRaises(ValueError):
            require_action("no_human_action_required")
        with self.assertRaises(ValueError):
            require_visibility("customer","external-channel")


if __name__=="__main__":
    unittest.main()
