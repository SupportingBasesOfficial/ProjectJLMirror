#!/usr/bin/env bash
set -euo pipefail

: "${SPIRE_ROOT:?SPIRE_ROOT is required}"
: "${SPIRE_VERSION:?SPIRE_VERSION is required}"
: "${WORK_DIR:?WORK_DIR is required}"

EXPECTED_VERSION="1.15.3"
TRUST_DOMAIN="keyprofile.validation.d3.jlmirror.invalid"
WORKLOAD_ID="spiffe://${TRUST_DOMAIN}/environment/validation/v1/runtime/api/v1/keyprofile-probe"
SERVER_BIN="${SPIRE_ROOT}/bin/spire-server"
AGENT_BIN="${SPIRE_ROOT}/bin/spire-agent"
PLUGIN_SRC="implementation/d3-identity-security/harness/spire_nonexporting_keymanager"
PLUGIN_BIN="${WORK_DIR}/plugin/jlmirror-d3-nonexporting-keymanager"
PLUGIN_AUDIT="${WORK_DIR}/run/keymanager-audit.log"
CURRENT_UID="$(id -u)"
WORKLOAD_BIN_PATH="$(readlink -f "${AGENT_BIN}")"

if [[ "${SPIRE_VERSION}" != "${EXPECTED_VERSION}" ]]; then
  echo "unexpected SPIRE version: ${SPIRE_VERSION}" >&2
  exit 1
fi
if [[ "${CURRENT_UID}" == "0" ]]; then
  echo "probe requires non-root workload caller" >&2
  exit 1
fi
for binary in "${SERVER_BIN}" "${AGENT_BIN}"; do
  test -x "${binary}"
done
test -f "${PLUGIN_SRC}/go.mod"
test -f "${PLUGIN_SRC}/main.go"

# The evidence signer source must not contain a private-key serialization path.
if grep -En 'MarshalPKCS8PrivateKey|MarshalECPrivateKey|MarshalPKCS1PrivateKey|PRIVATE KEY' "${PLUGIN_SRC}/main.go" >/dev/null; then
  echo "evidence signer contains a private-key serialization/export path" >&2
  exit 1
fi

audit_cleanup() {
  set +e
  [[ -n "${AGENT_PID:-}" ]] && kill "${AGENT_PID}" >/dev/null 2>&1 || true
  [[ -n "${SERVER_PID:-}" ]] && kill "${SERVER_PID}" >/dev/null 2>&1 || true
  [[ -n "${AGENT_PID:-}" ]] && wait "${AGENT_PID}" >/dev/null 2>&1 || true
  [[ -n "${SERVER_PID:-}" ]] && wait "${SERVER_PID}" >/dev/null 2>&1 || true
}
trap audit_cleanup EXIT

mkdir -p "${WORK_DIR}"/{server-data,agent-data,run,output,plugin,go-mod-cache,go-build-cache}
chmod 700 "${WORK_DIR}" "${WORK_DIR}/server-data" "${WORK_DIR}/agent-data" "${WORK_DIR}/run" "${WORK_DIR}/plugin"

# Compile with the exact toolchain declared by SPIRE 1.15.3 and exact pseudo-version
# of spire-plugin-sdk used by that release. Go's module checksum database remains enabled.
(
  cd "${PLUGIN_SRC}"
  GOTOOLCHAIN=go1.26.6 \
  GOMODCACHE="${WORK_DIR}/go-mod-cache" \
  GOCACHE="${WORK_DIR}/go-build-cache" \
  GOSUMDB=sum.golang.org \
    go build -trimpath -buildvcs=false -o "${PLUGIN_BIN}" .
)
test -x "${PLUGIN_BIN}"
PLUGIN_CHECKSUM="$(sha256sum "${PLUGIN_BIN}" | awk '{print $1}')"
[[ "${PLUGIN_CHECKSUM}" =~ ^[0-9a-f]{64}$ ]]

SERVER_SOCKET="${WORK_DIR}/run/server.sock"
AGENT_SOCKET="${WORK_DIR}/run/agent.sock"
SERVER_CONF="${WORK_DIR}/server.conf"
AGENT_CONF="${WORK_DIR}/agent.conf"
DISK_NEGATIVE_CONF="${WORK_DIR}/disk-negative-agent.conf"
TRUST_BUNDLE="${WORK_DIR}/run/trust-bundle.pem"
JOIN_TOKEN_FILE="${WORK_DIR}/run/join-token"
SERVER_LOG="${WORK_DIR}/server.log"
AGENT_LOG="${WORK_DIR}/agent.log"
FETCH_LOG="${WORK_DIR}/fetch.log"
SERVER_PID=""
AGENT_PID=""

