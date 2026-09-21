SET ROLE jlmirror_g10_itsm_app_invoker;
INSERT INTO itsm.incident_comment(
  tenant_id,incident_comment_id,incident_id,body,logical_action_id,
  actor_principal_id,authority_snapshot
) VALUES (
  'tenant-a','forbidden-comment','forbidden-incident','x','op','actor-a','{}'::jsonb
);
