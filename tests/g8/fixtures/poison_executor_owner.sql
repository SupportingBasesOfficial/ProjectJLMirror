DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='jlmirror_g8_human_operations_executor'
  ) THEN
    CREATE ROLE jlmirror_g8_human_operations_executor
      NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
END;
$$;
CREATE TABLE public.g8_executor_owned_poison(id INTEGER);
ALTER TABLE public.g8_executor_owned_poison
OWNER TO jlmirror_g8_human_operations_executor;
