\set ON_ERROR_STOP on

CREATE EXTENSION IF NOT EXISTS timescaledb;

DROP SCHEMA IF EXISTS ts_evidence CASCADE;
DROP ROLE IF EXISTS ts_report_a;
DROP ROLE IF EXISTS ts_report_b;
DROP ROLE IF EXISTS ts_runtime;
DROP ROLE IF EXISTS ts_owner;

CREATE ROLE ts_owner
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE ts_runtime
    LOGIN PASSWORD 'runtime-evidence-only'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE ts_report_a
    LOGIN PASSWORD 'report-a-evidence-only'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE ts_report_b
    LOGIN PASSWORD 'report-b-evidence-only'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

CREATE SCHEMA ts_evidence AUTHORIZATION ts_owner;
GRANT USAGE ON SCHEMA ts_evidence TO ts_runtime, ts_report_a, ts_report_b;

CREATE TABLE ts_evidence.capability_probe (
    probe text PRIMARY KEY,
    supported boolean NOT NULL,
    sqlstate text,
    detail text NOT NULL
);
ALTER TABLE ts_evidence.capability_probe OWNER TO ts_owner;

-- ---------------------------------------------------------------------------
-- Profile A: direct pooled rowstore hypertable with PostgreSQL RLS.
-- This profile is valid only for the trusted platform runtime trust class.
-- ---------------------------------------------------------------------------
SET ROLE ts_owner;
CREATE TABLE ts_evidence.rls_history (
    tenant_id uuid NOT NULL,
    observed_at timestamptz NOT NULL,
    metric_definition_id uuid NOT NULL,
    numeric_value numeric NOT NULL
);
SELECT public.create_hypertable(
    'ts_evidence.rls_history',
    'observed_at',
    chunk_time_interval => interval '1 day'
);
ALTER TABLE ts_evidence.rls_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE ts_evidence.rls_history FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_history_tenant_policy
ON ts_evidence.rls_history
USING (
    tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), '')::uuid
)
WITH CHECK (
    tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), '')::uuid
);
RESET ROLE;

GRANT SELECT, INSERT ON ts_evidence.rls_history TO ts_runtime;

-- Seed as the evidence administrator, never as the normal runtime role.
INSERT INTO ts_evidence.rls_history (
    tenant_id, observed_at, metric_definition_id, numeric_value
)
VALUES
    (
        'aaaaaaaa-0000-0000-0000-000000000001'::uuid,
        '2026-08-27T10:00:00Z',
        'bbbbbbbb-0000-0000-0000-000000000001'::uuid,
        10
    ),
    (
        'aaaaaaaa-0000-0000-0000-000000000002'::uuid,
        '2026-08-27T10:00:00Z',
        'bbbbbbbb-0000-0000-0000-000000000002'::uuid,
        20
    );

-- Probe the exact direct pooled RLS + Hypercore/columnstore combination. A
-- rejection is a valid evidence result and must be preserved, not bypassed.
DO $$
DECLARE
    v_chunk regclass;
BEGIN
    BEGIN
        ALTER TABLE ts_evidence.rls_history SET (
            timescaledb.enable_columnstore,
            timescaledb.segmentby = 'tenant_id',
            timescaledb.orderby = 'observed_at DESC'
        );

        SELECT public.show_chunks('ts_evidence.rls_history')
          INTO v_chunk
          LIMIT 1;

        IF v_chunk IS NULL THEN
            RAISE EXCEPTION 'columnstore probe could not resolve a chunk';
        END IF;

        EXECUTE format('CALL public.convert_to_columnstore(%L::regclass)', v_chunk::text);

        INSERT INTO ts_evidence.capability_probe (probe, supported, detail)
        VALUES (
            'direct_rls_plus_columnstore',
            true,
            'Pinned Timescale version accepted conversion; runtime isolation must still be attacked after conversion.'
        );
    EXCEPTION
        WHEN OTHERS THEN
            INSERT INTO ts_evidence.capability_probe (probe, supported, sqlstate, detail)
            VALUES (
                'direct_rls_plus_columnstore',
                false,
                SQLSTATE,
                SQLERRM
            );
    END;
END;
$$;

-- Probe continuous aggregate creation directly over an RLS-enabled source.
DO $$
BEGIN
    BEGIN
        EXECUTE $cagg$
            CREATE MATERIALIZED VIEW ts_evidence.rls_hourly
            WITH (timescaledb.continuous) AS
            SELECT
                tenant_id,
                public.time_bucket(interval '1 hour', observed_at) AS bucket,
                avg(numeric_value) AS avg_value
            FROM ts_evidence.rls_history
            GROUP BY tenant_id, public.time_bucket(interval '1 hour', observed_at)
            WITH NO DATA
        $cagg$;

        INSERT INTO ts_evidence.capability_probe (probe, supported, detail)
        VALUES (
            'direct_rls_plus_continuous_aggregate',
            true,
            'Pinned Timescale version accepted CAGG creation; every exposed relation still requires isolation attack.'
        );
    EXCEPTION
        WHEN OTHERS THEN
            INSERT INTO ts_evidence.capability_probe (probe, supported, sqlstate, detail)
            VALUES (
                'direct_rls_plus_continuous_aggregate',
                false,
                SQLSTATE,
                SQLERRM
            );
    END;
