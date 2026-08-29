#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: physical_pitr.sh <external-control-container> <postgres-image>" >&2
  exit 2
fi

control_container="$1"
pg_image="$2"
password="evidence"
source_container="jlmirror-open-rel-030-pitr-source"
restored_container="jlmirror-open-rel-030-pitr-restored"
clone_container="jlmirror-open-rel-030-pitr-restored-clone"
tmpdir="$(mktemp -d)"
recovery_nonce="$(openssl rand -hex 16)"
recovery_duplicate_nonce="$(openssl rand -hex 16)"
race_nonce_a="$(openssl rand -hex 16)"
race_nonce_b="$(openssl rand -hex 16)"
required_receipt='effect|after-r'
race_receipt='effect|race'

primary_role="pitr_restore_primary"
rival_role="pitr_restore_rival"
race_a_role="pitr_restore_race_a"
race_b_role="pitr_restore_race_b"

cleanup() {
  docker rm -f "$source_container" "$restored_container" "$clone_container" >/dev/null 2>&1 || true
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
  echo "PITR database TCP path did not become ready: $container" >&2
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

# ---------------------------------------------------------------------------
# Surviving recovery authority.
#
# Authority is keyed by the governed recovery boundary, not by arbitrary grant
# id. Grants bind to authenticated surviving effect evidence. A grant claim is
# single-winner across all grant ids for the same boundary and retry is accepted
# only for the same authenticated principal + restored-instance capability.
# ---------------------------------------------------------------------------
psql_in "$control_container" "
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
  DROP SCHEMA IF EXISTS pitr_external_evidence CASCADE;
  DROP ROLE IF EXISTS $primary_role;
  DROP ROLE IF EXISTS $rival_role;
  DROP ROLE IF EXISTS $race_a_role;
  DROP ROLE IF EXISTS $race_b_role;
  CREATE SCHEMA pitr_external_evidence;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.canonical_field(p_value text)
  RETURNS text LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog
  AS \$\$
    SELECT octet_length(convert_to(p_value,'UTF8'))::text || ':' ||
           encode(convert_to(p_value,'UTF8'),'hex')
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.canonical_boundary(
    p_domain text,p_boundary_r text,p_boundary_f text,p_successor_epoch bigint,
    p_placement_version bigint,p_required_receipt text
  ) RETURNS text LANGUAGE sql IMMUTABLE STRICT
  SET search_path=pg_catalog,pitr_external_evidence
  AS \$\$
    SELECT pitr_external_evidence.canonical_field(p_domain) ||
           pitr_external_evidence.canonical_field(p_boundary_r) ||
           pitr_external_evidence.canonical_field(p_boundary_f) ||
           pitr_external_evidence.canonical_field(p_successor_epoch::text) ||
           pitr_external_evidence.canonical_field(p_placement_version::text) ||
           pitr_external_evidence.canonical_field(p_required_receipt)
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.boundary_fingerprint(
    p_domain text,p_boundary_r text,p_boundary_f text,p_successor_epoch bigint,
    p_placement_version bigint,p_required_receipt text
  ) RETURNS text LANGUAGE sql IMMUTABLE STRICT
  SET search_path=pg_catalog,pitr_external_evidence,public
  AS \$\$
    SELECT encode(public.digest(convert_to(
      pitr_external_evidence.canonical_boundary(
        p_domain,p_boundary_r,p_boundary_f,p_successor_epoch,
        p_placement_version,p_required_receipt
      ),'UTF8'),'sha256'),'hex')
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.canonical_effect(
    p_domain text,p_boundary_r text,p_boundary_f text,p_business_state text,
    p_source_poll_generation bigint,p_required_receipt text
  ) RETURNS text LANGUAGE sql IMMUTABLE STRICT
  SET search_path=pg_catalog,pitr_external_evidence
  AS \$\$
    SELECT pitr_external_evidence.canonical_field(p_domain) ||
           pitr_external_evidence.canonical_field(p_boundary_r) ||
           pitr_external_evidence.canonical_field(p_boundary_f) ||
           pitr_external_evidence.canonical_field(p_business_state) ||
           pitr_external_evidence.canonical_field(p_source_poll_generation::text) ||
           pitr_external_evidence.canonical_field(p_required_receipt)
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.canonical_grant(
    p_domain text,p_boundary_r text,p_boundary_f text,p_successor_epoch bigint,
    p_placement_version bigint,p_required_receipt text,p_effect_digest text,p_nonce text
  ) RETURNS text LANGUAGE sql IMMUTABLE STRICT
  SET search_path=pg_catalog,pitr_external_evidence
  AS \$\$
    SELECT pitr_external_evidence.canonical_boundary(
             p_domain,p_boundary_r,p_boundary_f,p_successor_epoch,
             p_placement_version,p_required_receipt
           ) ||
           pitr_external_evidence.canonical_field(p_effect_digest) ||
           pitr_external_evidence.canonical_field(p_nonce)
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.instance_fingerprint(p_secret text)
  RETURNS text LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog,public
  AS \$\$
    SELECT encode(public.digest(
      convert_to('open-rel-030-recovery-instance-v1:' || p_secret,'UTF8'),
      'sha256'
    ),'hex')
  \$\$;

  CREATE TABLE pitr_external_evidence.authority (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    boundary_r text NOT NULL,
    boundary_f text NOT NULL,
    expected_successor_epoch bigint NOT NULL,
    expected_placement_version bigint NOT NULL,
    required_receipt text NOT NULL
  );
  INSERT INTO pitr_external_evidence.authority
    (singleton,boundary_r,boundary_f,expected_successor_epoch,expected_placement_version,required_receipt)
  VALUES (true,'R','F',6,8,'$required_receipt');

  CREATE TABLE pitr_external_evidence.signing_key (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    key_material text NOT NULL
  );
  INSERT INTO pitr_external_evidence.signing_key(singleton,key_material)
  SELECT true,encode(gen_random_bytes(32),'hex');
  REVOKE ALL ON pitr_external_evidence.signing_key FROM PUBLIC;

  CREATE TABLE pitr_external_evidence.recovery_effect (
    effect_digest text PRIMARY KEY,
    domain text NOT NULL,
    boundary_r text NOT NULL,
    boundary_f text NOT NULL,
    business_state text NOT NULL,
    source_poll_generation bigint NOT NULL,
    required_receipt text NOT NULL,
    canonical_payload text NOT NULL,
    attestation text NOT NULL,
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(domain,boundary_r,boundary_f,required_receipt)
  );
  REVOKE ALL ON pitr_external_evidence.recovery_effect FROM PUBLIC;

  CREATE TABLE pitr_external_evidence.recovery_grant (
    grant_id text PRIMARY KEY,
    domain text NOT NULL,
    boundary_r text NOT NULL,
    boundary_f text NOT NULL,
    successor_epoch bigint NOT NULL,
    placement_version bigint NOT NULL,
    required_receipt text NOT NULL,
    effect_digest text NOT NULL,
    nonce text NOT NULL,
    canonical_payload text NOT NULL,
    attestation text NOT NULL,
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    claimed_principal name,
    claimed_instance_id uuid,
    claimed_instance_fingerprint text,
    claimed_at timestamptz
  );
  REVOKE ALL ON pitr_external_evidence.recovery_grant FROM PUBLIC;

  CREATE TABLE pitr_external_evidence.recovery_boundary_claim (
    boundary_fingerprint text PRIMARY KEY,
    domain text NOT NULL,
    boundary_r text NOT NULL,
    boundary_f text NOT NULL,
    successor_epoch bigint NOT NULL,
    placement_version bigint NOT NULL,
    required_receipt text NOT NULL,
    effect_digest text NOT NULL,
    winning_grant_id text NOT NULL,
    claimed_principal name NOT NULL,
    claimed_instance_id uuid NOT NULL,
    claimed_instance_fingerprint text NOT NULL,
    claimed_at timestamptz NOT NULL DEFAULT clock_timestamp()
  );
  REVOKE ALL ON pitr_external_evidence.recovery_boundary_claim FROM PUBLIC;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.stored_effect_is_valid(p_effect_digest text)
  RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
  SET search_path=pg_catalog,pitr_external_evidence,public
  AS \$\$
  DECLARE v_key text; v_effect pitr_external_evidence.recovery_effect%ROWTYPE;
          v_canonical text; v_digest text; v_expected text;
  BEGIN
    SELECT * INTO v_effect FROM pitr_external_evidence.recovery_effect
     WHERE effect_digest=p_effect_digest;
    IF NOT FOUND THEN RETURN false; END IF;
    v_canonical := pitr_external_evidence.canonical_effect(
      v_effect.domain,v_effect.boundary_r,v_effect.boundary_f,
      v_effect.business_state,v_effect.source_poll_generation,v_effect.required_receipt
    );
    v_digest := encode(public.digest(convert_to(v_canonical,'UTF8'),'sha256'),'hex');
    IF v_effect.canonical_payload IS DISTINCT FROM v_canonical
       OR v_effect.effect_digest IS DISTINCT FROM v_digest THEN RETURN false; END IF;
    SELECT key_material INTO STRICT v_key FROM pitr_external_evidence.signing_key WHERE singleton;
    v_expected := encode(public.hmac(convert_to(v_canonical,'UTF8'),decode(v_key,'hex'),'sha256'),'hex');
    RETURN v_expected = v_effect.attestation;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.stored_grant_is_valid(p_grant_id text)
  RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
  SET search_path=pg_catalog,pitr_external_evidence,public
  AS \$\$
  DECLARE v_key text; v_grant pitr_external_evidence.recovery_grant%ROWTYPE;
          v_effect pitr_external_evidence.recovery_effect%ROWTYPE;
          v_canonical text; v_expected text;
  BEGIN
    SELECT * INTO v_grant FROM pitr_external_evidence.recovery_grant WHERE grant_id=p_grant_id;
    IF NOT FOUND OR NOT pitr_external_evidence.stored_effect_is_valid(v_grant.effect_digest) THEN
      RETURN false;
    END IF;
    SELECT * INTO STRICT v_effect FROM pitr_external_evidence.recovery_effect
     WHERE effect_digest=v_grant.effect_digest;
    IF v_effect.domain IS DISTINCT FROM v_grant.domain
       OR v_effect.boundary_r IS DISTINCT FROM v_grant.boundary_r
       OR v_effect.boundary_f IS DISTINCT FROM v_grant.boundary_f
       OR v_effect.required_receipt IS DISTINCT FROM v_grant.required_receipt THEN
      RETURN false;
    END IF;
    v_canonical := pitr_external_evidence.canonical_grant(
      v_grant.domain,v_grant.boundary_r,v_grant.boundary_f,
      v_grant.successor_epoch,v_grant.placement_version,v_grant.required_receipt,
      v_grant.effect_digest,v_grant.nonce
    );
    IF v_grant.canonical_payload IS DISTINCT FROM v_canonical THEN RETURN false; END IF;
    SELECT key_material INTO STRICT v_key FROM pitr_external_evidence.signing_key WHERE singleton;
    v_expected := encode(public.hmac(convert_to(v_canonical,'UTF8'),decode(v_key,'hex'),'sha256'),'hex');
    RETURN v_expected = v_grant.attestation;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.claim_grant(
    p_grant_id text,p_instance_id uuid,p_instance_secret text
  ) RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
  SET search_path=pg_catalog,pitr_external_evidence,public
  AS \$\$
  DECLARE v_grant pitr_external_evidence.recovery_grant%ROWTYPE;
          v_claim pitr_external_evidence.recovery_boundary_claim%ROWTYPE;
          v_principal name := session_user; v_instance_fp text; v_boundary_fp text;
  BEGIN
    SELECT * INTO v_grant FROM pitr_external_evidence.recovery_grant
     WHERE grant_id=p_grant_id FOR UPDATE;
    IF NOT FOUND OR NOT pitr_external_evidence.stored_grant_is_valid(p_grant_id) THEN
      RETURN false;
    END IF;
    v_instance_fp := pitr_external_evidence.instance_fingerprint(p_instance_secret);
    v_boundary_fp := pitr_external_evidence.boundary_fingerprint(
      v_grant.domain,v_grant.boundary_r,v_grant.boundary_f,
      v_grant.successor_epoch,v_grant.placement_version,v_grant.required_receipt
    );

    INSERT INTO pitr_external_evidence.recovery_boundary_claim(
      boundary_fingerprint,domain,boundary_r,boundary_f,successor_epoch,
      placement_version,required_receipt,effect_digest,winning_grant_id,
      claimed_principal,claimed_instance_id,claimed_instance_fingerprint
    ) VALUES (
      v_boundary_fp,v_grant.domain,v_grant.boundary_r,v_grant.boundary_f,
      v_grant.successor_epoch,v_grant.placement_version,v_grant.required_receipt,
      v_grant.effect_digest,v_grant.grant_id,v_principal,p_instance_id,v_instance_fp
    ) ON CONFLICT(boundary_fingerprint) DO NOTHING;

    SELECT * INTO STRICT v_claim FROM pitr_external_evidence.recovery_boundary_claim
     WHERE boundary_fingerprint=v_boundary_fp FOR UPDATE;

    IF v_claim.claimed_principal IS DISTINCT FROM v_principal
       OR v_claim.claimed_instance_id IS DISTINCT FROM p_instance_id
       OR v_claim.claimed_instance_fingerprint IS DISTINCT FROM v_instance_fp
       OR v_claim.effect_digest IS DISTINCT FROM v_grant.effect_digest THEN
      RETURN false;
    END IF;

    UPDATE pitr_external_evidence.recovery_grant
       SET claimed_principal=v_principal,claimed_instance_id=p_instance_id,
           claimed_instance_fingerprint=v_instance_fp,
           claimed_at=coalesce(claimed_at,clock_timestamp())
     WHERE grant_id=p_grant_id
       AND (claimed_principal IS NULL OR
            (claimed_principal=v_principal AND claimed_instance_id=p_instance_id
             AND claimed_instance_fingerprint=v_instance_fp));
    RETURN true;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.verify_claimed_grant(
    p_grant_id text,p_instance_id uuid,p_instance_secret text
  ) RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
  SET search_path=pg_catalog,pitr_external_evidence,public
  AS \$\$
  DECLARE v_grant pitr_external_evidence.recovery_grant%ROWTYPE;
          v_claim pitr_external_evidence.recovery_boundary_claim%ROWTYPE;
          v_principal name := session_user; v_instance_fp text; v_boundary_fp text;
  BEGIN
    SELECT * INTO v_grant FROM pitr_external_evidence.recovery_grant WHERE grant_id=p_grant_id;
    IF NOT FOUND OR NOT pitr_external_evidence.stored_grant_is_valid(p_grant_id) THEN RETURN false; END IF;
    v_instance_fp := pitr_external_evidence.instance_fingerprint(p_instance_secret);
    v_boundary_fp := pitr_external_evidence.boundary_fingerprint(
      v_grant.domain,v_grant.boundary_r,v_grant.boundary_f,
      v_grant.successor_epoch,v_grant.placement_version,v_grant.required_receipt
    );
    SELECT * INTO v_claim FROM pitr_external_evidence.recovery_boundary_claim
     WHERE boundary_fingerprint=v_boundary_fp;
    IF NOT FOUND THEN RETURN false; END IF;
    RETURN v_claim.claimed_principal = v_principal
       AND v_claim.claimed_instance_id = p_instance_id
       AND v_claim.claimed_instance_fingerprint = v_instance_fp
       AND v_claim.effect_digest = v_grant.effect_digest;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.fetch_claimed_recovery_material(
    p_grant_id text,p_instance_id uuid,p_instance_secret text
  ) RETURNS text LANGUAGE plpgsql STRICT SECURITY DEFINER
  SET search_path=pg_catalog,pitr_external_evidence
  AS \$\$
  DECLARE v_grant pitr_external_evidence.recovery_grant%ROWTYPE;
          v_effect pitr_external_evidence.recovery_effect%ROWTYPE;
          v_claim pitr_external_evidence.recovery_boundary_claim%ROWTYPE;
          v_boundary_fp text;
  BEGIN
    IF NOT pitr_external_evidence.verify_claimed_grant(p_grant_id,p_instance_id,p_instance_secret) THEN
      RETURN NULL;
    END IF;
    SELECT * INTO STRICT v_grant FROM pitr_external_evidence.recovery_grant WHERE grant_id=p_grant_id;
    SELECT * INTO STRICT v_effect FROM pitr_external_evidence.recovery_effect WHERE effect_digest=v_grant.effect_digest;
    v_boundary_fp := pitr_external_evidence.boundary_fingerprint(
      v_grant.domain,v_grant.boundary_r,v_grant.boundary_f,
      v_grant.successor_epoch,v_grant.placement_version,v_grant.required_receipt
    );
    SELECT * INTO STRICT v_claim FROM pitr_external_evidence.recovery_boundary_claim
     WHERE boundary_fingerprint=v_boundary_fp;
    RETURN jsonb_build_object(
      'domain',v_grant.domain,'boundary_r',v_grant.boundary_r,'boundary_f',v_grant.boundary_f,
      'successor_epoch',v_grant.successor_epoch,'placement_version',v_grant.placement_version,
      'required_receipt',v_grant.required_receipt,'business_state',v_effect.business_state,
      'source_poll_generation',v_effect.source_poll_generation,'effect_digest',v_effect.effect_digest,
      'canonical_grant',v_grant.canonical_payload,'claimed_principal',v_claim.claimed_principal::text,
      'claimed_instance_id',v_claim.claimed_instance_id::text,
      'claimed_instance_fingerprint',v_claim.claimed_instance_fingerprint
    )::text;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.verifier_delay_probe()
  RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog
  AS \$\$ BEGIN PERFORM pg_catalog.pg_sleep(5); RETURN true; END; \$\$;

  REVOKE ALL ON ALL TABLES IN SCHEMA pitr_external_evidence FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_external_evidence.stored_effect_is_valid(text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_external_evidence.stored_grant_is_valid(text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_external_evidence.instance_fingerprint(text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_external_evidence.claim_grant(text,uuid,text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_external_evidence.verify_claimed_grant(text,uuid,text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_external_evidence.fetch_claimed_recovery_material(text,uuid,text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_external_evidence.verifier_delay_probe() FROM PUBLIC;
" >/dev/null

if [[ ${recovery_key+x} == x ]]; then
  echo "controller retained a recovery_key variable" >&2
  exit 1
fi
printf '%s\n' 'physical_pitr_controller_does_not_retain_recovery_signing_key=PASS'

legacy_probe="$(psql_in "$control_container" "
  SELECT (('domain'||'|'||'R|F'||'|'||'tail')=('domain|R'||'|'||'F'||'|'||'tail'))::text || '|' ||
         (pitr_external_evidence.canonical_field('domain')||
          pitr_external_evidence.canonical_field('R|F')||
          pitr_external_evidence.canonical_field('tail') <>
          pitr_external_evidence.canonical_field('domain|R')||
          pitr_external_evidence.canonical_field('F')||
          pitr_external_evidence.canonical_field('tail'))::text;
")"
assert_exact "physical_pitr_grant_delimiter_collision_closed" "true|true" "$legacy_probe"

# ---------------------------------------------------------------------------
# Build committed R, then a real post-R business effect and F.
# ---------------------------------------------------------------------------
docker run -d --name "$source_container" \
  -e POSTGRES_PASSWORD="$password" -e POSTGRES_DB=jlmirror "$pg_image" \
  postgres -c wal_level=replica -c archive_mode=on \
  -c "archive_command=mkdir -p /tmp/wal_archive && test ! -f /tmp/wal_archive/%f && cp %p /tmp/wal_archive/%f" >/dev/null
wait_tcp "$source_container"

psql_in "$source_container" "
  CREATE TABLE pitr_local_state (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    business_state text NOT NULL,poll_epoch bigint NOT NULL,poll_generation bigint NOT NULL,
    placement_version bigint NOT NULL,reconciled_through_f boolean NOT NULL DEFAULT false,
    external_grant_id text,external_grant_fingerprint text,external_effect_digest text,
    external_grant_principal text,external_grant_instance_id uuid,
    external_grant_instance_fingerprint text
  );
  CREATE TABLE pitr_continuity_receipt(receipt_id text PRIMARY KEY);
  INSERT INTO pitr_local_state(singleton,business_state,poll_epoch,poll_generation,placement_version)
  VALUES(true,'pre_R',4,9,7);
" >/dev/null

docker exec -u postgres -e PGPASSWORD="$password" "$source_container" \
  sh -c 'rm -rf /tmp/basebackup && pg_basebackup -h 127.0.0.1 -U postgres -D /tmp/basebackup -Fp -Xs -P' >/dev/null

psql_in "$source_container" "UPDATE pitr_local_state SET business_state='state_at_R',poll_epoch=5,poll_generation=10 WHERE singleton;" >/dev/null
assert_exact "physical_pitr_R_transaction_committed" "state_at_R|5|10" \
  "$(psql_in "$source_container" "SELECT business_state||'|'||poll_epoch||'|'||poll_generation FROM pitr_local_state WHERE singleton;")"
r_lsn="$(psql_in "$source_container" "SELECT pg_create_restore_point('jlmirror_R');")"

psql_in "$source_container" "
  UPDATE pitr_local_state SET business_state='post_R_business_change',poll_generation=11 WHERE singleton;
  INSERT INTO pitr_continuity_receipt(receipt_id) VALUES('$required_receipt');
" >/dev/null
assert_exact "physical_pitr_F_transaction_committed" "post_R_business_change|11|1" \
  "$(psql_in "$source_container" "SELECT business_state||'|'||poll_generation||'|'||(SELECT count(*) FROM pitr_continuity_receipt) FROM pitr_local_state WHERE singleton;")"
f_lsn="$(psql_in "$source_container" "SELECT pg_create_restore_point('jlmirror_F');")"
[[ "$r_lsn" != "$f_lsn" ]] || { echo "PITR R and F share LSN" >&2; exit 1; }
printf 'physical_pitr_restore_points=PASS R=%s F=%s\n' "$r_lsn" "$f_lsn"
source_effect_business_state="$(psql_in "$source_container" "SELECT business_state FROM pitr_local_state WHERE singleton;")"
source_effect_generation="$(psql_in "$source_container" "SELECT poll_generation::text FROM pitr_local_state WHERE singleton;")"
source_effect_receipt="$(psql_in "$source_container" "SELECT receipt_id FROM pitr_continuity_receipt WHERE receipt_id='$required_receipt';")"
assert_exact "physical_pitr_surviving_effect_source_state" "post_R_business_change|11|$required_receipt" "$source_effect_business_state|$source_effect_generation|$source_effect_receipt"

# Publish authenticated surviving effect evidence after F, then issue two valid
# grant ids for the same boundary to prove grant-id multiplicity cannot create
# multiple authorities. A second synthetic boundary is used for a cross-grant
# concurrent race without consuming the primary boundary.
psql_in "$control_container" "
  WITH c AS (
    SELECT 'open-rel-030-recovery-v1'::text domain,'R'::text boundary_r,'F'::text boundary_f,
           '$source_effect_business_state'::text business_state,$source_effect_generation::bigint source_poll_generation,
           '$source_effect_receipt'::text required_receipt,
           pitr_external_evidence.canonical_effect(
             'open-rel-030-recovery-v1','R','F','$source_effect_business_state',$source_effect_generation,'$source_effect_receipt'
           ) canonical_payload
  ), d AS (
    SELECT c.*,encode(public.digest(convert_to(canonical_payload,'UTF8'),'sha256'),'hex') effect_digest FROM c
  )
  INSERT INTO pitr_external_evidence.recovery_effect(
    effect_digest,domain,boundary_r,boundary_f,business_state,source_poll_generation,
    required_receipt,canonical_payload,attestation
  )
  SELECT d.effect_digest,d.domain,d.boundary_r,d.boundary_f,d.business_state,d.source_poll_generation,
         d.required_receipt,d.canonical_payload,
         encode(public.hmac(convert_to(d.canonical_payload,'UTF8'),decode(k.key_material,'hex'),'sha256'),'hex')
    FROM d CROSS JOIN pitr_external_evidence.signing_key k WHERE k.singleton;

  WITH c AS (
    SELECT 'open-rel-030-recovery-v1'::text domain,'R-race'::text boundary_r,'F-race'::text boundary_f,
           'race-effect'::text business_state,111::bigint source_poll_generation,
           '$race_receipt'::text required_receipt,
           pitr_external_evidence.canonical_effect(
             'open-rel-030-recovery-v1','R-race','F-race','race-effect',111,'$race_receipt'
           ) canonical_payload
  ), d AS (
    SELECT c.*,encode(public.digest(convert_to(canonical_payload,'UTF8'),'sha256'),'hex') effect_digest FROM c
  )
  INSERT INTO pitr_external_evidence.recovery_effect(
    effect_digest,domain,boundary_r,boundary_f,business_state,source_poll_generation,
    required_receipt,canonical_payload,attestation
  )
  SELECT d.effect_digest,d.domain,d.boundary_r,d.boundary_f,d.business_state,d.source_poll_generation,
         d.required_receipt,d.canonical_payload,
         encode(public.hmac(convert_to(d.canonical_payload,'UTF8'),decode(k.key_material,'hex'),'sha256'),'hex')
    FROM d CROSS JOIN pitr_external_evidence.signing_key k WHERE k.singleton;

  WITH facts(grant_id,domain,boundary_r,boundary_f,successor_epoch,placement_version,required_receipt,effect_digest,nonce) AS (
    SELECT 'grant-F-1','open-rel-030-recovery-v1','R','F',6,8,'$required_receipt',effect_digest,'$recovery_nonce'
      FROM pitr_external_evidence.recovery_effect WHERE boundary_r='R' AND boundary_f='F'
    UNION ALL
    SELECT 'grant-F-duplicate','open-rel-030-recovery-v1','R','F',6,8,'$required_receipt',effect_digest,'$recovery_duplicate_nonce'
      FROM pitr_external_evidence.recovery_effect WHERE boundary_r='R' AND boundary_f='F'
    UNION ALL
    SELECT 'grant-race-a','open-rel-030-recovery-v1','R-race','F-race',106,108,'$race_receipt',effect_digest,'$race_nonce_a'
      FROM pitr_external_evidence.recovery_effect WHERE boundary_r='R-race' AND boundary_f='F-race'
    UNION ALL
    SELECT 'grant-race-b','open-rel-030-recovery-v1','R-race','F-race',106,108,'$race_receipt',effect_digest,'$race_nonce_b'
      FROM pitr_external_evidence.recovery_effect WHERE boundary_r='R-race' AND boundary_f='F-race'
  ), c AS (
    SELECT f.*,pitr_external_evidence.canonical_grant(
      domain,boundary_r,boundary_f,successor_epoch,placement_version,required_receipt,effect_digest,nonce
    ) canonical_payload FROM facts f
  )
  INSERT INTO pitr_external_evidence.recovery_grant(
    grant_id,domain,boundary_r,boundary_f,successor_epoch,placement_version,
    required_receipt,effect_digest,nonce,canonical_payload,attestation
  )
  SELECT c.grant_id,c.domain,c.boundary_r,c.boundary_f,c.successor_epoch,c.placement_version,
         c.required_receipt,c.effect_digest,c.nonce,c.canonical_payload,
         encode(public.hmac(convert_to(c.canonical_payload,'UTF8'),decode(k.key_material,'hex'),'sha256'),'hex')
    FROM c CROSS JOIN pitr_external_evidence.signing_key k WHERE k.singleton;

  INSERT INTO pitr_external_evidence.recovery_grant(
    grant_id,domain,boundary_r,boundary_f,successor_epoch,placement_version,
    required_receipt,effect_digest,nonce,canonical_payload,attestation
  )
  SELECT 'grant-F-tampered',domain,boundary_r,boundary_f,successor_epoch,placement_version,
         required_receipt,effect_digest,nonce||'-tampered',
         pitr_external_evidence.canonical_grant(
           domain,boundary_r,boundary_f,successor_epoch,placement_version,
           required_receipt,effect_digest,nonce||'-tampered'
         ),repeat('0',64)
    FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';
" >/dev/null

main_effect_digest="$(psql_in "$control_container" "SELECT effect_digest FROM pitr_external_evidence.recovery_effect WHERE boundary_r='R' AND boundary_f='F';")"
[[ -n "$main_effect_digest" ]] || { echo "missing surviving effect digest" >&2; exit 1; }
printf '%s\n' 'physical_pitr_surviving_effect_evidence_published=PASS'
assert_exact "physical_pitr_grant_receipt_contains_pipe" "$required_receipt" \
  "$(psql_in "$control_container" "SELECT required_receipt FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
assert_exact "physical_pitr_duplicate_grants_same_boundary" "1" \
  "$(psql_in "$control_container" "SELECT (count(DISTINCT pitr_external_evidence.boundary_fingerprint(domain,boundary_r,boundary_f,successor_epoch,placement_version,required_receipt)))::text FROM pitr_external_evidence.recovery_grant WHERE grant_id IN ('grant-F-1','grant-F-duplicate');")"

# Complete WAL archiving and restore two physical copies to exact R.
docker exec -e PGPASSWORD="$password" "$source_container" psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c "SELECT pg_switch_wal(); CHECKPOINT; SELECT pg_switch_wal();" >/dev/null
for _ in $(seq 1 80); do
  archived_count="$(psql_in "$source_container" "SELECT archived_count FROM pg_stat_archiver;")"
  failed_count="$(psql_in "$source_container" "SELECT failed_count FROM pg_stat_archiver;")"
  [[ "$failed_count" == "0" ]] || { echo "PITR archive failures=$failed_count" >&2; exit 1; }
  [[ "$archived_count" -ge 2 ]] && break
  sleep 0.25
done
[[ "${archived_count:-0}" -ge 2 ]] || { echo "PITR archive incomplete" >&2; exit 1; }
printf 'physical_pitr_archive=PASS archived_count=%s\n' "$archived_count"

mkdir -p "$tmpdir/base" "$tmpdir/clone_base" "$tmpdir/archive"
docker cp "$source_container:/tmp/basebackup/." "$tmpdir/base/"
docker cp "$source_container:/tmp/wal_archive/." "$tmpdir/archive/"
[[ -n "$(find "$tmpdir/archive" -type f -print -quit)" ]] || { echo "PITR archive copy empty" >&2; exit 1; }
docker stop "$source_container" >/dev/null
pg_uid="$(docker run --rm --entrypoint sh "$pg_image" -c 'id -u postgres')"
pg_gid="$(docker run --rm --entrypoint sh "$pg_image" -c 'id -g postgres')"
sudo tee -a "$tmpdir/base/postgresql.auto.conf" >/dev/null <<'RECOVERY'
restore_command = 'cp /archive/%f %p'
recovery_target_name = 'jlmirror_R'
recovery_target_action = 'promote'
recovery_target_timeline = 'current'
RECOVERY
sudo touch "$tmpdir/base/recovery.signal"
sudo cp -a "$tmpdir/base/." "$tmpdir/clone_base/"
sudo chown -R "$pg_uid:$pg_gid" "$tmpdir/base" "$tmpdir/clone_base" "$tmpdir/archive"

docker run -d --name "$restored_container" -v "$tmpdir/base:/var/lib/postgresql/data" -v "$tmpdir/archive:/archive:ro" "$pg_image" >/dev/null
docker run -d --name "$clone_container" -v "$tmpdir/clone_base:/var/lib/postgresql/data" -v "$tmpdir/archive:/archive:ro" "$pg_image" >/dev/null
wait_tcp "$restored_container"
wait_tcp "$clone_container"
assert_exact "physical_pitr_promoted_at_R" "false" "$(psql_in "$restored_container" "SELECT pg_is_in_recovery()::text;")"
assert_exact "physical_pitr_clone_promoted_at_R" "false" "$(psql_in "$clone_container" "SELECT pg_is_in_recovery()::text;")"
assert_exact "physical_pitr_exact_R_state" "state_at_R|5|10|7|false|0|" \
  "$(psql_in "$restored_container" "SELECT business_state||'|'||poll_epoch||'|'||poll_generation||'|'||placement_version||'|'||reconciled_through_f::text||'|'||(SELECT count(*) FROM pitr_continuity_receipt)||'|'||coalesce(external_grant_id,'') FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_clone_exact_R_state" "state_at_R|5|10|7|false|0|" \
  "$(psql_in "$clone_container" "SELECT business_state||'|'||poll_epoch||'|'||poll_generation||'|'||placement_version||'|'||reconciled_through_f::text||'|'||(SELECT count(*) FROM pitr_continuity_receipt)||'|'||coalesce(external_grant_id,'') FROM pitr_local_state WHERE singleton;")"

# ---------------------------------------------------------------------------
# Restored-instance capability + bounded local cross-authority transport.
# All claim/verify/material-fetch helpers share the same async dblink primitive;
# connect_timeout bounds setup and caller-local polling bounds response time.
# ---------------------------------------------------------------------------
for c in "$restored_container" "$clone_container"; do
  psql_in "$c" "
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    CREATE EXTENSION IF NOT EXISTS dblink;
    CREATE TABLE pitr_recovery_instance(
      singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),instance_id uuid NOT NULL,
      instance_secret text NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp()
    );
    INSERT INTO pitr_recovery_instance(singleton,instance_id,instance_secret)
    SELECT true,gen_random_uuid(),encode(gen_random_bytes(32),'hex');
    REVOKE ALL ON pitr_recovery_instance FROM PUBLIC;

    CREATE OR REPLACE FUNCTION pitr_local_canonical_field(p_value text)
    RETURNS text LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog
    AS \$\$ SELECT octet_length(convert_to(p_value,'UTF8'))::text || ':' || encode(convert_to(p_value,'UTF8'),'hex') \$\$;

    CREATE OR REPLACE FUNCTION pitr_bounded_remote_text(p_conn text,p_sql text,p_timeout_ms integer)
    RETURNS text LANGUAGE plpgsql STRICT SECURITY DEFINER SET search_path=pg_catalog,public
    AS \$\$
    DECLARE v_name text; v_deadline timestamptz; v_value text;
    BEGIN
      IF p_timeout_ms < 50 OR p_timeout_ms > 5000 THEN RETURN NULL; END IF;
      v_name := 'or030_recovery_' || pg_backend_pid()::text || '_' || substr(md5(clock_timestamp()::text || random()::text),1,12);
      v_deadline := clock_timestamp() + (p_timeout_ms::text || ' milliseconds')::interval;
      PERFORM public.dblink_connect(v_name,p_conn);
      IF public.dblink_send_query(v_name,p_sql) <> 1 THEN
        BEGIN PERFORM public.dblink_disconnect(v_name); EXCEPTION WHEN OTHERS THEN NULL; END;
        RETURN NULL;
      END IF;
      LOOP
        EXIT WHEN public.dblink_is_busy(v_name)=0;
        IF clock_timestamp() >= v_deadline THEN
          BEGIN PERFORM public.dblink_cancel_query(v_name); EXCEPTION WHEN OTHERS THEN NULL; END;
          BEGIN PERFORM public.dblink_disconnect(v_name); EXCEPTION WHEN OTHERS THEN NULL; END;
          RETURN NULL;
        END IF;
        PERFORM pg_catalog.pg_sleep(0.025);
      END LOOP;
      SELECT value INTO v_value FROM public.dblink_get_result(v_name,false) AS r(value text) LIMIT 1;
      PERFORM public.dblink_disconnect(v_name);
      RETURN v_value;
    EXCEPTION WHEN OTHERS THEN
      BEGIN PERFORM public.dblink_disconnect(v_name); EXCEPTION WHEN OTHERS THEN NULL; END;
      RETURN NULL;
    END;
    \$\$;

    CREATE OR REPLACE FUNCTION pitr_local_claim_external(p_conn text,p_grant_id text)
    RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER SET search_path=pg_catalog,public
    AS \$\$
    DECLARE v_id uuid; v_secret text; v_text text;
    BEGIN
      SELECT instance_id,instance_secret INTO STRICT v_id,v_secret FROM public.pitr_recovery_instance WHERE singleton;
      v_text := public.pitr_bounded_remote_text(
        p_conn,format('SELECT pitr_external_evidence.claim_grant(%L,%L::uuid,%L)::text',p_grant_id,v_id::text,v_secret),750
      );
      RETURN coalesce(v_text::boolean,false);
    EXCEPTION WHEN OTHERS THEN RETURN false; END;
    \$\$;

    CREATE OR REPLACE FUNCTION pitr_local_verify_external(p_conn text,p_grant_id text)
    RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER SET search_path=pg_catalog,public
    AS \$\$
    DECLARE v_id uuid; v_secret text; v_text text;
    BEGIN
      SELECT instance_id,instance_secret INTO STRICT v_id,v_secret FROM public.pitr_recovery_instance WHERE singleton;
      v_text := public.pitr_bounded_remote_text(
        p_conn,format('SELECT pitr_external_evidence.verify_claimed_grant(%L,%L::uuid,%L)::text',p_grant_id,v_id::text,v_secret),750
      );
      RETURN coalesce(v_text::boolean,false);
    EXCEPTION WHEN OTHERS THEN RETURN false; END;
    \$\$;

    CREATE OR REPLACE FUNCTION pitr_local_apply_external(p_conn text,p_grant_id text)
    RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER SET search_path=pg_catalog,public
    AS \$\$
    DECLARE v_id uuid; v_secret text; v_text text; v_doc jsonb;
            v_effect_canonical text; v_effect_digest text; v_grant_fingerprint text;
            v_domain text; v_r text; v_f text; v_receipt text; v_business_state text;
            v_epoch bigint; v_placement bigint; v_source_generation bigint;
            v_principal text; v_instance_id uuid; v_instance_fp text;
    BEGIN
      SELECT instance_id,instance_secret INTO STRICT v_id,v_secret FROM public.pitr_recovery_instance WHERE singleton;
      v_text := public.pitr_bounded_remote_text(
        p_conn,format('SELECT pitr_external_evidence.fetch_claimed_recovery_material(%L,%L::uuid,%L)',p_grant_id,v_id::text,v_secret),750
      );
      IF v_text IS NULL THEN RETURN false; END IF;
      v_doc := v_text::jsonb;
      v_domain := v_doc->>'domain'; v_r := v_doc->>'boundary_r'; v_f := v_doc->>'boundary_f';
      v_receipt := v_doc->>'required_receipt'; v_business_state := v_doc->>'business_state';
      v_epoch := (v_doc->>'successor_epoch')::bigint; v_placement := (v_doc->>'placement_version')::bigint;
      v_source_generation := (v_doc->>'source_poll_generation')::bigint;
      v_principal := v_doc->>'claimed_principal'; v_instance_id := (v_doc->>'claimed_instance_id')::uuid;
      v_instance_fp := v_doc->>'claimed_instance_fingerprint';
      IF v_domain <> 'open-rel-030-recovery-v1' OR v_r <> 'R' OR v_f <> 'F'
         OR v_receipt <> 'effect|after-r' OR v_source_generation <> 11
         OR v_instance_id <> v_id THEN RETURN false; END IF;
      v_effect_canonical := public.pitr_local_canonical_field(v_domain) ||
        public.pitr_local_canonical_field(v_r) || public.pitr_local_canonical_field(v_f) ||
        public.pitr_local_canonical_field(v_business_state) ||
        public.pitr_local_canonical_field(v_source_generation::text) ||
        public.pitr_local_canonical_field(v_receipt);
      v_effect_digest := encode(public.digest(convert_to(v_effect_canonical,'UTF8'),'sha256'),'hex');
      IF v_effect_digest IS DISTINCT FROM v_doc->>'effect_digest' THEN RETURN false; END IF;
      v_grant_fingerprint := encode(public.digest(convert_to(v_doc->>'canonical_grant','UTF8'),'sha256'),'hex');
      INSERT INTO public.pitr_continuity_receipt(receipt_id) VALUES(v_receipt) ON CONFLICT DO NOTHING;
      UPDATE public.pitr_local_state SET
        business_state=v_business_state,poll_epoch=v_epoch,poll_generation=1,
        placement_version=v_placement,reconciled_through_f=true,
        external_grant_id=p_grant_id,external_grant_fingerprint=v_grant_fingerprint,
        external_effect_digest=v_effect_digest,external_grant_principal=v_principal,
        external_grant_instance_id=v_instance_id,external_grant_instance_fingerprint=v_instance_fp
      WHERE singleton;
      RETURN true;
    EXCEPTION WHEN OTHERS THEN RETURN false; END;
    \$\$;

    REVOKE ALL ON FUNCTION pitr_bounded_remote_text(text,text,integer) FROM PUBLIC;
    REVOKE ALL ON FUNCTION pitr_local_claim_external(text,text) FROM PUBLIC;
    REVOKE ALL ON FUNCTION pitr_local_verify_external(text,text) FROM PUBLIC;
    REVOKE ALL ON FUNCTION pitr_local_apply_external(text,text) FROM PUBLIC;
  " >/dev/null
done

primary_instance_id="$(psql_in "$restored_container" "SELECT instance_id::text FROM pitr_recovery_instance WHERE singleton;")"
clone_instance_id="$(psql_in "$clone_container" "SELECT instance_id::text FROM pitr_recovery_instance WHERE singleton;")"
# Local raw secrets never leave the database; only distinct local fingerprints are compared.
primary_local_fp="$(psql_in "$restored_container" "SELECT encode(public.digest(convert_to(instance_secret,'UTF8'),'sha256'),'hex') FROM pitr_recovery_instance WHERE singleton;")"
clone_local_fp="$(psql_in "$clone_container" "SELECT encode(public.digest(convert_to(instance_secret,'UTF8'),'sha256'),'hex') FROM pitr_recovery_instance WHERE singleton;")"
[[ "$primary_instance_id" != "$clone_instance_id" && "$primary_local_fp" != "$clone_local_fp" ]] || {
  echo "physical restore clones did not generate distinct post-R instance capabilities" >&2; exit 1;
}
printf '%s\n' 'physical_pitr_recovery_instance_capability_generated_post_R=PASS'
printf '%s\n' 'physical_pitr_recovery_clone_capability_distinct=PASS'

primary_password="$(openssl rand -hex 24)"
rival_password="$(openssl rand -hex 24)"
race_a_password="$(openssl rand -hex 24)"
race_b_password="$(openssl rand -hex 24)"
control_ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$control_container")"
[[ -n "$control_ip" ]] || { echo "cannot resolve control IP" >&2; exit 1; }

psql_in "$control_container" "
  CREATE ROLE $primary_role LOGIN PASSWORD '$primary_password';
  CREATE ROLE $rival_role LOGIN PASSWORD '$rival_password';
  CREATE ROLE $race_a_role LOGIN PASSWORD '$race_a_password';
  CREATE ROLE $race_b_role LOGIN PASSWORD '$race_b_password';
  GRANT USAGE ON SCHEMA pitr_external_evidence TO $primary_role,$rival_role,$race_a_role,$race_b_role;
  GRANT EXECUTE ON FUNCTION pitr_external_evidence.claim_grant(text,uuid,text),
    pitr_external_evidence.verify_claimed_grant(text,uuid,text),
    pitr_external_evidence.fetch_claimed_recovery_material(text,uuid,text),
    pitr_external_evidence.verifier_delay_probe()
    TO $primary_role,$rival_role,$race_a_role,$race_b_role;
" >/dev/null

conn_string() {
  local user="$1" pass="$2"
  printf 'hostaddr=%s port=5432 dbname=jlmirror user=%s password=%s connect_timeout=2' "$control_ip" "$user" "$pass"
}
primary_conn="$(conn_string "$primary_role" "$primary_password")"
rival_conn="$(conn_string "$rival_role" "$rival_password")"

claim_args="$(psql_in "$control_container" "SELECT pg_get_function_identity_arguments('pitr_external_evidence.claim_grant(text,uuid,text)'::regprocedure);")"
assert_exact "physical_pitr_recovery_claim_api_grant_plus_instance_proof" "p_grant_id text, p_instance_id uuid, p_instance_secret text" "$claim_args"
printf '%s\n' 'physical_pitr_recovery_claim_identity_from_authenticated_session=PASS'

# Recovery principals cannot inspect surviving grant/effect/claim state directly.
set +e
docker exec -e PGPASSWORD="$primary_password" "$restored_container" psql -X -v ON_ERROR_STOP=1 \
  -h "$control_ip" -U "$primary_role" -d jlmirror -Atq -c "SELECT grant_id FROM pitr_external_evidence.recovery_grant;" \
  >"$tmpdir/direct.out" 2>"$tmpdir/direct.err"
direct_rc=$?
set -e
[[ "$direct_rc" -ne 0 ]] || { echo "restore principal can read recovery_grant directly" >&2; exit 1; }
printf '%s\n' 'physical_pitr_recovery_principal_no_direct_grant_read=PASS'

set +e
docker exec -e PGPASSWORD="$rival_password" "$restored_container" psql -X -v ON_ERROR_STOP=1 \
  -h "$control_ip" -U "$primary_role" -d jlmirror -Atq -c 'SELECT 1;' \
  >"$tmpdir/spoof.out" 2>"$tmpdir/spoof.err"
spoof_rc=$?
set -e
[[ "$spoof_rc" -ne 0 ]] || { echo "rival credential authenticated as primary" >&2; exit 1; }
printf '%s\n' 'physical_pitr_recovery_principal_spoof_rejected=PASS'

# Invalid grant attestation cannot create any boundary winner.
assert_exact "physical_pitr_tampered_grant_cannot_claim" "false" \
  "$(psql_in "$restored_container" "SELECT pitr_local_claim_external('$primary_conn','grant-F-tampered')::text;")"
assert_exact "physical_pitr_tamper_leaves_boundary_unclaimed" "0" \
  "$(psql_in "$control_container" "SELECT count(*)::text FROM pitr_external_evidence.recovery_boundary_claim WHERE boundary_r='R' AND boundary_f='F';")"

# Local bounded-response negative: authenticated peer accepts the session but
# sleeps for 5 seconds. The caller-local 500 ms deadline must fail closed first.
claim_source="$(psql_in "$restored_container" "SELECT pg_get_functiondef('pitr_local_claim_external(text,text)'::regprocedure);")"
verify_source="$(psql_in "$restored_container" "SELECT pg_get_functiondef('pitr_local_verify_external(text,text)'::regprocedure);")"
apply_source="$(psql_in "$restored_container" "SELECT pg_get_functiondef('pitr_local_apply_external(text,text)'::regprocedure);")"
[[ "$claim_source" == *"pitr_bounded_remote_text"* && "$verify_source" == *"pitr_bounded_remote_text"* && "$apply_source" == *"pitr_bounded_remote_text"* ]] || {
  echo "recovery helpers bypass bounded local transport" >&2; exit 1;
}
printf '%s\n' 'physical_pitr_recovery_helpers_use_bounded_transport=PASS'
delay_start="$(date +%s%3N)"
delay_value="$(psql_in "$restored_container" "SELECT coalesce(pitr_bounded_remote_text('$primary_conn','SELECT pitr_external_evidence.verifier_delay_probe()::text',500),'');")"
delay_end="$(date +%s%3N)"
delay_ms=$((delay_end - delay_start))
assert_exact "physical_pitr_recovery_stalled_peer_fails_closed" "" "$delay_value"
[[ "$delay_ms" -lt 1800 ]] || { echo "recovery local deadline not authoritative: ${delay_ms}ms" >&2; exit 1; }
printf 'physical_pitr_recovery_local_deadline=PASS elapsed_ms=%s\n' "$delay_ms"

# Cross-grant concurrent race on a separate boundary: two different grant IDs,
# two authenticated principals and two instance capabilities still yield one
# governed boundary winner.
race_a_id="$(psql_in "$control_container" "SELECT gen_random_uuid()::text;")"
race_b_id="$(psql_in "$control_container" "SELECT gen_random_uuid()::text;")"
race_a_secret="$(openssl rand -hex 32)"
race_b_secret="$(openssl rand -hex 32)"
psql_control_direct() {
  local user="$1" pass="$2" sql="$3"
  docker exec -e PGPASSWORD="$pass" "$restored_container" \
    psql -X -v ON_ERROR_STOP=1 -h "$control_ip" -U "$user" -d jlmirror -Atq -c "$sql"
}
race_sql_a="SELECT pitr_external_evidence.claim_grant('grant-race-a','$race_a_id'::uuid,'$race_a_secret')::text;"
race_sql_b="SELECT pitr_external_evidence.claim_grant('grant-race-b','$race_b_id'::uuid,'$race_b_secret')::text;"
( psql_control_direct "$race_a_role" "$race_a_password" "$race_sql_a" >"$tmpdir/race-a.out" ) & race_pid_a=$!
( psql_control_direct "$race_b_role" "$race_b_password" "$race_sql_b" >"$tmpdir/race-b.out" ) & race_pid_b=$!
wait "$race_pid_a"; wait "$race_pid_b"
race_a="$(cat "$tmpdir/race-a.out")"; race_b="$(cat "$tmpdir/race-b.out")"
if [[ "$race_a|$race_b" != "true|false" && "$race_a|$race_b" != "false|true" ]]; then
  echo "cross-grant recovery boundary race not single-winner: $race_a|$race_b" >&2; exit 1
fi
if [[ "$race_a" == true ]]; then
  race_winner_role="$race_a_role"; race_winner_password="$race_a_password"; race_winner_sql="$race_sql_a"
  race_loser_role="$race_b_role"; race_loser_password="$race_b_password"; race_loser_sql="$race_sql_b"
else
  race_winner_role="$race_b_role"; race_winner_password="$race_b_password"; race_winner_sql="$race_sql_b"
  race_loser_role="$race_a_role"; race_loser_password="$race_a_password"; race_loser_sql="$race_sql_a"
fi
assert_exact "physical_pitr_recovery_claim_winner_retry" "true" "$(psql_control_direct "$race_winner_role" "$race_winner_password" "$race_winner_sql")"
assert_exact "physical_pitr_recovery_claim_loser_rejected" "false" "$(psql_control_direct "$race_loser_role" "$race_loser_password" "$race_loser_sql")"
assert_exact "physical_pitr_recovery_boundary_claim_rows_after_cross_grant_race" "1" \
  "$(psql_in "$control_container" "SELECT count(*)::text FROM pitr_external_evidence.recovery_boundary_claim WHERE boundary_r='R-race' AND boundary_f='F-race';")"
printf '%s\n' 'physical_pitr_recovery_cross_grant_boundary_single_winner_race=PASS'
printf '%s\n' 'physical_pitr_recovery_claim_single_winner_race=PASS'

# A locally recreated continuity receipt is still insufficient. The clone can
# fabricate the expected receipt but has no surviving boundary claim/effect proof.
psql_in "$clone_container" "INSERT INTO pitr_continuity_receipt(receipt_id) VALUES('$required_receipt') ON CONFLICT DO NOTHING;" >/dev/null
assert_exact "physical_pitr_local_self_mint_cannot_admit" "false" \
  "$(psql_in "$clone_container" "SELECT (reconciled_through_f AND external_effect_digest IS NOT NULL)::text FROM pitr_local_state WHERE singleton;")"

# Main boundary: primary claims one grant. A duplicate grant id for the same
# boundary cannot authorize a different physical instance, even with the exact
# same external credential. The winning instance may converge through either id.
assert_exact "physical_pitr_recovery_grant_claimed" "true" \
  "$(psql_in "$restored_container" "SELECT pitr_local_claim_external('$primary_conn','grant-F-1')::text;")"
assert_exact "physical_pitr_recovery_grant_same_instance_retry" "true" \
  "$(psql_in "$restored_container" "SELECT pitr_local_claim_external('$primary_conn','grant-F-1')::text;")"
assert_exact "physical_pitr_recovery_duplicate_grant_same_winner_retry" "true" \
  "$(psql_in "$restored_container" "SELECT pitr_local_claim_external('$primary_conn','grant-F-duplicate')::text;")"
assert_exact "physical_pitr_recovery_duplicate_grant_clone_rejected" "false" \
  "$(psql_in "$clone_container" "SELECT pitr_local_claim_external('$primary_conn','grant-F-duplicate')::text;")"
assert_exact "physical_pitr_recovery_same_principal_clone_rejected" "false" \
  "$(psql_in "$clone_container" "SELECT pitr_local_claim_external('$primary_conn','grant-F-1')::text;")"
assert_exact "physical_pitr_recovery_other_principal_rejected" "false" \
  "$(psql_in "$clone_container" "SELECT pitr_local_claim_external('$rival_conn','grant-F-1')::text;")"
assert_exact "physical_pitr_recovery_main_boundary_single_claim" "1" \
  "$(psql_in "$control_container" "SELECT count(*)::text FROM pitr_external_evidence.recovery_boundary_claim WHERE boundary_r='R' AND boundary_f='F';")"
printf '%s\n' 'physical_pitr_recovery_single_winner_per_boundary_across_grant_ids=PASS'

claimed_binding="$(psql_in "$control_container" "SELECT claimed_principal::text||'|'||claimed_instance_id::text||'|'||claimed_instance_fingerprint||'|'||effect_digest FROM pitr_external_evidence.recovery_boundary_claim WHERE boundary_r='R' AND boundary_f='F';")"
claimed_principal="${claimed_binding%%|*}"
remaining="${claimed_binding#*|}"; claimed_instance_id="${remaining%%|*}"
remaining="${remaining#*|}"; claimed_instance_fingerprint="${remaining%%|*}"
claimed_effect_digest="${remaining#*|}"
assert_exact "physical_pitr_recovery_grant_authenticated_principal_binding" "$primary_role" "$claimed_principal"
assert_exact "physical_pitr_recovery_grant_instance_id_binding" "$primary_instance_id" "$claimed_instance_id"
assert_exact "physical_pitr_recovery_effect_digest_binding" "$main_effect_digest" "$claimed_effect_digest"
[[ -n "$claimed_instance_fingerprint" ]] || { echo "missing claimed instance fingerprint" >&2; exit 1; }
printf '%s\n' 'physical_pitr_recovery_instance_fingerprint_binding=PASS'

# Claim alone does not mutate local business truth. Only authenticated surviving
# recovery material may apply the actual post-R effect and successor authority.
assert_exact "physical_pitr_claim_without_effect_application_stays_at_R" "state_at_R|false|0" \
  "$(psql_in "$restored_container" "SELECT business_state||'|'||reconciled_through_f::text||'|'||(SELECT count(*) FROM pitr_continuity_receipt) FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_authenticated_effect_application" "true" \
  "$(psql_in "$restored_container" "SELECT pitr_local_apply_external('$primary_conn','grant-F-1')::text;")"
after_state="$(psql_in "$restored_container" "SELECT business_state||'|'||poll_epoch||'|'||poll_generation||'|'||placement_version||'|'||reconciled_through_f::text||'|'||(SELECT count(*) FROM pitr_continuity_receipt)||'|'||external_grant_id||'|'||external_effect_digest FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_reconciled_from_authenticated_surviving_effect" "post_R_business_change|6|1|8|true|1|grant-F-1|$main_effect_digest" "$after_state"

local_ready="$(psql_in "$restored_container" "SELECT (business_state='post_R_business_change' AND reconciled_through_f AND poll_epoch=6 AND placement_version=8 AND external_effect_digest='$main_effect_digest' AND external_grant_principal='$primary_role' AND external_grant_instance_id='$primary_instance_id'::uuid AND external_grant_instance_fingerprint='$claimed_instance_fingerprint' AND EXISTS(SELECT 1 FROM pitr_continuity_receipt WHERE receipt_id='$required_receipt'))::text FROM pitr_local_state WHERE singleton;")"
external_ready="$(psql_in "$restored_container" "SELECT pitr_local_verify_external('$primary_conn','grant-F-1')::text;")"
clone_ready="$(psql_in "$clone_container" "SELECT pitr_local_verify_external('$primary_conn','grant-F-1')::text;")"
assert_exact "physical_pitr_local_reconciled_state" "true" "$local_ready"
assert_exact "physical_pitr_external_authority_still_verifies" "true" "$external_ready"
assert_exact "physical_pitr_duplicate_restored_authority_not_admitted" "false" "$clone_ready"
if [[ "$local_ready" != true || "$external_ready" != true || "$clone_ready" != false ]]; then
  echo "PITR admission lacks effect-bound boundary-single-winner instance authority" >&2; exit 1
fi

unset primary_password rival_password race_a_password race_b_password race_a_secret race_b_secret
printf '%s\n' 'physical_pitr_recovery_single_winner_instance_capability=PASS'
printf '%s\n' 'physical_pitr_post_reconcile_admission=PASS authority=surviving_external_authenticated_effect_bound_boundary_single_winner_instance_capability'
printf '%s\n' 'physical_pitr_rf_reconciliation=PASS'
