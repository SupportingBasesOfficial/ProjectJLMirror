CREATE ROLE g9_unexpected_execute_grantee NOLOGIN;
ALTER DEFAULT PRIVILEGES
GRANT EXECUTE ON FUNCTIONS TO g9_unexpected_execute_grantee;
