# ---------------------------------------------------------------------------
# Evidence-only verifier transport hardening.
#
# Verifier credentials are capabilities, not signing authority. They are kept
# in restricted authority-owned tables rather than interpolated into pg_proc
# source text. Cross-authority queries use asynchronous dblink polling with a
# local deadline after connection establishment; connect_timeout separately
# bounds connection setup. This remains C2 laboratory transport, not production
# RPC/authentication/secret-distribution selection.
# ---------------------------------------------------------------------------
pg_sql "
  CREATE TABLE relocation_evidence.target_verifier_connection (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    hostaddr text NOT NULL,
    password text NOT NULL
  );
  INSERT INTO relocation_evidence.target_verifier_connection(singleton,hostaddr,password)
  VALUES(true,'$ts_ip','$target_verify_password');
  REVOKE ALL ON relocation_evidence.target_verifier_connection FROM PUBLIC,relocation_tier1_verifier;

  CREATE OR REPLACE FUNCTION relocation_evidence.bounded_remote_boolean(
    p_conn text,p_sql text,p_timeout_ms integer
  ) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
  SET search_path=pg_catalog,public
  AS \$\$
  DECLARE
    v_name text;
    v_deadline timestamptz;
    v_verified boolean;
  BEGIN
    IF p_timeout_ms < 50 OR p_timeout_ms > 5000 THEN
      RETURN false;
    END IF;
    v_name := 'or030_' || pg_backend_pid()::text || '_' ||
              substr(md5(clock_timestamp()::text || random()::text),1,12);
    v_deadline := clock_timestamp() + (p_timeout_ms::text || ' milliseconds')::interval;

    PERFORM public.dblink_connect(v_name,p_conn);
    IF public.dblink_send_query(v_name,p_sql) <> 1 THEN
      BEGIN PERFORM public.dblink_disconnect(v_name); EXCEPTION WHEN OTHERS THEN NULL; END;
      RETURN false;
    END IF;

    LOOP
      EXIT WHEN public.dblink_is_busy(v_name) = 0;
      IF clock_timestamp() >= v_deadline THEN
        BEGIN PERFORM public.dblink_disconnect(v_name); EXCEPTION WHEN OTHERS THEN NULL; END;
        RETURN false;
      END IF;
      PERFORM pg_catalog.pg_sleep(0.025);
    END LOOP;

    SELECT verified INTO v_verified
      FROM public.dblink_get_result(v_name,false) AS r(verified boolean)
      LIMIT 1;
    PERFORM public.dblink_disconnect(v_name);
    RETURN coalesce(v_verified,false);
  EXCEPTION WHEN OTHERS THEN
    BEGIN PERFORM public.dblink_disconnect(v_name); EXCEPTION WHEN OTHERS THEN NULL; END;
    RETURN false;
  END;
  \$\$;
  REVOKE ALL ON FUNCTION relocation_evidence.bounded_remote_boolean(text,text,integer)
    FROM PUBLIC,relocation_tier1_verifier;

  CREATE OR REPLACE FUNCTION relocation_evidence.target_attestation_is_valid(
    p_tenant uuid,p_fence bigint,p_checkpoint_id uuid,p_checkpoint_generation bigint,
    p_target_sealed boolean,p_target_count bigint,p_target_digest text,
    p_target_max_ordinal bigint,p_target_attestation text
  ) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
  SET search_path=pg_catalog,relocation_evidence,public
  AS \$\$
  DECLARE v_hostaddr text; v_password text; v_conn text; v_sql text;
  BEGIN
    SELECT hostaddr,password INTO STRICT v_hostaddr,v_password
      FROM relocation_evidence.target_verifier_connection WHERE singleton;
    v_conn := format(
      'hostaddr=%s port=5432 dbname=jlmirror user=relocation_target_verifier password=%s connect_timeout=1',
      v_hostaddr,v_password
    );
    v_sql := format(
      'SELECT relocation_evidence.verify_target_attestation(%L::uuid,%s,%L::uuid,%s,%L::boolean,%s,%L,%s,%L)',
      p_tenant,p_fence,p_checkpoint_id,p_checkpoint_generation,p_target_sealed,
      p_target_count,p_target_digest,p_target_max_ordinal,p_target_attestation
    );
    RETURN relocation_evidence.bounded_remote_boolean(v_conn,v_sql,750);
  EXCEPTION WHEN OTHERS THEN
    RETURN false;
  END;
  \$\$;
  REVOKE ALL ON FUNCTION relocation_evidence.target_attestation_is_valid(uuid,bigint,uuid,bigint,boolean,bigint,text,bigint,text) FROM PUBLIC,relocation_tier1_verifier;

  CREATE OR REPLACE FUNCTION relocation_evidence.verifier_delay_probe()
  RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
  SET search_path=pg_catalog
  AS \$\$
  BEGIN
    PERFORM pg_catalog.pg_sleep(5);
    RETURN true;
  END;
  \$\$;
  REVOKE ALL ON FUNCTION relocation_evidence.verifier_delay_probe() FROM PUBLIC;
  GRANT EXECUTE ON FUNCTION relocation_evidence.verifier_delay_probe() TO relocation_tier1_verifier;
