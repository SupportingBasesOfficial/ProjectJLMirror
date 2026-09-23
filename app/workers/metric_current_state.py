"""Metric current state polling worker.

Reads last-known metric values from Zabbix (item.get lastvalue) and persists
current observations via the monitoring domain.  Requires ZABBIX_API_TOKEN.
"""

from __future__ import annotations

import logging
import time

import psycopg
from psycopg.rows import dict_row

from jlmirror_monitoring import collect_metric_current_state
from jlmirror_monitoring.source import opaque_token

from app.adapters.db_repositories import DbMonitoringMetricCurrentStateRepository, fetch_pending_ops
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


def run_metric_current_state_worker() -> None:
    interval = getattr(settings, "worker_metric_current_state_interval", 60)
    logger.info("Starting metric current state worker (interval=%ds)", interval)
    while True:
        try:
            _metric_current_state_cycle()
        except Exception:
            logger.exception("Metric current state cycle failed")
        time.sleep(interval)


def _metric_current_state_cycle() -> None:
    if not settings.zabbix_api_token:
        logger.debug("ZABBIX_API_TOKEN not set; skipping metric current state cycle")
        return

    pending = fetch_pending_ops("metric_current_state_sync")
    if not pending:
        return

    credential_resolver = _make_credential_resolver()
    for row in pending:
        tenant_id = row["tenant_id"]
        op_id = row["monitoring_sync_operation_id"]
        _run_one_metric_current_state(tenant_id, op_id, credential_resolver)


def _run_one_metric_current_state(
    tenant_id: str,
    monitoring_sync_operation_id: str,
    credential_resolver: EnvCredentialResolver,
) -> None:
    claim_token = opaque_token("mcs-claim")
    try:
        with psycopg.connect(settings.database_migration_url, row_factory=dict_row) as conn:
            repo = DbMonitoringMetricCurrentStateRepository(conn, tenant_id)
            try:
                claim = repo.claim_metric_current_state(monitoring_sync_operation_id, claim_token=claim_token)
            except Exception:
                logger.warning(
                    "Failed to claim metric current state op %s for tenant %s",
                    monitoring_sync_operation_id, tenant_id, exc_info=True,
                )
                return

            result = collect_metric_current_state(
                claim,
                credential_resolver=credential_resolver,
                outbound_admission=_admission,
                item_reader=_adapter,
            )
            try:
                repo.complete_metric_current_state(claim, result)
                logger.info(
                    "Metric current state completed: op=%s tenant=%s state=%s accepted=%d",
                    monitoring_sync_operation_id, tenant_id,
                    result.operation_state.value, len(result.accepted_observations),
                )
            except Exception:
                logger.error(
                    "Failed to complete metric current state op %s for tenant %s",
                    monitoring_sync_operation_id, tenant_id, exc_info=True,
                )
    except Exception:
        logger.exception(
            "Unexpected error running metric current state op %s for tenant %s",
            monitoring_sync_operation_id, tenant_id,
        )
