#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_monitoring_alerting_publication_postgres=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-monitoring-alerting-publication-postgres}"
PG_PASSWORD="${PG_PASSWORD:-wave4-publication-password}"
PG_DATABASE="${PG_DATABASE:-jlmirror}"
cleanup(){ docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

docker pull "$POSTGRES_IMAGE" >/dev/null
docker run -d --rm --name "$PG_CONTAINER" -e POSTGRES_PASSWORD="$PG_PASSWORD" -e POSTGRES_DB="$PG_DATABASE" "$POSTGRES_IMAGE" >/dev/null
stable_ready=0
for _ in $(seq 1 90); do
  if docker inspect -f '{{.State.Running}}' "$PG_CONTAINER" 2>/dev/null | grep -qx true \
     && docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c 'SELECT 1' 2>/dev/null | grep -qx 1; then
    stable_ready=$((stable_ready+1)); [[ "$stable_ready" -ge 3 ]] && break
  else stable_ready=0; fi
  sleep 1
done
test "$stable_ready" -ge 3

# Compose the already-accepted async substrate and Monitoring runtime before the
# cross-domain bridge. The integration migration itself must not duplicate either.
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < sql/wave2/001_async_correctness.sql >/dev/null
while IFS= read -r migration; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done < <(find sql/wave4 -maxdepth 1 -type f -name '*.sql' | sort)
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < sql/integration/001_monitoring_alerting_publication.sql >/dev/null

role_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT rolcanlogin::int || ':' || rolsuper::int || ':' || rolbypassrls::int || ':' || rolinherit::int
FROM pg_roles WHERE rolname='jlmirror_wave4_monitoring_publication_executor';")"
test "$role_state" = "0:0:0:0"

trigger_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT
  (EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='monitoring.monitoring_problem_transition'::regclass AND tgname='monitoring_problem_transition_outbox' AND NOT tgisinternal))::int || ':' ||
  (EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='monitoring.health_projection_transition'::regclass AND tgname='health_projection_transition_outbox' AND NOT tgisinternal))::int;")"
test "$trigger_state" = "1:1"

acl_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT
  has_table_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_message','SELECT')::int || ':' ||
  has_table_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_message','INSERT')::int || ':' ||
  has_table_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_dispatch','INSERT')::int || ':' ||
  has_sequence_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_message_outbox_record_id_seq','USAGE')::int;")"
test "$acl_state" = "1:1:1:1"

