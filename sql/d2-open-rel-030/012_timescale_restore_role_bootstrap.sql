\set ON_ERROR_STOP on

-- Evidence-only deterministic role bootstrap for a genuinely fresh Timescale
-- cluster. This exists to prove that database restore does not depend on the
-- source cluster retaining global role state. Production role provisioning is
-- still a deployment/platform concern and is not selected by this spike.

CREATE ROLE ts_owner
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

CREATE ROLE ts_automation_owner
    LOGIN PASSWORD NULL
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

CREATE ROLE ts_runtime
    LOGIN PASSWORD 'runtime-evidence-only'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

CREATE ROLE ts_report_a
    LOGIN PASSWORD 'report-a-evidence-only'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

CREATE ROLE ts_report_b
    LOGIN PASSWORD 'report-b-evidence-only'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

DO $$
DECLARE
    v_bad bigint;
    v_memberships bigint;
    v_automation_password boolean;
BEGIN
    SELECT count(*) INTO v_bad
      FROM pg_roles
     WHERE rolname IN ('ts_owner','ts_automation_owner','ts_runtime','ts_report_a','ts_report_b')
       AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolinherit OR rolbypassrls);
    IF v_bad <> 0 THEN
        RAISE EXCEPTION 'fresh-cluster bootstrap created overprivileged role(s): %', v_bad;
    END IF;

    SELECT count(*) INTO v_memberships
      FROM pg_auth_members m
      JOIN pg_roles member_role ON member_role.oid = m.member
      JOIN pg_roles granted_role ON granted_role.oid = m.roleid
     WHERE member_role.rolname IN ('ts_runtime','ts_report_a','ts_report_b')
       AND granted_role.rolname IN ('ts_owner','ts_automation_owner');
    IF v_memberships <> 0 THEN
        RAISE EXCEPTION 'fresh-cluster bootstrap created owner membership(s): %', v_memberships;
    END IF;

    SELECT rolpassword IS NULL INTO v_automation_password
      FROM pg_authid
     WHERE rolname='ts_automation_owner';
    IF v_automation_password IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'automation owner unexpectedly has a password credential';
    END IF;
END;
$$;
