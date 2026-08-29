# ---------------------------------------------------------------------------
# Canonical timestamp hardening.
#
# PostgreSQL timestamptz supports BC dates. Formatting only YYYY-MM-DD is not
# injective across the BC/AD era boundary. Both authorities therefore serialize
# UTC timestamp + microseconds + explicit AD/BC era before canonical_field().
# ---------------------------------------------------------------------------
pg_sql "
  CREATE OR REPLACE FUNCTION relocation_evidence.canonical_timestamp(p_value timestamptz)
  RETURNS text LANGUAGE sql IMMUTABLE STRICT
  SET search_path=pg_catalog
  AS \$\$
    SELECT to_char(
      p_value AT TIME ZONE 'UTC',
      'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\" AD'
    )
  \$\$;
  REVOKE ALL ON FUNCTION relocation_evidence.canonical_timestamp(timestamptz) FROM PUBLIC;

  CREATE OR REPLACE FUNCTION relocation_evidence.authoritative_digest(p_tenant uuid,p_fence bigint)
  RETURNS text LANGUAGE sql STABLE
  SET search_path=pg_catalog,relocation_evidence
  AS \$\$
    SELECT encode(public.digest(convert_to(coalesce(string_agg(
      relocation_evidence.canonical_field(accepted_ordinal::text) ||
      relocation_evidence.canonical_field(observation_id) ||
      relocation_evidence.canonical_field(metric_definition_id::text) ||
      relocation_evidence.canonical_field(relocation_evidence.canonical_timestamp(observed_at)) ||
      relocation_evidence.canonical_field(trim_scale(numeric_value)::text),
      '' ORDER BY accepted_ordinal,observation_id
    ),''),'UTF8'),'sha256'),'hex')
    FROM relocation_evidence.acceptance
    WHERE tenant_id=p_tenant AND accepted_ordinal<=p_fence
  \$\$;
" >/dev/null

ts_sql "
  CREATE OR REPLACE FUNCTION relocation_evidence.canonical_timestamp(p_value timestamptz)
  RETURNS text LANGUAGE sql IMMUTABLE STRICT SECURITY DEFINER
  SET search_path=pg_catalog
  AS \$\$
    SELECT to_char(
      p_value AT TIME ZONE 'UTC',
      'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\" AD'
    )
  \$\$;
  ALTER FUNCTION relocation_evidence.canonical_timestamp(timestamptz) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.canonical_timestamp(timestamptz) FROM PUBLIC;

  CREATE OR REPLACE FUNCTION relocation_evidence.target_digest(p_tenant uuid,p_fence bigint)
  RETURNS text LANGUAGE sql STABLE SECURITY DEFINER
  SET search_path=pg_catalog,relocation_evidence
  AS \$\$
    SELECT encode(public.digest(convert_to(coalesce(string_agg(
      relocation_evidence.canonical_field(accepted_ordinal::text) ||
      relocation_evidence.canonical_field(observation_id) ||
      relocation_evidence.canonical_field(metric_definition_id::text) ||
      relocation_evidence.canonical_field(relocation_evidence.canonical_timestamp(observed_at)) ||
      relocation_evidence.canonical_field(trim_scale(numeric_value)::text),
      '' ORDER BY accepted_ordinal,observation_id
    ),''),'UTF8'),'sha256'),'hex')
    FROM relocation_evidence.target_history
    WHERE tenant_id=p_tenant AND accepted_ordinal<=p_fence
  \$\$;
  ALTER FUNCTION relocation_evidence.target_digest(uuid,bigint) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.target_digest(uuid,bigint) FROM PUBLIC;
" >/dev/null

pg_bc="$(pg_sql "SELECT relocation_evidence.canonical_timestamp('0001-01-01 00:00:00+00 BC'::timestamptz);")"
pg_ad="$(pg_sql "SELECT relocation_evidence.canonical_timestamp('0001-01-01 00:00:00+00 AD'::timestamptz);")"
ts_bc="$(ts_sql "SELECT relocation_evidence.canonical_timestamp('0001-01-01 00:00:00+00 BC'::timestamptz);")"
ts_ad="$(ts_sql "SELECT relocation_evidence.canonical_timestamp('0001-01-01 00:00:00+00 AD'::timestamptz);")"

if [[ "$pg_bc" == "$pg_ad" || "$ts_bc" == "$ts_ad" ]]; then
  echo "canonical relocation timestamp lost BC/AD era distinction" >&2
  exit 1
fi
if [[ "$pg_bc" != "$ts_bc" || "$pg_ad" != "$ts_ad" ]]; then
  printf 'canonical timestamp cross-store mismatch pg_bc=%q ts_bc=%q pg_ad=%q ts_ad=%q\n' \
    "$pg_bc" "$ts_bc" "$pg_ad" "$ts_ad" >&2
  exit 1
fi
printf 'relocation_timestamp_era_injective=PASS bc=%q ad=%q\n' "$pg_bc" "$pg_ad"
printf '%s\n' 'relocation_timestamp_era_cross_store=PASS'

pg_authoritative_source="$(pg_sql "SELECT prosrc FROM pg_proc WHERE oid='relocation_evidence.authoritative_digest(uuid,bigint)'::regprocedure;")"
ts_target_source="$(ts_sql "SELECT prosrc FROM pg_proc WHERE oid='relocation_evidence.target_digest(uuid,bigint)'::regprocedure;")"
if [[ "$pg_authoritative_source" != *"canonical_timestamp"* || "$ts_target_source" != *"canonical_timestamp"* ]]; then
  echo "relocation digest path bypasses era-aware canonical_timestamp" >&2
  exit 1
fi
printf '%s\n' 'relocation_digest_uses_era_aware_timestamp=PASS'