cat >"${SERVER_CONF}" <<EOF
server {
    bind_address = "127.0.0.1"
    bind_port = "18281"
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
    NodeAttestor "join_token" { plugin_data {} }
    KeyManager "memory" { plugin_data = {} }
}
EOF

cat >"${AGENT_CONF}" <<EOF
agent {
    data_dir = "${WORK_DIR}/agent-data"
    log_level = "INFO"
    server_address = "127.0.0.1"
    server_port = "18281"
    socket_path = "${AGENT_SOCKET}"
    trust_bundle_path = "${TRUST_BUNDLE}"
    trust_domain = "${TRUST_DOMAIN}"
}
plugins {
    NodeAttestor "join_token" { plugin_data {} }
    KeyManager "jlmirror_nonexporting" {
        plugin_cmd = "${PLUGIN_BIN}"
        plugin_checksum = "${PLUGIN_CHECKSUM}"
    }
    WorkloadAttestor "unix" {
        plugin_data {
            discover_workload_path = true
            workload_size_limit = -1
        }
    }
}
EOF

# Negative control: a disk-backed key manager is valid SPIRE syntax but invalid for the
# JLMirror non-exporting evidence profile. The harness must detect that distinction.
cat >"${DISK_NEGATIVE_CONF}" <<EOF
plugins {
    KeyManager "disk" {
        plugin_data { directory = "${WORK_DIR}/agent-data" }
    }
}
EOF

profile_accepts() {
  local conf="$1"
  grep -F 'KeyManager "jlmirror_nonexporting"' "${conf}" >/dev/null &&
    grep -F "plugin_cmd = \"${PLUGIN_BIN}\"" "${conf}" >/dev/null &&
    grep -F "plugin_checksum = \"${PLUGIN_CHECKSUM}\"" "${conf}" >/dev/null &&
    ! grep -E 'KeyManager[[:space:]]+"(disk|memory)"' "${conf}" >/dev/null
}

profile_accepts "${AGENT_CONF}"
if profile_accepts "${DISK_NEGATIVE_CONF}"; then
  echo "disk-backed KeyManager unexpectedly passed non-exporting profile" >&2
  exit 1
fi
if grep -F 'PRIVATE KEY' "${AGENT_CONF}" "${SERVER_CONF}" >/dev/null; then
  echo "ordinary SPIRE configuration contains private key material" >&2
  exit 1
fi

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
  if [[ -S "${SERVER_SOCKET}" ]] && "${SERVER_BIN}" bundle show -socketPath "${SERVER_SOCKET}" -format pem >"${TRUST_BUNDLE}" 2>/dev/null; then
    server_ready=1
    break
  fi
  sleep 0.5
done
[[ "${server_ready}" == "1" ]]

token_output="$("${SERVER_BIN}" token generate -socketPath "${SERVER_SOCKET}" -ttl 120)"
JOIN_TOKEN="$(printf '%s\n' "${token_output}" | sed -n 's/^Token:[[:space:]]*//p' | head -n1)"
test -n "${JOIN_TOKEN}"
printf '%s' "${JOIN_TOKEN}" >"${JOIN_TOKEN_FILE}"
chmod 600 "${JOIN_TOKEN_FILE}"
unset JOIN_TOKEN token_output

export JLMIRROR_D3_KEYMANAGER_AUDIT="${PLUGIN_AUDIT}"
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
  if [[ -S "${AGENT_SOCKET}" ]] && "${AGENT_BIN}" healthcheck -socketPath "${AGENT_SOCKET}" >/dev/null 2>&1; then
    agent_ready=1
    break
  fi
  sleep 0.5
done
if [[ "${agent_ready}" != "1" ]]; then
  echo "SPIRE agent did not become ready with external signer" >&2
  cat "${AGENT_LOG}" >&2
  exit 1
fi

agent_json="$("${SERVER_BIN}" agent list -socketPath "${SERVER_SOCKET}" -attestationType join_token -output json)"
ATTESTED_NODE_ID="$(AGENT_JSON="${agent_json}" TRUST_DOMAIN="${TRUST_DOMAIN}" python3 - <<'PY'
import json
import os
payload = json.loads(os.environ['AGENT_JSON'])
agents = payload.get('agents', [])
if len(agents) != 1:
    raise SystemExit(f'expected one attested agent, got {len(agents)}')
item = agents[0].get('id') or {}
if item.get('trust_domain') != os.environ['TRUST_DOMAIN']:
    raise SystemExit('attested agent trust domain mismatch')
