# JLMIRROR

JLMIRROR is an enterprise-grade, multi-tenant platform for infrastructure monitoring, operational intelligence, IT service management, automation, governance, and extensible integrations.

This repository is the canonical source of truth for the product, architecture, engineering standards, implementation, and operational model of JLMIRROR.

## Engineering status

The project is being designed specification-first. Product requirements, domain boundaries, quality attributes, security guarantees, architecture decisions, data ownership, contracts, reliability, and operational requirements are defined before implementation structure is frozen.

## Canonical design order

1. Engineering foundation
2. Product definition
3. Requirements and business rules
4. Domain model
5. Quality attributes and non-functional requirements
6. Security and trust model
7. Architecture
8. System design
9. Data architecture
10. API and contracts
11. Event and asynchronous architecture
12. Reliability and resilience
13. Observability
14. Platform and infrastructure
15. Deployment and environments
16. CI/CD and software supply chain
17. Test engineering
18. Performance and capacity
19. Disaster recovery
20. Operations and runbooks
21. Implementation blueprint
22. Implementation

## Repository principles

- The repository is the canonical specification; chat transcripts and external notes are not normative.
- Architecture follows requirements and measurable quality attributes, not technology fashion.
- Tenant isolation is an invariant, not a feature.
- Security, observability, auditability, and recoverability are designed end-to-end.
- Business domains own their state and rules.
- Cross-domain interaction occurs through explicit contracts.
- External systems are integrations, not architectural centers of gravity.
- Infrastructure choices remain replaceable unless a deliberate ADR makes them a constraint.
- Implementation begins only after the relevant design baseline is accepted.

## Documentation

Canonical documentation lives under `docs/`. Significant architecture decisions live under `adr/`. Cross-cutting proposals that require review live under `rfcs/`.

## Security

Never commit credentials, tokens, production connection strings, customer data, private endpoints, or operational secrets to this repository.

## Quickstart (clone & run)

The repository is designed specification-first, but it also includes a runnable
backend application that implements the domain primitives in `src/` as a FastAPI
modular monolith backed by PostgreSQL + TimescaleDB.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- Python 3.11+ (the domain primitives use `enum.StrEnum`)
- `make` (optional but recommended; commands work without it too)

### Run with Docker Compose (recommended)

```bash
git clone https://github.com/SupportingBasesOfficial/ProjectJLMirror.git
cd ProjectJLMirror
cp .env.example .env          # adjust values if needed
docker compose up -d          # starts PostgreSQL + TimescaleDB + API
docker compose exec api python scripts/migrate.py apply
```

The API is available at `http://localhost:8000`. Interactive docs at
`http://localhost:8000/docs`.

### Run locally (API on host, database in Docker)

```bash
git clone https://github.com/SupportingBasesOfficial/ProjectJLMirror.git
cd ProjectJLMirror
cp .env.example .env
make install                  # pip install -e ".[dev]"
docker compose up -d db        # start only PostgreSQL
make migrate                   # apply SQL migrations
make dev                      # uvicorn with hot reload
```

### Run the domain unit tests

The existing specification-first unit tests do not require a database:

```bash
make test-unit                # PYTHONPATH=src python -m unittest discover
```

### Common commands

| Command | Description |
|---|---|
| `make up` | Start PostgreSQL + API containers (detached) |
| `make down` | Stop and remove containers |
| `make migrate` | Apply all SQL migrations in canonical order |
| `make dev` | Run the API locally with hot reload |
| `make dev-workers` | Run independent worker processes (ADR-001) |
| `make test` | Run unit + integration tests |
| `make test-unit` | Run domain unit tests (no database needed) |
| `make logs` | Tail container logs |
| `make help` | List all available commands |

### Project layout

```
src/                Domain primitives (stdlib-only, portable)
  jlmirror_authority/   Identity, authorization, fencing, control plane
  jlmirror_async/        Outbox, inbox, quarantine, reconciliation
  jlmirror_monitoring/   Health projection, metrics, problem state, host inventory
  jlmirror_observability/  Signal catalog, evidence pipeline
  jlmirror_release/      Deployment authority, provenance, verification
app/                FastAPI application layer (API + persistence + workers)
  routers/            HTTP endpoints per bounded context
  repositories/       PostgreSQL persistence (RLS-enforced)
  workers/            Independent worker runtimes
sql/                Canonical SQL migrations (PostgreSQL + TimescaleDB)
docs/               Canonical specification documentation
adr/                Architecture Decision Records
tests/              Unit and integration tests
tools/              Assurance and validation tooling
scripts/            Operational scripts (migration runner)
```
