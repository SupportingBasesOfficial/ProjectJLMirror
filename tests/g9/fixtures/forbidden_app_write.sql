SET ROLE jlmirror_g9_notification_app_invoker;
INSERT INTO notification.notification_projection(
  tenant_id,notification_intent_id,delivery_state,
  external_read_observed,retry_required,reconciliation_required,
  fallback_action_required,projection_revision
) VALUES (
  'tenant-a','forbidden-intent','unknown',
  FALSE,FALSE,FALSE,FALSE,1
);
