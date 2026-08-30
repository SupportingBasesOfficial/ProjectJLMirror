#!/usr/bin/env bash
set -euo pipefail

: "${SPIRE_ROOT:?SPIRE_ROOT is required}"
: "${SPIRE_VERSION:?SPIRE_VERSION is required}"
: "${WORK_DIR:?WORK_DIR is required}"

SERVER_BIN="${SPIRE_ROOT}/bin/spire-server"
AGENT_BIN="${SPIRE_ROOT}/bin/spire-agent"
EXPECTED_VERSION="1.15.3"
TRUST_DOMAIN="validation.d3.jlmirror.invalid"
FOREIGN_TRUST_DOMAIN="foreign.d3.jlmirror.invalid"
CANONICAL_VALIDATION_ENV="environment.validation@1"
CANONICAL_PRODUCTION_ENV="environment.production@1"
CANONICAL_RUNTIME_PROFILE="runtime.api@1"
CANONICAL_WRONG_RUNTIME_PROFILE="runtime.worker@1"
# SPIFFE path segments intentionally use an adapter-safe representation. The canonical
# JLMirror identifiers above remain unchanged and MUST NOT inherit SPIFFE path grammar.
VALIDATION_ID="spiffe://${TRUST_DOMAIN}/environment/validation/v1/runtime/api/v1/workload-probe"
PRODUCTION_ID="spiffe://${TRUST_DOMAIN}/environment/production/v1/runtime/api/v1/forbidden-probe"
WRONG_RUNTIME_ID="spiffe://${TRUST_DOMAIN}/environment/validation/v1/runtime/worker/v1/forbidden-profile-probe"
FOREIGN_TRUST_ID="spiffe://${FOREIGN_TRUST_DOMAIN}/environment/validation/v1/runtime/api/v1/foreign-probe"
CURRENT_UID="$(id -u)"
FORBIDDEN_UID="0"
WORKLOAD_BIN_PATH="$(readlink -f "${AGENT_BIN}")"
WRONG_WORKLOAD_PATH="/nonexistent/jlmirror-d3-wrong-runtime"

if [[ "${CURRENT_UID}" == "${FORBIDDEN_UID}" ]]; then
  echo "probe requires a non-root workload caller so unix:uid attestation can be falsified" >&2
  exit 1
fi

if [[ "${SPIRE_VERSION}" != "${EXPECTED_VERSION}" ]]; then
  echo "unexpected SPIRE version: ${SPIRE_VERSION}" >&2
  exit 1
fi

for binary in "${SERVER_BIN}" "${AGENT_BIN}"; do
  test -x "${binary}"
done

test -n "${WORKLOAD_BIN_PATH}"
test "${WORKLOAD_BIN_PATH}" != "${WRONG_WORKLOAD_PATH}"

mkdir -p "${WORK_DIR}"/{server-data,agent-data,run,output}
chmod 700 "${WORK_DIR}" "${WORK_DIR}/server-data" "${WORK_DIR}/agent-data" "${WORK_DIR}/run"

SERVER_SOCKET="${WORK_DIR}/run/server.sock"
AGENT_SOCKET="${WORK_DIR}/run/agent.sock"
SERVER_CONF="${WORK_DIR}/server.conf"
AGENT_CONF="${WORK_DIR}/agent.conf"
TRUST_BUNDLE="${WORK_DIR}/run/trust-bundle.pem"
JOIN_TOKEN_FILE="${WORK_DIR}/run/join-token"
SERVER_LOG="${WORK_DIR}/server.log"
AGENT_LOG="${WORK_DIR}/agent.log"
FETCH_LOG="${WORK_DIR}/fetch.log"
FOREIGN_ENTRY_LOG="${WORK_DIR}/foreign-entry.log"
SERVER_PID=""
AGENT_PID=""

cleanup() {
  set +e
  if [[ -n "${AGENT_PID}" ]]; then
    kill "${AGENT_PID}" >/dev/null 2>&1 || true
    wait "${AGENT_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${SERVER_PID}" ]]; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
  rm -f "${JOIN_TOKEN_FILE}"
}
trap cleanup EXIT

cat >"${SERVER_CONF}" <<EOF
server {
    bind_address = "127.0.0.1"
    bind_port = "18081"
    socket_path = "${SERVER_SOCKET}"
    trust_domain = "${TRUST_DOMAIN}"
    data_dir = "${WORK_DIR}/server-data"
    log_level = "INFO"
    ca_ttl = "30m"
    default_x509_svid_ttl = "30s"
}

