#!/usr/bin/env bash
set -euo pipefail

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-g1-identity-postgres}"
PG_PASSWORD="${PG_PASSWORD:-jlmirror-g1-test-password}"
PG_DATABASE="${PG_DATABASE:-jlmirror}"

cleanup() {
  docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

docker pull "$POSTGRES_IMAGE" >/dev/null
docker image inspect "$POSTGRES_IMAGE" --format '{{range .RepoDigests}}{{println .}}{{end}}' | grep -Fx "$POSTGRES_IMAGE" >/dev/null

docker run -d --rm \
  --name "$PG_CONTAINER" \
  -e POSTGRES_PASSWORD="$PG_PASSWORD" \
  -e POSTGRES_DB="$PG_DATABASE" \
  "$POSTGRES_IMAGE" >/dev/null

stable_ready=0
for _ in $(seq 1 90); do
  if docker inspect -f '{{.State.Running}}' "$PG_CONTAINER" 2>/dev/null | grep -qx 'true' \
     && docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c 'SELECT 1' 2>/dev/null | grep -qx '1'; then
    stable_ready=$((stable_ready + 1))
    if [[ "$stable_ready" -ge 3 ]]; then
      break
    fi
  else
    stable_ready=0
  fi
  sleep 1
done
test "$stable_ready" -ge 3

docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < sql/g1/001_browser_session_authority.sql >/dev/null

transaction_id="0123456789abcdef0123456789abcdef"
session_digest="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
state_digest="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
nonce_digest="cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
handle_digest="dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
verifier="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._~-"

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "INSERT INTO g1_identity.browser_auth_transaction(transaction_id, initiating_session_digest, state_digest, nonce_digest, pkce_verifier, expected_issuer, expected_client_id, expected_redirect_uri, created_at, expires_at) VALUES ('$transaction_id','$session_digest','$state_digest','$nonce_digest','$verifier','https://identity.example.test/realms/jlmirror','jlmirror-bff','https://app.example.test/auth/callback','2026-09-17T12:00:00Z','2026-09-17T12:05:00Z');" >/dev/null

first_consume="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT count(*) FROM g1_identity.consume_browser_auth_transaction('$transaction_id','2026-09-17T12:01:00Z');")"
test "$first_consume" = "1"
second_consume="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT count(*) FROM g1_identity.consume_browser_auth_transaction('$transaction_id','2026-09-17T12:01:01Z');")"
test "$second_consume" = "0"

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "INSERT INTO g1_identity.browser_session(handle_digest, principal_id, principal_kind, session_generation, auth_authenticated_at, auth_time_source, auth_acr, auth_amr, auth_policy_version, created_at, expires_at) VALUES ('$handle_digest','principal-a','human_browser_session','session-generation-a','2026-09-17T11:59:30Z','oidc_auth_time','urn:example:loa:1',ARRAY['pwd'],'auth-strength-v1','2026-09-17T12:00:00Z','2026-09-17T13:00:00Z');" >/dev/null

auth_round_trip="$(docker exec "$PG_CONTAINER" psql -Atq -F '|' -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT principal_kind, auth_time_source, coalesce(auth_acr,''), array_to_string(auth_amr,','), auth_policy_version, auth_authenticated_at <= created_at FROM g1_identity.browser_session WHERE handle_digest='$handle_digest';")"
test "$auth_round_trip" = "human_browser_session|oidc_auth_time|urn:example:loa:1|pwd|auth-strength-v1|t"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "INSERT INTO g1_identity.browser_session(handle_digest, principal_id, principal_kind, session_generation, auth_authenticated_at, auth_time_source, auth_amr, auth_policy_version, created_at, expires_at) VALUES ('eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee','principal-b','platform_admin_principal','session-generation-b','2026-09-17T11:59:30Z','oidc_auth_time',ARRAY['pwd'],'auth-strength-v1','2026-09-17T12:00:00Z','2026-09-17T13:00:00Z');" >/dev/null 2>&1; then
  echo "noncanonical principal_kind unexpectedly accepted" >&2
  exit 1
fi

retire_first="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT g1_identity.retire_browser_session('$handle_digest','session-generation-a','2026-09-17T12:02:00Z');")"
test "$retire_first" = "t"
retire_second="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT g1_identity.retire_browser_session('$handle_digest','session-generation-a','2026-09-17T12:02:01Z');")"
test "$retire_second" = "f"

raw_capability_presence="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT count(*) FROM information_schema.columns WHERE table_schema='g1_identity' AND column_name IN ('session_handle','access_token','refresh_token','id_token');")"
test "$raw_capability_presence" = "0"

foreign_truth_columns="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT count(*) FROM information_schema.columns WHERE table_schema='g1_identity' AND column_name IN ('membership_id','permission_id','tenant_status','tenant_access_generation');")"
test "$foreign_truth_columns" = "0"

auth_evidence_columns="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT count(*) FROM information_schema.columns WHERE table_schema='g1_identity' AND table_name='browser_session' AND column_name IN ('auth_authenticated_at','auth_time_source','auth_acr','auth_amr','auth_policy_version');")"
test "$auth_evidence_columns" = "5"

printf '%s\n' "g1_postgres_conformance=PASS transaction=single_use session=opaque_digest+auth_strength+single_retirement foreign_authority=absent topology=unspecified"
