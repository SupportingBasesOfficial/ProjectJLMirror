DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='jlmirror_g10_itsm_executor'
  ) THEN
    CREATE ROLE jlmirror_g10_itsm_executor
      NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
END;
$$;
CREATE TABLE public.g10_executor_owned_poison(id INTEGER);
ALTER TABLE public.g10_executor_owned_poison OWNER TO jlmirror_g10_itsm_executor;
