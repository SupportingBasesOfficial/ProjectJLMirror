import unittest

from jlmirror_monitoring.host_inventory import (
    HostInventoryClaim,
    HostInventoryResult,
    HostInventoryWorker,
    InventoryFailureClass,
    MAX_HOSTS_PER_SNAPSHOT,
    ZabbixHostEvidence,
    ZabbixHostInterfaceEvidence,
    ZabbixHostSnapshot,
    ZabbixInventoryEvidence,
    ZabbixNamedRefEvidence,
    ZabbixTagEvidence,
)
from jlmirror_monitoring.source import ConfiguredProviderScope, OperationalEvidenceState, SyncOperationState, ZabbixProviderConfiguration
from jlmirror_monitoring.validation_worker import (
    AdmittedProviderEndpoint,
    CredentialResolutionError,
    EgressAdmissionError,
    ProviderUnavailableError,
    ResolvedZabbixCredential,
    ZabbixHostGroup,
)


class FakeRepository:
    def __init__(self, authoritative_result=None):
        self.completed = []
        self.authoritative_result = authoritative_result

    def claim_host_inventory(self, operation_id, *, claim_token):
        return HostInventoryClaim(
            claim_token=claim_token,
            tenant_id="tenant-a",
            monitoring_sync_operation_id=operation_id,
            monitoring_source_id="source-a",
            provider_scope_tenant_binding_id="binding-a",
            source_instance_generation="generation-a",
            configuration_revision=3,
            scope_revision=7,
            provider_instance_ref="provider-instance-a",
            provider_configuration=ZabbixProviderConfiguration("https://zabbix.example.test/zabbix"),
            credential_binding_ref="credential-a",
            configured_provider_scope=ConfiguredProviderScope.from_refs(("10", "20")),
        )

    def complete_host_inventory(self, claim, result, *, snapshot_evidence_id):
        self.completed.append((claim, result, snapshot_evidence_id))
        return self.authoritative_result if self.authoritative_result is not None else result


class Resolver:
    def __init__(self, error=None): self.error = error
    def resolve_zabbix_api_token(self, ref):
        if self.error: raise self.error()
        return ResolvedZabbixCredential("secret", "credential-generation:9")


class Admission:
    def __init__(self, events, error=None): self.events, self.error = events, error
    def admit_zabbix_api(self, config):
        self.events.append("egress")
        if self.error: raise self.error()
        return AdmittedProviderEndpoint(config.base_url + "/api_jsonrpc.php", "egress:7")


class Reader:
    def __init__(self, events, snapshot=None, error=None, visible_group_refs=("10", "20")):
        self.events, self.snapshot, self.error = events, snapshot, error
        self.visible_group_refs = visible_group_refs

    def hostgroup_get(self, endpoint, credential, refs):
        self.events.append(("hostgroup.get", tuple(refs)))
        if self.error: raise self.error()
        return tuple(ZabbixHostGroup(ref, f"group-{ref}") for ref in self.visible_group_refs)

    def host_get(self, endpoint, credential, refs, *, max_hosts):
        self.events.append(("host.get", tuple(refs), max_hosts))
        if self.error: raise self.error()
        return self.snapshot


def host(hostid="101", groups=("10",), name="edge-sw-01"):
    return ZabbixHostEvidence(
        hostid=hostid,
        technical_name=name,
        display_name="Edge Switch 01",
        inventory=ZabbixInventoryEvidence(vendor="Cisco", model="C9300", os="IOS-XE"),
        interfaces=(ZabbixHostInterfaceEvidence("1", "snmp", True, True, "10.0.0.2", None, "161"),),
        groups=tuple(ZabbixNamedRefEvidence(ref, f"group-{ref}") for ref in groups),
        templates=(ZabbixNamedRefEvidence("200", "Cisco IOS SNMP"),),
        tags=(ZabbixTagEvidence("site", "hq"),),
    )


