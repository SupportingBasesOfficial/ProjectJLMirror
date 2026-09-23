SET session_replication_role=replica;
UPDATE monitoring.monitoring_source
   SET operational_evidence_state='stale'
 WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a';
SET session_replication_role=origin;
