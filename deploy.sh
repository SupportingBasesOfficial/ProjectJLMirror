#!/usr/bin/env bash
# JLMirror — first-boot production deploy script.
# Run once on the datacenter server after cloning the repo and filling .env.
#
# Usage:
#   cp .env.prod.example .env   # then edit .env with real values
#   chmod +x deploy.sh
#   ./deploy.sh
#
# Re-running after the first boot is safe — migrations are idempotent,
# OpenBao init is skipped if already initialized.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[deploy]${NC} $*"; }
error() { echo -e "${RED}[deploy]${NC} $*" >&2; exit 1; }

[ -f .env ] || error ".env not found. Copy .env.prod.example to .env and fill all REQUIRED values."

# ── 0. Sanity checks ──────────────────────────────────────────────────────────
for cmd in docker curl jq; do
  command -v "$cmd" &>/dev/null || error "'$cmd' is not installed."
done

docker info &>/dev/null || error "Docker is not running or this user lacks Docker access."

# Warn if any REQUIRED placeholder was left unfilled
if grep -q "REQUIRED_CHANGE_ME" .env; then
  error "Found REQUIRED_CHANGE_ME in .env — fill all required values before deploying."
fi

# ── 1. Pull / build images ────────────────────────────────────────────────────
info "Building application images..."
docker compose build --pull

# ── 2. Start infrastructure (DB + Keycloak + OpenBao) ────────────────────────
info "Starting database and Keycloak..."
docker compose up -d db keycloak

info "Waiting for database to be healthy..."
for i in $(seq 1 30); do
  docker compose exec -T db pg_isready -U jlmirror_owner -d jlmirror &>/dev/null && break
  [ "$i" -eq 30 ] && error "Database did not become healthy after 150s."
  sleep 5
done
info "Database is ready."

info "Waiting for Keycloak to be ready..."
for i in $(seq 1 60); do
  curl -sf "http://localhost:8180/realms/jlmirror" &>/dev/null && break
  [ "$i" -eq 60 ] && error "Keycloak did not become ready after 300s."
  sleep 5
done
info "Keycloak is ready — realm jlmirror imported."

# ── 3. Run database migrations ────────────────────────────────────────────────
info "Running migrations..."
docker compose run --rm migrate
info "Migrations complete."

# ── 4. Initialize OpenBao (skipped if already initialized) ───────────────────
info "Starting OpenBao..."
docker compose --profile secrets up -d openbao

info "Waiting for OpenBao to start..."
for i in $(seq 1 20); do
  BAO_STATUS=$(curl -sf "http://localhost:8200/v1/sys/health" 2>/dev/null || true)
  [ -n "$BAO_STATUS" ] && break
  sleep 3
done

BAO_INIT=$(curl -sf "http://localhost:8200/v1/sys/init" | jq -r '.initialized' 2>/dev/null || echo "false")
if [ "$BAO_INIT" = "false" ]; then
  info "Initializing OpenBao..."
  docker compose --profile secrets run --rm bao-init
  info "OpenBao initialized. Root token written to ./secrets/bao_token."
  warn "Add BAO_TOKEN=$(cat ./secrets/bao_token 2>/dev/null || echo '<see ./secrets/bao_token>') to .env and re-run deploy.sh to load credentials."
  exit 0
else
  info "OpenBao already initialized — skipping init."
fi

# ── 5. Start all core services ────────────────────────────────────────────────
info "Starting API, BFF, and Worker..."
docker compose --profile worker up -d

info "Waiting for BFF health check..."
for i in $(seq 1 30); do
  curl -sf "http://localhost:8080/health" &>/dev/null && break
  [ "$i" -eq 30 ] && { warn "BFF health check timed out — check: docker compose logs bff"; }
  sleep 5
done

# ── 6. Status summary ─────────────────────────────────────────────────────────
echo ""
info "Deploy complete. Service status:"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo ""
info "BFF is accessible at http://localhost:8080 (or your domain via reverse proxy)."
info "Keycloak admin at http://localhost:8180 — change the admin password immediately."
