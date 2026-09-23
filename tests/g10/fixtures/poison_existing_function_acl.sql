CREATE ROLE g10_existing_function_grantee NOLOGIN;
CREATE SCHEMA IF NOT EXISTS itsm;
CREATE FUNCTION itsm.g10_get_incident(TEXT,TEXT)
RETURNS JSONB
LANGUAGE sql
AS $$ SELECT '{}'::jsonb $$;
GRANT EXECUTE ON FUNCTION itsm.g10_get_incident(TEXT,TEXT)
TO g10_existing_function_grantee;