recovery_acl="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
WITH p AS (
 SELECT oid,proacl,proowner FROM pg_proc
 WHERE oid='monitoring.recover_problem_state_publication(text,text)'::regprocedure
), h AS (
 SELECT oid,proacl,proowner FROM pg_proc
 WHERE oid='monitoring.recover_health_projection_publication(text,text)'::regprocedure
)
SELECT
 has_function_privilege('jlmirror_wave4_recovery_authority','monitoring.recover_problem_state_publication(text,text)','EXECUTE')::int || ':' ||
 has_function_privilege('jlmirror_wave4_recovery_authority','monitoring.recover_health_projection_publication(text,text)','EXECUTE')::int || ':' ||
 (NOT EXISTS (SELECT 1 FROM p, LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE'))::int || ':' ||
 (NOT EXISTS (SELECT 1 FROM h, LATERAL aclexplode(COALESCE(h.proacl,acldefault('f',h.proowner))) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE'))::int;")"
test "$recovery_acl" = "1:1:1:1"

# Exercise the exact trigger functions against temporary transition fixtures. They
# reference only immutable NEW fields, so this proves the runtime publication law
# without manufacturing unrelated Monitoring parent-state fixtures.
docker exec "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" >/dev/null <<'SQL'
CREATE TEMP TABLE problem_transition_fixture(
  tenant_id text NOT NULL,
  problem_transition_id text NOT NULL,
  problem_id text NOT NULL,
  monitoring_source_id text NOT NULL,
  source_instance_generation text NOT NULL,
  monitoring_resource_id text NOT NULL,
  projection_revision bigint NOT NULL,
  occurred_at timestamptz NOT NULL
);
CREATE TRIGGER problem_fixture_outbox
AFTER INSERT ON problem_transition_fixture
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_publish_problem_transition();

INSERT INTO problem_transition_fixture VALUES(
  'tenant-a','problem-transition-001','problem-001','source-001','generation-001',
  'resource-001',7,'2026-09-12 12:00:00+00'
);
-- Exact replay must observe the same logical publication, not create a second one.
INSERT INTO problem_transition_fixture VALUES(
  'tenant-a','problem-transition-001','problem-001','source-001','generation-001',
  'resource-001',7,'2026-09-12 12:00:00+00'
);

-- Same scoped logical identity with changed immutable meaning must fail closed.
DO $$
BEGIN
  BEGIN
    INSERT INTO problem_transition_fixture VALUES(
      'tenant-a','problem-transition-001','problem-001','source-001','generation-001',
      'resource-001',8,'2026-09-12 12:00:00+00'
    );
    RAISE EXCEPTION 'expected publication identity conflict was not raised';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM <> 'monitoring.publication_identity_conflict' THEN
      RAISE;
    END IF;
  END;
END;
$$;

CREATE TEMP TABLE health_transition_fixture(
  tenant_id text NOT NULL,
  health_transition_id text NOT NULL,
  monitoring_resource_id text NOT NULL,
  monitoring_source_id text NOT NULL,
  source_instance_generation text NOT NULL,
  projection_revision bigint NOT NULL,
  occurred_at timestamptz NOT NULL
);
CREATE TRIGGER health_fixture_outbox
AFTER INSERT ON health_transition_fixture
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_publish_health_transition();

INSERT INTO health_transition_fixture VALUES(
  'tenant-a','health-transition-001','resource-001','source-001','generation-001',
  11,'2026-09-12 12:01:00+00'
);
INSERT INTO health_transition_fixture VALUES(
  'tenant-a','health-transition-001','resource-001','source-001','generation-001',
  11,'2026-09-12 12:01:00+00'
);
SQL

bridge_where="contract_name IN ('monitoring.problem-state.changed','monitoring.health-projection.changed')"
outbox_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM system.async_outbox_message WHERE $bridge_where;")"
if [[ "$outbox_count" != "2" ]]; then
  echo "publication_bridge_outbox_count=$outbox_count expected=2" >&2
  docker exec "$PG_CONTAINER" psql -U postgres -d "$PG_DATABASE" -c "SELECT outbox_record_id,contract_name,message_id,tenant_id,subject_type,subject_id FROM system.async_outbox_message WHERE $bridge_where ORDER BY outbox_record_id;" >&2
  exit 1
fi

dispatch_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT count(*)
FROM system.async_outbox_dispatch d
JOIN system.async_outbox_message m USING(outbox_record_id)
WHERE $bridge_where AND d.state='pending';")"
if [[ "$dispatch_count" != "2" ]]; then
  echo "publication_bridge_pending_dispatch_count=$dispatch_count expected=2" >&2
  exit 1
fi

problem_ok="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
WITH m AS (
 SELECT *,convert_from(encoded_payload,'UTF8')::jsonb AS p
 FROM system.async_outbox_message WHERE contract_name='monitoring.problem-state.changed'
)
SELECT
 (message_class='integration_event')::int || ':' ||
 (contract_version='1')::int || ':' ||
 (producer='Monitoring')::int || ':' ||
 (scope_class='tenant' AND tenant_id='tenant-a')::int || ':' ||
 (subject_type='monitoring_problem' AND subject_id='problem-001')::int || ':' ||
 (data_classification='confidential_tenant')::int || ':' ||
 (p='{"problem_id":"problem-001","monitoring_source_id":"source-001","source_instance_generation":"generation-001","monitoring_resource_id":"resource-001","projection_revision":7,"problem_transition_id":"problem-transition-001"}'::jsonb)::int || ':' ||
 (NOT (p ?| ARRAY['problem_state','severity_class','provider_acknowledged','summary','provider_eventid','provider_trigger_ref']))::int || ':' ||
 (octet_length(comparison_evidence)>0)::int
FROM m;")"
test "$problem_ok" = "1:1:1:1:1:1:1:1:1"

health_ok="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
WITH m AS (
 SELECT *,convert_from(encoded_payload,'UTF8')::jsonb AS p
 FROM system.async_outbox_message WHERE contract_name='monitoring.health-projection.changed'
)
SELECT
 (message_class='integration_event')::int || ':' ||
 (contract_version='1')::int || ':' ||
 (producer='Monitoring')::int || ':' ||
 (scope_class='tenant' AND tenant_id='tenant-a')::int || ':' ||
 (subject_type='monitoring_resource' AND subject_id='resource-001')::int || ':' ||
 (data_classification='confidential_tenant')::int || ':' ||
 (p='{"monitoring_source_id":"source-001","source_instance_generation":"generation-001","monitoring_resource_id":"resource-001","projection_revision":11,"health_transition_id":"health-transition-001"}'::jsonb)::int || ':' ||
 (NOT (p ?| ARRAY['health_class','health_evidence_state','reason_refs','provider_acknowledged','severity_class']))::int || ':' ||
 (octet_length(comparison_evidence)>0)::int
FROM m;")"
test "$health_ok" = "1:1:1:1:1:1:1:1:1"

# Prove exact replay did not duplicate either bridge logical event and each bridge
# outbox record still has exactly one dispatch record. Other composed-substrate
# messages are intentionally outside this slice's count.
identity_ok="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
WITH bridge AS (
  SELECT * FROM system.async_outbox_message WHERE $bridge_where
)
SELECT
 (count(*)=count(DISTINCT producer_message_scope || chr(31) || message_id))::int || ':' ||
 (count(*)=(
    SELECT count(*)
    FROM system.async_outbox_dispatch d
    JOIN bridge b USING(outbox_record_id)
 ))::int
FROM bridge;")"
test "$identity_ok" = "1:1"

echo "wave4_monitoring_alerting_publication_postgres=PASS"