END;
$$;

DROP MATERIALIZED VIEW IF EXISTS ts_evidence.rls_hourly;

-- ---------------------------------------------------------------------------
-- Profile B: mediated pooled query surface.
-- The shared raw/CAGG relations intentionally do not claim row-level isolation;
-- normal reporting principals receive zero direct table/view privilege. Their
-- tenant boundary is a principal mapping outside caller-writable SQL state plus
-- a narrowly scoped fixed-search-path SECURITY DEFINER reader.
-- ---------------------------------------------------------------------------
SET ROLE ts_owner;
CREATE TABLE ts_evidence.shared_history (
    tenant_id uuid NOT NULL,
    observed_at timestamptz NOT NULL,
    metric_definition_id uuid NOT NULL,
    numeric_value numeric NOT NULL
);
SELECT public.create_hypertable(
    'ts_evidence.shared_history',
    'observed_at',
    chunk_time_interval => interval '1 day'
);

CREATE TABLE ts_evidence.report_principal_tenant (
    login_name name PRIMARY KEY,
    tenant_id uuid NOT NULL UNIQUE
);

INSERT INTO ts_evidence.report_principal_tenant (login_name, tenant_id)
VALUES
    ('ts_report_a', 'aaaaaaaa-0000-0000-0000-000000000001'::uuid),
    ('ts_report_b', 'aaaaaaaa-0000-0000-0000-000000000002'::uuid);

INSERT INTO ts_evidence.shared_history (
    tenant_id, observed_at, metric_definition_id, numeric_value
)
VALUES
    (
        'aaaaaaaa-0000-0000-0000-000000000001'::uuid,
        '2026-08-27T10:05:00Z',
        'bbbbbbbb-0000-0000-0000-000000000001'::uuid,
        11
    ),
    (
        'aaaaaaaa-0000-0000-0000-000000000001'::uuid,
        '2026-08-27T10:35:00Z',
        'bbbbbbbb-0000-0000-0000-000000000001'::uuid,
        13
    ),
    (
        'aaaaaaaa-0000-0000-0000-000000000002'::uuid,
        '2026-08-27T10:15:00Z',
        'bbbbbbbb-0000-0000-0000-000000000002'::uuid,
        21
    ),
    (
        'aaaaaaaa-0000-0000-0000-000000000002'::uuid,
        '2026-08-27T10:45:00Z',
        'bbbbbbbb-0000-0000-0000-000000000002'::uuid,
        23
    );

CREATE MATERIALIZED VIEW ts_evidence.shared_hourly
WITH (timescaledb.continuous) AS
SELECT
    tenant_id,
    public.time_bucket(interval '1 hour', observed_at) AS bucket,
    metric_definition_id,
    avg(numeric_value) AS avg_value
FROM ts_evidence.shared_history
GROUP BY
    tenant_id,
    public.time_bucket(interval '1 hour', observed_at),
    metric_definition_id
WITH NO DATA;

CALL public.refresh_continuous_aggregate(
    'ts_evidence.shared_hourly',
    NULL,
    NULL
);

CREATE OR REPLACE FUNCTION ts_evidence.read_hourly()
RETURNS TABLE (
    tenant_id uuid,
    bucket timestamptz,
    metric_definition_id uuid,
    avg_value numeric
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, ts_evidence
AS $function$
    SELECT
        h.tenant_id,
        h.bucket,
        h.metric_definition_id,
        h.avg_value
    FROM ts_evidence.shared_hourly AS h
    JOIN ts_evidence.report_principal_tenant AS p
      ON p.tenant_id = h.tenant_id
    WHERE p.login_name = session_user
    ORDER BY h.bucket, h.metric_definition_id
$function$;

REVOKE ALL ON FUNCTION ts_evidence.read_hourly() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ts_evidence.read_hourly() TO ts_report_a, ts_report_b;
RESET ROLE;

-- Explicitly ensure reporting users have no direct data relation privileges.
REVOKE ALL ON ts_evidence.shared_history FROM PUBLIC, ts_report_a, ts_report_b;
REVOKE ALL ON ts_evidence.shared_hourly FROM PUBLIC, ts_report_a, ts_report_b;
REVOKE ALL ON ts_evidence.report_principal_tenant FROM PUBLIC, ts_report_a, ts_report_b;

SELECT
    current_setting('server_version') AS postgresql_version,
    extversion AS timescaledb_version
FROM pg_extension
WHERE extname = 'timescaledb';

SELECT probe, supported, coalesce(sqlstate, '') AS sqlstate, detail
FROM ts_evidence.capability_probe
ORDER BY probe;
