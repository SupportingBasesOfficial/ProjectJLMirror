SET ROLE jlmirror_g8_human_operations_invoker;
INSERT INTO human_operations.alert_acknowledgement(
 tenant_id,acknowledgement_id,alert_id,principal_id,logical_action_id,
 content_hash,authority_snapshot,note
) VALUES (
 'tenant-a','forbidden','alert-a','principal-x','forbidden-action',
 'forbidden-hash','{"current":true}'::jsonb,NULL
);
