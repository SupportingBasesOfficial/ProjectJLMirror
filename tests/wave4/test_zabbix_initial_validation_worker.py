import unittest

from jlmirror_monitoring.source import ConfiguredProviderScope, OperationalEvidenceState, SyncOperationState, ZabbixProviderConfiguration
from jlmirror_monitoring.validation_worker import (
    AdmittedProviderEndpoint,
    CredentialResolutionError,
    EgressAdmissionError,
    InitialValidationClaim,
    InitialValidationWorker,
    ProviderAuthenticationError,
    ProviderProtocolError,
    ProviderUnavailableError,
    ResolvedZabbixCredential,
    ValidationFailureClass,
    ZabbixHostGroup,
)


class FakeRepository:
    def __init__(self, claim):
        self.claim = claim
        self.completed = []

    def claim_initial_validation(self, operation_id, *, claim_token):
        self.claimed_operation_id = operation_id
        self.claim_token = claim_token
        return InitialValidationClaim(claim_token=claim_token, **self.claim)

    def complete_initial_validation(self, claim, result, *, validation_evidence_id):
        self.completed.append((claim, result, validation_evidence_id))


class CredentialResolver:
    def __init__(self, error=None): self.error = error
    def resolve_zabbix_api_token(self, ref):
        if self.error: raise self.error()
        return ResolvedZabbixCredential("super-secret-token", "credential-generation:7")


class Admission:
    def __init__(self, events, error=None): self.events, self.error = events, error
    def admit_zabbix_api(self, config):
        self.events.append("egress")
        if self.error: raise self.error()
        return AdmittedProviderEndpoint(config.base_url + "/api_jsonrpc.php", "egress-decision:9")


class Reader:
    def __init__(self, events, groups=(), error=None): self.events, self.groups, self.error = events, groups, error
    def hostgroup_get(self, endpoint, credential, refs):
        self.events.append("hostgroup.get")
        if self.error: raise self.error()
        return self.groups


def claim_dict():
    return dict(
        tenant_id="tenant-a",
        monitoring_sync_operation_id="sync-a",
        monitoring_source_id="source-a",
        provider_scope_tenant_binding_id="binding-a",
        source_instance_generation="generation-a",
        configuration_revision=1,
        scope_revision=1,
        provider_instance_ref="provider-instance:central-zabbix",
        provider_configuration=ZabbixProviderConfiguration("https://zabbix.example.test/zabbix"),
        credential_binding_ref="credential-binding:central",
        configured_provider_scope=ConfiguredProviderScope.from_refs(("10", "20")),
    )


class InitialValidationWorkerTests(unittest.TestCase):
    def run_worker(self, groups=(), credential_error=None, admission_error=None, reader_error=None):
        events = []
        repo = FakeRepository(claim_dict())
        worker = InitialValidationWorker(
            repository=repo,
            credential_resolver=CredentialResolver(credential_error),
            outbound_admission=Admission(events, admission_error),
            host_group_reader=Reader(events, groups, reader_error),
        )
        result = worker.run("sync-a")
        self.assertEqual(len(repo.completed), 1)
        return result, events, repo

    def test_all_scope_anchors_visible_is_current(self):
        result, events, _ = self.run_worker((ZabbixHostGroup("10"), ZabbixHostGroup("20")))
        self.assertEqual(events, ["egress", "hostgroup.get"])
        self.assertEqual(result.operational_evidence_state, OperationalEvidenceState.CURRENT)
        self.assertEqual(result.operation_state, SyncOperationState.SUCCEEDED)
        self.assertEqual(result.visible_host_group_refs, ("10", "20"))
        self.assertEqual(result.missing_host_group_refs, ())
        self.assertIsNone(result.failure_class)

    def test_missing_anchor_is_incomplete_not_mass_absence(self):
        result, _, _ = self.run_worker((ZabbixHostGroup("10"),))
        self.assertEqual(result.operational_evidence_state, OperationalEvidenceState.INCOMPLETE)
        self.assertEqual(result.operation_state, SyncOperationState.RECONCILIATION_REQUIRED)
        self.assertEqual(result.failure_class, ValidationFailureClass.SCOPE_ANCHOR_INACCESSIBLE)
        self.assertEqual(result.visible_host_group_refs, ("10",))
        self.assertEqual(result.missing_host_group_refs, ("20",))

    def test_provider_unavailable_preserves_reconciliation_state(self):
        result, _, _ = self.run_worker(reader_error=ProviderUnavailableError)
        self.assertEqual(result.operational_evidence_state, OperationalEvidenceState.UNAVAILABLE)
        self.assertEqual(result.operation_state, SyncOperationState.RECONCILIATION_REQUIRED)
        self.assertEqual(result.failure_class, ValidationFailureClass.PROVIDER_UNAVAILABLE)

    def test_authentication_rejection_is_safe_degradation(self):
        result, _, _ = self.run_worker(reader_error=ProviderAuthenticationError)
        self.assertEqual(result.failure_class, ValidationFailureClass.PROVIDER_AUTHENTICATION_REJECTED)
        self.assertEqual(result.operational_evidence_state, OperationalEvidenceState.UNAVAILABLE)

    def test_credential_resolution_failure_never_attempts_network(self):
        result, events, _ = self.run_worker(credential_error=CredentialResolutionError)
        self.assertEqual(events, [])
        self.assertEqual(result.failure_class, ValidationFailureClass.CREDENTIAL_UNAVAILABLE)

    def test_egress_denial_prevents_provider_call(self):
        result, events, _ = self.run_worker(admission_error=EgressAdmissionError)
        self.assertEqual(events, ["egress"])
        self.assertEqual(result.failure_class, ValidationFailureClass.EGRESS_NOT_ADMITTED)

    def test_duplicate_or_out_of_scope_provider_response_fails_closed(self):
        result, _, _ = self.run_worker((ZabbixHostGroup("10"), ZabbixHostGroup("10")))
        self.assertEqual(result.failure_class, ValidationFailureClass.PROVIDER_PROTOCOL_INVALID)
        result, _, _ = self.run_worker((ZabbixHostGroup("10"), ZabbixHostGroup("99")))
        self.assertEqual(result.failure_class, ValidationFailureClass.PROVIDER_PROTOCOL_INVALID)

    def test_secret_is_not_exposed_by_credential_repr(self):
        credential = ResolvedZabbixCredential("super-secret-token", "credential-generation:7")
        self.assertNotIn("super-secret-token", repr(credential))


if __name__ == "__main__":
    unittest.main()
