-- Pre-stage dedicated NOLOGIN/NOBYPASSRLS roles used by recovery authority hardening.
BEGIN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_host_inventory_executor') THEN
        CREATE ROLE jlmirror_wave4_host_inventory_executor NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_recovery_authority') THEN
        CREATE ROLE jlmirror_wave4_recovery_authority NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END;
$$;
GRANT USAGE, CREATE ON SCHEMA monitoring TO jlmirror_wave4_host_inventory_executor, jlmirror_wave4_recovery_authority;
COMMIT;
