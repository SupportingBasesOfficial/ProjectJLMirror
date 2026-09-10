from __future__ import annotations

import unittest

from jlmirror_monitoring.host_inventory import (
    MAX_NORMALIZED_EVIDENCE_BYTES,
    ZabbixHostEvidence,
    ZabbixInventoryEvidence,
    ZabbixNamedRefEvidence,
)


class HostInventoryEvidenceSizeTests(unittest.TestCase):
    def test_small_normalized_host_evidence_remains_valid(self) -> None:
        host = ZabbixHostEvidence(
            hostid="101",
            technical_name="core-sw-01",
            display_name="Core Switch",
            inventory=ZabbixInventoryEvidence(vendor="Cisco", model="C9300"),
            interfaces=(),
            groups=(ZabbixNamedRefEvidence(ref="10", name="Network"),),
            templates=(),
            tags=(),
        )

        self.assertEqual(len(host.evidence_fingerprint()), 64)

    def test_aggregate_normalized_host_evidence_above_persistence_safe_bound_is_rejected(self) -> None:
        # Every individual field and collection remains within its own accepted bound.
        # The failure is intentionally only the aggregate canonical JSON byte size.
        groups = tuple(
            ZabbixNamedRefEvidence(ref=str(index), name="N" * 512)
            for index in range(128)
        )

        with self.assertRaisesRegex(ValueError, "persistence-safe byte ceiling"):
            ZabbixHostEvidence(
                hostid="oversized-aggregate",
                technical_name="aggregate-boundary-host",
                display_name="Aggregate Boundary Host",
                inventory=ZabbixInventoryEvidence(),
                interfaces=(),
                groups=groups,
                templates=(),
                tags=(),
            )

    def test_byte_bound_not_character_count_with_multibyte_provider_text(self) -> None:
        groups = tuple(
            ZabbixNamedRefEvidence(ref=f"utf8-{index}", name="界" * 512)
            for index in range(40)
        )

        with self.assertRaisesRegex(ValueError, "persistence-safe byte ceiling"):
            ZabbixHostEvidence(
                hostid="utf8-aggregate",
                technical_name="utf8-boundary-host",
                display_name="UTF8 Boundary Host",
                inventory=ZabbixInventoryEvidence(),
                interfaces=(),
                groups=groups,
                templates=(),
                tags=(),
            )

        self.assertLess(MAX_NORMALIZED_EVIDENCE_BYTES, 65_536)


if __name__ == "__main__":
    unittest.main()
