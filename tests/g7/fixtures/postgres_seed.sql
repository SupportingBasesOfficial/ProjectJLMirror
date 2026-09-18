SET session_replication_role=replica;

INSERT INTO monitoring.monitoring_source(
 tenant_id,monitoring_source_id,provider_scope_tenant_binding_id,provider_profile,
 active_source_instance_generation,configuration_revision,scope_revision,display_name,
 credential_binding_ref,configured_provider_scope,operational_evidence_state,
 replacement_candidate_ref,last_successful_sync_at,last_attempt_at,last_sync_operation_id
) VALUES
(
 'tenant-a','source-a','binding-a','zabbix','generation-a',1,1,'Source A',
 'credential-a','{"host_group_refs":["10"]}'::jsonb,'current',
 NULL,transaction_timestamp(),transaction_timestamp(),'sync-g7-a'
),
(
 'tenant-b','source-b','binding-b','zabbix','generation-b',1,1,'Source B',
 'credential-b','{"host_group_refs":["20"]}'::jsonb,'current',
 NULL,transaction_timestamp(),transaction_timestamp(),'sync-g7-b'
);

INSERT INTO monitoring.monitoring_source_generation(
 tenant_id,monitoring_source_id,source_instance_generation,provider_profile,
 provider_instance_ref,provider_base_url
) VALUES
 ('tenant-a','source-a','generation-a','zabbix','provider-a','https://zabbix-a.invalid'),
 ('tenant-a','source-a','generation-old','zabbix','provider-a-old','https://zabbix-old.invalid'),
 ('tenant-b','source-b','generation-b','zabbix','provider-b','https://zabbix-b.invalid');

INSERT INTO monitoring.monitoring_resource(
 tenant_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,
 resource_kind,provider_object_kind,provider_external_ref,display_name,
 scope_state,scope_projection_revision,scope_evidence_state,presence_state,
 presence_evidence_state,last_observed_at,last_confirmed_present_at,removed_at,
 latest_provider_evidence_id
) VALUES
(
 'tenant-a','resource-a','source-a','generation-a','host','zabbix_host','101','Host A',
 'in_scope',1,'current','present','current',
 transaction_timestamp(),transaction_timestamp(),NULL,NULL
),
(
 'tenant-b','resource-b','source-b','generation-b','host','zabbix_host','201','Host B',
 'in_scope',1,'current','present','current',
 transaction_timestamp(),transaction_timestamp(),NULL,NULL
);

INSERT INTO monitoring.monitoring_problem_provider_binding(
 tenant_id,problem_id,monitoring_source_id,source_instance_generation,
 monitoring_resource_id,provider_profile,provider_external_ref,provider_trigger_ref
) VALUES
 ('tenant-a','problem-a','source-a','generation-a','resource-a','zabbix','9001','trigger-a'),
 ('tenant-b','problem-b','source-b','generation-b','resource-b','zabbix','9002','trigger-b');

INSERT INTO monitoring.monitoring_problem(
 tenant_id,problem_id,monitoring_source_id,source_instance_generation,
 monitoring_resource_id,problem_state,severity_class,summary,opened_at,resolved_at,
 last_confirmed_at,evidence_state,projection_revision,problem_poll_epoch,
 problem_poll_generation,provider_metadata
) VALUES
(
 'tenant-a','problem-a','source-a','generation-a','resource-a',
 'active','critical','Problem A',transaction_timestamp()-interval '10 minutes',
 NULL,transaction_timestamp(),'current',7,1,1,'{}'::jsonb
),
(
 'tenant-b','problem-b','source-b','generation-b','resource-b',
 'active','critical','Problem B',transaction_timestamp()-interval '10 minutes',
 NULL,transaction_timestamp(),'current',4,1,1,'{}'::jsonb
);

INSERT INTO monitoring.health_projection(
 tenant_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,
 health_class,evidence_state,projection_revision,last_changed_at,last_evidence_at,
 problem_snapshot_evidence_id,reason_refs
) VALUES
(
 'tenant-a','resource-a','source-a','generation-a','degraded','current',11,
 transaction_timestamp()-interval '5 minutes',transaction_timestamp(),NULL,'[]'::jsonb
),
(
 'tenant-b','resource-b','source-b','generation-b','unhealthy','current',8,
 transaction_timestamp()-interval '5 minutes',transaction_timestamp(),NULL,'[]'::jsonb
);

SET session_replication_role=origin;
