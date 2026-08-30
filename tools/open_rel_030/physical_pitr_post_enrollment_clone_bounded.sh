#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: physical_pitr_post_enrollment_clone_bounded.sh <external-control-container> <postgres-image>" >&2
  exit 2
fi

control_container="$1"
pg_image="$2"
password="evidence"
primary_container="jlmirror-open-rel-030-postclone-primary"
clone_container="jlmirror-open-rel-030-postclone-copy"
shared_role="pitr_postclone_shared"
tmpdir="$(mktemp -d)"
secret_path="/run/jlmirror-recovery-instance/secret"
blackhole_rule_installed=0
blackhole_chain=""
blackhole_control_ip=""
blackhole_clone_ip=""

cleanup() {
  if [[ "$blackhole_rule_installed" == "1" && -n "$blackhole_chain" && -n "$blackhole_control_ip" && -n "$blackhole_clone_ip" ]]; then
    sudo iptables -D "$blackhole_chain" -s "$blackhole_control_ip" -d "$blackhole_clone_ip" \
      -p tcp --sport 5432 -j DROP >/dev/null 2>&1 || true
    blackhole_rule_installed=0
  fi
  docker rm -f "$primary_container" "$clone_container" >/dev/null 2>&1 || true
  sudo rm -rf "$tmpdir" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

wait_tcp() {
  local container="$1" consecutive=0
  for _ in $(seq 1 160); do
    if docker exec -e PGPASSWORD="$password" "$container" \
      pg_isready -h 127.0.0.1 -U postgres -d jlmirror >/dev/null 2>&1; then
      consecutive=$((consecutive + 1))
      [[ "$consecutive" -ge 3 ]] && return 0
    else
      consecutive=0
    fi
    sleep 0.25
  done
  echo "post-enrollment clone database did not become ready: $container" >&2
  docker logs "$container" >&2 || true
  return 1
}

psql_in() {
  local container="$1" sql="$2"
  docker exec -e PGPASSWORD="$password" "$container" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c "$sql"
}

assert_exact() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$actual" != "$expected" ]]; then
    printf '%s expected=%q actual=%q\n' "$label" "$expected" "$actual" >&2
    return 1
  fi
  printf '%s=PASS value=%q\n' "$label" "$actual"
}

pg_uid="$(docker run --rm --entrypoint sh "$pg_image" -c 'id -u postgres')"
pg_gid="$(docker run --rm --entrypoint sh "$pg_image" -c 'id -g postgres')"
mkdir -p "$tmpdir/primary-data" "$tmpdir/clone-data"
sudo chown -R "$pg_uid:$pg_gid" "$tmpdir/primary-data" "$tmpdir/clone-data"

primary_secret="$(openssl rand -hex 32)"
printf '%s\n' "$primary_secret" >"$tmpdir/primary.secret"
sudo chown "$pg_uid:$pg_gid" "$tmpdir/primary.secret"
sudo chmod 0400 "$tmpdir/primary.secret"

docker run -d --name "$primary_container" \
  -e POSTGRES_PASSWORD="$password" -e POSTGRES_DB=jlmirror \
  -v "$tmpdir/primary-data:/var/lib/postgresql/data" \
  -v "$tmpdir/primary.secret:$secret_path:ro" \
  "$pg_image" >/dev/null
wait_tcp "$primary_container"

