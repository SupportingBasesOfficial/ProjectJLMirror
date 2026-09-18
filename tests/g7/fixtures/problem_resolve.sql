SET session_replication_role=replica;
UPDATE monitoring.monitoring_problem
   SET problem_state='resolved',
       resolved_at=transaction_timestamp(),
       projection_revision=8,
       updated_at=transaction_timestamp()
 WHERE tenant_id='tenant-a' AND problem_id='problem-a';
SET session_replication_role=origin;
