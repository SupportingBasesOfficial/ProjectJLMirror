"""Monitoring validation worker.

Runs the initial validation worker for monitoring sources (ADR for monitoring
domain).  Reads pending validation claims from the database, calls the Zabbix
API via ZabbixAdapter to verify host-group scope, and persists the result.

If ZABBIX_API_TOKEN is not configured the cycle is skipped with a warning.
"""

from __future__ import annotations

import logging
import time

import psycopg
from psycopg.rows import dict_row

from jlmirror_monitoring import validate_host_group_scope
from jlmirror_monitoring.source import opaque_token

from app.adapters.db_repositories import DbMonitoringValidationRepository, fetch_pending_ops
from app.adapters.provider_stubs import EnvCredentialResolver, PermissiveOutboundAdmission
from app.adapters.zabbix import ZabbixAdapter
from app.config import settings

logger = logging.getLogger(__name__)

_adapter = ZabbixAdapter()
_admission = PermissiveOutboundAdmission()


def _make_credential_resolver() -> EnvCredentialResolver:
    return EnvCredentialResolver(
        api_token=settings.zabbix_api_token,
        credential_generation_ref=settings.zabbix_credential_generation_ref,
    )


def run_validation_worker() -> None:
    """Run the monitoring validation worker loop."""
    logger.info("Starting validation worker (interval=%ds)", settings.worker_validation_interval)
    while True:
        try:
            _validation_cycle()
        except Exception:
            logger.exception("Validation cycle failed")
        time.sleep(settings.worker_validation_interval)


def _validation_cycle() -> None:
    """One validation cycle — claim and validate all pending monitoring sources."""
    if not settings.zabbix_api_token:
        logger.debug("ZABBIX_API_TOKEN not set; skipping validation cycle")
        return

    pending = fetch_pending_ops("validation_and_initial_sync")
    if not pending:
        return

    credential_resolver = _make_credential_resolver()
    for row in pending:
        tenant_id = row["tenant_id"]
        op_id = row["monitoring_sync_operation_id"]
        _run_one_validation(tenant_id, op_id, credential_resolver)


def _run_one_validation(
    tenant_id: str,
    monitoring_sync_operation_id: str,
    credential_resolver: EnvCredentialResolver,
) -> None:
    claim_token = opaque_token("vld-claim")
    try:
        with psycopg.connect(settings.database_migration_url, row_factory=dict_row) as conn:
            repo = DbMonitoringValidationRepository(conn, tenant_id)
            try:
                claim = repo.claim_initial_validation(monitoring_sync_operation_id, claim_token=claim_token)
            except Exception:
                logger.warning(
                    "Failed to claim validation op %s for tenant %s",
                    monitoring_sync_operation_id, tenant_id, exc_info=True,
                )
                return

            result = validate_host_group_scope(
                claim,
                credential_resolver=credential_resolver,
                outbound_admission=_admission,
                host_group_reader=_adapter,
            )
            evidence_id = opaque_token("vld-evidence")
            try:
                repo.complete_initial_validation(claim, result, validation_evidence_id=evidence_id)
                logger.info(
                    "Validation completed: op=%s tenant=%s state=%s",
                    monitoring_sync_operation_id, tenant_id, result.operation_state.value,
                )
            except Exception:
                logger.error(
                    "Failed to complete validation op %s for tenant %s",
                    monitoring_sync_operation_id, tenant_id, exc_info=True,
                )
    except Exception:
        logger.exception(
            "Unexpected error running validation op %s for tenant %s",
            monitoring_sync_operation_id, tenant_id,
        )
