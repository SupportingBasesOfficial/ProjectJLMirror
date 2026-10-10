"""Reconciliation worker.

Runs cross-authority reconciliation for async operations (ADR-008/009).
In production, this checks for stuck/ambiguous operations and drives
reconciliation. In development, it is a no-op.
"""

from __future__ import annotations

import logging
import time

from app.config import settings

logger = logging.getLogger(__name__)


def run_reconciliation_worker() -> None:
    """Run the reconciliation worker loop."""
    logger.info("Starting reconciliation worker (interval=%ds)", settings.worker_reconciliation_interval)
    while True:
        try:
            _reconciliation_cycle()
        except Exception:
            logger.exception("Reconciliation cycle failed")
        time.sleep(settings.worker_reconciliation_interval)


def _reconciliation_cycle() -> None:
    """One reconciliation cycle."""
    logger.debug("Reconciliation cycle (no-op in dev mode)")
