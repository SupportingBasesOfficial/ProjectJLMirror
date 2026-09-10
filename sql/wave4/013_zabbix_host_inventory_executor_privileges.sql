-- Finalize least-privilege execution grants for guarded host-inventory functions.
BEGIN;
GRANT SELECT ON monitoring.monitoring_source_generation,
    monitoring.monitoring_source_validation_evidence
TO jlmirror_wave4_host_inventory_executor;

GRANT SELECT, UPDATE ON monitoring.monitoring_source
TO jlmirror_wave4_recovery_authority;

REVOKE CREATE ON SCHEMA monitoring FROM jlmirror_wave4_host_inventory_executor, jlmirror_wave4_recovery_authority;
COMMIT;
