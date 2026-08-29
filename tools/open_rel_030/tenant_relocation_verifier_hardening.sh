# ---------------------------------------------------------------------------
# Evidence-only verifier transport hardening.
#
# Verifier credentials are capabilities, not signing authority. They are kept
# in restricted authority-owned tables rather than interpolated into pg_proc
# source text. The SECURITY DEFINER helpers expose only a boolean result and use
# fixed search paths. This remains C2 laboratory transport, not production RPC.
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

  CREATE OR REPLACE FUNCTION relocation_evidence.target_attestation_is_valid(
    p_tenant uuid,p_fence bigint,p_checkpoint_id uuid,p_checkpoint_generation bigint,
    p_target_sealed boolean,p_target_count bigint,p_target_digest text,
    p_target_max_ordinal bigint,p_target_attestation text
  ) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
  SET search_path=pg_catalog,relocation_evidence,public
  AS \$\$
  DECLARE v_verified boolean; v_hostaddr text; v_password text; v_conn text;
  BEGIN
    SELECT hostaddr,password INTO STRICT v_hostaddr,v_password
      FROM relocation_evidence.target_verifier_connection WHERE singleton;
    v_conn := format(
      'hostaddr=%s port=5432 dbname=jlmirror user=relocation_target_verifier password=%s connect_timeout=2',
      v_hostaddr,v_password
    );
    SELECT verified INTO v_verified
    FROM public.dblink(
      v_conn,
      format(
        'SELECT relocation_evidence.verify_target_attestation(%L::uuid,%s,%L::uuid,%s,%L::boolean,%s,%L,%s,%L)',
        p_tenant,p_fence,p_checkpoint_id,p_checkpoint_generation,p_target_sealed,
        p_target_count,p_target_digest,p_target_max_ordinal,p_target_attestation
      )
    ) AS r(verified boolean);
    RETURN coalesce(v_verified,false);
  EXCEPTION WHEN OTHERS THEN
    RETURN false;
  END;
  \$\$;
  REVOKE ALL ON FUNCTION relocation_evidence.target_attestation_is_valid(uuid,bigint,uuid,bigint,boolean,bigint,text,bigint,text) FROM PUBLIC,relocation_tier1_verifier;
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

  CREATE OR REPLACE FUNCTION relocation_evidence.tier1_activation_grant_is_valid(
    p_tenant uuid,p_fence bigint,p_checkpoint_id uuid,p_checkpoint_generation bigint,
    p_placement_version bigint,p_target_attestation text
  ) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
  SET search_path=pg_catalog,relocation_evidence,public
  AS \$\$
  DECLARE v_verified boolean; v_hostaddr text; v_password text; v_conn text;
  BEGIN
    SELECT hostaddr,password INTO STRICT v_hostaddr,v_password
      FROM relocation_evidence.tier1_verifier_connection WHERE singleton;
    v_conn := format(
      'hostaddr=%s port=5432 dbname=jlmirror user=relocation_tier1_verifier password=%s connect_timeout=2',
      v_hostaddr,v_password
    );
    SELECT verified INTO v_verified
    FROM public.dblink(
      v_conn,
      format(
        'SELECT relocation_evidence.verify_activation_grant(%L::uuid,%s,%L::uuid,%s,%s,%L)',
        p_tenant,p_fence,p_checkpoint_id,p_checkpoint_generation,p_placement_version,p_target_attestation
      )
    ) AS r(verified boolean);
    RETURN coalesce(v_verified,false);
  EXCEPTION WHEN OTHERS THEN
    RETURN false;
  END;
  \$\$;
  ALTER FUNCTION relocation_evidence.tier1_activation_grant_is_valid(uuid,bigint,uuid,bigint,bigint,text) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.tier1_activation_grant_is_valid(uuid,bigint,uuid,bigint,bigint,text)
    FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b,ts_automation_owner,relocation_target_verifier;
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
printf '%s\n' 'relocation_target_verifier_secret_not_in_function_source=PASS'

ts_helper_source="$(ts_sql "SELECT prosrc FROM pg_proc WHERE oid='relocation_evidence.tier1_activation_grant_is_valid(uuid,bigint,uuid,bigint,bigint,text)'::regprocedure;")"
if [[ "$ts_helper_source" == *"$tier1_verify_password"* ]]; then
  echo "Tier 2 verifier credential leaked into function source" >&2
  exit 1
fi
printf '%s\n' 'relocation_tier1_verifier_secret_not_in_function_source=PASS'
