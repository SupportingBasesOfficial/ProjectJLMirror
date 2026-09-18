CREATE ROLE g7_unexpected_execute_grantee NOLOGIN;
ALTER DEFAULT PRIVILEGES
GRANT EXECUTE ON FUNCTIONS TO g7_unexpected_execute_grantee;
