# G12 AIOps — AI-Advised Operational Insights

**Record #68 | Class: Feature Gate | Status: Authorized**
**Gate authority: G12 AIOps | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-23**

---

## 1. Context

JLMirror gates G1–G11 cover identity, monitoring, alerting, human operations,
notifications, ITSM, and incident response. These gates produce evidence:
active alerts, monitoring problems, resource health projections, and lifecycle
transitions. Operators must interpret this evidence manually.

G12 introduces an AI analysis layer that consumes governed evidence and emits
advisory findings. The findings surface patterns — anomalies, correlations,
root-cause hypotheses, and predictions — that would be difficult to see by
scanning individual alerts.

---

## 2. Canonical Invariant

**ALERT ≠ AIOPS FINDING**

A finding is advisory commentary, not an operational action. This is a
governance boundary, not just a design preference:

- Findings cannot create, resolve, or transition Alerts.
- Findings cannot trigger notifications, ITSM tickets, or incident responses.
- Findings are explicitly labeled as AI-generated advisory content.
- Findings carry confidence, model_id, and analysis_run_id for full
  traceability.

An AIOps finding that causes downstream automated action without a separately
authorized authority contract is a **governance violation**.

---

## 3. Authority Scope

| What G12 MAY do                                    | What G12 MAY NOT do                       |
|----------------------------------------------------|-------------------------------------------|
| Query active alerts and monitoring problems        | Create or resolve Alerts                  |
| Query monitoring source state                      | Trigger notifications (G9)                |
| Emit advisory findings to `aiops.finding`          | Open ITSM tickets (G10)                   |
| Expose findings via `GET /api/v1/aiops/findings`   | Claim incident responder authority (G11)  |
| Allow operators to dismiss individual findings     | Take any operational action automatically |

---

## 4. Evidence Window

The worker gathers evidence from a 24-hour rolling window:
- Up to 20 active alerts per tenant
- Monitoring source operational state

The evidence window `[evidence_window_start, evidence_window_end]` is recorded
on `aiops.analysis_run` for audit traceability.

---

## 5. Finding Schema

```
aiops.finding:
  tenant_id           TEXT    NOT NULL    — RLS boundary
  finding_id          TEXT    PK          — find-{hex16}
  analysis_run_id     TEXT    FK          — links to aiops.analysis_run
  finding_type        ENUM    NOT NULL    — anomaly|correlation|root_cause|prediction
  severity_hint       ENUM    NOT NULL    — low|medium|high (advisory, not alert severity)
  title               TEXT    NOT NULL    — ≤ 120 chars
  explanation         TEXT    NOT NULL    — model explanation ≤ 800 chars
  evidence_refs       JSONB   NOT NULL    — IDs of referenced alerts/problems
  confidence          NUMERIC(4,3)        — model confidence 0–1
  model_id            TEXT    NOT NULL    — anthropic model used
  expires_at          TIMESTAMPTZ         — auto-expires 7 days after creation
  dismissed_at        TIMESTAMPTZ NULL    — operator-dismissed findings excluded from reads
  created_at          TIMESTAMPTZ         — creation time
```

---

## 6. Analysis Cadence

- Worker runs every 30 minutes per tenant (in-process timer, non-distributed)
- Each run generates one `aiops.analysis_run` record regardless of findings count
- Up to 5 findings per run (Claude API tool-use with capped maxItems)
- Findings expire after 7 days; dismissed findings are excluded from API reads

---

## 7. Model Selection

| Layer        | Model               | Rationale                                      |
|--------------|---------------------|------------------------------------------------|
| Analysis     | claude-sonnet-5     | Capable multi-alert pattern recognition        |
| Alternatives | claude-haiku-4-5    | Acceptable if latency/cost constraints emerge  |

The model_id is stored on every finding for traceability. Model rotation
requires no schema change.

---

## 8. API Contract

```
GET  /api/v1/aiops/findings          — list active findings (limit=50)
GET  /api/v1/aiops/findings/{id}     — single finding with full explanation
PATCH /api/v1/aiops/findings/{id}/dismiss — operator dismissal (advisory suppression)
```

All three endpoints require authenticated tenant context (`alerting:read`
equivalent — any tenant member with a valid session).

---

## 9. Failure Modes

| Condition                    | Behavior                                              |
|------------------------------|-------------------------------------------------------|
| ANTHROPIC_API_KEY not set    | Worker silently skips AIOps (returns 0, no error log) |
| Claude API unreachable       | Worker logs exception, returns 0, retries next cycle  |
| DB unavailable               | Worker uses shared conn; fails like all other workers |
| No active alerts             | Worker skips tenant (no API call made)                |
| Model returns empty findings | 0 findings stored; analysis_run still recorded        |

---

## 10. Dependencies

| Gate | Dependency |
|------|------------|
| G1   | Tenant identity — `g1.tenants` provides the tenant list |
| G7   | Alerting — `alerting.alert` provides the evidence |
| G3   | Monitoring — `monitoring.monitoring_source` provides source state |

AIOps is downstream of these gates. If G7 has no alerts, G12 has no evidence.

---

## 11. Implementation Checklist

- [x] Decision record authored (this document)
- [x] `sql/aiops/001_g12_aiops_core.sql` — schema + tables + RLS
- [x] `sql/z_integration/011_g12_aiops_grants.sql` — role grants
- [x] `anthropic` added to `pyproject.toml`
- [x] `workers/aiops.py` — periodic analysis worker
- [x] `api/routers/aiops.py` — GET findings endpoints
- [x] `api/main.py` — router registered, sandbox prefix added
- [x] `workers/run_all.py` — aiops processor registered
- [x] `docker-compose.yml` — ANTHROPIC_API_KEY env var added to worker
- [x] `frontend/src/pages/AIOpsPage.tsx` — advisory findings page
- [x] `frontend/src/components/Shell.tsx` — AIOps nav item added

---

## 12. Open Questions

1. **Distributed rate limiting**: Currently each worker process tracks `_last_run`
   in memory. If multiple worker instances run (future scale-out), they will each
   run independently. Resolution: store `last_analysis_at` in `aiops.analysis_run`
   and use a DB-level check before each run. Deferred to G12.1.

2. **Problem evidence**: `monitoring.monitoring_problem` evidence not yet included
   in the analysis prompt. Adding it in G12.1 will improve root-cause findings.

3. **Finding feedback loop**: Operators can dismiss findings but cannot rate them.
   A thumbs-up/down mechanism would improve model prompt calibration over time.
   Deferred to G12.2.
