# 65 — Frontend Stack Decision Record

**Status:** proposed — candidate stack and initial screen scope under review; this record grants no implementation authority
**Decision class:** C2 product selection (frontend stack is a replaceable implementation choice within the accepted architecture shape: UI must project business truth, not define it)
**Drivers:** `ADR-001` (modular monolith), `ADR-005` (identity/session boundary), `ADR-013` (inbound adapter shape), UI/NOC product requirement

This document is **not** a new ADR. The candidate frontend stack is a product selection within the already-accepted constraint that the frontend is a projection layer — it reads from accepted APIs, never mutates business truth directly.

## Context and problem

`docs/00-foundation/project-memory/OPEN-QUESTIONS-AND-DEFERRED.md` lists "final UX/navigation/NOC screen contracts remain incomplete" and the frontend stack as unselected. G1–G10 are now IMPLEMENTED on the backend; the UI layer is the next required capability to make the product usable by operators.

## Requirements and invariants this selection must satisfy

- ADR-005: the frontend authenticates through the BFF per IR-D-001; browser JavaScript never holds platform tokens.
- All business-truth mutations go through accepted REST/event APIs; the frontend has no direct DB access.
- The stack must support real-time operational data: metric current state, problem/health projection, active alerts, ACK state.
- The stack must produce accessible, responsive NOC-grade dashboards operable under low-light/high-information-density conditions.
- Component library must provide accessible primitives (ARIA, keyboard navigation) without requiring custom from-scratch implementations.
- TypeScript is required: the domain model has many invariants (tenant scoping, alert lifecycle, ACK attribution) that must be enforced at compile time, not discovered at runtime in a NOC.

## Decision

### Core stack

| Layer | Selection | Version constraint |
|---|---|---|
| Language | TypeScript | ≥ 5.4 |
| Bundler / dev server | Vite | ≥ 5.4 |
| UI library | React | 18.x |
| Component primitives | shadcn/ui | current (Radix UI base) |
| Styling | Tailwind CSS | v4.x |
| Charts / time-series | Recharts | ≥ 2.12 |
| Server-state / cache | TanStack Query (react-query) | v5.x |
| Type checking | tsc (strict mode) | matches TS version |
| Testing | Vitest + Testing Library | current |

### Rationale

**React 18**: most mature ecosystem for operational dashboards; concurrent rendering handles high-frequency metric updates without manual batching.

**Vite**: fast HMR during development; ES-module native output; no webpack ceremony.

**TypeScript strict**: domain invariants (tenant boundary, alert state machine, ACK lifecycle) are compiler-checked, not runtime-discovered. Any call that crosses a tenant boundary is type-erased at the API boundary and must be typed from the response schema — strict mode prevents silent `any` propagation.

**shadcn/ui + Tailwind**: shadcn/ui provides fully accessible (WCAG 2.1 AA) component source that lives in the repo (not a black-box dependency); Tailwind v4 provides a utility-first token system without a separate CSS infrastructure. Together they satisfy the NOC density requirement while remaining accessible.

**Recharts**: SVG-based, React-native, sufficient for metric current-state sparklines, health timeline bars and alert trend charts. Replaces charting from scratch. Recharts does not satisfy advanced time-series zooming/streaming at scale (>10k points per view); if AIOps or Metric History requires that, a separate charting library (for example uPlot or ECharts) would require a separate accepted decision before use.

**TanStack Query v5**: handles polling, background refresh, cache invalidation and optimistic updates for live operational data without bespoke state management. SessionAuthorityPort's 30 s cache bound aligns with a default staleTime of 30 s on /api/me.

### Frontend boundary constraints

These constraints are architecture laws, not style preferences:

1. **No direct DB or event-bus access**: all reads are via accepted REST API endpoints.
2. **No business-truth mutation outside accepted API calls**: alert lifecycle, ACK, ticket creation, policy changes — all go through the backend.
3. **Session handled by BFF cookie only**: no localStorage/sessionStorage for auth tokens; TanStack Query calls /g1/api/me on load to establish identity context.
4. **Tenant context from BFF**: the frontend reads `tenant_id` from /g1/api/me; it does not select or impersonate tenants.
5. **NOC contract**: real-time data (metric, problem, alert, ACK) is polled or streamed; the frontend renders state, never derives business state from UI-local computation.

### Candidate initial screens (not yet authorized)

If this record is accepted through the project governance process, the proposed initial implementation scope is:

- **Shell / login gate** (G1, already implemented as HTML prototype)
- **Monitoring Source list** — onboarded sources per tenant
- **Resource inventory** — host/resource list with health projection badge
- **Active alerts** — list view with severity, policy, owner, ACK state
- **Alert detail** — timeline, linked problem events, ACK history, ITSM ticket link
- **NOC dashboard** — aggregate health projection grid, top-N active alerts, recent activity feed

Screens outside this scope (AIOps findings, FinOps, Commercial, multi-region NOC, advanced device topology) remain FUTURE until separately authorized.

## Consequences

### Positive
- TypeScript strict catches tenant-boundary errors at build time;
- shadcn/ui + Tailwind removes most custom CSS from the codebase;
- TanStack Query handles the operational data polling pattern out of the box.

### Negative / cost
- Tailwind v4 utility classes are verbose; requires discipline on component encapsulation;
- shadcn/ui component source lives in the repo — updates require intentional upgrades, not passive npm updates;
- Recharts SVG renders degrade at very high point counts; must limit data window per chart.

## Validation

Before the first frontend screen is treated as complete:
- TypeScript strict build passes with zero errors;
- Lighthouse accessibility score ≥ 90 on every implemented screen;
- all interactive controls pass keyboard-only navigation;
- /g1/api/me 401 → redirect to BFF login without JS token exposure;
- tenant_id from session is consistent across all rendered data.

## Exit / revisit conditions

Revisit if React 18's concurrent model conflicts with a chosen real-time streaming pattern (e.g., WebSocket-first NOC), if Tailwind v4 is incompatible with a chosen design-system token format, or if the NOC product requires a native-desktop or Electron distribution (separate technology decision required).
