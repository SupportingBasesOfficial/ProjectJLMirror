UPDATE notification.notification_dispatch_outbox
SET available_at=transaction_timestamp()-interval '1 second'
WHERE state='admitted';
