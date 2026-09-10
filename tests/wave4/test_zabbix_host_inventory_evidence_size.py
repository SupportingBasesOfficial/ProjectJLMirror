from __future__ import annotations

import json
import unittest

from jlmirror_monitoring.host_inventory import (
    MAX_GROUPS_PER_HOST,
    MAX_INTERFACES_PER_HOST,
    MAX_NORMALIZED_EVIDENCE_BYTES,
    MAX_TAGS_PER_HOST,
    MAX_TEMPLATES_PER_HOST,
    PERSISTED_NORMALIZED_EVIDENCE_LIMIT_BYTES,
    ZabbixHostEvidence,
    ZabbixHostInterfaceEvidence,
    ZabbixInventoryEvidence,
    ZabbixNamedRefEvidence,
    ZabbixTagEvidence,
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

    def test_application_ceiling_covers_maximum_jsonb_separator_overhead(self) -> None:
        # PostgreSQL jsonb::text adds separator spaces compared with the compact JSON
        # used for fingerprints. Separator overhead depends on structure, not string
        # lengths. Build the maximum allowed structure using tiny values and prove the
        # entire possible formatting overhead still fits inside the reserved margin.
        host = ZabbixHostEvidence(
            hostid="max-structure",
            technical_name="h",
            display_name="h",
            inventory=ZabbixInventoryEvidence(
                device_type="x",
                device_type_full="x",
                os="x",
                os_full="x",
                vendor="x",
                model="x",
                serial_primary="x",
                serial_secondary="x",
                asset_tag="x",
                hardware="x",
                software="x",
                location="x",
            ),
            interfaces=tuple(
                ZabbixHostInterfaceEvidence(
                    interfaceid=f"i{index}",
                    interface_type="agent",
                    main=False,
                    use_ip=True,
                    ip="1",
                    dns="d",
                    port="1",
                )
                for index in range(MAX_INTERFACES_PER_HOST)
            ),
            groups=tuple(
                ZabbixNamedRefEvidence(ref=f"g{index}", name="n")
                for index in range(MAX_GROUPS_PER_HOST)
            ),
            templates=tuple(
                ZabbixNamedRefEvidence(ref=f"t{index}", name="n")
                for index in range(MAX_TEMPLATES_PER_HOST)
            ),
            tags=tuple(
                ZabbixTagEvidence(tag=f"k{index}", value="v")
                for index in range(MAX_TAGS_PER_HOST)
            ),
        )
        evidence = host.canonical_evidence()
        compact_len = len(json.dumps(evidence, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8"))
        spaced_len = len(json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        maximum_separator_overhead = spaced_len - compact_len

        self.assertLessEqual(
            MAX_NORMALIZED_EVIDENCE_BYTES + maximum_separator_overhead,
            PERSISTED_NORMALIZED_EVIDENCE_LIMIT_BYTES,
        )


if __name__ == "__main__":
    unittest.main()
