from __future__ import annotations

import argparse
from dataclasses import astuple
from datetime import datetime, timezone
from http import HTTPStatus
import importlib.util
import json
from pathlib import Path
import hmac
import ssl
import subprocess
import sys
from threading import Lock, Thread
import time
from urllib.parse import parse_qs, quote, unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
APP = Path(__file__).resolve().parent
FRONTEND = APP / "frontend"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(APP))

from current_authorization import BoundMonitoringAuthorization
from onboarding import MonitoringSourceOnboarding, SourceSnapshot
from jlmirror_authority.model import AdmissionDenied
from jlmirror_authority.session import BrowserSessionHandle, resolve_browser_session
from jlmirror_monitoring import (
    AdmittedProviderEndpoint,
    ConfiguredProviderScope,
    EgressAdmissionError,
    InitialValidationClaim,
    InitialValidationResult,
    InitialValidationWorker,
    OperationalEvidenceState,
    ProviderUnavailableError,
    SyncOperationState,
    ZabbixHostGroup,
    ZabbixProviderConfiguration,
)


def _load_g1():
    path = ROOT / "apps/g1-identity-tenant-shell/bff_server.py"
    spec = importlib.util.spec_from_file_location("jlmirror_g1_composed_bff", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("canonical G1 BFF cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


G1 = _load_g1()


def _load_wave4_fixture():
    path = ROOT / "tests/wave4/test_zabbix_initial_validation_worker.py"
    spec = importlib.util.spec_from_file_location("jlmirror_wave4_accepted_fixture", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("accepted Wave 4 fixture cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


G2_CASE_COOKIE = "jlmirror_g2_case"


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


class FixtureSourcePort:
    def __init__(self, pg: Pg) -> None:
        self.pg = pg

    def create_initial(
        self,
        *,
        plan,
        idempotency_key: str,
        actor_principal_id: str,
        actor_principal_kind: str,
        actor_generation_ref: str,
        authorization_decision_ref: str,
        request_correlation_id: str,
    ) -> SourceSnapshot:
        row = self.pg.query(
            """
SELECT monitoring_source_id || '|' || monitoring_sync_operation_id || '|' || idempotency_state || '|' || replayed
FROM monitoring.create_zabbix_source(
  :'tenant', :'idem', :'fingerprint', :'source_id', :'generation', :'binding_id',
  :'operation_id', :'audit_evidence_id', :'actor_principal_id', :'actor_principal_kind',
  :'actor_generation_ref', :'authorization_decision_ref', :'request_correlation_id',
  :'display_name', :'provider_instance', :'base_url', :'binding_ref', :'scope_json'::jsonb
);
""",
            tenant=plan.source.tenant_id,
            idem=idempotency_key,
            fingerprint=plan.canonical_request_fingerprint,
            source_id=plan.source.monitoring_source_id,
            generation=plan.generation.source_instance_generation,
            binding_id=plan.source.provider_scope_tenant_binding_id,
            operation_id=plan.sync_operation.monitoring_sync_operation_id,
            audit_evidence_id=plan.audit_evidence_id,
            actor_principal_id=actor_principal_id,
            actor_principal_kind=actor_principal_kind,
            actor_generation_ref=actor_generation_ref,
            authorization_decision_ref=authorization_decision_ref,
            request_correlation_id=request_correlation_id,
            display_name=plan.source.display_name,
            provider_instance=plan.generation.provider_instance_ref,
            base_url=plan.generation.provider_configuration.base_url,
            binding_ref=plan.source.credential_binding_ref,
            scope_json=plan.source.configured_provider_scope.canonical_json(),
        )
        source_id, _, _, _ = row.split("|", 3)
        return self.read_source(tenant_id=plan.source.tenant_id, monitoring_source_id=source_id)

    def read_source(self, *, tenant_id: str, monitoring_source_id: str) -> SourceSnapshot:
        row = self.pg.query(
            """
SELECT s.monitoring_source_id || '|' || o.monitoring_sync_operation_id || '|' ||
       s.operational_evidence_state || '|' || o.state
  FROM monitoring.monitoring_source s
  JOIN monitoring.monitoring_sync_operation o
    ON o.tenant_id=s.tenant_id AND o.monitoring_sync_operation_id=s.last_sync_operation_id
 WHERE s.tenant_id=:'tenant' AND s.monitoring_source_id=:'source_id';
""",
            tenant=tenant_id,
            source_id=monitoring_source_id,
        )
        if not row:
            raise LookupError("monitoring source is not visible")
        source_id, operation_id, evidence, operation = row.split("|", 3)
        return SourceSnapshot(
            monitoring_source_id=source_id,
            monitoring_sync_operation_id=operation_id,
            operational_evidence_state=OperationalEvidenceState(evidence),
            sync_operation_state=SyncOperationState(operation),
        )


class FixtureValidationRepository:
    def __init__(self, pg: Pg, tenant_id: str) -> None:
        self.pg = pg
        self.tenant_id = tenant_id

    def claim_initial_validation(self, monitoring_sync_operation_id: str, **claim_context) -> InitialValidationClaim:
        if len(claim_context) != 1:
            raise RuntimeError("initial validation fencing context shape is invalid")
        claim_ref = next(iter(claim_context.values()))
        row = self.pg.query(
            """
SELECT monitoring_source_id || '|' || provider_scope_tenant_binding_id || '|' ||
       source_instance_generation || '|' || configuration_revision || '|' ||
       scope_revision || '|' || provider_instance_ref || '|' || provider_base_url || '|' ||
       credential_binding_ref || '|' || configured_provider_scope::text
  FROM monitoring.claim_zabbix_initial_validation(:'tenant', :'operation_id', :'claim_ref');
""",
            tenant=self.tenant_id,
            operation_id=monitoring_sync_operation_id,
            claim_ref=claim_ref,
        )
        parts = row.split("|", 8)
        if len(parts) != 9:
            raise RuntimeError("initial validation claim shape is invalid")
        return InitialValidationClaim(
            claim_ref,
            self.tenant_id,
            monitoring_sync_operation_id,
            parts[0],
            parts[1],
            parts[2],
            int(parts[3]),
            int(parts[4]),
            parts[5],
            ZabbixProviderConfiguration(parts[6]),
            parts[7],
            ConfiguredProviderScope.from_refs(json.loads(parts[8])["host_group_refs"]),
        )

    def complete_initial_validation(self, claim, result, *, validation_evidence_id: str) -> None:
        claim_ref = astuple(claim)[0]
        observed_generation_ref = astuple(result)[-1]
        self.pg.query(
            """
SELECT monitoring.complete_zabbix_initial_validation(
  :'tenant', :'operation_id', :'claim_ref', :'evidence_id',
  :'binding_id', :'provider_instance', :'evidence_state', :'operation_state',
  NULLIF(:'failure_class',''), :'visible'::jsonb, :'missing'::jsonb,
  NULLIF(:'decision_ref',''), NULLIF(:'observed_generation_ref','')
);
""",
            tenant=claim.tenant_id,
            operation_id=claim.monitoring_sync_operation_id,
            claim_ref=claim_ref,
            evidence_id=validation_evidence_id,
            binding_id=claim.provider_scope_tenant_binding_id,
            provider_instance=claim.provider_instance_ref,
            evidence_state=result.operational_evidence_state.value,
            operation_state=result.operation_state.value,
            failure_class="" if result.failure_class is None else result.failure_class.value,
            visible=json.dumps(list(result.visible_host_group_refs)),
            missing=json.dumps(list(result.missing_host_group_refs)),
            decision_ref=result.egress_decision_ref or "",
            observed_generation_ref=observed_generation_ref or "",
        )


class FixtureOutboundAdmission:
    def admit_zabbix_api(self, provider_configuration: ZabbixProviderConfiguration) -> AdmittedProviderEndpoint:
        if "egress-denied.example.test" in provider_configuration.base_url:
            raise EgressAdmissionError("fixture outbound admission denied")
        return AdmittedProviderEndpoint(
            api_url=provider_configuration.base_url.rstrip("/") + "/api_jsonrpc.php",
            egress_decision_ref="fixture-egress-decision",
        )


class FixtureHostGroupReader:
    def hostgroup_get(self, endpoint, access_context, host_group_refs):
        del endpoint, access_context
        return tuple(ZabbixHostGroup(groupid=ref) for ref in host_group_refs if ref != "group-missing")


class ProviderBinding:
    def current_instance_ref(self, *, tenant_id: str, provider_profile: str) -> str:
        if tenant_id != "tenant-a" or provider_profile != "zabbix":
            raise AdmissionDenied("current provider binding is unavailable")
        return "provider-instance:tenant-current"


class Dispatcher:
    def __init__(self, pg: Pg) -> None:
        self.pg = pg
        self._lock = Lock()
        self._started: set[tuple[str, str]] = set()

    def make_ready(self, *, tenant_id: str, monitoring_sync_operation_id: str) -> None:
        key = (tenant_id, monitoring_sync_operation_id)
        with self._lock:
            if key in self._started:
                return
            self._started.add(key)

        def run() -> None:
            time.sleep(0.05)
            accepted_fixture = _load_wave4_fixture()
            worker = InitialValidationWorker(
                repository=FixtureValidationRepository(self.pg, tenant_id),
                **{
                    "credential_resolver": getattr(accepted_fixture, "CredentialResolver")(),
                    "outbound_admission": FixtureOutboundAdmission(),
                    "host_group_reader": FixtureHostGroupReader(),
                },
            )
            try:
                worker.run(monitoring_sync_operation_id)
            except Exception:
                return

        Thread(target=run, daemon=True).start()


class G2Server(G1.G1Server):
    def __init__(self, server_address, handler, *, fixture_enabled: bool, pg: Pg):
        super().__init__(server_address, handler, fixture_enabled=fixture_enabled)
        self.g2_source = FixtureSourcePort(pg)
        self.g2_dispatcher = Dispatcher(pg)


class Handler(G1.Handler):
    server: G2Server

    def _view_json(self, view) -> dict:
        return {
            "monitoring_source_id": view.monitoring_source_id,
            "monitoring_sync_operation_id": view.monitoring_sync_operation_id,
            "state": view.state,
            "provider_connection_confirmed": view.provider_connection_confirmed,
            "can_recheck": view.can_recheck,
        }

    def _bound_authorization(self, session: str) -> BoundMonitoringAuthorization:
        if not self.server.fixture_enabled or self.server.state.authority_state is None:
            raise AdmissionDenied("G2 runtime adapters are not configured")
        record = resolve_browser_session(
            authority=self.server.state.sessions,
            handle=BrowserSessionHandle(session),
            now=utcnow(),
        )
        state = self.server.state.authority_state
        return BoundMonitoringAuthorization(
            principal=record.principal,
            authentication_strength=record.authentication_strength,
            principal_authority=G1.FixturePrincipalAuthority(state),
            placement_authority=G1.FixturePlacementAuthority(state),
            authorization_authority=G1.FixtureAuthorizationAuthority(state),
            strength_policy=G1.FixtureStrengthPolicy(),
            final_admission_authority=G1.FixtureFinalAdmissionAuthority(state),
            now=utcnow(),
        )

    def _csrf_session(self) -> str:
        origins = self.headers.get_all("Origin", [])
        headers = self.headers.get_all("X-JLMirror-CSRF", [])
        session = self._single_cookie(G1.SESSION_COOKIE)
        csrf_cookie = self._single_cookie(G1.CSRF_COOKIE)
        if origins != [self._origin()] or len(headers) != 1 or session is None or csrf_cookie is None:
            raise AdmissionDenied("state-changing G2 request lacks current CSRF evidence")
        handle = BrowserSessionHandle(session)
        with self.server.state.lock:
            lineage = self.server.state.lineage_by_session_digest.get(handle.digest)
        if lineage is None:
            raise AdmissionDenied("browser session lineage is unavailable")
        if not self.server.state.csrf.validate(
            **{"token": headers[0], "session_lineage_id": lineage}
        ):
            raise AdmissionDenied("CSRF binding is not current")
        if not hmac.compare_digest(headers[0], csrf_cookie):
            raise AdmissionDenied("CSRF cookie/header mismatch")
        return session

    def _service(self, session: str):
        authorization = self._bound_authorization(session)
        return (
            MonitoringSourceOnboarding(
                authorization=authorization,
                provider_binding=ProviderBinding(),
                source_port=self.server.g2_source,
                validation_responsibility=self.server.g2_dispatcher,
            ),
            authorization.actor_ref,
        )

    @staticmethod
    def _parse_source_path(path: str):
        parts = path.split("/")
        if len(parts) == 6 and parts[:4] == ["", "bff", "v1", "tenants"] and parts[5] == "monitoring-sources":
            return unquote(parts[4]), None
        if (
            len(parts) == 8
            and parts[:4] == ["", "bff", "v1", "tenants"]
            and parts[5] == "monitoring-sources"
            and parts[7] == "status"
        ):
            return unquote(parts[4]), unquote(parts[6])
        return None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send_static(FRONTEND / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/g2-app.mjs":
            self._send_static(FRONTEND / "app.mjs", "text/javascript; charset=utf-8")
            return
        if parsed.path == "/__fixture__/g2/login/start":
            if not self.server.fixture_enabled:
                self._send_json(HTTPStatus.NOT_FOUND, {"state": "unavailable"})
                return
            case = parse_qs(parsed.query).get("case", ["success"])[0]
            if case not in {"success", "missing", "revoked", "cross-tenant"}:
                self._send_json(HTTPStatus.BAD_REQUEST, {"state": "unavailable"})
                return
            tenant = "tenant-b" if case == "cross-tenant" else "tenant-a"
            mode = "revoked" if case == "revoked" else "allowed"
            location = "/__fixture__/login/start?target_tenant=" + quote(tenant) + "&scenario=allowed&mode=" + quote(mode)
            self._redirect(location, cookies=[(G2_CASE_COOKIE, case, False, 600, "Strict")])
            return

        route = self._parse_source_path(parsed.path)
        if route is not None and route[1] is not None:
            tenant_id, source_id = route
            session = self._single_cookie(G1.SESSION_COOKIE)
            if session is None:
                self._send_json(HTTPStatus.UNAUTHORIZED, {"state": "unauthenticated"})
                return
            try:
                service, actor = self._service(session)
                view = service.read(actor_ref=actor, tenant_id=tenant_id, monitoring_source_id=source_id)
            except AdmissionDenied:
                self._send_json(HTTPStatus.FORBIDDEN, {"state": "forbidden"})
                return
            except LookupError:
                self._send_json(HTTPStatus.NOT_FOUND, {"state": "unavailable"})
                return
            self._send_json(HTTPStatus.OK, self._view_json(view))
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        route = self._parse_source_path(parsed.path)
        if route is not None and route[1] is None:
            tenant_id, _ = route
            try:
                session = self._csrf_session()
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 16384:
                    raise ValueError("request body size is invalid")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("request body must be an object")
                service, actor = self._service(session)
                view = service.create(
                    actor_ref=actor,
                    tenant_id=tenant_id,
                    idempotency_key=self.headers.get("Idempotency-Key"),
                    payload=payload,
                )
            except AdmissionDenied:
                self._send_json(HTTPStatus.FORBIDDEN, {"state": "forbidden"})
                return
            except (ValueError, json.JSONDecodeError):
                self._send_json(HTTPStatus.BAD_REQUEST, {"state": "unavailable"})
                return
            except RuntimeError as exc:
                if "idempotency.key_reused" in str(exc):
                    self._send_json(HTTPStatus.CONFLICT, {"state": "reconciliation_required"})
                else:
                    self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"state": "unavailable"})
                return
            self._send_json(HTTPStatus.CREATED, self._view_json(view))
            return
        super().do_POST()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8445)
    parser.add_argument("--certfile", required=True)
    parser.add_argument("--keyfile", required=True)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--pg-container", default="jlmirror-g2-postgres")
    parser.add_argument("--pg-database", default="jlmirror")
    args = parser.parse_args()

    server = G2Server(
        (args.host, args.port),
        Handler,
        fixture_enabled=args.fixture,
        pg=Pg(container=args.pg_container, database=args.pg_database),
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(args.certfile, args.keyfile)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
