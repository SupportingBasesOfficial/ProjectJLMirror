-- G6 PostgreSQL conformance fixture only.
-- This file materializes accepted Wave 4 owner-state and invokes the accepted
-- publication trigger functions. It is not part of the G6 product runtime.

SET session_replication_role=replica;

INSERT INTO monitoring.monitoring_source(
 tenant_id,monitoring_source_id,provider_scope_tenant_binding_id,provider_profile,
 active_source_instance_generation,configuration_revision,scope_revision,display_name,
 credential_binding_ref,configured_provider_scope,operational_evidence_state,
 replacement_candidate_ref,last_successful_sync_at,last_attempt_at,last_sync_operation_id
) VALUES (
 'tenant-a','source-a','binding-a','zabbix','generation-a',1,1,'Source A',
 'credential-a','{"host_group_refs":["10"]}'::jsonb,'current',
 NULL,transaction_timestamp(),transaction_timestamp(),'sync-fixture'
);

INSERT INTO monitoring.monitoring_source_generation(
 tenant_id,monitoring_source_id,source_instance_generation,provider_profile,
 provider_instance_ref,provider_base_url
) VALUES
 ('tenant-a','source-a','generation-a','zabbix','provider-a','https://zabbix.example.test'),
 ('tenant-a','source-a','generation-old','zabbix','provider-a-old','https://zabbix-old.example.test');

INSERT INTO monitoring.monitoring_resource(
 tenant_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,
 resource_kind,provider_object_kind,provider_external_ref,display_name,
 scope_state,scope_projection_revision,scope_evidence_state,presence_state,
 presence_evidence_state,last_observed_at,last_confirmed_present_at,removed_at,
 latest_provider_evidence_id
) VALUES (
 'tenant-a','resource-1','source-a','generation-a','host','zabbix_host','101','Host 101',
 'in_scope',1,'current','present','current',
 transaction_timestamp(),transaction_timestamp(),NULL,NULL
);

INSERT INTO monitoring.monitoring_problem_provider_binding(
 tenant_id,problem_id,monitoring_source_id,source_instance_generation,
 monitoring_resource_id,provider_profile,provider_external_ref,provider_trigger_ref
) VALUES (
 'tenant-a','problem-1','source-a','generation-a','resource-1',
 'zabbix','9001','trigger-1'
);

INSERT INTO monitoring.monitoring_problem(
 tenant_id,problem_id,monitoring_source_id,source_instance_generation,
 monitoring_resource_id,problem_state,severity_class,summary,opened_at,resolved_at,
 last_confirmed_at,evidence_state,projection_revision,problem_poll_epoch,
 problem_poll_generation,provider_metadata
) VALUES (
 'tenant-a','problem-1','source-a','generation-a','resource-1',
 'active','warning','CPU threshold exceeded',
 transaction_timestamp()-interval '10 minutes',NULL,transaction_timestamp(),
 'current',7,1,1,'{}'::jsonb
);

INSERT INTO monitoring.health_projection(
 tenant_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,
 health_class,evidence_state,projection_revision,last_changed_at,last_evidence_at,
 problem_snapshot_evidence_id,reason_refs
) VALUES (
 'tenant-a','resource-1','source-a','generation-a','degraded','current',11,
 transaction_timestamp()-interval '5 minutes',transaction_timestamp(),
 NULL,'["problem-1"]'::jsonb
);

SET session_replication_role=origin;

CREATE TEMP TABLE problem_transition_fixture(
  tenant_id text NOT NULL,
  problem_transition_id text NOT NULL,
  problem_id text NOT NULL,
  monitoring_source_id text NOT NULL,
  source_instance_generation text NOT NULL,
  monitoring_resource_id text NOT NULL,
  projection_revision bigint NOT NULL,
  occurred_at timestamptz NOT NULL
);
CREATE TRIGGER problem_fixture_outbox
AFTER INSERT ON problem_transition_fixture
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_publish_problem_transition();

CREATE TEMP TABLE health_transition_fixture(
  tenant_id text NOT NULL,
  health_transition_id text NOT NULL,
  monitoring_resource_id text NOT NULL,
  monitoring_source_id text NOT NULL,
  source_instance_generation text NOT NULL,
  projection_revision bigint NOT NULL,
  occurred_at timestamptz NOT NULL
);
CREATE TRIGGER health_fixture_outbox
AFTER INSERT ON health_transition_fixture
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_publish_health_transition();

INSERT INTO problem_transition_fixture VALUES
 ('tenant-a','problem-transition-7','problem-1','source-a','generation-a','resource-1',7,'2026-09-18 12:00:00+00'),
 ('tenant-a','problem-transition-6','problem-1','source-a','generation-a','resource-1',6,'2026-09-18 11:59:00+00'),
 ('tenant-a','problem-transition-old','problem-1','source-a','generation-old','resource-1',1,'2026-09-18 11:00:00+00'),
 ('tenant-a','problem-transition-conflict','problem-1','source-a','generation-a','resource-1',7,'2026-09-18 12:01:00+00');

INSERT INTO health_transition_fixture VALUES
 ('tenant-a','health-transition-11','resource-1','source-a','generation-a',11,'2026-09-18 12:02:00+00'),
 ('tenant-a','health-transition-lease','resource-1','source-a','generation-a',11,'2026-09-18 12:03:00+00');