class HostInventoryTests(unittest.TestCase):
    def run_worker(
        self,
        snapshot=None,
        *,
        credential_error=None,
        admission_error=None,
        reader_error=None,
        visible_group_refs=("10", "20"),
        authoritative_result=None,
    ):
        events = []
        repo = FakeRepository(authoritative_result)
        worker = HostInventoryWorker(
            repository=repo,
            credential_resolver=Resolver(credential_error),
            outbound_admission=Admission(events, admission_error),
            host_reader=Reader(events, snapshot, reader_error, visible_group_refs),
        )
        result = worker.run("sync-hosts-a")
        self.assertEqual(len(repo.completed), 1)
        return result, events

    def test_complete_scoped_snapshot_is_current(self):
        result, events = self.run_worker(ZabbixHostSnapshot((host(),), True))
        self.assertTrue(result.snapshot_complete)
        self.assertEqual(result.operation_state, SyncOperationState.SUCCEEDED)
        self.assertEqual(result.operational_evidence_state, OperationalEvidenceState.CURRENT)
        self.assertIsNone(result.failure_class)
        self.assertEqual(events[0], "egress")
        self.assertEqual(events[1][0], "hostgroup.get")
        self.assertEqual(events[2][0], "host.get")
        self.assertEqual(events[2][2], MAX_HOSTS_PER_SNAPSHOT)

    def test_worker_returns_persisted_completion_outcome(self):
        persisted = HostInventoryResult(
            OperationalEvidenceState.INCOMPLETE,
            SyncOperationState.RECONCILIATION_REQUIRED,
            (),
            False,
            None,
            "egress:7",
            "credential-generation:9",
        )
        result, _ = self.run_worker(
            ZabbixHostSnapshot((host(),), True),
            authoritative_result=persisted,
        )
        self.assertIs(result, persisted)
        self.assertEqual(result.operation_state, SyncOperationState.RECONCILIATION_REQUIRED)
        self.assertFalse(result.succeeded)

    def test_scope_anchors_are_revalidated_before_host_snapshot(self):
        result, events = self.run_worker(ZabbixHostSnapshot((), True), visible_group_refs=("10",))
        self.assertFalse(result.snapshot_complete)
        self.assertEqual(result.operation_state, SyncOperationState.RECONCILIATION_REQUIRED)
        self.assertEqual(result.operational_evidence_state, OperationalEvidenceState.INCOMPLETE)
        self.assertEqual(result.failure_class, InventoryFailureClass.SCOPE_ANCHOR_INACCESSIBLE)
        self.assertEqual(events[0], "egress")
        self.assertEqual(events[1][0], "hostgroup.get")
        self.assertFalse(any(event[0] == "host.get" for event in events if isinstance(event, tuple)))

    def test_truncated_snapshot_preserves_positive_hosts_but_is_not_negative_authority(self):
        result, _ = self.run_worker(ZabbixHostSnapshot((host(),), False))
        self.assertFalse(result.snapshot_complete)
        self.assertEqual(result.operation_state, SyncOperationState.RECONCILIATION_REQUIRED)
        self.assertEqual(result.operational_evidence_state, OperationalEvidenceState.INCOMPLETE)
        self.assertEqual(result.failure_class, InventoryFailureClass.SNAPSHOT_TRUNCATED)
        self.assertEqual(len(result.hosts), 1)

    def test_host_without_current_scope_evidence_fails_closed(self):
        result, _ = self.run_worker(ZabbixHostSnapshot((host(groups=("999",)),), True))
        self.assertFalse(result.snapshot_complete)
        self.assertEqual(result.failure_class, InventoryFailureClass.SCOPE_EVIDENCE_INVALID)
        self.assertEqual(result.hosts, ())

    def test_provider_failure_never_becomes_empty_authoritative_snapshot(self):
        result, _ = self.run_worker(reader_error=ProviderUnavailableError)
        self.assertFalse(result.snapshot_complete)
        self.assertEqual(result.operational_evidence_state, OperationalEvidenceState.UNAVAILABLE)
        self.assertEqual(result.failure_class, InventoryFailureClass.PROVIDER_UNAVAILABLE)

    def test_credential_and_egress_failures_prevent_provider_read(self):
        result, events = self.run_worker(credential_error=CredentialResolutionError)
        self.assertEqual(events, [])
        self.assertEqual(result.failure_class, InventoryFailureClass.CREDENTIAL_UNAVAILABLE)
        result, events = self.run_worker(admission_error=EgressAdmissionError)
        self.assertEqual(events, ["egress"])
        self.assertEqual(result.failure_class, InventoryFailureClass.EGRESS_NOT_ADMITTED)

    def test_provider_evidence_is_normalized_and_fingerprint_stable(self):
        first = host()
        second = host()
        self.assertEqual(first.canonical_evidence(), second.canonical_evidence())
        self.assertEqual(first.evidence_fingerprint(), second.evidence_fingerprint())
        evidence = first.canonical_evidence()
        self.assertEqual(evidence["inventory"]["vendor"], "Cisco")
        self.assertEqual(evidence["interfaces"][0]["interface_type"], "snmp")

    def test_resource_classification_is_not_encoded_in_provider_evidence(self):
        evidence = host().canonical_evidence()
        self.assertNotIn("resource_kind", evidence)
        self.assertNotIn("canonical_device_class", evidence)
        self.assertNotIn("canonical_device_type", evidence)

    def test_duplicate_provider_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            ZabbixHostSnapshot((host("101"), host("101")), True)

    def test_duplicate_group_and_interface_refs_are_rejected(self):
        with self.assertRaises(ValueError):
            ZabbixHostEvidence(
                hostid="101",
                technical_name="h",
                display_name="h",
                inventory=ZabbixInventoryEvidence(),
                interfaces=(
                    ZabbixHostInterfaceEvidence("1", "agent", True, True, "10.0.0.1", None, "10050"),
                    ZabbixHostInterfaceEvidence("1", "snmp", False, True, "10.0.0.1", None, "161"),
                ),
                groups=(ZabbixNamedRefEvidence("10"),),
                templates=(),
                tags=(),
            )

    def test_snapshot_completeness_requires_real_boolean(self):
        with self.assertRaises(ValueError):
            ZabbixHostSnapshot((host(),), "true")  # type: ignore[arg-type]

    def test_interface_boolean_fields_reject_integer_or_text_coercion(self):
        with self.assertRaises(ValueError):
            ZabbixHostInterfaceEvidence("1", "snmp", 1, True, "10.0.0.2", None, "161")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            ZabbixHostInterfaceEvidence("1", "snmp", True, "true", "10.0.0.2", None, "161")  # type: ignore[arg-type]

    def test_non_snapshot_adapter_return_is_protocol_invalid_not_authoritative_empty(self):
        result, _ = self.run_worker({"hosts": [], "complete": True})
        self.assertFalse(result.snapshot_complete)
        self.assertEqual(result.failure_class, InventoryFailureClass.PROVIDER_PROTOCOL_INVALID)
        self.assertEqual(result.hosts, ())

    def test_non_normalized_collection_members_are_rejected(self):
        with self.assertRaises(ValueError):
            ZabbixHostEvidence(
                hostid="101",
                technical_name="h",
                display_name="h",
                inventory=ZabbixInventoryEvidence(),
                interfaces=(),
                groups=("10",),  # type: ignore[arg-type]
                templates=(),
                tags=(),
            )


if __name__ == "__main__":
    unittest.main()