" >/dev/null

ts_sql "
  CREATE TABLE relocation_evidence.tier1_verifier_connection (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    hostaddr text NOT NULL,
    password text NOT NULL
  );
  ALTER TABLE relocation_evidence.tier1_verifier_connection OWNER TO ts_owner;
  INSERT INTO relocation_evidence.tier1_verifier_connection(singleton,hostaddr,password)
  VALUES(true,'$pg_ip','$tier1_verify_password');
  REVOKE ALL ON relocation_evidence.tier1_verifier_connection
    FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b,ts_automation_owner,relocation_target_verifier;

  CREATE OR REPLACE FUNCTION relocation_evidence.bounded_remote_boolean(
    p_conn text,p_sql text,p_timeout_ms integer
  ) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
  SET search_path=pg_catalog,public
  AS \$\$
  DECLARE
    v_name text;
    v_deadline timestamptz;
    v_verified boolean;
  BEGIN
    IF p_timeout_ms < 50 OR p_timeout_ms > 5000 THEN
      RETURN false;
    END IF;
    v_name := 'or030_' || pg_backend_pid()::text || '_' ||
              substr(md5(clock_timestamp()::text || random()::text),1,12);
    v_deadline := clock_timestamp() + (p_timeout_ms::text || ' milliseconds')::interval;

    PERFORM public.dblink_connect(v_name,p_conn);
    IF public.dblink_send_query(v_name,p_sql) <> 1 THEN
      BEGIN PERFORM public.dblink_disconnect(v_name); EXCEPTION WHEN OTHERS THEN NULL; END;
      RETURN false;
    END IF;

    LOOP
      EXIT WHEN public.dblink_is_busy(v_name) = 0;
      IF clock_timestamp() >= v_deadline THEN
        BEGIN PERFORM public.dblink_disconnect(v_name); EXCEPTION WHEN OTHERS THEN NULL; END;
        RETURN false;
      END IF;
      PERFORM pg_catalog.pg_sleep(0.025);
    END LOOP;

    SELECT verified INTO v_verified
      FROM public.dblink_get_result(v_name,false) AS r(verified boolean)
      LIMIT 1;
    PERFORM public.dblink_disconnect(v_name);
    RETURN coalesce(v_verified,false);
  EXCEPTION WHEN OTHERS THEN
    BEGIN PERFORM public.dblink_disconnect(v_name); EXCEPTION WHEN OTHERS THEN NULL; END;
    RETURN false;
  END;
  \$\$;
  ALTER FUNCTION relocation_evidence.bounded_remote_boolean(text,text,integer) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.bounded_remote_boolean(text,text,integer)
    FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b,ts_automation_owner,relocation_target_verifier;

  CREATE OR REPLACE FUNCTION relocation_evidence.tier1_activation_grant_is_valid(
    p_tenant uuid,p_fence bigint,p_checkpoint_id uuid,p_checkpoint_generation bigint,
    p_placement_version bigint,p_target_attestation text
  ) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
  SET search_path=pg_catalog,relocation_evidence,public
  AS \$\$
  DECLARE v_hostaddr text; v_password text; v_conn text; v_sql text;
  BEGIN
    SELECT hostaddr,password INTO STRICT v_hostaddr,v_password
      FROM relocation_evidence.tier1_verifier_connection WHERE singleton;
    v_conn := format(
      'hostaddr=%s port=5432 dbname=jlmirror user=relocation_tier1_verifier password=%s connect_timeout=1',
      v_hostaddr,v_password
    );
    v_sql := format(
      'SELECT relocation_evidence.verify_activation_grant(%L::uuid,%s,%L::uuid,%s,%s,%L)',
      p_tenant,p_fence,p_checkpoint_id,p_checkpoint_generation,p_placement_version,p_target_attestation
    );
    RETURN relocation_evidence.bounded_remote_boolean(v_conn,v_sql,750);
  EXCEPTION WHEN OTHERS THEN
    RETURN false;
  END;
  \$\$;
  ALTER FUNCTION relocation_evidence.tier1_activation_grant_is_valid(uuid,bigint,uuid,bigint,bigint,text) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.tier1_activation_grant_is_valid(uuid,bigint,uuid,bigint,bigint,text)
    FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b,ts_automation_owner,relocation_target_verifier;

  CREATE OR REPLACE FUNCTION relocation_evidence.verifier_delay_probe()
  RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
  SET search_path=pg_catalog
  AS \$\$
  BEGIN
    PERFORM pg_catalog.pg_sleep(5);
    RETURN true;
  END;
  \$\$;
  ALTER FUNCTION relocation_evidence.verifier_delay_probe() OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.verifier_delay_probe() FROM PUBLIC;
  GRANT EXECUTE ON FUNCTION relocation_evidence.verifier_delay_probe() TO relocation_target_verifier;
" >/dev/null

