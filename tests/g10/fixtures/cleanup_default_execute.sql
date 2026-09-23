ALTER DEFAULT PRIVILEGES
REVOKE EXECUTE ON FUNCTIONS FROM g10_unexpected_execute_grantee;
DROP ROLE g10_unexpected_execute_grantee;
