CREATE ROLE g10_unexpected_execute_grantee NOLOGIN;
ALTER DEFAULT PRIVILEGES
GRANT EXECUTE ON FUNCTIONS TO g10_unexpected_execute_grantee;
