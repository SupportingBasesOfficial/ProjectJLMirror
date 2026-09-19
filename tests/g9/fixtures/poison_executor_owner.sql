DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='jlmirror_g9_notification_executor'
  ) THEN
    CREATE ROLE jlmirror_g9_notification_executor
      NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
END;
$$;
CREATE TABLE public.g9_executor_owned_poison(id INTEGER);
ALTER TABLE public.g9_executor_owned_poison
OWNER TO jlmirror_g9_notification_executor;
