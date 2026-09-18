from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/g3-resource-inventory"))

from inventory import ResourceInventory, ResourceRecord, READ_ACTION  # noqa: E402


class Authorization:
    def __init__(self) -> None:
        self.actor_ref = "principal-a"
        self.calls: list[tuple[str, str, str]] = []
        self.revoked = False

    def require(self, *, actor_ref: str, tenant_id: str, action: str):
        if self.revoked:
            raise RuntimeError("revoked")
        self.calls.append((actor_ref, tenant_id, action))
        return object()


class Repository:
    def __init__(self, row: ResourceRecord) -> None:
        self.row = row

    def list_active(self, *, tenant_id: str):
        if tenant_id != "tenant-a":
            return ()
        return (self.row,)

    def get(self, *, tenant_id: str, monitoring_resource_id: str):
        if tenant_id == "tenant-a" and monitoring_resource_id == self.row.monitoring_resource_id:
            return self.row
        return None


def row() -> ResourceRecord:
    return ResourceRecord(
        monitoring_resource_id="resource-101",
        monitoring_source_id="source-a",
        source_instance_generation="generation-a",
        generation_state="active_generation",
        display_name="Core Switch",
        resource_kind="host",
        scope_state="in_scope",
        scope_projection_revision=1,
        scope_evidence_state="current",
        presence_state="present",
        presence_evidence_state="current",
        provider_object_kind="zabbix_host",
        provider_external_ref="101",
        last_observed_at="2026-09-18T00:00:00Z",
        last_confirmed_present_at="2026-09-18T00:00:00Z",
        created_at="2026-09-18T00:00:00Z",
        updated_at="2026-09-18T00:00:00Z",
    )


class InventoryTests(unittest.TestCase):
    def test_list_uses_canonical_identity_and_hides_provider_native_id(self):
        auth = Authorization()
        view = ResourceInventory(repository=Repository(row()), authorization=auth).list_current(tenant_id="tenant-a")
        self.assertEqual(view["generation_state"], "active_generation")
        self.assertEqual(view["items"][0]["monitoring_resource_id"], "resource-101")
        self.assertNotIn("external_references", view["items"][0])
        self.assertNotIn("provider_external_ref", view["items"][0])
        self.assertEqual(auth.calls, [
            ("principal-a", "tenant-a", READ_ACTION),
            ("principal-a", "tenant-a", READ_ACTION),
        ])

    def test_detail_exposes_bounded_provider_evidence_not_identity(self):
        view = ResourceInventory(repository=Repository(row()), authorization=Authorization()).get_detail(
            tenant_id="tenant-a",
            monitoring_resource_id="resource-101",
        )
        self.assertEqual(view["monitoring_resource_id"], "resource-101")
        self.assertEqual(view["external_references"], {
            "provider_object_kind": "zabbix_host",
            "provider_external_ref": "101",
        })

    def test_historical_row_never_enters_current_list(self):
        historical = replace(row(), generation_state="historical_generation")
        with self.assertRaises(RuntimeError):
            ResourceInventory(repository=Repository(historical), authorization=Authorization()).list_current(
                tenant_id="tenant-a"
            )

    def test_historical_detail_is_visibly_historical(self):
        historical = replace(row(), generation_state="historical_generation")
        view = ResourceInventory(repository=Repository(historical), authorization=Authorization()).get_detail(
            tenant_id="tenant-a",
            monitoring_resource_id="resource-101",
        )
        self.assertEqual(view["generation_state"], "historical_generation")

    def test_resource_kind_is_host_not_device_classification(self):
        unsupported = replace(row(), resource_kind="server")
        with self.assertRaises(RuntimeError):
            ResourceInventory(repository=Repository(unsupported), authorization=Authorization()).list_current(
                tenant_id="tenant-a"
            )

    def test_second_authorization_check_can_fail_after_read(self):
        class RevokingRepository(Repository):
            def list_active(inner_self, *, tenant_id: str):
                rows = super().list_active(tenant_id=tenant_id)
                auth.revoked = True
                return rows

        auth = Authorization()
        with self.assertRaises(RuntimeError):
            ResourceInventory(repository=RevokingRepository(row()), authorization=auth).list_current(
                tenant_id="tenant-a"
            )


if __name__ == "__main__":
    unittest.main()
