#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: physical_pitr_post_enrollment_clone.sh <external-control-container> <postgres-image>" >&2
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

cleanup() {
  docker rm -f "$primary_container" "$clone_container" >/dev/null 2>&1 || true
  sudo rm -rf "$tmpdir" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

wait_tcp() {
  local container="$1"
  local consecutive=0
  for _ in $(seq 1 160); do
    if docker exec -e PGPASSWORD="$password" "$container" \
      pg_isready -h 127.0.0.1 -U postgres -d jlmirror >/dev/null 2>&1; then
      consecutive=$((consecutive + 1))
      if [[ "$consecutive" -ge 3 ]]; then return 0; fi
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
  local container="$1"
  local sql="$2"
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

# The effective instance proof is deliberately outside PGDATA. This is C2
# falsification machinery for the authority boundary, not a production secret
# store or workload-identity selection.
primary_secret="$(openssl rand -hex 32)"
printf '%s\n' "$primary_secret" >"$tmpdir/primary.secret"
sudo chown "$pg_uid:$pg_gid" "$tmpdir/primary.secret"
sudo chmod 0400 "$tmpdir/primary.secret"

# Initialize one restored authority and enroll its database-visible identity.
# The secret itself is never inserted into the database.
docker run -d --name "$primary_container" \
  -e POSTGRES_PASSWORD="$password" -e POSTGRES_DB=jlmirror \
  -v "$tmpdir/primary-data:/var/lib/postgresql/data" \
  -v "$tmpdir/primary.secret:$secret_path:ro" \
  "$pg_image" >/dev/null
wait_tcp "$primary_container"

psql_in "$primary_container" "
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
  CREATE EXTENSION IF NOT EXISTS dblink;
  CREATE TABLE pitr_instance_identity (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    instance_id uuid NOT NULL,
    enrolled_at timestamptz NOT NULL DEFAULT clock_timestamp()
  );
  INSERT INTO pitr_instance_identity(singleton,instance_id)
  VALUES(true,gen_random_uuid());
  REVOKE ALL ON pitr_instance_identity FROM PUBLIC;

  CREATE OR REPLACE FUNCTION pitr_claim_external(p_conn text,p_grant_id text)
  RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
  SET search_path=pg_catalog,public
  AS \$\$
  DECLARE v_id uuid; v_secret text; v_result boolean;
  BEGIN
    SELECT instance_id INTO STRICT v_id
      FROM public.pitr_instance_identity WHERE singleton;
    v_secret := btrim(pg_catalog.pg_read_file('$secret_path'));
    IF v_secret = '' THEN RETURN false; END IF;
    SELECT ok INTO v_result
      FROM public.dblink(
        p_conn,
        format(
          'SELECT pitr_postclone_evidence.claim_grant(%L,%L::uuid,%L)::text',
          p_grant_id,v_id::text,v_secret
        )
      ) AS r(ok boolean);
    RETURN coalesce(v_result,false);
  EXCEPTION WHEN OTHERS THEN
    RETURN false;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_verify_external(p_conn text,p_grant_id text)
  RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
  SET search_path=pg_catalog,public
  AS \$\$
  DECLARE v_id uuid; v_secret text; v_result boolean;
  BEGIN
    SELECT instance_id INTO STRICT v_id
      FROM public.pitr_instance_identity WHERE singleton;
    v_secret := btrim(pg_catalog.pg_read_file('$secret_path'));
    IF v_secret = '' THEN RETURN false; END IF;
    SELECT ok INTO v_result
      FROM public.dblink(
        p_conn,
        format(
          'SELECT pitr_postclone_evidence.verify_grant(%L,%L::uuid,%L)::text',
          p_grant_id,v_id::text,v_secret
        )
      ) AS r(ok boolean);
    RETURN coalesce(v_result,false);
  EXCEPTION WHEN OTHERS THEN
    RETURN false;
  END;
  \$\$;

  REVOKE ALL ON FUNCTION pitr_claim_external(text,text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_verify_external(text,text) FROM PUBLIC;
" >/dev/null

primary_instance_id="$(psql_in "$primary_container" "SELECT instance_id::text FROM pitr_instance_identity WHERE singleton;")"
[[ -n "$primary_instance_id" ]] || { echo "missing enrolled primary instance id" >&2; exit 1; }

# Prove the effective secret is outside the database clone domain before taking
# the post-enrollment physical copy.
if sudo grep -R -a -F -- "$primary_secret" "$tmpdir/primary-data" >/dev/null 2>&1; then
  echo "external instance capability leaked into PGDATA before clone" >&2
  exit 1
fi
printf '%s\n' 'physical_pitr_post_enrollment_capability_outside_pgdata=PASS'

# Stop cleanly, then physically copy PGDATA *after* identity enrollment. The
# clone therefore inherits the exact same database identity and helper code.
docker stop "$primary_container" >/dev/null
sudo cp -a "$tmpdir/primary-data/." "$tmpdir/clone-data/"
sudo chown -R "$pg_uid:$pg_gid" "$tmpdir/clone-data"

# A new physical authority gets a different external-to-PGDATA capability. The
# clone receives the same database bytes and later the same external DB login,
# but it does not receive the primary's instance proof merely by copying PGDATA.
clone_secret="$(openssl rand -hex 32)"
[[ "$clone_secret" != "$primary_secret" ]] || { echo "instance secrets collided" >&2; exit 1; }
printf '%s\n' "$clone_secret" >"$tmpdir/clone.secret"
sudo chown "$pg_uid:$pg_gid" "$tmpdir/clone.secret"
sudo chmod 0400 "$tmpdir/clone.secret"

# Restart both physical copies from the same post-enrollment database state.
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

primary_secret_fp="$(printf '%s' "$primary_secret" | sha256sum | awk '{print $1}')"
clone_secret_fp="$(printf '%s' "$clone_secret" | sha256sum | awk '{print $1}')"
[[ "$primary_secret_fp" != "$clone_secret_fp" ]] || { echo "external instance capability fingerprints collided" >&2; exit 1; }
printf '%s\n' 'physical_pitr_post_enrollment_external_capability_distinct=PASS'

# Surviving external authority. Both physical copies intentionally authenticate
# with the exact same external role/password. Single-winner identity therefore
# depends on the external-to-PGDATA instance proof, not reusable DB credentials
# or copied database identity.
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
    CHECK (
      (claimed_principal IS NULL AND claimed_instance_id IS NULL
       AND claimed_instance_fingerprint IS NULL AND claimed_at IS NULL)
      OR
      (claimed_principal IS NOT NULL AND claimed_instance_id IS NOT NULL
       AND claimed_instance_fingerprint IS NOT NULL AND claimed_at IS NOT NULL)
    )
  );
  INSERT INTO pitr_postclone_evidence.recovery_grant(grant_id)
  VALUES('grant-post-enrollment-clone');
  REVOKE ALL ON pitr_postclone_evidence.recovery_grant FROM PUBLIC;

  CREATE OR REPLACE FUNCTION pitr_postclone_evidence.instance_fingerprint(p_secret text)
  RETURNS text LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog,public
  AS \$\$
    SELECT encode(public.digest(
      convert_to('open-rel-030-postclone-instance-v1:' || p_secret,'UTF8'),
      'sha256'
    ),'hex')
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_postclone_evidence.claim_grant(
    p_grant_id text,p_instance_id uuid,p_instance_secret text
  ) RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
  SET search_path=pg_catalog,pitr_postclone_evidence,public
  AS \$\$
  DECLARE
    v_grant pitr_postclone_evidence.recovery_grant%ROWTYPE;
    v_principal name := session_user;
    v_fingerprint text;
  BEGIN
    SELECT * INTO v_grant FROM pitr_postclone_evidence.recovery_grant
     WHERE grant_id=p_grant_id FOR UPDATE;
    IF NOT FOUND THEN RETURN false; END IF;
    v_fingerprint := pitr_postclone_evidence.instance_fingerprint(p_instance_secret);
    IF v_grant.claimed_principal IS NULL THEN
      UPDATE pitr_postclone_evidence.recovery_grant
         SET claimed_principal=v_principal,
             claimed_instance_id=p_instance_id,
             claimed_instance_fingerprint=v_fingerprint,
             claimed_at=clock_timestamp()
       WHERE grant_id=p_grant_id;
      RETURN true;
    END IF;
    RETURN v_grant.claimed_principal = v_principal
       AND v_grant.claimed_instance_id = p_instance_id
       AND v_grant.claimed_instance_fingerprint = v_fingerprint;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_postclone_evidence.verify_grant(
    p_grant_id text,p_instance_id uuid,p_instance_secret text
  ) RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
  SET search_path=pg_catalog,pitr_postclone_evidence,public
  AS \$\$
  DECLARE
    v_grant pitr_postclone_evidence.recovery_grant%ROWTYPE;
    v_principal name := session_user;
    v_fingerprint text;
  BEGIN
    SELECT * INTO v_grant FROM pitr_postclone_evidence.recovery_grant
     WHERE grant_id=p_grant_id;
    IF NOT FOUND THEN RETURN false; END IF;
    v_fingerprint := pitr_postclone_evidence.instance_fingerprint(p_instance_secret);
    RETURN v_grant.claimed_principal = v_principal
       AND v_grant.claimed_instance_id = p_instance_id
       AND v_grant.claimed_instance_fingerprint = v_fingerprint;
  END;
  \$\$;

  REVOKE ALL ON FUNCTION pitr_postclone_evidence.instance_fingerprint(text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_postclone_evidence.claim_grant(text,uuid,text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_postclone_evidence.verify_grant(text,uuid,text) FROM PUBLIC;

  CREATE ROLE $shared_role LOGIN PASSWORD '$shared_password';
  GRANT USAGE ON SCHEMA pitr_postclone_evidence TO $shared_role;
  GRANT EXECUTE ON FUNCTION pitr_postclone_evidence.claim_grant(text,uuid,text) TO $shared_role;
  GRANT EXECUTE ON FUNCTION pitr_postclone_evidence.verify_grant(text,uuid,text) TO $shared_role;
" >/dev/null

control_ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$control_container")"
[[ -n "$control_ip" ]] || { echo "cannot resolve control IP" >&2; exit 1; }
shared_conn="hostaddr=$control_ip port=5432 dbname=jlmirror user=$shared_role password=$shared_password connect_timeout=2"

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
claimed_principal="${claimed_binding%%|*}"
remaining="${claimed_binding#*|}"
claimed_id="${remaining%%|*}"
claimed_fp="${remaining#*|}"
assert_exact "physical_pitr_post_enrollment_authenticated_principal_binding" "$shared_role" "$claimed_principal"
assert_exact "physical_pitr_post_enrollment_copied_database_id_binding" "$primary_instance_id" "$claimed_id"
[[ -n "$claimed_fp" ]] || { echo "missing post-enrollment claimed fingerprint" >&2; exit 1; }

# The clone copied the same PGDATA identity and reused the same external DB
# credential, yet was rejected because copying PGDATA did not copy the effective
# instance authority. This is the precise C2 invariant the production mechanism
# must preserve with a non-shareable workload/TPM/TEE/KMS-backed equivalent.
printf '%s\n' 'physical_pitr_post_enrollment_pgdata_clone_cannot_duplicate_authority=PASS'
printf '%s\n' 'physical_pitr_post_enrollment_single_winner_external_capability=PASS'

unset primary_secret clone_secret shared_password shared_conn
