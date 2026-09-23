-- Docker entrypoint init script.
-- Runs once when the PostgreSQL data directory is first initialized.
-- Creates the least-privilege application role used by the FastAPI API.
-- Migration/admin authority uses the POSTGRES_USER superuser directly.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'jlmirror_app') THEN
        CREATE ROLE jlmirror_app
            WITH LOGIN PASSWORD 'app_password'
            NOCREATEDB
            NOCREATEROLE
            NOSUPERUSER
            NOREPLICATION;
    END IF;
END
$$;

-- The application role needs to connect and use the schemas created by migrations.
-- Specific table/function grants are issued by the migration scripts themselves
-- (they create executor/invoker roles and grant least-privilege access).
GRANT CONNECT ON DATABASE "jlmirror" TO jlmirror_app;
