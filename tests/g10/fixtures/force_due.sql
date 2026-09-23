UPDATE itsm.incident_sync_outbox
SET available_at=transaction_timestamp()-interval '1 second'
WHERE sync_state='pending';
