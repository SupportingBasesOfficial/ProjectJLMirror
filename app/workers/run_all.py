"""Run all independent workers in a single process (development convenience).

In production, each worker should run as its own process/deployment (ADR-001).
This module is a convenience for local development.
"""

from __future__ import annotations

import logging
import signal
import threading

from app.workers.host_inventory import run_host_inventory_worker
from app.workers.metric_current_state import run_metric_current_state_worker
from app.workers.metric_definitions import run_metric_definitions_worker
from app.workers.metric_history import run_metric_history_worker
from app.workers.outbox_dispatcher import run_outbox_dispatcher
from app.workers.problem_state import run_problem_state_worker
from app.workers.reconciliation import run_reconciliation_worker
from app.workers.validation import run_validation_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

_workers = [
    ("outbox-dispatcher", run_outbox_dispatcher),
    ("validation", run_validation_worker),
    ("host-inventory", run_host_inventory_worker),
    ("metric-definitions", run_metric_definitions_worker),
    ("metric-current-state", run_metric_current_state_worker),
    ("metric-history", run_metric_history_worker),
    ("problem-state", run_problem_state_worker),
    ("reconciliation", run_reconciliation_worker),
]


def main() -> None:
    """Start all workers in background threads and wait for shutdown."""
    logger.info("Starting all JLMIRROR workers...")
    threads: list[threading.Thread] = []
    for name, target in _workers:
        t = threading.Thread(target=target, name=name, daemon=True)
        t.start()
        threads.append(t)
        logger.info("Started worker: %s", name)

    def _shutdown(signum, frame):
        logger.info("Received signal %s, shutting down workers...", signum)
        # Daemon threads will be killed when the main thread exits.
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        for t in threads:
            t.join()
    except SystemExit:
        pass


if __name__ == "__main__":
    main()
