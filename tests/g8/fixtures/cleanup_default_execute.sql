ALTER DEFAULT PRIVILEGES
REVOKE EXECUTE ON FUNCTIONS FROM g8_unexpected_execute_grantee;
DROP ROLE g8_unexpected_execute_grantee;
