SET session_replication_role=replica;
UPDATE monitoring.health_projection
   SET health_class='unhealthy',
       projection_revision=10,
       last_changed_at=transaction_timestamp(),
       last_evidence_at=transaction_timestamp(),
       updated_at=transaction_timestamp()
 WHERE tenant_id='tenant-b'
   AND monitoring_resource_id='resource-b'
   AND source_instance_generation='generation-b';
SET session_replication_role=origin;
