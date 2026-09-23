SET session_replication_role=replica;
UPDATE alerting.alert
   SET lifecycle_state='resolved',
       resolved_at=transaction_timestamp(),
       current_source_revision=2,
       updated_at=transaction_timestamp()
 WHERE tenant_id='tenant-a' AND alert_id='alert-a';
SET session_replication_role=origin;
