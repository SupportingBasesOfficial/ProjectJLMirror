\set ON_ERROR_STOP on
\timing on

-- Expand the exact mediated profile already proven for tenant isolation. These
-- are bounded evidence measurements, not production SLO thresholds.
SET ROLE ts_owner;

CREATE TABLE ts_evidence.capacity_measurement (
    phase text PRIMARY KEY,
    measured_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    raw_relation_bytes bigint NOT NULL,
    cagg_relation_bytes bigint NOT NULL,
    row_count bigint NOT NULL
);

INSERT INTO ts_evidence.shared_history (
    tenant_id,
    observed_at,
    metric_definition_id,
    numeric_value
)
SELECT
    CASE WHEN g % 2 = 0
        THEN 'aaaaaaaa-0000-0000-0000-000000000001'::uuid
        ELSE 'aaaaaaaa-0000-0000-0000-000000000002'::uuid
    END,
    '2026-08-24T00:00:00Z'::timestamptz + make_interval(secs => g * 2),
    CASE WHEN g % 2 = 0
        THEN 'bbbbbbbb-0000-0000-0000-000000000001'::uuid
        ELSE 'bbbbbbbb-0000-0000-0000-000000000002'::uuid
    END,
    (g % 1000)::numeric / 10
FROM generate_series(1, 100000) AS g;

CALL public.refresh_continuous_aggregate(
    'ts_evidence.shared_hourly',
    NULL,
    NULL
);

INSERT INTO ts_evidence.capacity_measurement (
    phase, raw_relation_bytes, cagg_relation_bytes, row_count
)
SELECT
    'rowstore',
    public.hypertable_size('ts_evidence.shared_history'),
    public.hypertable_size('ts_evidence.shared_hourly'),
    count(*)
FROM ts_evidence.shared_history;

ALTER TABLE ts_evidence.shared_history SET (
    timescaledb.enable_columnstore,
    timescaledb.segmentby = 'tenant_id',
    timescaledb.orderby = 'observed_at DESC'
);

-- Convert every current raw-history chunk to columnstore. The reporting roles
-- still have no direct privilege on this relation; columnstore is not asked to
-- provide RLS it does not support.
SELECT format(
    'CALL public.convert_to_columnstore(%L::regclass);',
    chunk::text
)
FROM public.show_chunks('ts_evidence.shared_history') AS chunk
ORDER BY chunk::text
\gexec

INSERT INTO ts_evidence.capacity_measurement (
    phase, raw_relation_bytes, cagg_relation_bytes, row_count
)
SELECT
    'columnstore',
    public.hypertable_size('ts_evidence.shared_history'),
    public.hypertable_size('ts_evidence.shared_hourly'),
    count(*)
FROM ts_evidence.shared_history;

-- Policies are created under the narrow object owner. Their foreground runs
-- are invoked separately by the shell harness so failures cannot be hidden.
CALL public.add_columnstore_policy(
    'ts_evidence.shared_history',
    INTERVAL '12 hours'
);

SELECT public.add_continuous_aggregate_policy(
    'ts_evidence.shared_hourly',
    start_offset => INTERVAL '14 days',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 hour'
);

RESET ROLE;

-- Capture all relevant jobs and prove they are owned by the object owner rather
-- than a tenant-facing/reporting role.
CREATE TABLE ts_evidence.job_evidence AS
SELECT
    job_id,
    application_name,
    schedule_interval,
    proc_schema,
    proc_name,
    owner,
    hypertable_schema,
    hypertable_name,
    config::text AS config
FROM timescaledb_information.jobs
WHERE hypertable_schema = 'ts_evidence'
  AND hypertable_name IN ('shared_history', 'shared_hourly');

DO $$
DECLARE
    v_bad bigint;
    v_jobs bigint;
BEGIN
    SELECT count(*) INTO v_jobs FROM ts_evidence.job_evidence;
    IF v_jobs < 2 THEN
        RAISE EXCEPTION 'expected at least columnstore + CAGG jobs, found %', v_jobs;
    END IF;

    SELECT count(*) INTO v_bad
      FROM ts_evidence.job_evidence
     WHERE owner::text IN ('ts_report_a', 'ts_report_b', 'ts_runtime');
    IF v_bad <> 0 THEN
        RAISE EXCEPTION 'tenant-facing/runtime role unexpectedly owns Timescale background job(s): %', v_bad;
    END IF;
END;
$$;

SELECT
    'timescale_capacity_measurement' AS result,
    phase,
    raw_relation_bytes,
    cagg_relation_bytes,
    row_count
FROM ts_evidence.capacity_measurement
ORDER BY measured_at;

SELECT
    'timescale_job' AS result,
    job_id,
    proc_schema,
    proc_name,
    owner,
    hypertable_schema,
    hypertable_name
FROM ts_evidence.job_evidence
ORDER BY job_id;
