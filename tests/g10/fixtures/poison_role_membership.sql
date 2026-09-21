DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_g10_itsm_executor') THEN
    CREATE ROLE jlmirror_g10_itsm_executor
      NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='g10_membership_poison') THEN
    CREATE ROLE g10_membership_poison LOGIN;
  END IF;
END;
$$;
GRANT jlmirror_g10_itsm_executor TO g10_membership_poison;
