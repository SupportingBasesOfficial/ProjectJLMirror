# 67 — Notification Channels Decision Record

**Status:** proposed — channel model and initial adapters selected; closure condition below is binding before notification delivery is treated as production-eligible
**Decision class:** C2 product selection (channel providers are replaceable within the accepted NotificationPort adapter pattern)
**Drivers:** `ADR-013` (inbound/outbound adapter pattern), `ADR-005` (tenant isolation), G9 (Notification Delivery, IMPLEMENTED), `OPEN-QUESTIONS-AND-DEFERRED.md` (notification channel capability model open)

This document closes the "Notification / authoritative visibility" open question for the notification channel capability model and initial provider selection. It does not close the authoritative read/view evidence or customer-identity-binding questions, which remain open.

## Context and problem

`OPEN-QUESTIONS-AND-DEFERRED.md` lists: "channel capability model is not yet authorized; exact WhatsApp/e-mail/SMS/push/provider integrations are not selected here; which workflows require authoritative read evidence versus best-effort notification must be explicitly authorized."

G9 (Notification Delivery) is IMPLEMENTED. That implementation contains the `NotificationPort` protocol and its adapters. This record formalizes the decision: which adapters are authorized, what the channel capability model is, and what delivery guarantees each channel carries.

## Requirements and invariants this selection must satisfy

- ADR-013: each channel is implemented behind a `NotificationPort` adapter; the business layer has no direct dependency on provider SDKs or HTTP client details.
- ADR-005: notification routing is per-tenant; one tenant's channel configuration cannot cause delivery to another tenant's channels.
- ADR-019: notifications are dispatched after alert/ACK/resolution events via the event-driven pipeline; there is no synchronous notification in the request path.
- Delivery guarantees must be explicit: the platform does not promise authoritative-read evidence for best-effort channels.
- Provider credentials (SMTP passwords, webhook signing keys) are never in application code or logs; they are loaded from the accepted secrets authority.

## Decision

### NotificationPort protocol

The canonical interface for all notification adapters is:

```python
class NotificationPort(Protocol):
    async def deliver(
        self,
        recipient: NotificationRecipient,
        payload: NotificationPayload,
        context: NotificationContext,
    ) -> NotificationDeliveryResult:
        ...
```

- `NotificationRecipient`: typed union — `EmailRecipient | WebhookRecipient | SmsRecipient | WhatsappRecipient`
- `NotificationPayload`: `subject`, `body_text`, `body_html` (optional), `severity`, `alert_id`, `tenant_id`
- `NotificationContext`: `trace_id`, `attempt_number`, `policy_snapshot_id`
- `NotificationDeliveryResult`: `success: bool`, `provider_message_id: str | None`, `failure_reason: str | None`

No adapter implements delivery guarantees beyond what the provider offers; the result is honest about provider acceptance, not ultimate delivery.

### Authorized adapters — initial set

#### Adapter 1 — SmtpNotificationAdapter (authorized, IMPLEMENTED in G9)

- Delivers via standard SMTP (TLS required; plaintext SMTP is not the accepted profile).
- Recipient: `EmailRecipient(address: str, display_name: str | None)`
- Provider acceptance = result success; email delivery to inbox is best-effort (SMTP standard).
- Retry policy: 3 attempts with exponential backoff (2 s, 8 s, 32 s); failures after 3 attempts log a `NotificationDeliveryFailure` and do not block alert lifecycle.
- Configuration per tenant: SMTP host, port, from-address, credential reference (secret name, not value).
- Supports HTML alert body with: severity badge, alert title, resource name, occurred_at, ITSM ticket link (if opened).

#### Adapter 2 — WebhookNotificationAdapter (authorized, IMPLEMENTED in G9)

- Delivers via HTTP POST to a tenant-configured HTTPS endpoint.
- Recipient: `WebhookRecipient(url: str, signing_key_ref: str, headers: dict[str, str])`
- Request body: JSON payload matching `NotificationPayload` schema (versioned with `"schema_version": "1.0"`).
- Request signature: `X-JLMirror-Signature: sha256=<HMAC-SHA256 of body using signing_key>` — the receiving webhook can verify authenticity.
- TLS: endpoint must present a valid certificate; self-signed certs are not accepted in production.
- Retry policy: same as SMTP (3 attempts, exp backoff).
- This adapter is compatible with Slack incoming webhooks, Microsoft Teams connectors, PagerDuty Events API, and any generic HTTPS receiver.

#### Adapter 3 — SmsNotificationAdapter (AUTHORIZED, implementation deferred)

- Authorized for implementation under this record; initial provider: Twilio SMS.
- Recipient: `SmsRecipient(phone_e164: str)`
- Payload: subject + first 140 characters of body_text (SMS constraint).
- The Twilio integration is behind the adapter boundary; replacing with another SMS provider requires only a new adapter implementation.
- Twilio credential (Account SID, Auth Token) loaded from secrets authority.
- Not IMPLEMENTED until G11 cycle begins.