# Install database-visible identity and bounded local transport before the PGDATA
# snapshot. The effective secret remains outside PGDATA. On uncertainty/timeout
# the function does not synchronously cancel/disconnect; every evidence call is
# made by a one-shot psql backend whose retirement closes an abandoned socket.
psql_in "$primary_container" "
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
  CREATE EXTENSION IF NOT EXISTS dblink;
  CREATE TABLE pitr_instance_identity (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    instance_id uuid NOT NULL,
    enrolled_at timestamptz NOT NULL DEFAULT clock_timestamp()
  );
  INSERT INTO pitr_instance_identity(singleton,instance_id) VALUES(true,gen_random_uuid());
  REVOKE ALL ON pitr_instance_identity FROM PUBLIC;

  CREATE OR REPLACE FUNCTION pitr_local_instance_fingerprint()
  RETURNS text LANGUAGE plpgsql STRICT SECURITY DEFINER SET search_path=pg_catalog,public
  AS \$\$
  DECLARE v_secret text;
  BEGIN
    v_secret := btrim(pg_catalog.pg_read_file('$secret_path'));
    IF v_secret = '' THEN RAISE EXCEPTION 'empty instance capability'; END IF;
    RETURN encode(public.digest(convert_to('open-rel-030-postclone-instance-v1:' || v_secret,'UTF8'),'sha256'),'hex');
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_postclone_bounded_remote_text(p_conn text,p_sql text,p_timeout_ms integer)
  RETURNS text LANGUAGE plpgsql STRICT SECURITY DEFINER SET search_path=pg_catalog,public
  AS \$\$
  DECLARE v_name text; v_deadline timestamptz; v_value text;
  BEGIN
    IF p_timeout_ms < 50 OR p_timeout_ms > 5000 THEN RETURN NULL; END IF;
    v_name := 'or030_postclone_' || pg_backend_pid()::text || '_' || substr(md5(clock_timestamp()::text || random()::text),1,12);
    v_deadline := clock_timestamp() + (p_timeout_ms::text || ' milliseconds')::interval;
    PERFORM public.dblink_connect(v_name,p_conn);
    IF public.dblink_send_query(v_name,p_sql) <> 1 THEN RETURN NULL; END IF;
    LOOP
      EXIT WHEN public.dblink_is_busy(v_name)=0;
      IF clock_timestamp() >= v_deadline THEN RETURN NULL; END IF;
      PERFORM pg_catalog.pg_sleep(0.025);
    END LOOP;
    SELECT value INTO v_value FROM public.dblink_get_result(v_name,false) AS r(value text) LIMIT 1;
    PERFORM public.dblink_disconnect(v_name);
    RETURN v_value;
  EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_claim_external(p_conn text,p_grant_id text)
  RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER SET search_path=pg_catalog,public
  AS \$\$
  DECLARE v_id uuid; v_secret text; v_text text;
  BEGIN
    SELECT instance_id INTO STRICT v_id FROM public.pitr_instance_identity WHERE singleton;
    v_secret := btrim(pg_catalog.pg_read_file('$secret_path'));
    IF v_secret = '' THEN RETURN false; END IF;
    v_text := public.pitr_postclone_bounded_remote_text(
      p_conn,format('SELECT pitr_postclone_evidence.claim_grant(%L,%L::uuid,%L)::text',p_grant_id,v_id::text,v_secret),750
    );
    RETURN coalesce(v_text::boolean,false);
  EXCEPTION WHEN OTHERS THEN RETURN false; END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_verify_external(p_conn text,p_grant_id text)
  RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER SET search_path=pg_catalog,public
  AS \$\$
  DECLARE v_id uuid; v_secret text; v_text text;
  BEGIN
    SELECT instance_id INTO STRICT v_id FROM public.pitr_instance_identity WHERE singleton;
    v_secret := btrim(pg_catalog.pg_read_file('$secret_path'));
    IF v_secret = '' THEN RETURN false; END IF;
    v_text := public.pitr_postclone_bounded_remote_text(
      p_conn,format('SELECT pitr_postclone_evidence.verify_grant(%L,%L::uuid,%L)::text',p_grant_id,v_id::text,v_secret),750
    );
    RETURN coalesce(v_text::boolean,false);
  EXCEPTION WHEN OTHERS THEN RETURN false; END;
  \$\$;

  REVOKE ALL ON FUNCTION pitr_local_instance_fingerprint() FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_postclone_bounded_remote_text(text,text,integer) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_claim_external(text,text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_verify_external(text,text) FROM PUBLIC;
" >/dev/null

primary_instance_id="$(psql_in "$primary_container" "SELECT instance_id::text FROM pitr_instance_identity WHERE singleton;")"
[[ -n "$primary_instance_id" ]] || { echo "missing enrolled primary instance id" >&2; exit 1; }
if sudo grep -R -a -F -- "$primary_secret" "$tmpdir/primary-data" >/dev/null 2>&1; then
  echo "external instance capability leaked into PGDATA before clone" >&2
  exit 1
fi
printf '%s\n' 'physical_pitr_post_enrollment_capability_outside_pgdata=PASS'

docker stop "$primary_container" >/dev/null
sudo cp -a "$tmpdir/primary-data/." "$tmpdir/clone-data/"
sudo chown -R "$pg_uid:$pg_gid" "$tmpdir/clone-data"
clone_secret="$(openssl rand -hex 32)"
[[ "$clone_secret" != "$primary_secret" ]] || { echo "instance secrets collided" >&2; exit 1; }
printf '%s\n' "$clone_secret" >"$tmpdir/clone.secret"
sudo chown "$pg_uid:$pg_gid" "$tmpdir/clone.secret"
sudo chmod 0400 "$tmpdir/clone.secret"

docker start "$primary_container" >/dev/null
docker run -d --name "$clone_container" \
  -e POSTGRES_PASSWORD="$password" -e POSTGRES_DB=jlmirror \
  -v "$tmpdir/clone-data:/var/lib/postgresql/data" \
  -v "$tmpdir/clone.secret:$secret_path:ro" \
  "$pg_image" >/dev/null
wait_tcp "$primary_container"
wait_tcp "$clone_container"

clone_instance_id="$(psql_in "$clone_container" "SELECT instance_id::text FROM pitr_instance_identity WHERE singleton;")"
assert_exact "physical_pitr_post_enrollment_pgdata_identity_copied" "$primary_instance_id" "$clone_instance_id"
primary_local_fp="$(psql_in "$primary_container" "SELECT pitr_local_instance_fingerprint();")"
clone_local_fp="$(psql_in "$clone_container" "SELECT pitr_local_instance_fingerprint();")"
[[ -n "$primary_local_fp" && -n "$clone_local_fp" && "$primary_local_fp" != "$clone_local_fp" ]] || {
  echo "post-enrollment physical copies lack distinct effective capability" >&2; exit 1;
}
printf '%s\n' 'physical_pitr_post_enrollment_local_capability_fingerprints_present=PASS'
printf '%s\n' 'physical_pitr_post_enrollment_external_capability_distinct=PASS'

shared_password="$(openssl rand -hex 24)"
psql_in "$control_container" "
  DROP SCHEMA IF EXISTS pitr_postclone_evidence CASCADE;
  DROP ROLE IF EXISTS $shared_role;
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
  CREATE SCHEMA pitr_postclone_evidence;
  CREATE TABLE pitr_postclone_evidence.recovery_grant (
    grant_id text PRIMARY KEY,
    claimed_principal name,
    claimed_instance_id uuid,
    claimed_instance_fingerprint text,
    claimed_at timestamptz,
    CHECK ((claimed_principal IS NULL AND claimed_instance_id IS NULL AND claimed_instance_fingerprint IS NULL AND claimed_at IS NULL)
       OR (claimed_principal IS NOT NULL AND claimed_instance_id IS NOT NULL AND claimed_instance_fingerprint IS NOT NULL AND claimed_at IS NOT NULL))
  );
  INSERT INTO pitr_postclone_evidence.recovery_grant(grant_id)
  VALUES('grant-post-enrollment-clone'),('grant-post-enrollment-clone-probe');
  REVOKE ALL ON pitr_postclone_evidence.recovery_grant FROM PUBLIC;

  CREATE OR REPLACE FUNCTION pitr_postclone_evidence.instance_fingerprint(p_secret text)
  RETURNS text LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog,public
  AS \$\$ SELECT encode(public.digest(convert_to('open-rel-030-postclone-instance-v1:' || p_secret,'UTF8'),'sha256'),'hex') \$\$;

  CREATE OR REPLACE FUNCTION pitr_postclone_evidence.claim_grant(p_grant_id text,p_instance_id uuid,p_instance_secret text)
  RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER SET search_path=pg_catalog,pitr_postclone_evidence,public
  AS \$\$
  DECLARE v_grant pitr_postclone_evidence.recovery_grant%ROWTYPE; v_principal name := session_user; v_fp text;
  BEGIN
    SELECT * INTO v_grant FROM pitr_postclone_evidence.recovery_grant WHERE grant_id=p_grant_id FOR UPDATE;
    IF NOT FOUND THEN RETURN false; END IF;
    v_fp := pitr_postclone_evidence.instance_fingerprint(p_instance_secret);
    IF v_grant.claimed_principal IS NULL THEN
      UPDATE pitr_postclone_evidence.recovery_grant SET claimed_principal=v_principal,claimed_instance_id=p_instance_id,
        claimed_instance_fingerprint=v_fp,claimed_at=clock_timestamp() WHERE grant_id=p_grant_id;
      RETURN true;
    END IF;
    RETURN v_grant.claimed_principal=v_principal AND v_grant.claimed_instance_id=p_instance_id
       AND v_grant.claimed_instance_fingerprint=v_fp;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_postclone_evidence.verify_grant(p_grant_id text,p_instance_id uuid,p_instance_secret text)
  RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER SET search_path=pg_catalog,pitr_postclone_evidence,public
  AS \$\$
  DECLARE v_grant pitr_postclone_evidence.recovery_grant%ROWTYPE; v_principal name := session_user; v_fp text;
  BEGIN
    SELECT * INTO v_grant FROM pitr_postclone_evidence.recovery_grant WHERE grant_id=p_grant_id;
    IF NOT FOUND THEN RETURN false; END IF;
    v_fp := pitr_postclone_evidence.instance_fingerprint(p_instance_secret);
    RETURN v_grant.claimed_principal=v_principal AND v_grant.claimed_instance_id=p_instance_id
       AND v_grant.claimed_instance_fingerprint=v_fp;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_postclone_evidence.verifier_delay_probe()
  RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog
  AS \$\$ BEGIN PERFORM pg_catalog.pg_sleep(5); RETURN true; END; \$\$;

  REVOKE ALL ON FUNCTION pitr_postclone_evidence.instance_fingerprint(text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_postclone_evidence.claim_grant(text,uuid,text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_postclone_evidence.verify_grant(text,uuid,text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_postclone_evidence.verifier_delay_probe() FROM PUBLIC;
  CREATE ROLE $shared_role LOGIN PASSWORD '$shared_password';
  GRANT USAGE ON SCHEMA pitr_postclone_evidence TO $shared_role;
  GRANT EXECUTE ON FUNCTION pitr_postclone_evidence.claim_grant(text,uuid,text),
    pitr_postclone_evidence.verify_grant(text,uuid,text),pitr_postclone_evidence.verifier_delay_probe() TO $shared_role;
" >/dev/null

control_ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$control_container")"
[[ -n "$control_ip" ]] || { echo "cannot resolve control IP" >&2; exit 1; }
shared_conn="hostaddr=$control_ip port=5432 dbname=jlmirror user=$shared_role password=$shared_password connect_timeout=2"

claim_source="$(psql_in "$clone_container" "SELECT pg_get_functiondef('pitr_claim_external(text,text)'::regprocedure);")"
verify_source="$(psql_in "$clone_container" "SELECT pg_get_functiondef('pitr_verify_external(text,text)'::regprocedure);")"
bounded_source="$(psql_in "$clone_container" "SELECT pg_get_functiondef('pitr_postclone_bounded_remote_text(text,text,integer)'::regprocedure);")"
[[ "$claim_source" == *"pitr_postclone_bounded_remote_text"* && "$verify_source" == *"pitr_postclone_bounded_remote_text"* ]] || {
  echo "post-enrollment helpers bypass bounded transport" >&2; exit 1;
}
[[ "$bounded_source" == *"dblink_send_query"* && "$bounded_source" == *"dblink_is_busy"* && "$bounded_source" != *"dblink_cancel_query"* ]] || {
  echo "post-enrollment bounded transport is not async/deadline safe" >&2; exit 1;
}
disconnect_count="$(grep -o 'dblink_disconnect' <<<"$bounded_source" | wc -l | tr -d ' ')"
[[ "$disconnect_count" == "1" ]] || { echo "post-enrollment timeout path contains synchronous cleanup" >&2; exit 1; }
printf '%s\n' 'physical_pitr_post_enrollment_helpers_use_bounded_transport=PASS'
printf '%s\n' 'physical_pitr_post_enrollment_deadline_path_has_no_synchronous_cleanup=PASS'

# Cooperative response stall.
delay_start="$(date +%s%3N)"
delay_value="$(psql_in "$clone_container" "SELECT coalesce(pitr_postclone_bounded_remote_text('$shared_conn','SELECT pitr_postclone_evidence.verifier_delay_probe()::text',500),'');")"
delay_end="$(date +%s%3N)"
delay_ms=$((delay_end - delay_start))
assert_exact "physical_pitr_post_enrollment_stalled_peer_fails_closed" "" "$delay_value"
[[ "$delay_ms" -lt 1800 ]] || { echo "post-enrollment local deadline not authoritative: ${delay_ms}ms" >&2; exit 1; }
printf 'physical_pitr_post_enrollment_local_deadline=PASS elapsed_ms=%s\n' "$delay_ms"

# Real established-session blackhole. A one-shot clone backend is retired after
# local deadline expiry, so no synchronous remote cleanup can extend the bound.
blackhole_clone_ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$clone_container")"
blackhole_control_ip="$control_ip"
[[ -n "$blackhole_clone_ip" ]] || { echo "cannot resolve clone IP" >&2; exit 1; }
if sudo iptables -nL DOCKER-USER >/dev/null 2>&1; then blackhole_chain="DOCKER-USER"; else blackhole_chain="FORWARD"; fi
(
  set +e
  timeout 5s docker exec -e PGPASSWORD="$password" "$clone_container" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq \
    -c "SELECT coalesce(pitr_postclone_bounded_remote_text('$shared_conn','SELECT pitr_postclone_evidence.verifier_delay_probe()::text',500),'');" \
    >"$tmpdir/blackhole.out" 2>"$tmpdir/blackhole.err"
  printf '%s\n' "$?" >"$tmpdir/blackhole.rc"
) & blackhole_pid=$!
blackhole_active=0
for _ in $(seq 1 40); do
  blackhole_active="$(psql_in "$control_container" "SELECT count(*)::text FROM pg_stat_activity WHERE usename='$shared_role' AND state='active' AND query LIKE '%verifier_delay_probe%';")"
  [[ "$blackhole_active" -ge 1 ]] && break
  sleep 0.05
done
[[ "$blackhole_active" -ge 1 ]] || { echo "post-enrollment blackhole probe never became active" >&2; kill "$blackhole_pid" >/dev/null 2>&1 || true; wait "$blackhole_pid" >/dev/null 2>&1 || true; exit 1; }
sudo iptables -I "$blackhole_chain" 1 -s "$blackhole_control_ip" -d "$blackhole_clone_ip" -p tcp --sport 5432 -j DROP
blackhole_rule_installed=1
blackhole_rule_at="$(date +%s%3N)"
wait "$blackhole_pid"
blackhole_rc="$(cat "$tmpdir/blackhole.rc")"
sudo iptables -D "$blackhole_chain" -s "$blackhole_control_ip" -d "$blackhole_clone_ip" -p tcp --sport 5432 -j DROP
blackhole_rule_installed=0
blackhole_end="$(date +%s%3N)"
blackhole_ms=$((blackhole_end - blackhole_rule_at))
[[ "$blackhole_rc" == "0" ]] || { echo "post-enrollment blackhole exceeded outer watchdog rc=$blackhole_rc" >&2; cat "$tmpdir/blackhole.err" >&2 || true; exit 1; }
assert_exact "physical_pitr_post_enrollment_real_blackhole_fails_closed" "" "$(cat "$tmpdir/blackhole.out")"
[[ "$blackhole_ms" -lt 1800 ]] || { echo "post-enrollment real blackhole deadline not authoritative: ${blackhole_ms}ms" >&2; exit 1; }
printf 'physical_pitr_post_enrollment_real_blackhole_local_deadline=PASS elapsed_ms=%s\n' "$blackhole_ms"
printf '%s\n' 'physical_pitr_post_enrollment_timeout_backend_retirement=PASS one_shot_sql_session=true'

# Positive control proves this exact clone path is operational before the main
# negative; failure therefore means capability mismatch, not a broken RPC path.
assert_exact "physical_pitr_post_enrollment_clone_probe_claimed" "true" \
  "$(psql_in "$clone_container" "SELECT pitr_claim_external('$shared_conn','grant-post-enrollment-clone-probe')::text;")"
assert_exact "physical_pitr_post_enrollment_clone_probe_verify" "true" \
  "$(psql_in "$clone_container" "SELECT pitr_verify_external('$shared_conn','grant-post-enrollment-clone-probe')::text;")"
clone_probe_binding="$(psql_in "$control_container" "SELECT claimed_principal::text||'|'||claimed_instance_id::text||'|'||claimed_instance_fingerprint FROM pitr_postclone_evidence.recovery_grant WHERE grant_id='grant-post-enrollment-clone-probe';")"
clone_probe_principal="${clone_probe_binding%%|*}"; clone_probe_remaining="${clone_probe_binding#*|}"
clone_probe_id="${clone_probe_remaining%%|*}"; clone_probe_fp="${clone_probe_remaining#*|}"
assert_exact "physical_pitr_post_enrollment_clone_probe_principal_binding" "$shared_role" "$clone_probe_principal"
assert_exact "physical_pitr_post_enrollment_clone_probe_database_id_binding" "$clone_instance_id" "$clone_probe_id"
assert_exact "physical_pitr_post_enrollment_clone_probe_capability_binding" "$clone_local_fp" "$clone_probe_fp"
printf '%s\n' 'physical_pitr_post_enrollment_clone_capability_path_operational=PASS'

assert_exact "physical_pitr_post_enrollment_primary_claimed" "true" \
  "$(psql_in "$primary_container" "SELECT pitr_claim_external('$shared_conn','grant-post-enrollment-clone')::text;")"
assert_exact "physical_pitr_post_enrollment_same_instance_retry" "true" \
  "$(psql_in "$primary_container" "SELECT pitr_claim_external('$shared_conn','grant-post-enrollment-clone')::text;")"
assert_exact "physical_pitr_post_enrollment_pgdata_clone_claim_rejected" "false" \
  "$(psql_in "$clone_container" "SELECT pitr_claim_external('$shared_conn','grant-post-enrollment-clone')::text;")"
assert_exact "physical_pitr_post_enrollment_primary_verify" "true" \
  "$(psql_in "$primary_container" "SELECT pitr_verify_external('$shared_conn','grant-post-enrollment-clone')::text;")"
assert_exact "physical_pitr_post_enrollment_pgdata_clone_verify_rejected" "false" \
  "$(psql_in "$clone_container" "SELECT pitr_verify_external('$shared_conn','grant-post-enrollment-clone')::text;")"

claimed_binding="$(psql_in "$control_container" "SELECT claimed_principal::text||'|'||claimed_instance_id::text||'|'||claimed_instance_fingerprint FROM pitr_postclone_evidence.recovery_grant WHERE grant_id='grant-post-enrollment-clone';")"
claimed_principal="${claimed_binding%%|*}"; remaining="${claimed_binding#*|}"
claimed_id="${remaining%%|*}"; claimed_fp="${remaining#*|}"
assert_exact "physical_pitr_post_enrollment_authenticated_principal_binding" "$shared_role" "$claimed_principal"
assert_exact "physical_pitr_post_enrollment_copied_database_id_binding" "$primary_instance_id" "$claimed_id"
assert_exact "physical_pitr_post_enrollment_primary_capability_binding" "$primary_local_fp" "$claimed_fp"
printf '%s\n' 'physical_pitr_post_enrollment_pgdata_clone_cannot_duplicate_authority=PASS'
printf '%s\n' 'physical_pitr_post_enrollment_single_winner_external_capability=PASS'

unset primary_secret clone_secret shared_password shared_conn primary_local_fp clone_local_fp
