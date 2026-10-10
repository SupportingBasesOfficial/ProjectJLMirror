"""Metric definitions polling worker.

Collects Zabbix item (metric) definitions for all monitoring sources and persists
them via the monitoring domain.  Requires ZABBIX_API_TOKEN.
"""

from __future__ import annotations

import logging
import time

import psycopg
from psycopg.rows import dict_row

from jlmirror_monitoring import collect_metric_definitions
from jlmirror_monitoring.source import opaque_token

from app.adapters.db_repositories import DbMonitoringMetricDefinitionRepository, fetch_pending_ops
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


def run_metric_definitions_worker() -> None:
    interval = getattr(settings, "worker_metric_definitions_interval", 300)
    logger.info("Starting metric definitions worker (interval=%ds)", interval)
    while True:
        try:
            _metric_definitions_cycle()
        except Exception:
            logger.exception("Metric definitions cycle failed")
        time.sleep(interval)


def _metric_definitions_cycle() -> None:
    if not settings.zabbix_api_token:
        logger.debug("ZABBIX_API_TOKEN not set; skipping metric definitions cycle")
        return

    pending = fetch_pending_ops("metric_definition_sync")
    if not pending:
        return

    credential_resolver = _make_credential_resolver()
    for row in pending:
        tenant_id = row["tenant_id"]
        op_id = row["monitoring_sync_operation_id"]
        _run_one_metric_definitions(tenant_id, op_id, credential_resolver)


def _run_one_metric_definitions(
    tenant_id: str,
    monitoring_sync_operation_id: str,
    credential_resolver: EnvCredentialResolver,
) -> None:
    claim_token = opaque_token("mdef-claim")
    try:
        with psycopg.connect(settings.database_migration_url, row_factory=dict_row) as conn:
            repo = DbMonitoringMetricDefinitionRepository(conn, tenant_id)
            try:
                claim = repo.claim_metric_definitions(monitoring_sync_operation_id, claim_token=claim_token)
            except Exception:
                logger.warning(
                    "Failed to claim metric definitions op %s for tenant %s",
                    monitoring_sync_operation_id, tenant_id, exc_info=True,
                )
                return

            result = collect_metric_definitions(
                claim,
                credential_resolver=credential_resolver,
                outbound_admission=_admission,
                item_reader=_adapter,
            )
            snapshot_id = opaque_token("mdef-snapshot")
            try:
                repo.complete_metric_definitions(claim, result, snapshot_evidence_id=snapshot_id)
                logger.info(
                    "Metric definitions completed: op=%s tenant=%s state=%s items=%d complete=%s",
                    monitoring_sync_operation_id, tenant_id,
                    result.operation_state.value, len(result.items), result.snapshot_complete,
                )
            except Exception:
                logger.error(
                    "Failed to complete metric definitions op %s for tenant %s",
                    monitoring_sync_operation_id, tenant_id, exc_info=True,
                )
    except Exception:
        logger.exception(
            "Unexpected error running metric definitions op %s for tenant %s",
            monitoring_sync_operation_id, tenant_id,
        )
