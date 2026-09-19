CREATE ROLE g9_existing_function_grantee NOLOGIN;
CREATE SCHEMA IF NOT EXISTS notification;
CREATE FUNCTION notification.g9_get_intent(TEXT,TEXT)
RETURNS JSONB
LANGUAGE sql
AS $$ SELECT '{}'::jsonb $$;
GRANT EXECUTE ON FUNCTION notification.g9_get_intent(TEXT,TEXT)
TO g9_existing_function_grantee;
