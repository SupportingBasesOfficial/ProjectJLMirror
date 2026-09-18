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
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
APP = Path(__file__).resolve().parent
FRONTEND = APP / "frontend"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(APP))

from current_authorization import BoundMetricsAuthorization
from metrics import (
    HistoryCoverage,
    HistoryRead,
    MetricCurrentRecord,
    MetricDefinitionRecord,
    MetricObservationRecord,
    MetricsView,
)
from jlmirror_authority.model import AdmissionDenied
from jlmirror_authority.session import BrowserSessionHandle, resolve_browser_session


def _load_g3():
    path = ROOT / "apps/g3-resource-inventory/bff_server.py"
    spec = importlib.util.spec_from_file_location("jlmirror_g3_g4_composed_bff", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("canonical G3 BFF cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


G3 = _load_g3()
G1 = G3.G1
G4_CASE_COOKIE = "jlmirror_g4_case"


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


class PgMetricsReadPort:
    def __init__(self, pg: Pg) -> None:
        self.pg = pg

    @staticmethod
    def _definition(value: dict) -> MetricDefinitionRecord:
        expected = {
            "metric_definition_id", "monitoring_resource_id", "monitoring_source_id",
            "source_instance_generation", "generation_state", "name", "value_kind", "unit",
            "scope_state", "scope_projection_revision", "scope_evidence_state", "definition_state",
            "provider_object_kind", "provider_external_ref",
        }
        if set(value) != expected:
            raise RuntimeError("metric definition read shape is invalid")
        return MetricDefinitionRecord(**value)

    @staticmethod
    def _current(value: dict) -> MetricCurrentRecord:
        expected = {
            "metric_definition_id", "monitoring_resource_id", "monitoring_source_id",
            "source_instance_generation", "generation_state", "scope_state",
            "scope_evidence_state", "current_observation_id", "observed_at", "accepted_at",
            "value_kind", "value", "evidence_state", "projection_revision", "last_changed_at",
        }
        if set(value) != expected:
            raise RuntimeError("metric current-state read shape is invalid")
        return MetricCurrentRecord(**value)

    @staticmethod
    def _observation(value: dict) -> MetricObservationRecord:
        expected = {
            "observation_id", "metric_definition_id", "monitoring_resource_id",
            "monitoring_source_id", "source_instance_generation", "observed_at",
            "accepted_at", "value_kind", "value",
        }
        if set(value) != expected:
            raise RuntimeError("metric observation read shape is invalid")
        return MetricObservationRecord(**value)

    def list_definitions(self, *, tenant_id: str, monitoring_resource_id: str):
        raw = self.pg.query(
            """
BEGIN;
SET LOCAL ROLE wave4_runtime;
SET LOCAL jlmirror.tenant_id=:'tenant';
SELECT COALESCE(json_agg(row_to_json(x) ORDER BY x.metric_definition_id),'[]'::json)::text
FROM (
  SELECT
    d.metric_definition_id,
    d.monitoring_resource_id,
    d.monitoring_source_id,
    d.source_instance_generation,
    'active_generation'::text AS generation_state,
    d.name,
    d.value_kind,
    d.unit,
    d.scope_state,
    d.scope_projection_revision,
    d.scope_evidence_state,
    d.definition_state,
    NULL::text AS provider_object_kind,
    NULL::text AS provider_external_ref
  FROM monitoring.metric_definition d
  JOIN monitoring.monitoring_source s
    ON s.tenant_id=d.tenant_id
   AND s.monitoring_source_id=d.monitoring_source_id
  WHERE d.tenant_id=:'tenant'
    AND d.monitoring_resource_id=:'resource_id'
    AND d.source_instance_generation=s.active_source_instance_generation
  ORDER BY d.metric_definition_id
  LIMIT 500
) x;
COMMIT;
""",
            tenant=tenant_id,
            resource_id=monitoring_resource_id,
        )
        values = json.loads(raw or "[]")
        if not isinstance(values, list) or len(values) > 500:
            raise RuntimeError("metric definition list exceeds read bound")
        return tuple(self._definition(value) for value in values)

    def get_definition(self, *, tenant_id: str, metric_definition_id: str):
        raw = self.pg.query(
            """
BEGIN;
SET LOCAL ROLE wave4_runtime;
SET LOCAL jlmirror.tenant_id=:'tenant';
SELECT row_to_json(x)::text
FROM (
  SELECT
    d.metric_definition_id,
    d.monitoring_resource_id,
    d.monitoring_source_id,
    d.source_instance_generation,
    CASE WHEN d.source_instance_generation=s.active_source_instance_generation
         THEN 'active_generation' ELSE 'historical_generation' END AS generation_state,
    d.name,
    d.value_kind,
    d.unit,
    d.scope_state,
    d.scope_projection_revision,
    d.scope_evidence_state,
    d.definition_state,
    b.provider_object_kind,
    b.provider_external_ref
  FROM monitoring.metric_definition d
  JOIN monitoring.monitoring_source s
    ON s.tenant_id=d.tenant_id
   AND s.monitoring_source_id=d.monitoring_source_id
  LEFT JOIN monitoring.metric_definition_provider_binding b
    ON b.tenant_id=d.tenant_id
   AND b.metric_definition_id=d.metric_definition_id
  WHERE d.tenant_id=:'tenant'
    AND d.metric_definition_id=:'metric_id'
) x;
COMMIT;
""",
            tenant=tenant_id,
            metric_id=metric_definition_id,
        )
        return None if not raw else self._definition(json.loads(raw))

    def list_current(self, *, tenant_id: str, monitoring_resource_id: str):
        raw = self.pg.query(
            """
BEGIN;
SET LOCAL ROLE wave4_runtime;
SET LOCAL jlmirror.tenant_id=:'tenant';
SELECT COALESCE(json_agg(row_to_json(x) ORDER BY x.metric_definition_id),'[]'::json)::text
FROM (
  SELECT
    c.metric_definition_id,
    c.monitoring_resource_id,
    c.monitoring_source_id,
    c.source_instance_generation,
    'active_generation'::text AS generation_state,
    d.scope_state,
    d.scope_evidence_state,
    c.current_observation_id,
    c.observed_at,
    c.accepted_at,
    c.value_kind,
    c.canonical_value AS value,
    c.evidence_state,
    c.projection_revision,
    c.last_changed_at
  FROM monitoring.metric_current_state c
  JOIN monitoring.metric_definition d
    ON d.tenant_id=c.tenant_id
   AND d.metric_definition_id=c.metric_definition_id
  JOIN monitoring.monitoring_source s
    ON s.tenant_id=c.tenant_id
   AND s.monitoring_source_id=c.monitoring_source_id
  WHERE c.tenant_id=:'tenant'
    AND c.monitoring_resource_id=:'resource_id'
    AND c.source_instance_generation=s.active_source_instance_generation
  ORDER BY c.metric_definition_id
  LIMIT 500
) x;
COMMIT;
""",
            tenant=tenant_id,
            resource_id=monitoring_resource_id,
        )
        values = json.loads(raw or "[]")
        if not isinstance(values, list) or len(values) > 500:
            raise RuntimeError("metric current-state list exceeds read bound")
        return tuple(self._current(value) for value in values)

    def get_current(self, *, tenant_id: str, metric_definition_id: str):
        raw = self.pg.query(
            """
BEGIN;
SET LOCAL ROLE wave4_runtime;
SET LOCAL jlmirror.tenant_id=:'tenant';
SELECT row_to_json(x)::text
FROM (
  SELECT
    c.metric_definition_id,
    c.monitoring_resource_id,
    c.monitoring_source_id,
    c.source_instance_generation,
    CASE WHEN c.source_instance_generation=s.active_source_instance_generation
         THEN 'active_generation' ELSE 'historical_generation' END AS generation_state,
    d.scope_state,
    d.scope_evidence_state,
    c.current_observation_id,
    c.observed_at,
    c.accepted_at,
    c.value_kind,
    c.canonical_value AS value,
    c.evidence_state,
    c.projection_revision,
    c.last_changed_at
  FROM monitoring.metric_current_state c
  JOIN monitoring.metric_definition d
    ON d.tenant_id=c.tenant_id
   AND d.metric_definition_id=c.metric_definition_id
  JOIN monitoring.monitoring_source s
    ON s.tenant_id=c.tenant_id
   AND s.monitoring_source_id=c.monitoring_source_id
  WHERE c.tenant_id=:'tenant'
    AND c.metric_definition_id=:'metric_id'
) x;
COMMIT;
""",
            tenant=tenant_id,
            metric_id=metric_definition_id,
        )
        return None if not raw else self._current(json.loads(raw))

    def history(
        self,
        *,
        tenant_id: str,
        metric_definition_id: str,
        from_ts: str,
        to_ts: str,
        limit: int,
    ):
        definition = self.get_definition(
            tenant_id=tenant_id,
            metric_definition_id=metric_definition_id,
        )
        if definition is None:
            return None

        raw = self.pg.query(
            """
BEGIN;
SET LOCAL ROLE wave4_runtime;
SET LOCAL jlmirror.tenant_id=:'tenant';
SELECT COALESCE(json_agg(row_to_json(x) ORDER BY x.observed_at,x.observation_id),'[]'::json)::text
FROM (
  SELECT
    o.observation_id,
    o.metric_definition_id,
    o.monitoring_resource_id,
    o.monitoring_source_id,
    o.source_instance_generation,
    o.observed_at,
    o.accepted_at,
    o.value_kind,
    o.canonical_value AS value
  FROM monitoring.metric_observation o
  WHERE o.tenant_id=:'tenant'
    AND o.metric_definition_id=:'metric_id'
    AND o.observed_at >= :'from_ts'::timestamptz
    AND o.observed_at < :'to_ts'::timestamptz
  ORDER BY o.observed_at,o.observation_id
  LIMIT :'limit'::integer
) x;
COMMIT;
""",
            tenant=tenant_id,
            metric_id=metric_definition_id,
            from_ts=from_ts,
            to_ts=to_ts,
            limit=str(limit),
        )
        values = json.loads(raw or "[]")
        observations = tuple(self._observation(value) for value in values)

        coverage_raw = self.pg.query(
            """
BEGIN;
SET LOCAL ROLE wave4_runtime;
SET LOCAL jlmirror.tenant_id=:'tenant';
SELECT COALESCE(json_agg(row_to_json(x)),'[]'::json)::text
FROM (
  SELECT
    coverage_state,
    finalized_through_clock,
    CASE WHEN finalized_through_clock IS NULL THEN NULL
         ELSE to_timestamp(finalized_through_clock) END AS finalized_through_at
  FROM monitoring.metric_history_stream_state
  WHERE tenant_id=:'tenant'
    AND metric_definition_id=:'metric_id'
) x;
COMMIT;
""",
            tenant=tenant_id,
            metric_id=metric_definition_id,
        )
        coverage_rows = json.loads(coverage_raw or "[]")
        if len(coverage_rows) > 1:
            raise RuntimeError("metric history coverage has ambiguous stream authority")

        state = "incomplete"
        covered_through = None
        gap_refs: tuple[str, ...] = ()
        if coverage_rows:
            row = coverage_rows[0]
            coverage_state = row["coverage_state"]
            if coverage_state == "gap":
                state = "gap_detected"
                gap_refs = ("provider-history-gap",)
            elif coverage_state == "reconciliation_required":
                state = "reconciliation_required"
            elif coverage_state == "finalized":
                finalized_through_at = row.get("finalized_through_at")
                if finalized_through_at is not None:
                    covered_through = finalized_through_at
                    finalized = datetime.fromisoformat(
                        finalized_through_at.replace("Z", "+00:00")
                    ).astimezone(timezone.utc)
                    requested_to = datetime.fromisoformat(
                        to_ts.replace("Z", "+00:00")
                    ).astimezone(timezone.utc)
                    state = "complete" if finalized >= requested_to else "incomplete"
            elif coverage_state != "open":
                raise RuntimeError("unknown metric history coverage state")

        return HistoryRead(
            definition=definition,
            coverage=HistoryCoverage(
                state=state,
                covered_through=covered_through,
                gap_refs=gap_refs,
            ),
            observations=observations,
        )


class FixtureMetricsReadPort:
    def __init__(self) -> None:
        self.definition = MetricDefinitionRecord(
            metric_definition_id="metric-cpu",
            monitoring_resource_id="resource-101",
            monitoring_source_id="source-a",
            source_instance_generation="generation-a",
            generation_state="active_generation",
            name="CPU utilization",
            value_kind="number",
            unit="%",
            scope_state="in_scope",
            scope_projection_revision=1,
            scope_evidence_state="current",
            definition_state="active",
            provider_object_kind="zabbix_item",
            provider_external_ref="2001",
        )
        self.current = MetricCurrentRecord(
            metric_definition_id="metric-cpu",
            monitoring_resource_id="resource-101",
            monitoring_source_id="source-a",
            source_instance_generation="generation-a",
            generation_state="active_generation",
            scope_state="in_scope",
            scope_evidence_state="current",
            current_observation_id="obs-2",
            observed_at="2026-09-18T05:10:00Z",
            accepted_at="2026-09-18T05:10:01Z",
            value_kind="number",
            value=42.5,
            evidence_state="current",
            projection_revision=2,
            last_changed_at="2026-09-18T05:10:01Z",
        )
        self.observations = (
            MetricObservationRecord(
                observation_id="obs-1",
                metric_definition_id="metric-cpu",
                monitoring_resource_id="resource-101",
                monitoring_source_id="source-a",
                source_instance_generation="generation-a",
                observed_at="2026-09-18T05:00:00Z",
                accepted_at="2026-09-18T05:00:01Z",
                value_kind="number",
                value=40.0,
            ),
            MetricObservationRecord(
                observation_id="obs-2",
                metric_definition_id="metric-cpu",
                monitoring_resource_id="resource-101",
                monitoring_source_id="source-a",
                source_instance_generation="generation-a",
                observed_at="2026-09-18T05:10:00Z",
                accepted_at="2026-09-18T05:10:01Z",
                value_kind="number",
                value=42.5,
            ),
        )

    def list_definitions(self, *, tenant_id: str, monitoring_resource_id: str):
        return (self.definition,) if tenant_id == "tenant-a" and monitoring_resource_id == "resource-101" else ()

    def get_definition(self, *, tenant_id: str, metric_definition_id: str):
        return self.definition if tenant_id == "tenant-a" and metric_definition_id == "metric-cpu" else None

    def list_current(self, *, tenant_id: str, monitoring_resource_id: str):
        return (self.current,) if tenant_id == "tenant-a" and monitoring_resource_id == "resource-101" else ()

    def get_current(self, *, tenant_id: str, metric_definition_id: str):
        return self.current if tenant_id == "tenant-a" and metric_definition_id == "metric-cpu" else None

    def history(self, *, tenant_id: str, metric_definition_id: str, from_ts: str, to_ts: str, limit: int):
        if tenant_id != "tenant-a" or metric_definition_id != "metric-cpu":
            return None
        return HistoryRead(
            definition=self.definition,
            coverage=HistoryCoverage(
                state="complete",
                covered_through="2026-09-18T05:10:00Z",
                gap_refs=(),
            ),
            observations=self.observations[:limit],
        )


class G4Server(G3.G3Server):
    def __init__(
        self,
        server_address,
        handler,
        *,
        fixture_enabled: bool,
        pg: Pg,
        fixture_memory: bool,
    ):
        super().__init__(
            server_address,
            handler,
            fixture_enabled=fixture_enabled,
            pg=G3.Pg(container=pg.container, database=pg.database),
            fixture_memory=fixture_memory,
        )
        self.g4_metrics = FixtureMetricsReadPort() if fixture_memory else PgMetricsReadPort(pg)


class Handler(G3.Handler):
    server: G4Server

    def _metrics_authorization(self, session: str) -> BoundMetricsAuthorization:
        if not self.server.fixture_enabled or self.server.state.authority_state is None:
            raise AdmissionDenied("G4 runtime adapters are not configured")
        record = resolve_browser_session(
            authority=self.server.state.sessions,
            handle=BrowserSessionHandle(session),
            now=utcnow(),
        )
        state = self.server.state.authority_state
        return BoundMetricsAuthorization(
            principal=record.principal,
            authentication_strength=record.authentication_strength,
            principal_authority=G1.FixturePrincipalAuthority(state),
            placement_authority=G1.FixturePlacementAuthority(state),
            authorization_authority=G1.FixtureAuthorizationAuthority(state),
            strength_policy=G1.FixtureStrengthPolicy(),
            final_admission_authority=G1.FixtureFinalAdmissionAuthority(state),
            now=utcnow(),
        )

    def _metrics_service(self, session: str) -> MetricsView:
        return MetricsView(
            repository=self.server.g4_metrics,
            authorization=self._metrics_authorization(session),
        )

    def _send_private_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "private, no-cache")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(payload)

    def _handle_metrics(self, parsed) -> bool:
        parts = parsed.path.split("/")
        if len(parts) < 6 or parts[:4] != ["", "api", "v1", "tenants"]:
            return False
        tenant_id = unquote(parts[4])
        collection = parts[5]
        item_id = unquote(parts[6]) if len(parts) == 7 else None
        if len(parts) not in {6, 7}:
            return False
        if collection not in {"metric-definitions", "metric-current-states", "metric-observations"}:
            return False

        session = self._single_cookie(G1.SESSION_COOKIE)
        if session is None:
            self._send_json(HTTPStatus.UNAUTHORIZED, {"state": "unauthenticated"})
            return True

        query = parse_qs(parsed.query)
        try:
            service = self._metrics_service(session)
            if collection == "metric-definitions":
                if item_id is not None:
                    value = service.get_definition(tenant_id=tenant_id, metric_definition_id=item_id)
                    if value is None:
                        self._send_json(HTTPStatus.NOT_FOUND, {"state": "not_found"})
                    else:
                        self._send_json(HTTPStatus.OK, value)
                    return True
                resource = query.get("monitoring_resource_id", [None])[0]
                if resource is None:
                    raise ValueError("monitoring_resource_id is required")
                self._send_private_json(
                    HTTPStatus.OK,
                    service.list_definitions(
                        tenant_id=tenant_id,
                        monitoring_resource_id=resource,
                    ),
                )
                return True

            if collection == "metric-current-states":
                if item_id is not None:
                    value = service.get_current(tenant_id=tenant_id, metric_definition_id=item_id)
                    if value is None:
                        self._send_json(HTTPStatus.NOT_FOUND, {"state": "not_found"})
                    else:
                        self._send_json(HTTPStatus.OK, value)
                    return True
                resource = query.get("monitoring_resource_id", [None])[0]
                if resource is None:
                    raise ValueError("monitoring_resource_id is required")
                self._send_json(
                    HTTPStatus.OK,
                    service.list_current(
                        tenant_id=tenant_id,
                        monitoring_resource_id=resource,
                    ),
                )
                return True

            if item_id is not None:
                return False
            metric_id = query.get("metric_definition_id", [None])[0]
            from_ts = query.get("from", [None])[0]
            to_ts = query.get("to", [None])[0]
            if metric_id is None or from_ts is None or to_ts is None:
                raise ValueError("metric_definition_id, from and to are required")
            limit_text = query.get("limit", ["200"])[0]
            try:
                limit = int(limit_text)
            except ValueError as exc:
                raise ValueError("history limit must be an integer") from exc
            value = service.history(
                tenant_id=tenant_id,
                metric_definition_id=metric_id,
                from_ts=from_ts,
                to_ts=to_ts,
                limit=limit,
            )
            if value is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"state": "not_found"})
            else:
                self._send_json(HTTPStatus.OK, value)
            return True
        except AdmissionDenied:
            self._send_json(HTTPStatus.FORBIDDEN, {"state": "forbidden"})
            return True
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"state": "invalid_request"})
            return True
        except RuntimeError:
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"state": "unavailable"})
            return True

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send_static(FRONTEND / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/g4-app.mjs":
            self._send_static(FRONTEND / "app.mjs", "text/javascript; charset=utf-8")
            return
        if parsed.path == "/__fixture__/g4/login/start":
            if not self.server.fixture_enabled:
                self._send_json(HTTPStatus.NOT_FOUND, {"state": "unavailable"})
                return
            case = parse_qs(parsed.query).get("case", ["success"])[0]
            if case not in {"success", "history", "revoked", "cross-tenant"}:
                self._send_json(HTTPStatus.BAD_REQUEST, {"state": "invalid_request"})
                return
            tenant = "tenant-b" if case == "cross-tenant" else "tenant-a"
            mode = "revoked" if case == "revoked" else "allowed"
            location = (
                "/__fixture__/login/start?target_tenant="
                + tenant
                + "&scenario=allowed&mode="
                + mode
            )
            self._redirect(location, cookies=[(G4_CASE_COOKIE, case, False, 600, "Strict")])
            return

        if self._handle_metrics(parsed):
            return
        super().do_GET()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8447)
    parser.add_argument("--certfile", required=True)
    parser.add_argument("--keyfile", required=True)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--fixture-memory", action="store_true")
    parser.add_argument("--pg-container", default="jlmirror-g4-postgres")
    parser.add_argument("--pg-database", default="jlmirror")
    args = parser.parse_args()

    server = G4Server(
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
