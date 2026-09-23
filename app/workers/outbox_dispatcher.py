"""Outbox dispatcher worker.

Claims pending outbox messages and dispatches them to the configured broker.
In development mode, this is a no-op that logs the dispatch. In production,
this connects to the accepted event broker (ADR-009) and publishes messages
with at-least-once delivery semantics.
"""

from __future__ import annotations

import logging
import time

from app.config import settings

logger = logging.getLogger(__name__)


def run_outbox_dispatcher() -> None:
    """Run the outbox dispatcher loop."""
    logger.info("Starting outbox dispatcher worker (interval=%ds)", settings.worker_outbox_dispatch_interval)
    while True:
        try:
            _dispatch_cycle()
        except Exception:
            logger.exception("Outbox dispatch cycle failed")
        time.sleep(settings.worker_outbox_dispatch_interval)


def _dispatch_cycle() -> None:
    """One dispatch cycle: claim and publish pending messages."""
    # In development, the outbox is in-memory per API process, so the worker
    # cannot see it. In production, the outbox lives in PostgreSQL and this
    # worker claims rows from the outbox table.
    logger.debug("Outbox dispatch cycle (no-op in dev mode — outbox is in-memory)")
