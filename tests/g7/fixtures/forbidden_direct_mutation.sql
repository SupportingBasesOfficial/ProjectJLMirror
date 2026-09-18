SET ROLE jlmirror_g7_alerting_invoker;
INSERT INTO alerting.alert_policy(tenant_id,policy_id)
VALUES ('tenant-x','forbidden-direct-write');