# Static/runtime privilege checks for the capability stores and function source.
expect_pg_reject "relocation_tier1_verifier_cannot_read_target_connection_capability" "permission denied" \
  "SET ROLE relocation_tier1_verifier; SELECT password FROM relocation_evidence.target_verifier_connection;"
expect_ts_reject "relocation_projection_writer_cannot_read_tier1_connection_capability" "permission denied" \
  "SET ROLE ts_automation_owner; SELECT password FROM relocation_evidence.tier1_verifier_connection;"
expect_ts_reject "relocation_target_verifier_cannot_read_tier1_connection_capability" "permission denied" \
  "SET ROLE relocation_target_verifier; SELECT password FROM relocation_evidence.tier1_verifier_connection;"

pg_helper_source="$(pg_sql "SELECT prosrc FROM pg_proc WHERE oid='relocation_evidence.target_attestation_is_valid(uuid,bigint,uuid,bigint,boolean,bigint,text,bigint,text)'::regprocedure;")"
if [[ "$pg_helper_source" == *"$target_verify_password"* ]]; then
  echo "Tier 1 verifier credential leaked into function source" >&2
  exit 1
fi
if [[ "$pg_helper_source" != *"bounded_remote_boolean"* ]]; then
  echo "Tier 1 verifier helper bypasses local bounded transport" >&2
  exit 1
fi
printf '%s\n' 'relocation_target_verifier_secret_not_in_function_source=PASS'

ts_helper_source="$(ts_sql "SELECT prosrc FROM pg_proc WHERE oid='relocation_evidence.tier1_activation_grant_is_valid(uuid,bigint,uuid,bigint,bigint,text)'::regprocedure;")"
if [[ "$ts_helper_source" == *"$tier1_verify_password"* ]]; then
  echo "Tier 2 verifier credential leaked into function source" >&2
  exit 1
fi
if [[ "$ts_helper_source" != *"bounded_remote_boolean"* ]]; then
  echo "Tier 2 verifier helper bypasses local bounded transport" >&2
  exit 1
fi
printf '%s\n' 'relocation_tier1_verifier_secret_not_in_function_source=PASS'

pg_bounded_priv="$(pg_sql "SELECT has_function_privilege('relocation_tier1_verifier','relocation_evidence.bounded_remote_boolean(text,text,integer)','EXECUTE')::text;")"
assert_exact "relocation_tier1_verifier_cannot_call_raw_bounded_transport" "false" "$pg_bounded_priv"
ts_bounded_priv="$(ts_sql "SELECT (has_function_privilege('ts_automation_owner','relocation_evidence.bounded_remote_boolean(text,text,integer)','EXECUTE') OR has_function_privilege('relocation_target_verifier','relocation_evidence.bounded_remote_boolean(text,text,integer)','EXECUTE'))::text;")"
assert_exact "relocation_target_principals_cannot_call_raw_bounded_transport" "false" "$ts_bounded_priv"

# Local deadline negative: the remote peer authenticates and begins a 5-second
# query. The caller-side asynchronous polling deadline must return false well
# before the remote role's own 2-second statement timeout could save us.
pg_delay_start="$(date +%s%3N)"
pg_delay_result="$(pg_sql "
  SELECT relocation_evidence.bounded_remote_boolean(
    format('hostaddr=%s port=5432 dbname=jlmirror user=relocation_target_verifier password=%s connect_timeout=1',hostaddr,password),
    'SELECT relocation_evidence.verifier_delay_probe()',500
  )::text
  FROM relocation_evidence.target_verifier_connection WHERE singleton;
")"
pg_delay_end="$(date +%s%3N)"
pg_delay_ms=$((pg_delay_end - pg_delay_start))
assert_exact "relocation_target_verifier_stalled_peer_fails_closed" "false" "$pg_delay_result"
if [[ "$pg_delay_ms" -ge 1800 ]]; then
  echo "Tier 1 local verifier deadline was not authoritative: ${pg_delay_ms}ms" >&2
  exit 1
fi
printf 'relocation_target_verifier_local_deadline=PASS elapsed_ms=%s\n' "$pg_delay_ms"

ts_delay_start="$(date +%s%3N)"
ts_delay_result="$(ts_sql "
  SELECT relocation_evidence.bounded_remote_boolean(
    format('hostaddr=%s port=5432 dbname=jlmirror user=relocation_tier1_verifier password=%s connect_timeout=1',hostaddr,password),
    'SELECT relocation_evidence.verifier_delay_probe()',500
  )::text
  FROM relocation_evidence.tier1_verifier_connection WHERE singleton;
")"
ts_delay_end="$(date +%s%3N)"
ts_delay_ms=$((ts_delay_end - ts_delay_start))
assert_exact "relocation_tier1_verifier_stalled_peer_fails_closed" "false" "$ts_delay_result"
if [[ "$ts_delay_ms" -ge 1800 ]]; then
  echo "Tier 2 local verifier deadline was not authoritative: ${ts_delay_ms}ms" >&2
  exit 1
fi
printf 'relocation_tier1_verifier_local_deadline=PASS elapsed_ms=%s\n' "$ts_delay_ms"
