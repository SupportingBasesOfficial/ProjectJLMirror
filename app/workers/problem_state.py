"""Problem state polling worker.

Reads active Zabbix problems and (where recoveries exist) recovery events,
persists canonical problem evidence via the monitoring domain.
Requires ZABBIX_API_TOKEN.

NOT YET WIRED TO DB — blocked on two missing pieces:

1. `monitoring.list_zabbix_problem_state_associations` stored proc does not
   exist.  The claim proc `claim_zabbix_problem_state` returns only 6 cols
   (tenant_id, op_id, claim_token, monitoring_source_id,
   source_instance_generation, current_state_poll_epoch/generation) — it does
   NOT return provider_instance_ref / provider_base_url / credential_binding_ref
   / configured_provider_scope, so the claim object cannot be built to call
   collect_problem_state().

2. `CanonicalProblemEvidence` does not carry `provider_trigger_ref`, which is
   required as a key in the `p_active_problems` JSONB argument to
   `complete_zabbix_problem_state`.

When both are resolved, wire this worker following the same pattern as
metric_current_state.py:
    - fetch_pending_ops("problem_state_sync")
    - DbMonitoringProblemStateRepository.claim_problem_state(op_id, claim_token=...)
    - collect_problem_state(claim, credential_resolver=..., outbound_admission=..., reader=_adapter)
    - repo.complete_problem_state(claim, result)
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


def run_problem_state_worker() -> None:
    interval = getattr(settings, "worker_problem_state_interval", 30)
    logger.info("Starting problem state worker (interval=%ds)", interval)
    while True:
        try:
            _problem_state_cycle()
        except Exception:
            logger.exception("Problem state cycle failed")
        time.sleep(interval)


def _problem_state_cycle() -> None:
    if not settings.zabbix_api_token:
        logger.debug("ZABBIX_API_TOKEN not set; skipping problem state cycle")
        return
    # DB integration blocked — see module docstring.
    logger.debug("Problem state DB integration not yet implemented; skipping")
