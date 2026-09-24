# G14 — Production Release Gate

**Record #70 | Class: Feature Gate | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-23**

---

## 1. Context

G1–G13 deliver the complete JLMirror feature set in a development configuration.
G14 is the gate that authorizes promoting ReadyJLMirror to a production environment.
It defines what "production ready" means and provides the tooling to verify it.

G14 does not add user-facing features. Its deliverables are:
1. A pre-production preflight validation script (`scripts/production_preflight.py`)
2. A Platform status page in the frontend shell (for operators and platform admins)
3. This decision record as the governance anchor

---

## 2. Production Readiness Criteria

A ReadyJLMirror deployment is production-ready when ALL of the following are true:

### 2.1 Environment configuration
| Check | Requirement |
|-------|-------------|
| `APP_ENVIRONMENT` | `production` (not `development`) |
| `DEV_AUTH_BYPASS` | `false` or unset |
| `BFF_INTERNAL_SECRET` | Not the dev literal `dev-internal-secret-change-me` |
| `KEYCLOAK_CLIENT_SECRET` | Not the dev literal `dev-bff-secret-change-me` |
| `NOTIFICATION_CALLBACK_SECRET` | Not the dev literal `dev-callback-secret` |

### 2.2 Transport security
| Check | Requirement |
|-------|-------------|
| BFF TLS | `TLS_CERT_FILE` and `TLS_KEY_FILE` set |
| API mTLS | `API_MTLS=1` with cert/key/CA configured |
| DB role | `DB_USER` is `jlmirror_app` or `jlmirror_worker` (never `jlmirror_owner`) |

### 2.3 Data plane
| Check | Requirement |
|-------|-------------|
| DB connection | Reachable within 5 s timeout |
| Migrations | All SQL migrations applied (count > 0 in `_migrations`) |
| Worker heartbeat | At least one worker alive within last 120 s |

### 2.4 Optional / advisory
| Check | Requirement |
|-------|-------------|
| `ANTHROPIC_API_KEY` | Set for AIOps (warns but does not block) |

---

## 3. Preflight Script

`python -m scripts.production_preflight`

- Exits 0: all required checks pass → deployment authorized
- Exits 1: any required check fails → deployment blocked
- Warnings (WARN): advisory issues logged but do not block

The script is designed to run in CI/CD before a production image promotion.

---

## 4. Platform Status Page

The frontend Platform page (`/platform`) shows:
- System health summary (DB state, worker state, environment)
- Release outcome classes reference (change classification vocabulary)
- Platform environment and version info

The page is visible to all authenticated tenant members. Platform-admin-only
features (organization management) remain in the existing platform API, not
the frontend shell (separate operator tooling concern).

---

## 5. Release Outcome Classification

The existing `POST /api/v1/release/outcome/classify` endpoint (Release router,
vendor `jlmirror_release`) provides change outcome classification. Any release
that modifies DB schema, auth configuration, or API contracts must be classified
before promotion. The Platform page surfaced the vocabulary.

---

## 6. Rollback Profile

- All DB schema changes use `IF NOT EXISTS` / `ON CONFLICT DO NOTHING`
  → forward-only migrations; rollback requires a point-in-time restore
- Container rollback: previous image tags must be retained for 30 days in
  the registry
- Worker state: the durable outbox/heartbeat pattern tolerates a worker restart
  gap of up to 2× the `WORKER_POLL_INTERVAL_SECONDS`

---

## 7. Implementation Checklist

- [x] Decision record authored (this document)
- [x] `scripts/production_preflight.py` — validation script
- [x] `frontend/src/pages/PlatformPage.tsx` — platform status page
- [x] `frontend/src/components/Shell.tsx` — Platform nav item added

---

## 8. What G14 Does NOT Cover

- DNS/load-balancer configuration
- CDN or edge cache setup
- Kubernetes/orchestration manifests (separate infra concern)
- Managed DB provisioning (separate infra concern)
- SLA definition and on-call setup
- Penetration test / security audit (separate engagement)

These are operational prerequisites tracked outside this gate.
