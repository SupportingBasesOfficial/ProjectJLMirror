"""Dev-mode infrastructure adapters for Zabbix credential resolution and outbound admission.

These stubs satisfy the CredentialResolver and OutboundAdmission Protocols using
environment configuration.  They are intentionally permissive (no egress firewall)
and should be replaced by a secrets-manager-backed implementation before production.
"""

from __future__ import annotations

from jlmirror_monitoring.validation_worker import (
    AdmittedProviderEndpoint,
    CredentialResolutionError,
    EgressAdmissionError,
    ResolvedZabbixCredential,
)
from jlmirror_monitoring.source import ZabbixProviderConfiguration


class EnvCredentialResolver:
    """Resolves Zabbix API tokens from environment configuration.

    In dev, a single token is shared across all credential_binding_refs.
    Production replaces this with a secrets-manager-backed adapter.
    """

    def __init__(self, api_token: str, credential_generation_ref: str) -> None:
        self._api_token = api_token
        self._credential_generation_ref = credential_generation_ref

    def resolve_zabbix_api_token(self, credential_binding_ref: str) -> ResolvedZabbixCredential:
        if not self._api_token:
            raise CredentialResolutionError(
                f"No ZABBIX_API_TOKEN configured for binding ref '{credential_binding_ref}'"
            )
        return ResolvedZabbixCredential(
            api_token=self._api_token,
            credential_generation_ref=self._credential_generation_ref,
        )


class PermissiveOutboundAdmission:
    """Dev-mode outbound admission: admits all configured Zabbix endpoints.

    Constructs AdmittedProviderEndpoint by appending /api_jsonrpc.php to the
    canonical base_url.  Production replaces this with an egress-policy-enforced
    admission controller that validates against the platform firewall registry.
    """

    _DEV_DECISION_REF = "dev-egress-admit-1"

    def admit_zabbix_api(
        self, provider_configuration: ZabbixProviderConfiguration
    ) -> AdmittedProviderEndpoint:
        base = provider_configuration.base_url.rstrip("/")
        api_url = f"{base}/api_jsonrpc.php"
        return AdmittedProviderEndpoint(
            api_url=api_url,
            egress_decision_ref=self._DEV_DECISION_REF,
        )
