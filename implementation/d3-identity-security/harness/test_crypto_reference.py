from __future__ import annotations

import concurrent.futures
import hashlib
import hmac
import unittest

from crypto_reference import (
    AtomicReplayLedger,
    CsrfKeyRing,
    ReferenceKeyAuthority,
    ReferenceKeyVersion,
    hkdf_expand_sha256,
)


def key(byte: int) -> bytes:
    return bytes([byte]) * 32


class D3CryptoReferenceTests(unittest.TestCase):
    def authority(self) -> ReferenceKeyAuthority:
        return ReferenceKeyAuthority(
            [
                ReferenceKeyVersion(1, key(1), signing_enabled=False, verification_enabled=False),
                ReferenceKeyVersion(2, key(2), signing_enabled=False, verification_enabled=True),
                ReferenceKeyVersion(3, key(3), signing_enabled=True, verification_enabled=True),
            ]
        )

    def test_csrf_current_token_verifies_for_same_lineage(self):
        ring = CsrfKeyRing(authority=self.authority(), current=3, previous=2)
        token = ring.issue(session_lineage_id="lineage-A")
        self.assertTrue(ring.verify(token=token, session_lineage_id="lineage-A"))

    def test_csrf_token_cannot_cross_session_lineage(self):
        ring = CsrfKeyRing(authority=self.authority(), current=3, previous=2)
        token = ring.issue(session_lineage_id="lineage-A")
        self.assertFalse(ring.verify(token=token, session_lineage_id="lineage-B"))

    def test_csrf_previous_generation_is_verify_only_overlap(self):
        authority = self.authority()
        old_ring = CsrfKeyRing(authority=authority, current=2, previous=None)
        old_token = old_ring.issue(session_lineage_id="lineage-A")
        rotated = CsrfKeyRing(authority=authority, current=3, previous=2)
        self.assertTrue(rotated.verify(token=old_token, session_lineage_id="lineage-A"))
        self.assertFalse(authority.can_sign(key_version=2))

    def test_csrf_retired_generation_is_rejected(self):
        old_authority = ReferenceKeyAuthority(
            [ReferenceKeyVersion(1, key(1), signing_enabled=True, verification_enabled=True)]
        )
        old_token = CsrfKeyRing(authority=old_authority, current=1, previous=None).issue(
            session_lineage_id="lineage-A"
        )
        rotated = CsrfKeyRing(authority=self.authority(), current=3, previous=2)
        self.assertFalse(rotated.verify(token=old_token, session_lineage_id="lineage-A"))

    def test_csrf_malformed_or_noncanonical_token_fails_closed(self):
        ring = CsrfKeyRing(authority=self.authority(), current=3, previous=2)
        for token in ("", "v3", "v03.abc", "v3.abc=", "v3.!!!!", "v99.AAAA"):
            self.assertFalse(ring.verify(token=token, session_lineage_id="lineage-A"), token)

    def test_csrf_routine_renewal_preserves_lineage_binding(self):
        ring = CsrfKeyRing(authority=self.authority(), current=3, previous=2)
        token_before_opaque_session_rotation = ring.issue(session_lineage_id="stable-lineage")
        self.assertTrue(
            ring.verify(
                token=token_before_opaque_session_rotation,
                session_lineage_id="stable-lineage",
            )
        )

    def test_csrf_privilege_boundary_new_lineage_requires_reissue(self):
        ring = CsrfKeyRing(authority=self.authority(), current=3, previous=2)
        old = ring.issue(session_lineage_id="pre-step-up")
        self.assertFalse(ring.verify(token=old, session_lineage_id="post-step-up"))
        new = ring.issue(session_lineage_id="post-step-up")
        self.assertTrue(ring.verify(token=new, session_lineage_id="post-step-up"))

    def test_domain_separation_changes_key_by_tenant_scope_and_erasure_unit(self):
        master = key(9)
        a = hkdf_expand_sha256(master_key=master, tenant_id="t1", scope="consumer-a", erasure_unit="record-1")
        b = hkdf_expand_sha256(master_key=master, tenant_id="t2", scope="consumer-a", erasure_unit="record-1")
        c = hkdf_expand_sha256(master_key=master, tenant_id="t1", scope="consumer-b", erasure_unit="record-1")
        d = hkdf_expand_sha256(master_key=master, tenant_id="t1", scope="consumer-a", erasure_unit="record-2")
        self.assertEqual(4, len({a, b, c, d}))

    def test_same_message_has_unlinkable_mac_across_domains(self):
        master = key(9)
        message = b"low-entropy-value"
        subkey_a = hkdf_expand_sha256(master_key=master, tenant_id="t1", scope="s1", erasure_unit="r1")
        subkey_b = hkdf_expand_sha256(master_key=master, tenant_id="t2", scope="s1", erasure_unit="r1")
        mac_a = hmac.new(subkey_a, message, hashlib.sha256).digest()
        mac_b = hmac.new(subkey_b, message, hashlib.sha256).digest()
        self.assertNotEqual(mac_a, mac_b)

    def test_historical_verifier_can_verify_without_signing(self):
        authority = self.authority()
        self.assertFalse(authority.can_sign(key_version=2))
        self.assertTrue(authority.can_verify(key_version=2))
        mac = authority.hmac_sha256(key_version=2, context=b"history", message=b"evidence")
        self.assertEqual(32, len(mac))

    def test_retired_historical_key_cannot_be_recreated_by_reference_authority(self):
        authority = self.authority()
        self.assertFalse(authority.can_verify(key_version=1))
        with self.assertRaises(ValueError):
            authority.hmac_sha256(key_version=1, context=b"history", message=b"evidence")

    def test_replay_concurrency_has_exactly_one_winner(self):
        ledger = AtomicReplayLedger()
        def attempt(_: int) -> bool:
            return ledger.create_or_observe(
                client_principal="machine-A",
                jti="assertion-jti-1",
                expected_generation=1,
            )
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            outcomes = list(pool.map(attempt, range(64)))
        self.assertEqual(1, sum(outcomes))

    def test_replay_authority_unavailable_fails_closed(self):
        ledger = AtomicReplayLedger()
        ledger.available = False
        with self.assertRaises(RuntimeError):
            ledger.create_or_observe(
                client_principal="machine-A",
                jti="assertion-jti-1",
                expected_generation=1,
            )

    def test_replay_restore_generation_mismatch_fails_closed(self):
        ledger = AtomicReplayLedger()
        self.assertTrue(
            ledger.create_or_observe(
                client_principal="machine-A",
                jti="assertion-jti-1",
                expected_generation=1,
            )
        )
        ledger.retire_continuity()
        with self.assertRaises(RuntimeError):
            ledger.create_or_observe(
                client_principal="machine-A",
                jti="assertion-jti-1",
                expected_generation=1,
            )

    def test_replay_identity_is_scoped_to_client_principal(self):
        ledger = AtomicReplayLedger()
        self.assertTrue(ledger.create_or_observe(client_principal="A", jti="same-jti", expected_generation=1))
        self.assertTrue(ledger.create_or_observe(client_principal="B", jti="same-jti", expected_generation=1))
        self.assertFalse(ledger.create_or_observe(client_principal="A", jti="same-jti", expected_generation=1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
