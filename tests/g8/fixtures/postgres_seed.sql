SET session_replication_role=replica;

INSERT INTO monitoring.monitoring_resource(
 tenant_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,
 resource_kind,provider_object_kind,provider_external_ref,display_name,
 scope_state,scope_projection_revision,scope_evidence_state,presence_state,
 presence_evidence_state,last_observed_at,last_confirmed_present_at,removed_at,
 latest_provider_evidence_id
) VALUES
(
 'tenant-a','resource-a','source-a','generation-a',
 'host','zabbix_host','101','Resource A',
 'in_scope',1,'current','present','current',
 transaction_timestamp(),transaction_timestamp(),NULL,NULL
),
(
 'tenant-b','resource-b','source-b','generation-b',
 'host','zabbix_host','201','Resource B',
 'in_scope',1,'current','present','current',
 transaction_timestamp(),transaction_timestamp(),NULL,NULL
);

INSERT INTO alerting.alert(
 tenant_id,alert_id,policy_id,policy_version,source_kind,source_subject_id,
 monitoring_source_id,monitoring_resource_id,source_instance_generation,
 source_occurrence_revision,current_source_revision,lifecycle_state,
 source_evidence_summary,opened_at,resolved_at,updated_at
) VALUES
(
 'tenant-a','alert-a','policy-a',1,'monitoring_problem','problem-a',
 'source-a','resource-a','generation-a',
 1,1,'active','{"fixture":"g8"}'::jsonb,
 transaction_timestamp()-interval '10 minutes',NULL,transaction_timestamp()
),
(
 'tenant-b','alert-b','policy-b',1,'monitoring_health_projection','resource-b',
 'source-b','resource-b','generation-b',
 1,1,'active','{"fixture":"g8"}'::jsonb,
 transaction_timestamp()-interval '10 minutes',NULL,transaction_timestamp()
);

SET session_replication_role=origin;
