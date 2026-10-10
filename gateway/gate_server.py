"""
Standalone gate server starter — runs in a child process.
Each gate gets its own Python process (sys.path isolation, no module name collisions).
"""
from __future__ import annotations

import sys
import os
from http.server import ThreadingHTTPServer


# Metadata for each gate: (pg_class_name, needs_authority_provider)
_GATE_META = {
    "g7": ("PgAlertPolicyLifecycleGateway", False),
    "g8": ("PgHumanOperationsGateway", True),
    "g9": ("PgNotificationGateway", True),
    "g10": ("PgIncidentGateway", True),
    "g11": ("PgIncidentResponseGateway", True),
}


def _passthrough_provider(domain_mod):
    """Build a dev authority_provider that always grants authority."""
    AuthoritySnapshot = domain_mod.AuthoritySnapshot

    def _provider(auth, required_action: str):
        return AuthoritySnapshot(
            tenant_id=auth.tenant_id,
            principal_id=getattr(auth, "principal_id", getattr(auth, "subject_id", "")),
            current=True,
            action=required_action,
            policy_revision="dev-passthrough",
        )

    return _provider


def serve(gate: str, gate_dir: str, host: str, port: int, db_url: str) -> None:
    """Entry point for a gate subprocess. Imports gate modules from gate_dir."""
    sys.path.insert(0, gate_dir)

    import psycopg  # type: ignore
    from importlib import import_module

    pg_mod = import_module("pg_port")
    http_mod = import_module("http_app")
    pg_class_name, needs_authority = _GATE_META[gate]

    conn = psycopg.connect(db_url, autocommit=True)
    port_obj = getattr(pg_mod, pg_class_name)(conn)

    if needs_authority:
        if gate == "g11":
            _all_g11_scopes = frozenset([
                "incident_response:push",
                "incident_response:read",
                "incident_response:write",
            ])
            def provider(token, tenant_id, _s=_all_g11_scopes):
                return "dev-passthrough-principal", _s
        else:
            domain_mod = import_module("domain")
            provider = _passthrough_provider(domain_mod)
        handler_cls = http_mod.make_handler(port_obj, provider)
    else:
        handler_cls = http_mod.make_handler(port_obj)

    server = ThreadingHTTPServer((host, port), handler_cls)
    print(f"[{gate}] listening on {host}:{port}", flush=True)
    server.serve_forever()
