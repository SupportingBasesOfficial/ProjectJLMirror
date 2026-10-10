"""Metric history ingestion worker.

Fetches bounded Zabbix history windows (history.get) and persists immutable
canonical metric observations via the monitoring domain.  Requires ZABBIX_API_TOKEN.

NOT YET WIRED TO DB — blocked on missing stored procs:

1. No `monitoring.claim_zabbix_metric_history(tenant_id, op_id, claim_token)` proc
   exists.  The claim must return source identity, history window (time_from,
   time_till), and the set of HistoryMetricTarget rows to poll (itemid,
   metric_definition_id, monitoring_resource_id, value_kind, history_value_type).
   The runtime admission check (monitoring_metric_history_runtime_admission) must
   also be performed inside the claim transaction.

2. No `monitoring.list_zabbix_metric_history_targets(...)` pagination proc exists
   (same pattern as list_zabbix_metric_current_targets) to build the targets tuple.

3. No `monitoring.complete_zabbix_metric_history(tenant_id, op_id, claim_token,
   coverage_state, observations JSONB)` proc exists to persist the accepted
   observations and advance the per-stream checkpoint / gap-evidence.

When all three procs are added, wire this worker following the pattern in
metric_current_state.py:
    - fetch_pending_ops("metric_history_sync")
    - DbMonitoringMetricHistoryRepository.claim_metric_history(op_id, claim_token=...)
    - read_metric_history_window(claim, credential_resolver=..., outbound_admission=..., reader=_adapter)
    - repo.complete_metric_history(claim, result)
"""

from __future__ import annotations

import logging
import time

from app.adapters.provider_stubs import EnvCredentialResolver, PermissiveOutboundAdmission
from app.adapters.zabbix import ZabbixAdapter
from app.config import settings

logger = logging.getLogger(__name__)

_adapter = ZabbixAdapter()
_admission = PermissiveOutboundAdmission()


def run_metric_history_worker() -> None:
    interval = getattr(settings, "worker_metric_history_interval", 120)
    logger.info("Starting metric history worker (interval=%ds)", interval)
    while True:
        try:
            _metric_history_cycle()
        except Exception:
            logger.exception("Metric history cycle failed")
        time.sleep(interval)


def _metric_history_cycle() -> None:
    if not settings.zabbix_api_token:
        logger.debug("ZABBIX_API_TOKEN not set; skipping metric history cycle")
        return
    # DB integration blocked — see module docstring.
    logger.debug("Metric history DB integration not yet implemented; skipping")
