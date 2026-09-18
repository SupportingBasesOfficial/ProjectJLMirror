-- G6 conflicting-equivalence fixture only.
INSERT INTO system.async_consumer_inbox(
 consumer_contract,message_identity_scope,message_id,tenant_id,
 comparison_profile_id,comparison_profile_version,comparison_evidence_form,
 comparison_verifier_generation,comparison_evidence
)
SELECT
 'alerting.monitoring-resync',
 producer_message_scope,
 message_id,
 tenant_id,
 'monitoring-invalidation-equivalence',
 '1',
 'canonical-jsonb-envelope-payload',
 NULL,
 decode('00','hex')
FROM system.async_outbox_message
WHERE contract_name='monitoring.problem-state.changed'
  AND convert_from(encoded_payload,'UTF8')::jsonb->>'problem_transition_id'='problem-transition-conflict';
