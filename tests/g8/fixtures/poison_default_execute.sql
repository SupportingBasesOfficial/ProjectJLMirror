CREATE ROLE g8_unexpected_execute_grantee NOLOGIN;
ALTER DEFAULT PRIVILEGES
GRANT EXECUTE ON FUNCTIONS TO g8_unexpected_execute_grantee;