#### Adapter 4 — WhatsappNotificationAdapter (AUTHORIZED, implementation deferred)

- Authorized for implementation; provider: WhatsApp Business API (Meta) or a BSP (Business Solution Provider).
- Recipient: `WhatsappRecipient(phone_e164: str, display_name: str | None)`
- Template-based delivery (WhatsApp requires pre-approved message templates for business-initiated messages).
- A separate governance record will authorize the template content for each notification event type before implementation.
- Not IMPLEMENTED until template governance is accepted.

### Channel capability model

Each channel carries an explicit capability classification:

| Channel | Delivery guarantee | Read evidence | Authoritative |
|---|---|---|---|
| Email (SMTP) | Provider acceptance only | None (best-effort) | No |
| Webhook | HTTP 2xx from endpoint | Response body | Endpoint-defined |
| SMS (Twilio) | Carrier acceptance | Delivery receipt (optional, Twilio-provided) | No |
| WhatsApp | Template delivery | Read receipt (optional, Meta-provided) | No |

"Authoritative read evidence" (a recipient has provably read and acknowledged the notification within a JLMirror-controlled surface) requires a separate authorized mechanism — the `AuthoritativeViewRecord` design — which remains open in `OPEN-QUESTIONS-AND-DEFERRED.md`. No channel in this record provides authoritative read evidence.

### Per-tenant channel routing

Channel routing is defined in `IncidentResponsePolicy.notify_channels` (IR-D-066):

```json
[
  {
    "channel_type": "email",
    "on_severities": ["HIGH", "CRITICAL"],
    "recipients": [{"address": "noc@customer.example", "display_name": "NOC Team"}]
  },
  {
    "channel_type": "webhook",
    "on_severities": ["MEDIUM", "HIGH", "CRITICAL"],
    "url": "https://hooks.customer.example/jlmirror",
    "signing_key_ref": "jlmirror_webhook_key"
  }
]
```

Rules:
- severity filter is evaluated against the alert's computed severity at dispatch time;
- a failing channel does not block other channels in the same routing list;
- each channel dispatch is an independent `NotificationDeliveryAttempt` record with its result;
- duplicate suppression: if an alert has already dispatched to the same `(alert_id, channel_type, recipient_hash)` in the last 24 h, re-dispatch is suppressed unless the alert severity has escalated.

### Privacy and retention

- Notification payloads are stored as `NotificationDeliveryAttempt` records for audit purposes; default retention 90 days.
- `body_html` is not stored in the audit record; only `subject`, `severity`, `alert_id`, `channel_type`, `recipient_hash` (not the raw address) and `result`.
- Raw recipient contact details (email addresses, phone numbers) are stored encrypted in the tenant configuration; they are decrypted only at dispatch time and never logged.
- Phone numbers for SMS and WhatsApp are stored E.164 format; display for NOC operators is masked by default (`+55••••••8765`).

### Closure condition — adapter delivery evidence (binding)

Before notification is treated as production-eligible for any channel:
- SmtpNotificationAdapter: deliver a test alert email to a real SMTP server; verify SMTP response code 250; verify the HTML body contains severity badge, alert title, occurred_at, and ITSM ticket link (if applicable).
- WebhookNotificationAdapter: deliver to a test HTTPS receiver; verify `X-JLMirror-Signature` matches HMAC-SHA256 of body; verify JSON body validates against schema version "1.0".
- For each adapter: a simulated provider failure (refused connection, 5xx response) triggers retry within the accepted backoff policy and logs `NotificationDeliveryFailure` after exhaustion without blocking alert state.

## Consequences

### Positive
- webhook adapter covers Slack, Teams, PagerDuty, and generic receivers without separate integrations;
- HMAC signature on webhooks allows receiving systems to verify authenticity without a separate credential;
- honest capability classification prevents false assumptions about authoritative-read evidence.

### Negative / cost
- WhatsApp template approval is an external dependency on Meta; cannot be unilaterally implemented;
- duplicate suppression keyed by `recipient_hash` requires a durable dedup table (PostgreSQL with TTL-based cleanup);
- SMS/WhatsApp implementation is deferred; tenants needing those channels must use webhook adapter to Twilio/Meta APIs in the interim.

## Validation

- alert OPEN event dispatches email to configured address within 60 s of alert creation;
- webhook delivery includes correct `X-JLMirror-Signature`; tampered body fails signature verification at receiver;
- severity below tenant-configured threshold produces zero dispatch attempts;
- `manual_override_only = true` on IncidentResponsePolicy produces zero notification dispatches;
- re-dispatch of the same alert to the same channel within 24 h is suppressed (only one `NotificationDeliveryAttempt` for that combination).

## Exit / revisit conditions

Revisit if WhatsApp Business API template approval requires a fundamentally different adapter architecture, if authoritative-read evidence (AuthoritativeViewRecord) is accepted and must be wired into the notification flow, or if notification volume requires a dedicated notification service rather than in-process adapter dispatch.
