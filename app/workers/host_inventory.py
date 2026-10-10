"""Host inventory polling worker.

Reads pending host inventory sync operations from the database, polls Zabbix
for current host state via ZabbixAdapter, and persists the result.
Requires ZABBIX_API_TOKEN.
"""

from __future__ import annotations

import logging
import time

import psycopg
from psycopg.rows import dict_row

from jlmirror_monitoring import collect_host_inventory
from jlmirror_monitoring.source import opaque_token

from app.adapters.db_repositories import DbMonitoringHostInventoryRepository, fetch_pending_ops
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


def run_host_inventory_worker() -> None:
    interval = getattr(settings, "worker_host_inventory_interval", 60)
    logger.info("Starting host inventory worker (interval=%ds)", interval)
    while True:
        try:
            _host_inventory_cycle()
        except Exception:
            logger.exception("Host inventory cycle failed")
        time.sleep(interval)


def _host_inventory_cycle() -> None:
    if not settings.zabbix_api_token:
        logger.debug("ZABBIX_API_TOKEN not set; skipping host inventory cycle")
        return

    pending = fetch_pending_ops("host_inventory_sync")
    if not pending:
        return

    credential_resolver = _make_credential_resolver()
    for row in pending:
        tenant_id = row["tenant_id"]
        op_id = row["monitoring_sync_operation_id"]
        _run_one_host_inventory(tenant_id, op_id, credential_resolver)


def _run_one_host_inventory(
    tenant_id: str,
    monitoring_sync_operation_id: str,
    credential_resolver: EnvCredentialResolver,
) -> None:
    claim_token = opaque_token("inv-claim")
    try:
        with psycopg.connect(settings.database_migration_url, row_factory=dict_row) as conn:
            repo = DbMonitoringHostInventoryRepository(conn, tenant_id)
            try:
                claim = repo.claim_host_inventory(monitoring_sync_operation_id, claim_token=claim_token)
            except Exception:
                logger.warning(
                    "Failed to claim host inventory op %s for tenant %s",
                    monitoring_sync_operation_id, tenant_id, exc_info=True,
                )
                return

            result = collect_host_inventory(
                claim,
                credential_resolver=credential_resolver,
                outbound_admission=_admission,
                host_reader=_adapter,
            )
            snapshot_id = opaque_token("inv-snapshot")
            try:
                repo.complete_host_inventory(claim, result, snapshot_evidence_id=snapshot_id)
                logger.info(
                    "Host inventory completed: op=%s tenant=%s state=%s hosts=%d complete=%s",
                    monitoring_sync_operation_id, tenant_id,
                    result.operation_state.value, len(result.hosts), result.snapshot_complete,
                )
            except Exception:
                logger.error(
                    "Failed to complete host inventory op %s for tenant %s",
                    monitoring_sync_operation_id, tenant_id, exc_info=True,
                )
    except Exception:
        logger.exception(
            "Unexpected error running host inventory op %s for tenant %s",
            monitoring_sync_operation_id, tenant_id,
        )
