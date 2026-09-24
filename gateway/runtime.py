"""
Gateway runtime entry point.

Starts each gate as an isolated subprocess (its own sys.path, no module
name collisions), then starts a reverse-proxy server on GATEWAY_PORT that
routes /api/v1/ requests to the appropriate gate.

Usage:
    python -m gateway.runtime

Environment variables:
    DATABASE_URL    psycopg conninfo string (required)
    GATEWAY_HOST    proxy bind host   (default: 0.0.0.0)
    GATEWAY_PORT    proxy bind port   (default: 8000)
    GATES           comma-separated gate keys to start (default: all)
                    e.g. GATES=g11 to start only incident-response

Gate ports are allocated internally (127.0.0.1 only, not exposed):
    g7=8007  g8=8008  g9=8009  g10=8010  g11=8011
"""
from __future__ import annotations

import multiprocessing
import os
import signal
import sys
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_APPS = _ROOT / "apps"

_GATE_DIRS = {
    "g7":  str(_APPS / "g7-alert-policy-lifecycle"),
    "g8":  str(_APPS / "g8-human-operations"),
    "g9":  str(_APPS / "g9-notification-delivery"),
    "g10": str(_APPS / "g10-itsm"),
    "g11": str(_APPS / "g11-incident-response"),
}

_GATE_INTERNAL_PORTS = {
    "g7": 8007, "g8": 8008, "g9": 8009, "g10": 8010, "g11": 8011,
}

_ALL_GATES = ["g7", "g8", "g9", "g10", "g11"]


def _start_gate_process(gate: str, db_url: str) -> multiprocessing.Process:
    from gateway.gate_server import serve
    p = multiprocessing.Process(
        target=serve,
        args=(gate, _GATE_DIRS[gate], "127.0.0.1", _GATE_INTERNAL_PORTS[gate], db_url),
        name=f"gate-{gate}",
        daemon=True,
    )
    p.start()
    return p


def _wait_for_gate(gate: str, timeout: float = 10.0) -> bool:
    import socket
    port = _GATE_INTERNAL_PORTS[gate]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def main() -> int:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL is required", file=sys.stderr)
        return 1

    host = os.environ.get("GATEWAY_HOST", "0.0.0.0")
    proxy_port = int(os.environ.get("GATEWAY_PORT", "8000"))

    gates_env = os.environ.get("GATES", "")
    active_gates = [g.strip() for g in gates_env.split(",") if g.strip()] or _ALL_GATES
    active_gates = [g for g in active_gates if g in _GATE_DIRS]

    # On Windows, multiprocessing spawn requires __main__ guard
    multiprocessing.freeze_support()

    print(f"Starting gates: {', '.join(active_gates)}")
    processes = []
    for gate in active_gates:
        p = _start_gate_process(gate, db_url)
        processes.append((gate, p))

    # Wait for all gates to be reachable
    for gate, _ in processes:
        if _wait_for_gate(gate):
            print(f"  [{gate}] ready on port {_GATE_INTERNAL_PORTS[gate]}")
        else:
            print(f"  [{gate}] WARNING: did not become ready within 10s", file=sys.stderr)

    from gateway.proxy import ProxyHandler
    ProxyHandler.gate_ports = {g: _GATE_INTERNAL_PORTS[g] for g in active_gates}

    server = ThreadingHTTPServer((host, proxy_port), ProxyHandler)
    print(f"JLMirror gateway proxy listening on http://{host}:{proxy_port}")
    print(f"Routes: {' · '.join(active_gates)}")

    def _shutdown(sig, frame):
        print("\nShutting down gateway…")
        server.shutdown()
        for _, p in processes:
            p.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
