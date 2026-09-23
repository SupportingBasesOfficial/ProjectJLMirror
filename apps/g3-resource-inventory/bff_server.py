from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http import HTTPStatus
import importlib.util
import json
from pathlib import Path
import ssl
import subprocess
import sys
from urllib.parse import parse_qs, quote, unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
APP = Path(__file__).resolve().parent
FRONTEND = APP / "frontend"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(APP))

from current_authorization import BoundResourceAuthorization
from inventory import ResourceInventory, ResourceRecord
from jlmirror_authority.model import AdmissionDenied
from jlmirror_authority.session import BrowserSessionHandle, resolve_browser_session


def _load_g1():
    path = ROOT / "apps/g1-identity-tenant-shell/bff_server.py"
    spec = importlib.util.spec_from_file_location("jlmirror_g1_g3_composed_bff", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("canonical G1 BFF cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


G1 = _load_g1()
G3_CASE_COOKIE = "jlmirror_g3_case"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Pg:
    def __init__(self, *, container: str, database: str) -> None:
        self.container = container
        self.database = database

    def query(self, sql: str, **variables: str) -> str:
        command = [
            "docker", "exec", "-i", self.container,
            "psql", "-Atq", "-v", "ON_ERROR_STOP=1",
            "-U", "postgres", "-d", self.database,
        ]
        for key, value in variables.items():
            command.extend(["-v", f"{key}={value}"])
        completed = subprocess.run(
            command,
            input=sql,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip()[-2000:])
        return completed.stdout.strip()


class FixtureResourceReadPort:
    def __init__(self) -> None:
        self._rows = (
            ResourceRecord(
                monitoring_resource_id="resource-101",
                monitoring_source_id="source-a",
                source_instance_generation="generation-a",
                generation_state="active_generation",
                display_name="Core Switch",
                resource_kind="host",
                scope_state="in_scope",
                scope_projection_revision=1,
                scope_evidence_state="current",
                presence_state="present",
                presence_evidence_state="current",
                provider_object_kind="zabbix_host",
                provider_external_ref="101",
                last_observed_at="2026-09-18T00:00:00Z",
                last_confirmed_present_at="2026-09-18T00:00:00Z",
                created_at="2026-09-18T00:00:00Z",
                updated_at="2026-09-18T00:00:00Z",
            ),
            ResourceRecord(
                monitoring_resource_id="resource-102",
                monitoring_source_id="source-a",
                source_instance_generation="generation-a",
                generation_state="active_generation",
                display_name="Application Server",
                resource_kind="host",
                scope_state="in_scope",
                scope_projection_revision=1,
                scope_evidence_state="current",
                presence_state="present",
                presence_evidence_state="current",
                provider_object_kind="zabbix_host",
                provider_external_ref="102",
                last_observed_at="2026-09-18T00:00:00Z",
                last_confirmed_present_at="2026-09-18T00:00:00Z",
                created_at="2026-09-18T00:00:00Z",
                updated_at="2026-09-18T00:00:00Z",
            ),
        )

    def list_active(self, *, tenant_id: str):
        return self._rows if tenant_id == "tenant-a" else ()

    def get(self, *, tenant_id: str, monitoring_resource_id: str):
        if tenant_id != "tenant-a":
            return None
        return next((row for row in self._rows if row.monitoring_resource_id == monitoring_resource_id), None)


class PgResourceReadPort:
    def __init__(self, pg: Pg) -> None:
        self.pg = pg

    @staticmethod
    def _record(value: dict) -> ResourceRecord:
        expected = {
            "monitoring_resource_id", "monitoring_source_id", "source_instance_generation",
            "generation_state", "display_name", "resource_kind", "scope_state",
            "scope_projection_revision", "scope_evidence_state", "presence_state",
            "presence_evidence_state", "provider_object_kind", "provider_external_ref",
            "last_observed_at", "last_confirmed_present_at", "created_at", "updated_at",
        }
        if set(value) != expected:
            raise RuntimeError("canonical resource read shape is invalid")
        return ResourceRecord(**value)

    def list_active(self, *, tenant_id: str):
        raw = self.pg.query(
            """
BEGIN;
SET LOCAL ROLE wave4_runtime;
SET LOCAL jlmirror.tenant_id=:'tenant';
SELECT COALESCE(
  json_agg(
    json_build_object(
      'monitoring_resource_id', r.monitoring_resource_id,
      'monitoring_source_id', r.monitoring_source_id,
      'source_instance_generation', r.source_instance_generation,
      'generation_state', 'active_generation',
      'display_name', r.display_name,
      'resource_kind', r.resource_kind,
      'scope_state', r.scope_state,
      'scope_projection_revision', r.scope_projection_revision,
      'scope_evidence_state', r.scope_evidence_state,
      'presence_state', r.presence_state,
      'presence_evidence_state', r.presence_evidence_state,
      'provider_object_kind', r.provider_object_kind,
      'provider_external_ref', r.provider_external_ref,
      'last_observed_at', r.last_observed_at,
      'last_confirmed_present_at', r.last_confirmed_present_at,
      'created_at', r.created_at,
      'updated_at', r.updated_at
    ) ORDER BY r.monitoring_resource_id
  ),
  '[]'::json
)::text
FROM monitoring.monitoring_resource r
JOIN monitoring.monitoring_source s
  ON s.tenant_id=r.tenant_id
 AND s.monitoring_source_id=r.monitoring_source_id
WHERE r.tenant_id=:'tenant'
  AND r.source_instance_generation=s.active_source_instance_generation;
COMMIT;
""",
            tenant=tenant_id,
        )
        values = json.loads(raw or "[]")
        if not isinstance(values, list) or len(values) > 500:
            raise RuntimeError("canonical resource list is outside G3 response bounds")
        return tuple(self._record(value) for value in values)

    def get(self, *, tenant_id: str, monitoring_resource_id: str):
        raw = self.pg.query(
            """
BEGIN;
SET LOCAL ROLE wave4_runtime;
SET LOCAL jlmirror.tenant_id=:'tenant';
SELECT json_build_object(
  'monitoring_resource_id', r.monitoring_resource_id,
  'monitoring_source_id', r.monitoring_source_id,
  'source_instance_generation', r.source_instance_generation,
  'generation_state', CASE
      WHEN r.source_instance_generation=s.active_source_instance_generation
      THEN 'active_generation' ELSE 'historical_generation' END,
  'display_name', r.display_name,
  'resource_kind', r.resource_kind,
  'scope_state', r.scope_state,
  'scope_projection_revision', r.scope_projection_revision,
  'scope_evidence_state', r.scope_evidence_state,
  'presence_state', r.presence_state,
  'presence_evidence_state', r.presence_evidence_state,
  'provider_object_kind', r.provider_object_kind,
  'provider_external_ref', r.provider_external_ref,
  'last_observed_at', r.last_observed_at,
  'last_confirmed_present_at', r.last_confirmed_present_at,
  'created_at', r.created_at,
  'updated_at', r.updated_at
)::text
FROM monitoring.monitoring_resource r
JOIN monitoring.monitoring_source s
  ON s.tenant_id=r.tenant_id
 AND s.monitoring_source_id=r.monitoring_source_id
WHERE r.tenant_id=:'tenant'
  AND r.monitoring_resource_id=:'resource_id';
COMMIT;
""",
            tenant=tenant_id,
            resource_id=monitoring_resource_id,
        )
        if not raw:
            return None
        return self._record(json.loads(raw))


class G3Server(G1.G1Server):
    def __init__(self, server_address, handler, *, fixture_enabled: bool, pg: Pg, fixture_memory: bool):
        super().__init__(server_address, handler, fixture_enabled=fixture_enabled)
        self.g3_resources = FixtureResourceReadPort() if fixture_memory else PgResourceReadPort(pg)


class Handler(G1.Handler):
    server: G3Server

    def _send_private_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "private, no-cache")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(payload)

    @staticmethod
    def _parse_resource_path(path: str):
        parts = path.split("/")
        if (
            len(parts) == 6
            and parts[:4] == ["", "api", "v1", "tenants"]
            and parts[5] == "monitoring-resources"
        ):
            return unquote(parts[4]), None
        if (
            len(parts) == 7
            and parts[:4] == ["", "api", "v1", "tenants"]
            and parts[5] == "monitoring-resources"
        ):
            return unquote(parts[4]), unquote(parts[6])
        return None

    def _bound_authorization(self, session: str) -> BoundResourceAuthorization:
        if not self.server.fixture_enabled or self.server.state.authority_state is None:
            raise AdmissionDenied("G3 runtime adapters are not configured")
        record = resolve_browser_session(
            authority=self.server.state.sessions,
            handle=BrowserSessionHandle(session),
            now=utcnow(),
        )
        state = self.server.state.authority_state
        return BoundResourceAuthorization(
            principal=record.principal,
            authentication_strength=record.authentication_strength,
            principal_authority=G1.FixturePrincipalAuthority(state),
            placement_authority=G1.FixturePlacementAuthority(state),
            authorization_authority=G1.FixtureAuthorizationAuthority(state),
            strength_policy=G1.FixtureStrengthPolicy(),
            final_admission_authority=G1.FixtureFinalAdmissionAuthority(state),
            now=utcnow(),
        )

    def _service(self, session: str) -> ResourceInventory:
        return ResourceInventory(
            repository=self.server.g3_resources,
            authorization=self._bound_authorization(session),
        )

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send_static(FRONTEND / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/g3-app.mjs":
            self._send_static(FRONTEND / "app.mjs", "text/javascript; charset=utf-8")
            return
        if parsed.path == "/__fixture__/g3/login/start":
            if not self.server.fixture_enabled:
                self._send_json(HTTPStatus.NOT_FOUND, {"state": "unavailable"})
                return
            case = parse_qs(parsed.query).get("case", ["success"])[0]
            if case not in {"success", "detail", "revoked", "cross-tenant"}:
                self._send_json(HTTPStatus.BAD_REQUEST, {"state": "unavailable"})
                return
            tenant = "tenant-b" if case == "cross-tenant" else "tenant-a"
            mode = "revoked" if case == "revoked" else "allowed"
            location = "/__fixture__/login/start?target_tenant=" + quote(tenant) + "&scenario=allowed&mode=" + quote(mode)
            self._redirect(location, cookies=[(G3_CASE_COOKIE, case, False, 600, "Strict")])
            return

        route = self._parse_resource_path(parsed.path)
        if route is not None:
            tenant_id, resource_id = route
            session = self._single_cookie(G1.SESSION_COOKIE)
            if session is None:
                self._send_json(HTTPStatus.UNAUTHORIZED, {"state": "unauthenticated"})
                return
            try:
                service = self._service(session)
                if resource_id is None:
                    self._send_private_json(HTTPStatus.OK, service.list_current(tenant_id=tenant_id))
                    return
                detail = service.get_detail(
                    tenant_id=tenant_id,
                    monitoring_resource_id=resource_id,
                )
            except AdmissionDenied:
                self._send_json(HTTPStatus.FORBIDDEN, {"state": "forbidden"})
                return
            except (ValueError, RuntimeError):
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"state": "unavailable"})
                return
            if detail is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"state": "not_found"})
                return
            self._send_json(HTTPStatus.OK, detail)
            return

        super().do_GET()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8446)
    parser.add_argument("--certfile", required=True)
    parser.add_argument("--keyfile", required=True)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--fixture-memory", action="store_true")
    parser.add_argument("--pg-container", default="jlmirror-g3-postgres")
    parser.add_argument("--pg-database", default="jlmirror")
    args = parser.parse_args()

    server = G3Server(
        (args.host, args.port),
        Handler,
        fixture_enabled=args.fixture,
        pg=Pg(container=args.pg_container, database=args.pg_database),
        fixture_memory=args.fixture_memory,
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(args.certfile, args.keyfile)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
