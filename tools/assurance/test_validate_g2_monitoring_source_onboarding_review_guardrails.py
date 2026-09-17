#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import shutil
import tempfile
from pathlib import Path

import validate_g2_monitoring_source_onboarding_authorization as authorization
import validate_g2_monitoring_source_onboarding_implementation_scope as scope
import validate_g2_monitoring_source_onboarding_scope_readiness as readiness

REPO = "SupportingBasesOfficial/ProjectJLMirror"
SERVER = "https://github.com"
BASE = "a" * 40
HEAD = "b" * 40
RUN_ID = 424242


def _policy() -> dict:
    value = authorization.load_manifest()["implementation_path_policy"]
    scope.configured_policy(value)
    return value


def falsify_g2_semantic_scope_guard() -> None:
    policy = _policy()
    rejected = (
        ("apps/g2-monitoring-source-onboarding/source.ts", "class ResourceInventory {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const metricCurrentState = true"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class SourceCutover {}"),
        ("tests/g2/parallel_store.py", "class Metric: pass"),
        ("implementation/g2-monitoring-source-onboarding/parallel.sql", "CREATE TABLE monitoring.metric_current_state (id uuid)"),
        ("tools/g2/run-onboarding", "class Health: pass"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const Мetric = true"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class ResourceІnventory {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class SourceСutover {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", r"const \u006detric = true;"),
        ("apps/g2-monitoring-source-onboarding/source.ts", r"class \u0052esourceInventory {}"),
        ("apps/g2-monitoring-source-onboarding/dashboard.vue", "<script>class ResourceІnventory {}</script>"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class Metrics {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class Problems {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class ResourceInventories {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", r"const \u{0000006d}etric = true;"),
        ("apps/g2-monitoring-source-onboarding/source.ts", r"class Resource\u0406nventory {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "async function fetch_metrics() {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class MetricsRepository {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class METRICSRepository {}"),
        ("apps/g2-monitoring-source-onboarding/metrics/collector.ts", "export const enabled = true"),
        ("apps/g2-monitoring-source-onboarding/problems/collector.ts", "export const enabled = true"),
        ("apps/g2-monitoring-source-onboarding/resource-inventories/collector.ts", "export const enabled = true"),
        ("apps/g2-monitoring-source-onboarding/METRICSRepository/collector.ts", "export const enabled = true"),
        ("implementation/g2-monitoring-source-onboarding/model.sql", 'CREATE TABLE "monitoring"."shadow_sources" (id uuid);'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'const ddl = `CREATE /*comment*/ TABLE monitoring.shadow_sources (id uuid)`;'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'const ddl = `CREATE OR REPLACE VIEW "monitoring"."shadow_sources" AS SELECT 1`;'),
        ("implementation/g2-monitoring-source-onboarding/model.sql", "CREATE TABLE measurements (source_id text, observed_value float, observed_at timestamp);"),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'function authorize(user) { return user.providerRole === "admin"; }'),
        ("apps/g2-monitoring-source-onboarding/source.ts", "async function save(password) { await database.insert({password}); }"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const store = database; await store.insert({sourceId, value});"),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'await database["insert"]({sourceId, value});'),
        ("apps/g2-monitoring-source-onboarding/source.ts", "return reply.send({password: payload.password});"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "export function browserAutomationMetric() {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "async function executeSourceCutover() {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "async function sendMonitoringToAlerting() {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "class InitialResourceIngestionService {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "async function runProductionDeployment() {}"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "await database?.insert({sourceId, value});"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "await (database).insert({sourceId, value});"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "await database.insert.call(database, {sourceId, value});"),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'await database["in" + "sert"]({sourceId, value});'),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const write = database.insert; await write({sourceId, value});"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const pw = payload.password; return reply.send({value: pw});"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "function emit(v) { return reply.send({value: v}); } const pw = payload.password; return emit(pw);"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const ddl = `CREATE TEMPORARY TABLE scratch_source (id uuid)`;"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const ddl = `CREATE UNLOGGED TABLE scratch_source (id uuid)`;"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const ddl = `CREATE UNIQUE INDEX idx_source ON scratch_source(id)`;"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const ddl = `CREATE INDEX CONCURRENTLY idx_source ON scratch_source(id)`;"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "await (database.insert)({sourceId, value});"),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'await database["insert"].call(database, {sourceId, value});'),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const ddl = `CREATE DATABASE g2_source_store`;"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const ddl = `CREATE FOREIGN TABLE source_cache (id uuid) SERVER remote`;"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const ddl = `CREATE GLOBAL TEMPORARY TABLE source_cache (id uuid)`;"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "await ((database.insert))({sourceId, value});"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "let store; store = database; await store.insert({sourceId, value});"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const {password: pw} = payload; return reply.send({value: pw});"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const ddl = `CREATE TABLESPACE g2_store LOCATION '/tmp/g2'`;"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "await fetch('/api/source-cutover');"),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'provider["permi" + "ssions"].includes("source:write")'),
        ("apps/g2-monitoring-source-onboarding/Мetric/page.ts", "export const enabled = true"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "await database.insert?.({sourceId, value});"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "await (database.insert)?.({sourceId, value});"),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'await database["insert"]?.({sourceId, value});'),
        ("apps/g2-monitoring-source-onboarding/source.ts", "let pw; pw = payload.password; return reply.send({value: pw});"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const emit = v => reply.send({value: v}); emit(payload.password);"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "const ddl = `CREATE SERVER g2 FOREIGN DATA WRAPPER postgres_fdw`;"),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'const p = provider; if (p.role === "admin") allow();'),
        ("apps/g2-monitoring-source-onboarding/source.ts", r'fetch("/api/\x6detric")'),
        ("apps/g2-monitoring-source-onboarding/source.ts", "db.insert.call?.(db, record);"),
        ("apps/g2-monitoring-source-onboarding/source.ts", "db.insert.apply?.(db, [record]);"),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'const key="password"; const out=payload[key]; reply.send.call?.(reply,{value:out});'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'const key="password"; const out=payload[key]; reply.send.apply?.(reply,[{value:out}]);'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'const key="password"; const out=payload[key]; reply?.["send"]?.({value:out});'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'db["query"](Prisma["sql"]`GRANT SELECT ON TABLE monitoring.sources TO app`);'),
        ("apps/g2-monitoring-source-onboarding/source.ts", '(db.query)((Prisma.sql)`GRANT SELECT ON TABLE monitoring.sources TO app`);'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'const [out] = [payload.password]; reply.send({value: out});'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'let out; ([out] = [payload.password]); reply.send({value: out});'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'const payload = "GRANT SELECT ON TABLE monitoring.sources TO app"; db.query(payload);'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'const payload = "DROP TABLE scratch_source"; db.query(payload);'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'const values=[payload.password]; const [out]=values; reply.send({value:out});'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'const values=[payload.password]; let out; ([out]=values); reply.send({value:out});'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'let payload; payload="GRANT SELECT ON TABLE monitoring.sources TO app"; db.query(payload);'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'db.query.call(db, "GRANT SELECT ON TABLE monitoring.sources TO app");'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'db.query.apply(db, ["GRANT SELECT ON TABLE monitoring.sources TO app"]);'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'Reflect.apply(db.query, db, ["GRANT SELECT ON TABLE monitoring.sources TO app"]);'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'reply.send.bind?.(reply)({value: payload.password});'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'const [emit]=[reply.send.bind(reply)]; emit({value:payload.password});'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'function expose(x){ reply.send({value:x}); } expose?.(payload.password);'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'function expose(x){ reply.send({value:x}); } expose.call(null,payload.password);'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'function expose(x){ reply.send({value:x}); } expose.apply(null,[payload.password]);'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'function expose(x){ reply.send({value:x}); } Reflect.apply(expose,null,[payload.password]);'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'const handlers={emit:reply.send.bind(reply)}; handlers.emit({value:payload.password});'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'const handlers={}; handlers.emit=reply.send.bind(reply); handlers.emit({value:payload.password});'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'function get(){ return payload.password; } const out=get(); reply.send({value:out});'),
        ("apps/g2-monitoring-source-onboarding/source.ts", 'function get(){ return payload.password; } function get2(){ return get(); } const out=get2(); reply.send({value:out});'),
    )
    for path, text in rejected:
        if not scope.validate_semantic_artifact(path, text, policy):
            raise AssertionError(f"forbidden semantic artifact unexpectedly accepted: {path}: {text}")

    allowed = (
        "export const browser_automation = true",
        'describe("browser automation", () => {})',
        "export const browserAutomationTest = true",
        "export const geometric_layout = true",
        "export const sourceStatus = 'reconciliation_required'",
        "export const credential_binding_ref = source.credential_binding_ref",
        "return reply.send({credential_binding_ref: source.credential_binding_ref});",
        "export async function submitOnboarding(payload) { return fetch('/api/v1/tenants/current/monitoring-sources', {method: 'POST'}); }",
        'export function SourceForm({provider}) { return <div role="status">{provider.name}</div>; }',
        'return reply.send({error: "password is required"});',
        '// reply.send({value: payload.password});',
        'const help = "reply.send({value: payload.password})";',
        'const out = "payload.password"; reply.send({value: out});',
        'search.query("Grant camera access");',
        'ui.run("Revoke camera access");',
        'const payload = "Grant camera access"; search.query(payload);',
        'const help = "Create table monitoring sources";',
        'const help = "Drop table instructions";',
    )
    for text in allowed:
        errors = scope.validate_semantic_artifact("apps/g2-monitoring-source-onboarding/source.ts", text, policy)
        if errors:
            raise AssertionError(f"bounded G2 semantics false-positive: {text}: {errors}")


def falsify_g2_authorization_ledger_admission() -> None:
    required = {
        "governance/adversarial/learning-ledger.d/pr-154-g2-authorization-review-findings.zz-026-031.json",
        "governance/adversarial/learning-ledger.d/z-pr-154-g2-authorization-review-findings-047-054.json",
        "governance/adversarial/learning-ledger.d/zzzz-pr-154-g2-authorization-review-findings-137-142.json",
    }
    missing = required - authorization.AUTH_PR_ALLOWED_PATHS
    if missing:
        raise AssertionError(f"governed learning-ledger fragments missing from authorization allowlist: {sorted(missing)}")
    workflow = (authorization.ROOT / ".github/workflows/g2-monitoring-source-onboarding-authorization.yml").read_text(encoding="utf-8")
    for path in required:
        if workflow.count(path) < 2:
            raise AssertionError(f"governed learning-ledger fragment missing from pull/push workflow filters: {path}")


def falsify_g2_materialized_scope_package() -> None:
    wrapper = authorization.ROOT / "tools/assurance/validate_g2_monitoring_source_onboarding_implementation_scope.py"
    core = authorization.ROOT / "tools/assurance/g2_scope_core.py"
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        target_wrapper = target / wrapper.name
        target_core = target / core.name
        shutil.copyfile(wrapper, target_wrapper)
        shutil.copyfile(core, target_core)
        spec = importlib.util.spec_from_file_location("g2_materialized_wrapper_probe", target_wrapper)
        if spec is None or spec.loader is None:
            raise AssertionError("unable to construct materialized wrapper probe")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if Path(module.CORE_PATH).resolve() != target_core.resolve():
            raise AssertionError(f"materialized wrapper did not bind sibling core: {module.CORE_PATH}")


def falsify_g2_trusted_workflow_semantics() -> None:
    workflow = authorization.SCOPE_WORKFLOW.read_text(encoding="utf-8")
    if authorization.validate_scope_workflow_text(workflow):
        raise AssertionError("canonical trusted workflow rejected")
    required = (
        'G2_SCOPE_CORE: tools/assurance/g2_scope_core.py',
        'git show "${PR_BASE_SHA}:${G2_SCOPE_VALIDATOR}" > "$trusted_validator"',
        'git show "${PR_BASE_SHA}:${G2_SCOPE_CORE}" > "$trusted_core"',
        'test -s "$trusted_core"',
    )
    for marker in required:
        if marker not in workflow:
            raise AssertionError(f"trusted scope package materialization missing: {marker}")
    mutations = (
        workflow + "\n# extra workflow material\n",
        workflow.replace("name: JLMIRROR G2 Monitoring Source Onboarding Implementation Scope", "name: drifted", 1),
        workflow.replace("cancel-in-progress: true", "cancel-in-progress: false", 1),
        workflow.replace("runs-on: ubuntu-24.04", "runs-on: ubuntu-latest", 1),
        workflow.replace("statuses: write", "contents: write", 1),
        workflow.replace('git show "${PR_BASE_SHA}:${G2_SCOPE_CORE}" > "$trusted_core"\n', "", 1),
    )
    for mutated in mutations:
        errors = authorization.validate_scope_workflow_text(mutated)
        if not errors or not any("canonical blob drift" in error for error in errors):
            raise AssertionError(f"trusted workflow mutation escaped exact lock: {errors}")


def _trusted_status(*, status_id: int, state: str, created_at: str = "2026-09-15T00:00:00Z") -> dict:
    context, description, _label, _mode = readiness.evidence_contract("scope", BASE, HEAD)
    return {
        "id": status_id,
        "context": context,
        "state": state,
        "description": description,
        "target_url": f"{SERVER}/{REPO}/actions/runs/{RUN_ID}",
        "created_at": created_at,
        "creator": {"login": readiness.TRUSTED_CREATOR_LOGIN, "id": readiness.TRUSTED_CREATOR_ID},
    }


def falsify_g2_same_second_status_ordering() -> None:
    success = _trusted_status(status_id=100, state="success")
    newer_pending = _trusted_status(status_id=101, state="pending")
    try:
        readiness.select_trusted_evidence([newer_pending, success], evidence="scope", repo=REPO, server_url=SERVER, base_sha=BASE, head_sha=HEAD)
    except AssertionError as exc:
        if "not successful" not in str(exc):
            raise
    else:
        raise AssertionError("same-second newer pending status did not supersede older success")
    duplicate = copy.deepcopy(success)
    try:
        readiness.select_trusted_evidence([success, duplicate], evidence="scope", repo=REPO, server_url=SERVER, base_sha=BASE, head_sha=HEAD)
    except AssertionError as exc:
        if "ordering is ambiguous" not in str(exc):
            raise
    else:
        raise AssertionError("duplicate trusted status ordering key did not fail closed")


def main() -> int:
    falsify_g2_semantic_scope_guard()
    falsify_g2_authorization_ledger_admission()
    falsify_g2_materialized_scope_package()
    falsify_g2_trusted_workflow_semantics()
    falsify_g2_same_second_status_ordering()
    print("g2_review_guardrails=PASS semantic=current-review-regressions+array-variable-taint+later-sql-binding+sql-helper-equivalence+optional-bind+array-sink-alias+wrapper-equivalence+object-sink-members+named-return-taint authorization=ledger-fragments workflow=blob-exact status=total-order")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())