path = item.get('path')
if not isinstance(path, str) or not path.startswith('/spire/agent/join_token/'):
    raise SystemExit('unexpected attested agent path')
print(f"spiffe://{item['trust_domain']}{path}")
PY
)"
unset agent_json
test -n "${ATTESTED_NODE_ID}"

"${SERVER_BIN}" entry create \
  -socketPath "${SERVER_SOCKET}" \
  -parentID "${ATTESTED_NODE_ID}" \
  -spiffeID "${WORKLOAD_ID}" \
  -selector "unix:uid:${CURRENT_UID}" \
  -selector "unix:path:${WORKLOAD_BIN_PATH}" \
  -x509SVIDTTL 30 >/dev/null

fetch_ready=0
for _ in $(seq 1 30); do
  rm -rf "${WORK_DIR}/output"/*
  if "${AGENT_BIN}" api fetch x509 -socketPath "${AGENT_SOCKET}" -timeout 2s -write "${WORK_DIR}/output" >"${FETCH_LOG}" 2>&1; then
    fetch_ready=1
    break
  fi
  sleep 0.5
done
if [[ "${fetch_ready}" != "1" ]]; then
  echo "workload SVID did not propagate through external signer profile" >&2
  cat "${FETCH_LOG}" >&2 || true
  exit 1
fi

mapfile -t workload_keys < <(find "${WORK_DIR}/output" -maxdepth 1 -type f -name 'svid.*.key' | sort)
mapfile -t workload_certs < <(find "${WORK_DIR}/output" -maxdepth 1 -type f -name 'svid.*.pem' ! -name '*.key' | sort)
if [[ "${#workload_keys[@]}" -ne 1 || "${#workload_certs[@]}" -ne 1 ]]; then
  echo "expected one short-lived workload cert/key pair" >&2
  find "${WORK_DIR}/output" -maxdepth 1 -type f -print >&2 || true
  exit 1
fi

# Workload SVID key delivery is intentionally local to the attested workload and is not
# confused with the agent SVID/secret-authority key managed behind the KeyManager RPC.
grep -F 'PRIVATE KEY' "${workload_keys[0]}" >/dev/null
CERT_TEXT="$(openssl x509 -in "${workload_certs[0]}" -noout -text)"
printf '%s\n' "${CERT_TEXT}" | grep -F "URI:${WORKLOAD_ID}" >/dev/null
NOT_BEFORE="$(openssl x509 -in "${workload_certs[0]}" -noout -startdate | cut -d= -f2-)"
NOT_AFTER="$(openssl x509 -in "${workload_certs[0]}" -noout -enddate | cut -d= -f2-)"
LIFETIME="$(( $(date -u -d "${NOT_AFTER}" +%s) - $(date -u -d "${NOT_BEFORE}" +%s) ))"
if (( LIFETIME <= 0 || LIFETIME > 45 )); then
  echo "workload SVID key is not bound to bounded short-lived credential lifetime: ${LIFETIME}s" >&2
  exit 1
fi

# Actual agent SVID operations must have crossed the external plugin boundary.
test -f "${PLUGIN_AUDIT}"
grep -E '^generate:agent-svid-[AB]$' "${PLUGIN_AUDIT}" >/dev/null
grep -E '^sign:agent-svid-[AB]$' "${PLUGIN_AUDIT}" >/dev/null

# No agent SVID private key may be serialized into the SPIRE agent data/config surface.
if find "${WORK_DIR}/agent-data" -type f \( -name 'keys.json' -o -name '*.key' -o -name '*.pem' \) -print | grep -q .; then
  echo "agent key material unexpectedly persisted as ordinary key/certificate file" >&2
  find "${WORK_DIR}/agent-data" -type f -maxdepth 2 -print >&2 || true
  exit 1
fi
if grep -R -a -l 'BEGIN .*PRIVATE KEY' "${WORK_DIR}/agent-data" >/dev/null 2>&1; then
  echo "agent private key marker found in persistent agent data" >&2
  exit 1
fi

printf 'private_key_non_exportability_profile=PASS signer_boundary=external_process_rpc_only plugin_checksum=%s\n' "${PLUGIN_CHECKSUM}"
printf 'agent_svid_private_key=NON_PERSISTED_NON_EXPORT_RPC disk_profile_rejected=true signer_generate_and_sign_observed=true\n'
printf 'workload_svid_private_key=EXPECTED_SHORT_LIVED_WORKLOAD_LOCAL lifetime_seconds=%s secret_authority_equivalence=false\n' "${LIFETIME}"
printf 'conformance_claim=exploratory_only evidence_credited=false ledger_change=false\n'
printf 'wave4=not_granted production=none d4=not_selected_not_granted\n'