plugins {
    DataStore "sql" {
        plugin_data {
            database_type = "sqlite3"
            connection_string = "${WORK_DIR}/server-data/datastore.sqlite3"
        }
    }
    NodeAttestor "join_token" {
        plugin_data {}
    }
    KeyManager "memory" {
        plugin_data = {}
    }
}
EOF

"${SERVER_BIN}" validate -config "${SERVER_CONF}"
"${SERVER_BIN}" run -config "${SERVER_CONF}" >"${SERVER_LOG}" 2>&1 &
SERVER_PID="$!"

server_ready=0
for _ in $(seq 1 60); do
  if ! kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    echo "SPIRE server exited before readiness" >&2
    cat "${SERVER_LOG}" >&2
    exit 1
  fi
  if [[ -S "${SERVER_SOCKET}" ]] && \
     "${SERVER_BIN}" bundle show -socketPath "${SERVER_SOCKET}" -format pem >"${TRUST_BUNDLE}" 2>/dev/null; then
    server_ready=1
    break
  fi
  sleep 0.5
done
if [[ "${server_ready}" != "1" ]]; then
  echo "SPIRE server did not become ready" >&2
  cat "${SERVER_LOG}" >&2
  exit 1
fi

# join_token owns the backend agent identifier. Do not suggest a canonical JLMirror identity
# here: the attested parent is discovered from SPIRE after successful node attestation.
token_output="$("${SERVER_BIN}" token generate -socketPath "${SERVER_SOCKET}" -ttl 120)"
JOIN_TOKEN="$(printf '%s\n' "${token_output}" | sed -n 's/^Token:[[:space:]]*//p' | head -n1)"
if [[ -z "${JOIN_TOKEN}" ]]; then
  echo "unable to parse SPIRE join token output" >&2
  printf '%s\n' "${token_output}" >&2
  exit 1
fi
printf '%s' "${JOIN_TOKEN}" >"${JOIN_TOKEN_FILE}"
chmod 600 "${JOIN_TOKEN_FILE}"
unset JOIN_TOKEN token_output

cat >"${AGENT_CONF}" <<EOF
agent {
    data_dir = "${WORK_DIR}/agent-data"
    log_level = "INFO"
    server_address = "127.0.0.1"
    server_port = "18081"
    socket_path = "${AGENT_SOCKET}"
    trust_bundle_path = "${TRUST_BUNDLE}"
    trust_domain = "${TRUST_DOMAIN}"
}

plugins {
    NodeAttestor "join_token" {
        plugin_data {}
    }
    KeyManager "disk" {
        plugin_data {
            directory = "${WORK_DIR}/agent-data"
        }
    }
    WorkloadAttestor "unix" {
        plugin_data {
            discover_workload_path = true
            workload_size_limit = -1
        }
    }
}
EOF

"${AGENT_BIN}" validate -config "${AGENT_CONF}"
"${AGENT_BIN}" run -config "${AGENT_CONF}" -joinTokenFile "${JOIN_TOKEN_FILE}" >"${AGENT_LOG}" 2>&1 &
AGENT_PID="$!"

agent_ready=0
for _ in $(seq 1 60); do
  if ! kill -0 "${AGENT_PID}" >/dev/null 2>&1; then
    echo "SPIRE agent exited before readiness" >&2
    cat "${AGENT_LOG}" >&2
    exit 1
  fi
  if [[ -S "${AGENT_SOCKET}" ]] && \
     "${AGENT_BIN}" healthcheck -socketPath "${AGENT_SOCKET}" >/dev/null 2>&1; then
    agent_ready=1
    break
  fi
  sleep 0.5
done
if [[ "${agent_ready}" != "1" ]]; then
  echo "SPIRE agent did not become ready" >&2
  cat "${AGENT_LOG}" >&2
  exit 1
fi

# Resolve the actual backend-owned attested agent identity from the SPIRE Server API.
# Exactly one join-token agent is permitted in this bounded probe. Its identity must stay
# inside the backend-reserved namespace and is never promoted to canonical JLMirror identity.
agent_json="$("${SERVER_BIN}" agent list -socketPath "${SERVER_SOCKET}" -attestationType join_token -output json)"
ATTESTED_NODE_ID="$(AGENT_JSON="${agent_json}" TRUST_DOMAIN="${TRUST_DOMAIN}" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["AGENT_JSON"])
agents = payload.get("agents", [])
if len(agents) != 1:
    raise SystemExit(f"expected exactly one attested join_token agent, got {len(agents)}")
