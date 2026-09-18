CREATE SCHEMA IF NOT EXISTS human_operations;
CREATE FUNCTION human_operations.g8_alert_human_operations(TEXT,TEXT)
RETURNS JSONB
LANGUAGE sql
AS $$ SELECT '{}'::jsonb $$;
