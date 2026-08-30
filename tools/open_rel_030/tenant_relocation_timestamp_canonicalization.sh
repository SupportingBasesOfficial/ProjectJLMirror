# ---------------------------------------------------------------------------
# Canonical typed-scalar hardening.
#
# PostgreSQL timestamptz supports BC dates and the non-finite sentinels
# `infinity` / `-infinity`. PostgreSQL unconstrained numeric also supports
# `NaN`, `Infinity` and `-Infinity`. Canonical representations must therefore be
# total and injective over the full supported evidence domain before values are
# passed into canonical_field().
# ---------------------------------------------------------------------------
pg_sql "
  CREATE OR REPLACE FUNCTION relocation_evidence.canonical_timestamp(p_value timestamptz)
  RETURNS text LANGUAGE sql IMMUTABLE STRICT
  SET search_path=pg_catalog
  AS \$\$
    SELECT CASE
      WHEN p_value = '-infinity'::timestamptz THEN '-infinity'
      WHEN p_value = 'infinity'::timestamptz THEN 'infinity'
      ELSE to_char(
        p_value AT TIME ZONE 'UTC',
        'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\" AD'
      )
    END
  \$\$;
  REVOKE ALL ON FUNCTION relocation_evidence.canonical_timestamp(timestamptz) FROM PUBLIC;

  CREATE OR REPLACE FUNCTION relocation_evidence.canonical_numeric(p_value numeric)
  RETURNS text LANGUAGE sql IMMUTABLE STRICT
  SET search_path=pg_catalog
  AS \$\$
    SELECT CASE
      WHEN p_value = '-Infinity'::numeric THEN '-Infinity'
      WHEN p_value = 'Infinity'::numeric THEN 'Infinity'
      WHEN p_value = 'NaN'::numeric THEN 'NaN'
      ELSE trim_scale(p_value)::text
    END
  \$\$;
  REVOKE ALL ON FUNCTION relocation_evidence.canonical_numeric(numeric) FROM PUBLIC;

  CREATE OR REPLACE FUNCTION relocation_evidence.authoritative_digest(p_tenant uuid,p_fence bigint)
  RETURNS text LANGUAGE sql STABLE
  SET search_path=pg_catalog,relocation_evidence
  AS \$\$
    SELECT encode(public.digest(convert_to(coalesce(string_agg(
      relocation_evidence.canonical_field(accepted_ordinal::text) ||
      relocation_evidence.canonical_field(observation_id) ||
      relocation_evidence.canonical_field(metric_definition_id::text) ||
      relocation_evidence.canonical_field(relocation_evidence.canonical_timestamp(observed_at)) ||
      relocation_evidence.canonical_field(relocation_evidence.canonical_numeric(numeric_value)),
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
    SELECT CASE
      WHEN p_value = '-infinity'::timestamptz THEN '-infinity'
      WHEN p_value = 'infinity'::timestamptz THEN 'infinity'
      ELSE to_char(
        p_value AT TIME ZONE 'UTC',
        'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\" AD'
      )
    END
  \$\$;
  ALTER FUNCTION relocation_evidence.canonical_timestamp(timestamptz) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.canonical_timestamp(timestamptz) FROM PUBLIC;

  CREATE OR REPLACE FUNCTION relocation_evidence.canonical_numeric(p_value numeric)
  RETURNS text LANGUAGE sql IMMUTABLE STRICT SECURITY DEFINER
  SET search_path=pg_catalog
  AS \$\$
    SELECT CASE
      WHEN p_value = '-Infinity'::numeric THEN '-Infinity'
      WHEN p_value = 'Infinity'::numeric THEN 'Infinity'
      WHEN p_value = 'NaN'::numeric THEN 'NaN'
      ELSE trim_scale(p_value)::text
    END
  \$\$;
  ALTER FUNCTION relocation_evidence.canonical_numeric(numeric) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.canonical_numeric(numeric) FROM PUBLIC;

  CREATE OR REPLACE FUNCTION relocation_evidence.target_digest(p_tenant uuid,p_fence bigint)
  RETURNS text LANGUAGE sql STABLE SECURITY DEFINER
  SET search_path=pg_catalog,relocation_evidence
  AS \$\$
    SELECT encode(public.digest(convert_to(coalesce(string_agg(
      relocation_evidence.canonical_field(accepted_ordinal::text) ||
      relocation_evidence.canonical_field(observation_id) ||
      relocation_evidence.canonical_field(metric_definition_id::text) ||
      relocation_evidence.canonical_field(relocation_evidence.canonical_timestamp(observed_at)) ||
      relocation_evidence.canonical_field(relocation_evidence.canonical_numeric(numeric_value)),
      '' ORDER BY accepted_ordinal,observation_id
    ),''),'UTF8'),'sha256'),'hex')
    FROM relocation_evidence.target_history
    WHERE tenant_id=p_tenant AND accepted_ordinal<=p_fence
  \$\$;
  ALTER FUNCTION relocation_evidence.target_digest(uuid,bigint) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.target_digest(uuid,bigint) FROM PUBLIC;
" >/dev/null

# Finite BC/AD timestamp injectivity and cross-store equivalence.
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

# Non-finite timestamp sentinels must remain explicit rather than becoming NULL.
pg_neg_inf="$(pg_sql "SELECT relocation_evidence.canonical_timestamp('-infinity'::timestamptz);")"
pg_pos_inf="$(pg_sql "SELECT relocation_evidence.canonical_timestamp('infinity'::timestamptz);")"
ts_neg_inf="$(ts_sql "SELECT relocation_evidence.canonical_timestamp('-infinity'::timestamptz);")"
ts_pos_inf="$(ts_sql "SELECT relocation_evidence.canonical_timestamp('infinity'::timestamptz);")"

if [[ -z "$pg_neg_inf" || -z "$pg_pos_inf" || -z "$ts_neg_inf" || -z "$ts_pos_inf" ]]; then
  echo "canonical relocation timestamp returned empty/NULL non-finite representation" >&2
  exit 1
fi
assert_exact "relocation_timestamp_negative_infinity_canonical" "-infinity" "$pg_neg_inf"
assert_exact "relocation_timestamp_positive_infinity_canonical" "infinity" "$pg_pos_inf"
if [[ "$pg_neg_inf" == "$pg_pos_inf" || "$ts_neg_inf" == "$ts_pos_inf" ]]; then
  echo "canonical relocation timestamp collapsed infinity signs" >&2
  exit 1
fi
if [[ "$pg_neg_inf" != "$ts_neg_inf" || "$pg_pos_inf" != "$ts_pos_inf" ]]; then
  printf 'non-finite canonical timestamp cross-store mismatch pg_neg=%q ts_neg=%q pg_pos=%q ts_pos=%q\n' \
    "$pg_neg_inf" "$ts_neg_inf" "$pg_pos_inf" "$ts_pos_inf" >&2
  exit 1
fi
printf '%s\n' 'relocation_timestamp_nonfinite_cross_store=PASS'

pg_neg_field="$(pg_sql "SELECT relocation_evidence.canonical_field(relocation_evidence.canonical_timestamp('-infinity'::timestamptz));")"
pg_pos_field="$(pg_sql "SELECT relocation_evidence.canonical_field(relocation_evidence.canonical_timestamp('infinity'::timestamptz));")"
ts_neg_field="$(ts_sql "SELECT relocation_evidence.canonical_field(relocation_evidence.canonical_timestamp('-infinity'::timestamptz));")"
ts_pos_field="$(ts_sql "SELECT relocation_evidence.canonical_field(relocation_evidence.canonical_timestamp('infinity'::timestamptz));")"
if [[ -z "$pg_neg_field" || -z "$pg_pos_field" || "$pg_neg_field" == "$pg_pos_field" ]]; then
  echo "non-finite timestamp field framing is absent or ambiguous" >&2
  exit 1
fi
if [[ "$pg_neg_field" != "$ts_neg_field" || "$pg_pos_field" != "$ts_pos_field" ]]; then
  echo "non-finite timestamp field framing differs across stores" >&2
  exit 1
fi

pg_neg_digest="$(pg_sql "SELECT encode(public.digest(convert_to(relocation_evidence.canonical_field(relocation_evidence.canonical_timestamp('-infinity'::timestamptz)),'UTF8'),'sha256'),'hex');")"
pg_pos_digest="$(pg_sql "SELECT encode(public.digest(convert_to(relocation_evidence.canonical_field(relocation_evidence.canonical_timestamp('infinity'::timestamptz)),'UTF8'),'sha256'),'hex');")"
ts_neg_digest="$(ts_sql "SELECT encode(public.digest(convert_to(relocation_evidence.canonical_field(relocation_evidence.canonical_timestamp('-infinity'::timestamptz)),'UTF8'),'sha256'),'hex');")"
ts_pos_digest="$(ts_sql "SELECT encode(public.digest(convert_to(relocation_evidence.canonical_field(relocation_evidence.canonical_timestamp('infinity'::timestamptz)),'UTF8'),'sha256'),'hex');")"
if [[ "$pg_neg_digest" == "$pg_pos_digest" || "$ts_neg_digest" == "$ts_pos_digest" ]]; then
  echo "non-finite timestamp digests are not injective" >&2
  exit 1
fi
if [[ "$pg_neg_digest" != "$ts_neg_digest" || "$pg_pos_digest" != "$ts_pos_digest" ]]; then
  echo "non-finite timestamp digest differs across stores" >&2
  exit 1
fi
printf '%s\n' 'relocation_timestamp_nonfinite_digest_injective=PASS'

# Unconstrained numeric special values are explicit canonical facts as well.
pg_num_nan="$(pg_sql "SELECT relocation_evidence.canonical_numeric('NaN'::numeric);")"
pg_num_pos="$(pg_sql "SELECT relocation_evidence.canonical_numeric('Infinity'::numeric);")"
pg_num_neg="$(pg_sql "SELECT relocation_evidence.canonical_numeric('-Infinity'::numeric);")"
pg_num_finite="$(pg_sql "SELECT relocation_evidence.canonical_numeric('1.2300'::numeric);")"
ts_num_nan="$(ts_sql "SELECT relocation_evidence.canonical_numeric('NaN'::numeric);")"
ts_num_pos="$(ts_sql "SELECT relocation_evidence.canonical_numeric('Infinity'::numeric);")"
ts_num_neg="$(ts_sql "SELECT relocation_evidence.canonical_numeric('-Infinity'::numeric);")"
ts_num_finite="$(ts_sql "SELECT relocation_evidence.canonical_numeric('1.2300'::numeric);")"

assert_exact "relocation_numeric_nan_canonical" "NaN" "$pg_num_nan"
assert_exact "relocation_numeric_positive_infinity_canonical" "Infinity" "$pg_num_pos"
assert_exact "relocation_numeric_negative_infinity_canonical" "-Infinity" "$pg_num_neg"
assert_exact "relocation_numeric_finite_scale_canonical" "1.23" "$pg_num_finite"
if [[ "$pg_num_nan" != "$ts_num_nan" || "$pg_num_pos" != "$ts_num_pos" || "$pg_num_neg" != "$ts_num_neg" || "$pg_num_finite" != "$ts_num_finite" ]]; then
  echo "canonical numeric differs across PostgreSQL and Timescale authorities" >&2
  exit 1
fi
if [[ -z "$pg_num_nan" || -z "$pg_num_pos" || -z "$pg_num_neg" || "$pg_num_nan" == "$pg_num_pos" || "$pg_num_nan" == "$pg_num_neg" || "$pg_num_pos" == "$pg_num_neg" ]]; then
  echo "numeric special-value canonicalization is absent or ambiguous" >&2
  exit 1
fi
printf '%s\n' 'relocation_numeric_special_values_cross_store=PASS'

pg_num_nan_field="$(pg_sql "SELECT relocation_evidence.canonical_field(relocation_evidence.canonical_numeric('NaN'::numeric));")"
pg_num_pos_field="$(pg_sql "SELECT relocation_evidence.canonical_field(relocation_evidence.canonical_numeric('Infinity'::numeric));")"
pg_num_neg_field="$(pg_sql "SELECT relocation_evidence.canonical_field(relocation_evidence.canonical_numeric('-Infinity'::numeric));")"
ts_num_nan_field="$(ts_sql "SELECT relocation_evidence.canonical_field(relocation_evidence.canonical_numeric('NaN'::numeric));")"
ts_num_pos_field="$(ts_sql "SELECT relocation_evidence.canonical_field(relocation_evidence.canonical_numeric('Infinity'::numeric));")"
ts_num_neg_field="$(ts_sql "SELECT relocation_evidence.canonical_field(relocation_evidence.canonical_numeric('-Infinity'::numeric));")"
if [[ "$pg_num_nan_field" != "$ts_num_nan_field" || "$pg_num_pos_field" != "$ts_num_pos_field" || "$pg_num_neg_field" != "$ts_num_neg_field" ]]; then
  echo "numeric special-value framing differs across stores" >&2
  exit 1
fi

pg_num_nan_digest="$(pg_sql "SELECT encode(public.digest(convert_to(relocation_evidence.canonical_field(relocation_evidence.canonical_numeric('NaN'::numeric)),'UTF8'),'sha256'),'hex');")"
pg_num_pos_digest="$(pg_sql "SELECT encode(public.digest(convert_to(relocation_evidence.canonical_field(relocation_evidence.canonical_numeric('Infinity'::numeric)),'UTF8'),'sha256'),'hex');")"
pg_num_neg_digest="$(pg_sql "SELECT encode(public.digest(convert_to(relocation_evidence.canonical_field(relocation_evidence.canonical_numeric('-Infinity'::numeric)),'UTF8'),'sha256'),'hex');")"
ts_num_nan_digest="$(ts_sql "SELECT encode(public.digest(convert_to(relocation_evidence.canonical_field(relocation_evidence.canonical_numeric('NaN'::numeric)),'UTF8'),'sha256'),'hex');")"
ts_num_pos_digest="$(ts_sql "SELECT encode(public.digest(convert_to(relocation_evidence.canonical_field(relocation_evidence.canonical_numeric('Infinity'::numeric)),'UTF8'),'sha256'),'hex');")"
ts_num_neg_digest="$(ts_sql "SELECT encode(public.digest(convert_to(relocation_evidence.canonical_field(relocation_evidence.canonical_numeric('-Infinity'::numeric)),'UTF8'),'sha256'),'hex');")"
if [[ "$pg_num_nan_digest" == "$pg_num_pos_digest" || "$pg_num_nan_digest" == "$pg_num_neg_digest" || "$pg_num_pos_digest" == "$pg_num_neg_digest" ]]; then
  echo "numeric special-value digests are not injective" >&2
  exit 1
fi
if [[ "$pg_num_nan_digest" != "$ts_num_nan_digest" || "$pg_num_pos_digest" != "$ts_num_pos_digest" || "$pg_num_neg_digest" != "$ts_num_neg_digest" ]]; then
  echo "numeric special-value digest differs across stores" >&2
  exit 1
fi
printf '%s\n' 'relocation_numeric_special_value_digest_injective=PASS'

pg_authoritative_source="$(pg_sql "SELECT prosrc FROM pg_proc WHERE oid='relocation_evidence.authoritative_digest(uuid,bigint)'::regprocedure;")"
ts_target_source="$(ts_sql "SELECT prosrc FROM pg_proc WHERE oid='relocation_evidence.target_digest(uuid,bigint)'::regprocedure;")"
if [[ "$pg_authoritative_source" != *"canonical_timestamp"* || "$ts_target_source" != *"canonical_timestamp"* ]]; then
  echo "relocation digest path bypasses total canonical_timestamp" >&2
  exit 1
fi
if [[ "$pg_authoritative_source" != *"canonical_numeric"* || "$ts_target_source" != *"canonical_numeric"* ]]; then
  echo "relocation digest path bypasses total canonical_numeric" >&2
  exit 1
fi
printf '%s\n' 'relocation_digest_uses_total_timestamp_canonicalizer=PASS'
printf '%s\n' 'relocation_digest_uses_total_numeric_canonicalizer=PASS'
