from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http import HTTPStatus
import importlib.util
import json
from pathlib import Path
import ssl
import sys
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
APP = Path(__file__).resolve().parent
FRONTEND = APP / "frontend"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(APP))

from current_authorization import BoundProblemHealthAuthorization
from problem_health import HealthRecord, ProblemHealthView, ProblemRecord
from jlmirror_authority.model import AdmissionDenied
from jlmirror_authority.session import BrowserSessionHandle, resolve_browser_session


def _load_g4():
    path = ROOT / "apps/g4-metrics/bff_server.py"
    g4_app = str(path.parent)
    spec = importlib.util.spec_from_file_location("jlmirror_g4_g5_composed_bff", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("canonical G4 BFF cannot be loaded")

    saved_modules = {
        name: sys.modules.get(name)
        for name in ("current_authorization", "metrics")
    }
    previous_path = list(sys.path)
    try:
        sys.path.insert(0, g4_app)
        for name in saved_modules:
            sys.modules.pop(name, None)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = previous_path
        for name, value in saved_modules.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


G4 = _load_g4()
G1 = G4.G1
G5_CASE_COOKIE = "jlmirror_g5_case"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PgProblemHealthReadPort:
    def __init__(self, pg) -> None:
        self.pg = pg

    @staticmethod
    def _problem(value: dict) -> ProblemRecord:
        expected = {
            "problem_id", "monitoring_source_id", "source_instance_generation",
            "generation_state", "monitoring_resource_id", "summary", "problem_state",
            "severity_class", "opened_at", "resolved_at", "last_confirmed_at",
            "evidence_state", "provider_object_kind", "provider_external_ref",
        }
        if set(value) != expected:
            raise RuntimeError("problem read shape is invalid")
        return ProblemRecord(**value)

    @staticmethod
    def _health(value: dict) -> HealthRecord:
        expected = {
            "monitoring_resource_id", "monitoring_source_id", "source_instance_generation",
            "generation_state", "scope_state", "scope_evidence_state", "presence_state",
            "presence_evidence_state", "health_class", "evidence_state",
            "projection_revision", "last_changed_at", "last_evidence_at", "reason_refs",
        }
        if set(value) != expected:
            raise RuntimeError("health read shape is invalid")
        refs = value["reason_refs"]
        if not isinstance(refs, list):
            raise RuntimeError("health reason refs shape is invalid")
        return HealthRecord(**{**value, "reason_refs": tuple(refs)})

    def list_problems(
        self,
        *,
        tenant_id: str,
        monitoring_source_id: str | None,
        monitoring_resource_id: str | None,
        generation_state: str,
        problem_state: str | None,
        severity_class: str | None,
        cursor: str | None,
        limit: int,
    ):
        raw = self.pg.query(
            """
BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL ROLE wave4_runtime;
SET LOCAL jlmirror.tenant_id=:'tenant';
WITH eligible AS (
  SELECT
    p.problem_id,
    p.monitoring_source_id,
    p.source_instance_generation,
    CASE WHEN p.source_instance_generation=s.active_source_instance_generation
         THEN 'active_generation' ELSE 'historical_generation' END AS generation_state,
    p.monitoring_resource_id,
    p.summary,
    p.problem_state,
    p.severity_class,
    p.opened_at,
    p.resolved_at,
    p.last_confirmed_at,
    p.evidence_state,
    NULL::text AS provider_object_kind,
    NULL::text AS provider_external_ref
  FROM monitoring.monitoring_problem p
  JOIN monitoring.monitoring_source s
    ON s.tenant_id=p.tenant_id
   AND s.monitoring_source_id=p.monitoring_source_id
  WHERE p.tenant_id=:'tenant'
    AND (:'source_id'='' OR p.monitoring_source_id=:'source_id')
    AND (:'resource_id'='' OR p.monitoring_resource_id=:'resource_id')
    AND (
      (:'generation_state'='active_generation'
       AND p.source_instance_generation=s.active_source_instance_generation)
      OR
      (:'generation_state'='historical_generation'
       AND p.source_instance_generation<>s.active_source_instance_generation)
    )
    AND (:'problem_state'='' OR p.problem_state=:'problem_state')
    AND (:'severity_class'='' OR p.severity_class=:'severity_class')
),
anchor_row AS (
  SELECT opened_at,problem_id
  FROM eligible
  WHERE problem_id=:'cursor'
),
anchor AS (
  SELECT (:'cursor'='' OR EXISTS (SELECT 1 FROM anchor_row)) AS valid
),
page AS (
  SELECT e.*
  FROM eligible e CROSS JOIN anchor a
  WHERE a.valid
    AND (
      :'cursor'=''
      OR e.opened_at < (SELECT opened_at FROM anchor_row)
      OR (
        e.opened_at = (SELECT opened_at FROM anchor_row)
        AND e.problem_id > :'cursor'
      )
    )
  ORDER BY e.opened_at DESC,e.problem_id ASC
  LIMIT :'fetch_limit'::integer
)
SELECT json_build_object(
  'cursor_valid',(SELECT valid FROM anchor),
  'items',COALESCE((SELECT json_agg(row_to_json(page) ORDER BY opened_at DESC,problem_id ASC) FROM page),'[]'::json)
)::text;
COMMIT;
""",
            tenant=tenant_id,
            source_id=monitoring_source_id or "",
            resource_id=monitoring_resource_id or "",
            generation_state=generation_state,
            problem_state=problem_state or "",
            severity_class=severity_class or "",
            cursor=cursor or "",
            fetch_limit=str(limit + 1),
        )
        payload = json.loads(raw or "{}")
        if set(payload) != {"cursor_valid", "items"} or not isinstance(payload["items"], list):
            raise RuntimeError("problem page shape is invalid")
        if not payload["cursor_valid"]:
            raise ValueError("cursor_invalid")
        values = payload["items"]
        if len(values) > limit + 1:
            raise RuntimeError("problem page exceeds read bound")
        has_more = len(values) > limit
        rows = tuple(self._problem(value) for value in values[:limit])
        next_cursor = rows[-1].problem_id if has_more and rows else None
        return rows, next_cursor

    def get_problem(self, *, tenant_id: str, problem_id: str):
        raw = self.pg.query(
            """
BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL ROLE wave4_runtime;
SET LOCAL jlmirror.tenant_id=:'tenant';
SELECT row_to_json(x)::text
FROM (
  SELECT
    p.problem_id,
    p.monitoring_source_id,
    p.source_instance_generation,
    CASE WHEN p.source_instance_generation=s.active_source_instance_generation
         THEN 'active_generation' ELSE 'historical_generation' END AS generation_state,
    p.monitoring_resource_id,
    p.summary,
    p.problem_state,
    p.severity_class,
    p.opened_at,
    p.resolved_at,
    p.last_confirmed_at,
    p.evidence_state,
    'zabbix_event'::text AS provider_object_kind,
    b.provider_external_ref
  FROM monitoring.monitoring_problem p
  JOIN monitoring.monitoring_source s
    ON s.tenant_id=p.tenant_id
   AND s.monitoring_source_id=p.monitoring_source_id
  LEFT JOIN monitoring.monitoring_problem_provider_binding b
    ON b.tenant_id=p.tenant_id
   AND b.problem_id=p.problem_id
  WHERE p.tenant_id=:'tenant'
    AND p.problem_id=:'problem_id'
) x;
COMMIT;
""",
            tenant=tenant_id,
            problem_id=problem_id,
        )
        return None if not raw else self._problem(json.loads(raw))

    def list_health(
        self,
        *,
        tenant_id: str,
        monitoring_source_id: str | None,
        generation_state: str,
        health_class: str | None,
        evidence_state: str | None,
        scope_state: str | None,
        cursor: str | None,
        limit: int,
    ):
        raw = self.pg.query(
            """
BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL ROLE wave4_runtime;
SET LOCAL jlmirror.tenant_id=:'tenant';
WITH raw AS (
  SELECT
    h.monitoring_resource_id,
    h.monitoring_source_id,
    h.source_instance_generation,
    CASE WHEN h.source_instance_generation=s.active_source_instance_generation
         THEN 'active_generation' ELSE 'historical_generation' END AS generation_state,
    r.scope_state,
    r.scope_evidence_state,
    r.presence_state,
    r.presence_evidence_state,
    h.health_class,
    CASE
      WHEN h.source_instance_generation<>s.active_source_instance_generation
           AND h.evidence_state='current'
        THEN 'stale'
      WHEN (
        r.scope_state<>'in_scope'
        OR r.scope_evidence_state<>'current'
        OR r.presence_state<>'present'
        OR r.presence_evidence_state<>'current'
      ) AND h.evidence_state='current'
        THEN 'reconciliation_required'
      ELSE h.evidence_state
    END AS evidence_state,
    h.projection_revision,
    h.last_changed_at,
    h.last_evidence_at,
    h.reason_refs
  FROM monitoring.health_projection h
  JOIN monitoring.monitoring_source s
    ON s.tenant_id=h.tenant_id
   AND s.monitoring_source_id=h.monitoring_source_id
  JOIN monitoring.monitoring_resource r
    ON r.tenant_id=h.tenant_id
   AND r.monitoring_resource_id=h.monitoring_resource_id
  WHERE h.tenant_id=:'tenant'
),
eligible AS (
  SELECT *
  FROM raw
  WHERE (:'source_id'='' OR monitoring_source_id=:'source_id')
    AND generation_state=:'generation_state'
    AND (:'health_class'='' OR health_class=:'health_class')
    AND (:'evidence_state'='' OR evidence_state=:'evidence_state')
    AND (:'scope_state'='' OR scope_state=:'scope_state')
),
anchor AS (
  SELECT (:'cursor'='' OR EXISTS (
    SELECT 1 FROM eligible WHERE monitoring_resource_id=:'cursor'
  )) AS valid
),
page AS (
  SELECT e.*
  FROM eligible e CROSS JOIN anchor a
  WHERE a.valid
    AND (:'cursor'='' OR e.monitoring_resource_id > :'cursor')
  ORDER BY e.monitoring_resource_id ASC
  LIMIT :'fetch_limit'::integer
)
SELECT json_build_object(
  'cursor_valid',(SELECT valid FROM anchor),
  'items',COALESCE((SELECT json_agg(row_to_json(page) ORDER BY monitoring_resource_id ASC) FROM page),'[]'::json)
)::text;
COMMIT;
""",
            tenant=tenant_id,
            source_id=monitoring_source_id or "",
            generation_state=generation_state,
            health_class=health_class or "",
            evidence_state=evidence_state or "",
            scope_state=scope_state or "",
            cursor=cursor or "",
            fetch_limit=str(limit + 1),
        )
        payload = json.loads(raw or "{}")
        if set(payload) != {"cursor_valid", "items"} or not isinstance(payload["items"], list):
            raise RuntimeError("health page shape is invalid")
        if not payload["cursor_valid"]:
            raise ValueError("cursor_invalid")
        values = payload["items"]
        if len(values) > limit + 1:
            raise RuntimeError("health page exceeds read bound")
        has_more = len(values) > limit
        rows = tuple(self._health(value) for value in values[:limit])
        next_cursor = rows[-1].monitoring_resource_id if has_more and rows else None
        return rows, next_cursor

    def get_health(self, *, tenant_id: str, monitoring_resource_id: str):
        raw = self.pg.query(
            """
BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL ROLE wave4_runtime;
SET LOCAL jlmirror.tenant_id=:'tenant';
SELECT COALESCE(json_agg(row_to_json(x)),'[]'::json)::text
FROM (
  SELECT
    h.monitoring_resource_id,
    h.monitoring_source_id,
    h.source_instance_generation,
    CASE WHEN h.source_instance_generation=s.active_source_instance_generation
         THEN 'active_generation' ELSE 'historical_generation' END AS generation_state,
    r.scope_state,
    r.scope_evidence_state,
    r.presence_state,
    r.presence_evidence_state,
    h.health_class,
    h.evidence_state,
    h.projection_revision,
    h.last_changed_at,
    h.last_evidence_at,
    h.reason_refs
  FROM monitoring.health_projection h
  JOIN monitoring.monitoring_source s
    ON s.tenant_id=h.tenant_id
   AND s.monitoring_source_id=h.monitoring_source_id
  JOIN monitoring.monitoring_resource r
    ON r.tenant_id=h.tenant_id
   AND r.monitoring_resource_id=h.monitoring_resource_id
  WHERE h.tenant_id=:'tenant'
    AND h.monitoring_resource_id=:'resource_id'
) x;
COMMIT;
""",
            tenant=tenant_id,
            resource_id=monitoring_resource_id,
        )
        values = json.loads(raw or "[]")
        if not isinstance(values, list) or len(values) > 1:
            raise RuntimeError("health detail has ambiguous generation authority")
        return None if not values else self._health(values[0])


class FixtureProblemHealthReadPort:
    def __init__(self) -> None:
        self.active = ProblemRecord(
            problem_id="problem-1",
            monitoring_source_id="source-a",
            source_instance_generation="generation-a",
            generation_state="active_generation",
            monitoring_resource_id="resource-101",
            summary="CPU threshold exceeded",
            problem_state="active",
            severity_class="warning",
            opened_at="2026-09-18T05:00:00Z",
            resolved_at=None,
            last_confirmed_at="2026-09-18T05:10:00Z",
            evidence_state="current",
            provider_object_kind="zabbix_event",
            provider_external_ref="9001",
        )
        self.resolved = ProblemRecord(
            problem_id="problem-2",
            monitoring_source_id="source-a",
            source_instance_generation="generation-a",
            generation_state="active_generation",
            monitoring_resource_id="resource-101",
            summary="Memory pressure",
            problem_state="resolved",
            severity_class="degraded",
            opened_at="2026-09-18T04:00:00Z",
            resolved_at="2026-09-18T04:30:00Z",
            last_confirmed_at="2026-09-18T04:30:00Z",
            evidence_state="current",
        )
        self.health = HealthRecord(
            monitoring_resource_id="resource-101",
            monitoring_source_id="source-a",
            source_instance_generation="generation-a",
            generation_state="active_generation",
            scope_state="in_scope",
            scope_evidence_state="current",
            presence_state="present",
            presence_evidence_state="current",
            health_class="degraded",
            evidence_state="current",
            projection_revision=3,
            last_changed_at="2026-09-18T05:00:01Z",
            last_evidence_at="2026-09-18T05:10:01Z",
            reason_refs=("problem-1",),
        )

    def list_problems(
        self,
        *,
        tenant_id: str,
        monitoring_source_id: str | None,
        monitoring_resource_id: str | None,
        generation_state: str,
        problem_state: str | None,
        severity_class: str | None,
        cursor: str | None,
        limit: int,
    ):
        if tenant_id != "tenant-a":
            if cursor is not None:
                raise ValueError("cursor_invalid")
            return (), None
        rows = [self.active, self.resolved]
        rows = [r for r in rows if generation_state == r.generation_state]
        if monitoring_source_id is not None:
            rows = [r for r in rows if r.monitoring_source_id == monitoring_source_id]
        if monitoring_resource_id is not None:
            rows = [r for r in rows if r.monitoring_resource_id == monitoring_resource_id]
        if problem_state is not None:
            rows = [r for r in rows if r.problem_state == problem_state]
        if severity_class is not None:
            rows = [r for r in rows if r.severity_class == severity_class]
        rows.sort(key=lambda r: r.problem_id)
        rows.sort(key=lambda r: r.opened_at, reverse=True)
        if cursor is not None:
            indexes = [i for i,r in enumerate(rows) if r.problem_id == cursor]
            if len(indexes) != 1:
                raise ValueError("cursor_invalid")
            rows = rows[indexes[0]+1:]
        page = rows[:limit+1]
        has_more = len(page) > limit
        page = page[:limit]
        return tuple(page), page[-1].problem_id if has_more and page else None

    def get_problem(self, *, tenant_id: str, problem_id: str):
        if tenant_id != "tenant-a":
            return None
        return next((r for r in (self.active,self.resolved) if r.problem_id == problem_id), None)

    def list_health(
        self,
        *,
        tenant_id: str,
        monitoring_source_id: str | None,
        generation_state: str,
        health_class: str | None,
        evidence_state: str | None,
        scope_state: str | None,
        cursor: str | None,
        limit: int,
    ):
        if tenant_id != "tenant-a":
            if cursor is not None:
                raise ValueError("cursor_invalid")
            return (), None
        rows = [self.health] if generation_state == self.health.generation_state else []
        if monitoring_source_id is not None:
            rows = [r for r in rows if r.monitoring_source_id == monitoring_source_id]
        if health_class is not None:
            rows = [r for r in rows if r.health_class == health_class]
        if evidence_state is not None:
            rows = [r for r in rows if r.evidence_state == evidence_state]
        if scope_state is not None:
            rows = [r for r in rows if r.scope_state == scope_state]
        if cursor is not None:
            if not rows or rows[0].monitoring_resource_id != cursor:
                raise ValueError("cursor_invalid")
            rows = []
        return tuple(rows[:limit]), None

    def get_health(self, *, tenant_id: str, monitoring_resource_id: str):
        if tenant_id == "tenant-a" and monitoring_resource_id == "resource-101":
            return self.health
        return None


class G5Server(G4.G4Server):
    def __init__(self, server_address, handler, *, fixture_enabled: bool, pg, fixture_memory: bool):
        super().__init__(
            server_address,
            handler,
            fixture_enabled=fixture_enabled,
            pg=pg,
            fixture_memory=fixture_memory,
        )
        self.g5_problem_health = (
            FixtureProblemHealthReadPort()
            if fixture_memory
            else PgProblemHealthReadPort(pg)
        )


class Handler(G4.Handler):
    server: G5Server

    def _problem_health_authorization(self, session: str) -> BoundProblemHealthAuthorization:
        if not self.server.fixture_enabled or self.server.state.authority_state is None:
            raise AdmissionDenied("G5 runtime adapters are not configured")
        record = resolve_browser_session(
            authority=self.server.state.sessions,
            handle=BrowserSessionHandle(session),
            now=utcnow(),
        )
        state = self.server.state.authority_state
        return BoundProblemHealthAuthorization(
            principal=record.principal,
            authentication_strength=record.authentication_strength,
            principal_authority=G1.FixturePrincipalAuthority(state),
            placement_authority=G1.FixturePlacementAuthority(state),
            authorization_authority=G1.FixtureAuthorizationAuthority(state),
            strength_policy=G1.FixtureStrengthPolicy(),
            final_admission_authority=G1.FixtureFinalAdmissionAuthority(state),
            now=utcnow(),
        )

    def _problem_health_service(self, session: str) -> ProblemHealthView:
        return ProblemHealthView(
            repository=self.server.g5_problem_health,
            authorization=self._problem_health_authorization(session),
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

    @staticmethod
    def _limit(query) -> int:
        try:
            return int(query.get("limit", ["200"])[0])
        except ValueError as exc:
            raise ValueError("limit must be an integer") from exc

    def _handle_g5(self, parsed) -> bool:
        parts = parsed.path.split("/")
        if len(parts) < 6 or parts[:4] != ["", "api", "v1", "tenants"]:
            return False
        tenant_id = unquote(parts[4])
        collection = parts[5]
        item_id = unquote(parts[6]) if len(parts) == 7 else None
        if len(parts) not in {6,7} or collection not in {"problems","health-projections"}:
            return False

        session = self._single_cookie(G1.SESSION_COOKIE)
        if session is None:
            self._send_json(HTTPStatus.UNAUTHORIZED, {"state":"unauthenticated"})
            return True

        query = parse_qs(parsed.query)
        try:
            service = self._problem_health_service(session)
            if collection == "problems":
                if item_id is not None:
                    value = service.get_problem(tenant_id=tenant_id,problem_id=item_id)
                    if value is None:
                        self._send_json(HTTPStatus.NOT_FOUND,{"state":"not_found"})
                    else:
                        self._send_json(HTTPStatus.OK,value)
                    return True
                self._send_json(
                    HTTPStatus.OK,
                    service.list_problems(
                        tenant_id=tenant_id,
                        monitoring_source_id=query.get("monitoring_source_id",[None])[0],
                        monitoring_resource_id=query.get("monitoring_resource_id",[None])[0],
                        generation_state=query.get("generation_state",["active_generation"])[0],
                        problem_state=query.get("problem_state",[None])[0],
                        severity_class=query.get("severity_class",[None])[0],
                        cursor=query.get("cursor",[None])[0],
                        limit=self._limit(query),
                    ),
                )
                return True

            if item_id is not None:
                value = service.get_health(
                    tenant_id=tenant_id,
                    monitoring_resource_id=item_id,
                )
                if value is None:
                    self._send_json(HTTPStatus.NOT_FOUND,{"state":"not_found"})
                else:
                    self._send_private_json(HTTPStatus.OK,value)
                return True

            self._send_private_json(
                HTTPStatus.OK,
                service.list_health(
                    tenant_id=tenant_id,
                    monitoring_source_id=query.get("monitoring_source_id",[None])[0],
                    generation_state=query.get("generation_state",["active_generation"])[0],
                    health_class=query.get("health_class",[None])[0],
                    evidence_state=query.get("evidence_state",[None])[0],
                    scope_state=query.get("scope_state",[None])[0],
                    cursor=query.get("cursor",[None])[0],
                    limit=self._limit(query),
                ),
            )
            return True
        except AdmissionDenied:
            self._send_json(HTTPStatus.FORBIDDEN,{"state":"forbidden"})
            return True
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST,{"state":"invalid_request"})
            return True
        except RuntimeError:
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE,{"state":"unavailable"})
            return True

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/","/index.html"}:
            self._send_static(FRONTEND/"index.html","text/html; charset=utf-8")
            return
        if parsed.path == "/g5-app.mjs":
            self._send_static(FRONTEND/"app.mjs","text/javascript; charset=utf-8")
            return
        if parsed.path == "/__fixture__/g5/login/start":
            if not self.server.fixture_enabled:
                self._send_json(HTTPStatus.NOT_FOUND,{"state":"unavailable"})
                return
            case = parse_qs(parsed.query).get("case",["active"])[0]
            if case not in {"active","resolved","health","revoked","cross-tenant"}:
                self._send_json(HTTPStatus.BAD_REQUEST,{"state":"invalid_request"})
                return
            tenant = "tenant-b" if case == "cross-tenant" else "tenant-a"
            mode = "revoked" if case == "revoked" else "allowed"
            location = (
                "/__fixture__/login/start?target_tenant="
                + tenant
                + "&scenario=allowed&mode="
                + mode
            )
            self._redirect(location,cookies=[(G5_CASE_COOKIE,case,False,600,"Strict")])
            return

        if self._handle_g5(parsed):
            return
        super().do_GET()


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8448)
    parser.add_argument("--certfile",required=True)
    parser.add_argument("--keyfile",required=True)
    parser.add_argument("--fixture",action="store_true")
    parser.add_argument("--fixture-memory",action="store_true")
    parser.add_argument("--pg-container",default="jlmirror-g5-postgres")
    parser.add_argument("--pg-database",default="jlmirror")
    args=parser.parse_args()

    pg=G4.Pg(container=args.pg_container,database=args.pg_database)
    server=G5Server(
        (args.host,args.port),
        Handler,
        fixture_enabled=args.fixture,
        pg=pg,
        fixture_memory=args.fixture_memory,
    )
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(args.certfile,args.keyfile)
    server.socket=context.wrap_socket(server.socket,server_side=True)
    server.serve_forever()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