agent = agents[0]
if agent.get("attestation_type") != "join_token":
    raise SystemExit("attested agent type drifted from join_token")
spiffe_id = agent.get("id") or {}
trust_domain = spiffe_id.get("trust_domain")
path = spiffe_id.get("path")
expected_trust_domain = os.environ["TRUST_DOMAIN"]
if trust_domain != expected_trust_domain:
    raise SystemExit(f"attested agent trust domain mismatch: {trust_domain!r}")
if not isinstance(path, str) or not path.startswith("/spire/agent/join_token/"):
    raise SystemExit(f"attested agent path is outside join_token backend namespace: {path!r}")
print(f"spiffe://{trust_domain}{path}")
PY
)"
unset agent_json
if [[ -z "${ATTESTED_NODE_ID}" ]]; then
  echo "unable to resolve attested SPIRE agent identity" >&2
  exit 1
fi

# A non-federated foreign trust-domain identity must not be registrable under this server.
if "${SERVER_BIN}" entry create \
     -socketPath "${SERVER_SOCKET}" \
     -parentID "${ATTESTED_NODE_ID}" \
     -spiffeID "${FOREIGN_TRUST_ID}" \
     -selector "unix:uid:${CURRENT_UID}" \
     -x509SVIDTTL 30 >"${FOREIGN_ENTRY_LOG}" 2>&1; then
  echo "foreign trust-domain workload identity was unexpectedly registrable" >&2
  cat "${FOREIGN_ENTRY_LOG}" >&2 || true
  exit 1
fi

# The allowed identity requires both process ownership and the exact observed workload path.
# This makes the runtime-profile evidence stronger than a shared uid alone.
"${SERVER_BIN}" entry create \
  -socketPath "${SERVER_SOCKET}" \
  -parentID "${ATTESTED_NODE_ID}" \
  -spiffeID "${VALIDATION_ID}" \
  -selector "unix:uid:${CURRENT_UID}" \
  -selector "unix:path:${WORKLOAD_BIN_PATH}" \
  -x509SVIDTTL 30 >/dev/null

# A broader production-shaped identity exists in the backend but is selector-bound to a UID
# the workload caller does not possess. Its mere registration must not make it fetchable.
"${SERVER_BIN}" entry create \
  -socketPath "${SERVER_SOCKET}" \
  -parentID "${ATTESTED_NODE_ID}" \
  -spiffeID "${PRODUCTION_ID}" \
  -selector "unix:uid:${FORBIDDEN_UID}" \
  -selector "unix:path:${WORKLOAD_BIN_PATH}" \
  -x509SVIDTTL 30 >/dev/null

# A different runtime-profile identity shares the caller uid but is bound to an impossible
# workload path. Caller uid alone therefore cannot authorize a broader runtime profile.
"${SERVER_BIN}" entry create \
  -socketPath "${SERVER_SOCKET}" \
  -parentID "${ATTESTED_NODE_ID}" \
  -spiffeID "${WRONG_RUNTIME_ID}" \
  -selector "unix:uid:${CURRENT_UID}" \
  -selector "unix:path:${WRONG_WORKLOAD_PATH}" \
  -x509SVIDTTL 30 >/dev/null

