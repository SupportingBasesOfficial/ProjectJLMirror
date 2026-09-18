#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "g6_monitoring_alerting_transport_postgres=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280"
PG_CONTAINER="jlmirror-g6-monitoring-alerting-postgres"
PG_PASSWORD="g6-transport-password"
PG_DATABASE="jlmirror"

cleanup(){ docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

docker pull "$POSTGRES_IMAGE" >/dev/null
docker run -d --rm --name "$PG_CONTAINER" -e POSTGRES_PASSWORD="$PG_PASSWORD" -e POSTGRES_DB="$PG_DATABASE" "$POSTGRES_IMAGE" >/dev/null

stable_ready=0
for _ in $(seq 1 90); do
  if docker inspect -f '{{.State.Running}}' "$PG_CONTAINER" 2>/dev/null | grep -qx true      && docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c 'SELECT 1' 2>/dev/null | grep -qx 1; then
    stable_ready=$((stable_ready+1))
    [[ "$stable_ready" -ge 3 ]] && break
  else
    stable_ready=0
  fi
  sleep 1
done
test "$stable_ready" -ge 3

for migration in   sql/wave2/001_async_correctness.sql   sql/wave2/002_reconciliation_evidence_and_transition_hardening.sql   sql/wave2/003_cross_authority_completion_hardening.sql   sql/wave2/004_reconciliation_generation_handoff.sql   sql/wave2/005_reconciliation_attempt_generation_binding.sql   sql/wave2/006_operation_scope_binding_hardening.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

while IFS= read -r migration; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done < <(find sql/wave4 -maxdepth 1 -type f -name '*.sql' | sort)

docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < sql/integration/001_monitoring_alerting_publication.sql >/dev/null
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < sql/integration/002_monitoring_alerting_consumer.sql >/dev/null

role_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT string_agg(rolname||':'||rolcanlogin::int||':'||rolsuper::int||':'||rolbypassrls::int||':'||rolinherit::int,',' ORDER BY rolname)
FROM pg_roles
WHERE rolname IN ('jlmirror_g6_alerting_transport_executor','jlmirror_g6_alerting_transport_invoker');")"
test "$role_state" = "jlmirror_g6_alerting_transport_executor:0:0:0:0,jlmirror_g6_alerting_transport_invoker:0:0:0:0"

acl_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT
 has_table_privilege('jlmirror_g6_alerting_transport_invoker','system.async_consumer_inbox','SELECT')::int||':'||
 has_table_privilege('jlmirror_g6_alerting_transport_invoker','system.async_consumer_inbox','INSERT')::int||':'||
 has_table_privilege('jlmirror_g6_alerting_transport_invoker','monitoring.monitoring_problem','SELECT')::int||':'||
 has_function_privilege('jlmirror_g6_alerting_transport_invoker','system.g6_admit_monitoring_alerting_message(text,text,text,text,text,text,text,text,text,text,text,timestamptz,timestamptz,text,timestamptz,timestamptz,text,text,text,text,bytea)','EXECUTE')::int||':'||
 has_function_privilege('jlmirror_g6_alerting_transport_invoker','system.g6_claim_monitoring_alerting_receipt(text,text,text,integer,text,text,text,text,text,text,text,text,bigint)','EXECUTE')::int||':'||
 has_function_privilege('jlmirror_g6_alerting_transport_invoker','system.g6_complete_monitoring_alerting_resync(text,text,text,bigint)','EXECUTE')::int;")"
test "$acl_state" = "0:0:0:1:1:1"

docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
BEGIN;
SET LOCAL session_replication_role=replica;

COPY monitoring.monitoring_source(
 tenant_id,monitoring_source_id,provider_scope_tenant_binding_id,provider_profile,
 active_source_instance_generation,configuration_revision,scope_revision,display_name,
 credential_binding_ref,configured_provider_scope,operational_evidence_state,last_sync_operation_id
) FROM STDIN;
tenant-a	source-1	binding-1	zabbix	generation-1	1	1	Source 1	credential-1	{"host_group_refs":[]}	current	sync-1
\.

COPY monitoring.monitoring_source_generation(
 tenant_id,monitoring_source_id,source_instance_generation,provider_profile,provider_instance_ref,provider_base_url
) FROM STDIN;
tenant-a	source-1	generation-1	zabbix	instance-1	https://zabbix.example.invalid
tenant-a	source-1	generation-old	zabbix	instance-old	https://zabbix.example.invalid
\.

COPY monitoring.monitoring_resource(
 tenant_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,
 resource_kind,provider_object_kind,provider_external_ref,display_name,
 scope_state,scope_projection_revision,scope_evidence_state,presence_state,presence_evidence_state,
 last_observed_at,last_confirmed_present_at
) FROM STDIN;
tenant-a	resource-1	source-1	generation-1	host	zabbix_host	101	Resource 1	in_scope	1	current	present	current	2026-09-18 12:00:00+00	2026-09-18 12:00:00+00
\.

COPY monitoring.monitoring_problem_provider_binding(
 tenant_id,problem_id,monitoring_source_id,source_instance_generation,monitoring_resource_id,
 provider_profile,provider_external_ref,provider_trigger_ref
) FROM STDIN;
tenant-a	problem-1	source-1	generation-1	resource-1	zabbix	9001	7001
\.

COPY monitoring.monitoring_problem(
 tenant_id,problem_id,monitoring_source_id,source_instance_generation,monitoring_resource_id,
 problem_state,severity_class,summary,opened_at,resolved_at,last_confirmed_at,evidence_state,
 projection_revision,problem_poll_epoch,problem_poll_generation
) FROM STDIN;
tenant-a	problem-1	source-1	generation-1	resource-1	active	warning	CPU threshold exceeded	2026-09-18 11:00:00+00	\N	2026-09-18 12:00:00+00	current	7	1	1
\.

COPY monitoring.health_projection(
 tenant_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,
 health_class,evidence_state,projection_revision,last_changed_at,last_evidence_at,
 problem_snapshot_evidence_id,reason_refs
) FROM STDIN;
tenant-a	resource-1	source-1	generation-1	degraded	current	11	2026-09-18 11:00:00+00	2026-09-18 12:00:00+00	\N	["problem-1"]
\.

COMMIT;
SQL

problem_payload='{"monitoring_resource_id":"resource-1","monitoring_source_id":"source-1","problem_id":"problem-1","problem_transition_id":"problem-transition-1","projection_revision":7,"source_instance_generation":"generation-1"}'
health_payload='{"health_transition_id":"health-transition-1","monitoring_resource_id":"resource-1","monitoring_source_id":"source-1","projection_revision":11,"source_instance_generation":"generation-1"}'
old_payload='{"monitoring_resource_id":"resource-1","monitoring_source_id":"source-1","problem_id":"problem-old","problem_transition_id":"problem-transition-old","projection_revision":1,"source_instance_generation":"generation-old"}'
reordered_payload='{"monitoring_resource_id":"resource-1","monitoring_source_id":"source-1","problem_id":"problem-1","problem_transition_id":"problem-transition-earlier","projection_revision":6,"source_instance_generation":"generation-1"}'
lease_payload='{"health_transition_id":"health-transition-lease","monitoring_resource_id":"resource-1","monitoring_source_id":"source-1","projection_revision":11,"source_instance_generation":"generation-1"}'

md5hex(){ printf '%s' "$1" | md5sum | awk '{print $1}'; }
sep=$''
scope="monitoring:tenant:$(md5hex 'tenant-a')"

admit(){
  local contract="$1" subject_type="$2" subject_id="$3" transition="$4" payload="$5" occurred="$6"
  local msg correlation causation
  msg="$contract@1:$(md5hex "tenant-a$sep$transition")"
  correlation="monitoring-correlation:$(md5hex "tenant-a$sep$transition")"
  causation="monitoring-transition:$(md5hex "$contract$sep""tenant-a$sep$transition")"
  docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "
    SET ROLE jlmirror_g6_alerting_transport_invoker;
    SELECT system.g6_admit_monitoring_alerting_message(
      '$scope','$msg','integration_event','$contract','1','Monitoring',NULL,
      'tenant','tenant-a','$subject_type','$subject_id','$occurred'::timestamptz,
      NULL,NULL,NULL,NULL,'$correlation','$causation','confidential_tenant','jsonb-text-utf8@1',
      convert_to('$payload','UTF8')
    )::text;"
}

claim(){
  local msg="$1"
  docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "
    SET ROLE jlmirror_g6_alerting_transport_invoker;
    SELECT system.g6_claim_monitoring_alerting_receipt(
      '$scope','$msg','worker-a',30,'admission-1','authz-1','service-worker-a',
      'cred-1','runtime-1','production','placement-1','tenant-a-worker',7
    )::text;"
}

complete(){
  local msg="$1" gen="$2"
  docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "
    SET ROLE jlmirror_g6_alerting_transport_invoker;
    SELECT system.g6_complete_monitoring_alerting_resync('$scope','$msg','worker-a',$gen)::text;"
}

problem_msg="monitoring.problem-state.changed@1:$(md5hex "tenant-a$sep""problem-transition-1")"
health_msg="monitoring.health-projection.changed@1:$(md5hex "tenant-a$sep""health-transition-1")"
old_msg="monitoring.problem-state.changed@1:$(md5hex "tenant-a$sep""problem-transition-old")"
reordered_msg="monitoring.problem-state.changed@1:$(md5hex "tenant-a$sep""problem-transition-earlier")"
lease_msg="monitoring.health-projection.changed@1:$(md5hex "tenant-a$sep""health-transition-lease")"

first="$(admit 'monitoring.problem-state.changed' 'monitoring_problem' 'problem-1' 'problem-transition-1' "$problem_payload" '2026-09-18 12:00:00+00')"
grep -q '"receipt_state": "admitted"' <<<"$first"
grep -q '"duplicate": false' <<<"$first"

duplicate="$(admit 'monitoring.problem-state.changed' 'monitoring_problem' 'problem-1' 'problem-transition-1' "$problem_payload" '2026-09-18 12:00:00+00')"
grep -q '"duplicate": true' <<<"$duplicate"

set +e
conflict="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "
 SET ROLE jlmirror_g6_alerting_transport_invoker;
 SELECT system.g6_admit_monitoring_alerting_message(
 '$scope','$problem_msg','integration_event','monitoring.problem-state.changed','1','Monitoring',NULL,
 'tenant','tenant-a','monitoring_problem','problem-1','2026-09-18 12:00:01+00'::timestamptz,
 NULL,NULL,NULL,NULL,
 'monitoring-correlation:$(md5hex "tenant-a$sep""problem-transition-1")',
 'monitoring-transition:$(md5hex "monitoring.problem-state.changed$sep""tenant-a$sep""problem-transition-1")',
 'confidential_tenant','jsonb-text-utf8@1',convert_to('$problem_payload','UTF8')
 )::text;" 2>&1)"
conflict_rc=$?
set -e
test "$conflict_rc" -ne 0
grep -q 'g6.transport_duplicate_equivalence_conflict' <<<"$conflict"

problem_claim="$(claim "$problem_msg")"
grep -q '"receipt_state": "processing"' <<<"$problem_claim"
problem_complete="$(complete "$problem_msg" 1)"
grep -q '"receipt_state": "completed"' <<<"$problem_complete"
grep -q 'monitoring_problem_owner_reread_current' <<<"$problem_complete"

admit 'monitoring.health-projection.changed' 'monitoring_resource' 'resource-1' 'health-transition-1' "$health_payload" '2026-09-18 12:01:00+00' >/dev/null
claim "$health_msg" >/dev/null
health_complete="$(complete "$health_msg" 1)"
grep -q 'monitoring_health_owner_reread_current' <<<"$health_complete"

admit 'monitoring.problem-state.changed' 'monitoring_problem' 'problem-old' 'problem-transition-old' "$old_payload" '2026-09-18 10:00:00+00' >/dev/null
claim "$old_msg" >/dev/null
old_complete="$(complete "$old_msg" 1)"
grep -q 'monitoring_owner_reread_noncurrent_generation' <<<"$old_complete"

admit 'monitoring.problem-state.changed' 'monitoring_problem' 'problem-1' 'problem-transition-earlier' "$reordered_payload" '2026-09-18 09:00:00+00' >/dev/null
claim "$reordered_msg" >/dev/null
reordered_complete="$(complete "$reordered_msg" 1)"
grep -q 'monitoring_problem_owner_reread_current' <<<"$reordered_complete"

admit 'monitoring.health-projection.changed' 'monitoring_resource' 'resource-1' 'health-transition-lease' "$lease_payload" '2026-09-18 12:02:00+00' >/dev/null
docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "
  SET ROLE jlmirror_g6_alerting_transport_invoker;
  SELECT system.g6_claim_monitoring_alerting_receipt(
    '$scope','$lease_msg','worker-a',1,'admission-lease','authz-lease','service-worker-a',
    'cred-1','runtime-1','production','placement-1','tenant-a-worker',7
  )::text;" >/dev/null
sleep 2
lease_complete="$(complete "$lease_msg" 1)"
grep -q '"receipt_state": "reconciliation_required"' <<<"$lease_complete"

alert_business_tables="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT count(*) FROM information_schema.tables WHERE table_schema='alerting';")"
test "$alert_business_tables" = "0"

inbox_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT count(*) FROM system.async_consumer_inbox
WHERE consumer_contract='alerting.monitoring-resync@1';")"
test "$inbox_count" = "5"

completed_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT count(*) FROM system.async_consumer_inbox
WHERE consumer_contract='alerting.monitoring-resync@1' AND state='completed';")"
test "$completed_count" = "4"

reconcile_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT count(*) FROM system.async_consumer_inbox
WHERE consumer_contract='alerting.monitoring-resync@1' AND state='reconciliation_required';")"
test "$reconcile_count" = "1"

echo "g6_monitoring_alerting_transport_postgres=PASS duplicate=dedup conflict=blocked problem_reread=current health_reread=current historical=noncurrent reorder=no_regression lease_expiry=reconciliation alert_business_state=absent"