# SPIRE Agent synchronizes authorized entries with the Server asynchronously (default 5s).
# Bound the propagation wait to 15s; inability to observe the authorized identity within the
# evidence window remains a hard failure rather than being treated as eventual success.
fetch_ready=0
for _ in $(seq 1 30); do
  rm -rf "${WORK_DIR}/output"/*
  if "${AGENT_BIN}" api fetch x509 \
       -socketPath "${AGENT_SOCKET}" \
       -timeout 2s \
       -write "${WORK_DIR}/output" >"${FETCH_LOG}" 2>&1; then
    fetch_ready=1
    break
  fi
  sleep 0.5
done
if [[ "${fetch_ready}" != "1" ]]; then
  echo "authorized workload SVID did not propagate within bounded 15s evidence window" >&2
  cat "${FETCH_LOG}" >&2 || true
  exit 1
fi

mapfile -t SVID_CERTS < <(find "${WORK_DIR}/output" -maxdepth 1 -type f -name 'svid.*.pem' ! -name '*.key' | sort)
if [[ "${#SVID_CERTS[@]}" -ne 1 ]]; then
  echo "expected exactly one selector-authorized workload SVID, got ${#SVID_CERTS[@]}" >&2
  find "${WORK_DIR}/output" -maxdepth 1 -type f -print >&2 || true
  exit 1
fi
SVID_CERT="${SVID_CERTS[0]}"

CERT_TEXT="$(openssl x509 -in "${SVID_CERT}" -noout -text)"
printf '%s\n' "${CERT_TEXT}" | grep -F "URI:${VALIDATION_ID}" >/dev/null
for forbidden_id in "${PRODUCTION_ID}" "${WRONG_RUNTIME_ID}" "${FOREIGN_TRUST_ID}"; do
  if printf '%s\n' "${CERT_TEXT}" | grep -F "${forbidden_id}" >/dev/null; then
    echo "forbidden workload identity leaked into workload SVID: ${forbidden_id}" >&2
    exit 1
  fi
done

NOT_BEFORE="$(openssl x509 -in "${SVID_CERT}" -noout -startdate | cut -d= -f2-)"
NOT_AFTER="$(openssl x509 -in "${SVID_CERT}" -noout -enddate | cut -d= -f2-)"
NOT_BEFORE_EPOCH="$(date -u -d "${NOT_BEFORE}" +%s)"
NOT_AFTER_EPOCH="$(date -u -d "${NOT_AFTER}" +%s)"
LIFETIME="$((NOT_AFTER_EPOCH - NOT_BEFORE_EPOCH))"
if (( LIFETIME <= 0 || LIFETIME > 45 )); then
  echo "X.509-SVID lifetime is outside bounded short-lived evidence profile: ${LIFETIME}s" >&2
  exit 1
fi

# Negative controls prove the forbidden registrations really exist server-side and differ
# only at the intended environment/runtime selector boundaries.
production_entry_output="$("${SERVER_BIN}" entry show -socketPath "${SERVER_SOCKET}" -spiffeID "${PRODUCTION_ID}")"
printf '%s\n' "${production_entry_output}" | grep -F "${PRODUCTION_ID}" >/dev/null
printf '%s\n' "${production_entry_output}" | grep -F "unix:uid:${FORBIDDEN_UID}" >/dev/null

wrong_runtime_entry_output="$("${SERVER_BIN}" entry show -socketPath "${SERVER_SOCKET}" -spiffeID "${WRONG_RUNTIME_ID}")"
printf '%s\n' "${wrong_runtime_entry_output}" | grep -F "${WRONG_RUNTIME_ID}" >/dev/null
printf '%s\n' "${wrong_runtime_entry_output}" | grep -F "unix:uid:${CURRENT_UID}" >/dev/null
printf '%s\n' "${wrong_runtime_entry_output}" | grep -F "unix:path:${WRONG_WORKLOAD_PATH}" >/dev/null

printf 'spire_candidate_evaluation=PASS version=%s trust_domain=%s\n' "${SPIRE_VERSION}" "${TRUST_DOMAIN}"
printf 'backend_attested_parent=PASS parent_id=%s canonical_authority=false\n' "${ATTESTED_NODE_ID}"
printf 'canonical_to_spiffe_adapter=PASS canonical_environment=%s canonical_runtime=%s wire_spiffe_id=%s\n' \
  "${CANONICAL_VALIDATION_ENV}" "${CANONICAL_RUNTIME_PROFILE}" "${VALIDATION_ID}"
printf 'runtime_attestation_selector_binding=PASS caller_uid=%s workload_path=%s authorized_id=%s\n' \
  "${CURRENT_UID}" "${WORKLOAD_BIN_PATH}" "${VALIDATION_ID}"
printf 'trust_domain_environment_runtime_binding=PASS foreign_trust_registration_rejected=true forbidden_environment=%s forbidden_environment_not_issued=true wrong_runtime=%s wrong_runtime_not_issued=true\n' \
  "${CANONICAL_PRODUCTION_ENV}" "${CANONICAL_WRONG_RUNTIME_PROFILE}"
printf 'short_lived_x509_svid=PASS lifetime_seconds=%s rotation_retired_bundle=not_claimed\n' "${LIFETIME}"
printf 'conformance_claim=exploratory_only evidence_credited=false private_key_non_exportability=not_claimed restore_recovery=not_claimed vendor_adapter=not_claimed\n'
printf 'wave4=not_granted production=none d4=not_selected_not_granted\n'