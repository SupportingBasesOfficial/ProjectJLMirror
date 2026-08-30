#!/usr/bin/env bash
set -euo pipefail

: "${SPIRE_ROOT:?SPIRE_ROOT is required}"
: "${SPIRE_VERSION:?SPIRE_VERSION is required}"
: "${WORK_DIR:?WORK_DIR is required}"

SERVER_BIN="${SPIRE_ROOT}/bin/spire-server"
AGENT_BIN="${SPIRE_ROOT}/bin/spire-agent"
EXPECTED_VERSION="1.15.3"
TRUST_DOMAIN="rotation.validation.d3.jlmirror.invalid"
CURRENT_UID="$(id -u)"
FORBIDDEN_UID="0"
WORKLOAD_BIN_PATH="$(readlink -f "${AGENT_BIN}")"
WORKLOAD_ID="spiffe://${TRUST_DOMAIN}/runtime/rotation-evidence/v1/workload"

if [[ "${SPIRE_VERSION}" != "${EXPECTED_VERSION}" ]]; then
  echo "unexpected SPIRE version: ${SPIRE_VERSION}" >&2
  exit 1
fi
if [[ "${CURRENT_UID}" == "${FORBIDDEN_UID}" ]]; then
  echo "rotation probe requires a non-root workload caller" >&2
  exit 1
fi
for binary in "${SERVER_BIN}" "${AGENT_BIN}"; do
  test -x "${binary}"
done

mkdir -p "${WORK_DIR}"/{server-data,agent-data,run,initial-output,rotation-output,final-output}
chmod 700 "${WORK_DIR}" "${WORK_DIR}/server-data" "${WORK_DIR}/agent-data" "${WORK_DIR}/run"

SERVER_SOCKET="${WORK_DIR}/run/server.sock"
AGENT_SOCKET="${WORK_DIR}/run/agent.sock"
SERVER_CONF="${WORK_DIR}/server.conf"
AGENT_CONF="${WORK_DIR}/agent.conf"
BOOTSTRAP_BUNDLE="${WORK_DIR}/run/bootstrap-bundle.pem"
JOIN_TOKEN_FILE="${WORK_DIR}/run/join-token"
SERVER_LOG="${WORK_DIR}/server.log"
AGENT_LOG="${WORK_DIR}/agent.log"
FETCH_LOG="${WORK_DIR}/fetch.log"
PRE_CA_SVID="${WORK_DIR}/run/pre-ca-svid.pem"
POST_CA_SVID="${WORK_DIR}/run/post-ca-svid.pem"
ACTIVE_CA_DER="${WORK_DIR}/run/active-ca.der"
ACTIVE_CA_PEM="${WORK_DIR}/run/active-ca.pem"
FINAL_BUNDLE="${WORK_DIR}/run/final-bundle.pem"
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

cert_fingerprint() {
  openssl x509 -in "$1" -noout -fingerprint -sha256 | cut -d= -f2
}

single_svid_cert() {
  local output_dir="$1"
  local -a certs
  mapfile -t certs < <(find "${output_dir}" -maxdepth 1 -type f -name 'svid.*.pem' ! -name '*.key' | sort)
  if [[ "${#certs[@]}" -ne 1 ]]; then
    return 1
  fi
  printf '%s\n' "${certs[0]}"
}

cat >"${SERVER_CONF}" <<EOF_SERVER
server {
    bind_address = "127.0.0.1"
    bind_port = "18082"
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
EOF_SERVER

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
     "${SERVER_BIN}" bundle show -socketPath "${SERVER_SOCKET}" -format pem >"${BOOTSTRAP_BUNDLE}" 2>/dev/null; then
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

cat >"${AGENT_CONF}" <<EOF_AGENT
agent {
    data_dir = "${WORK_DIR}/agent-data"
    log_level = "INFO"
    server_address = "127.0.0.1"
    server_port = "18082"
    socket_path = "${AGENT_SOCKET}"
    trust_bundle_path = "${BOOTSTRAP_BUNDLE}"
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
EOF_AGENT

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
if trust_domain != os.environ["TRUST_DOMAIN"]:
    raise SystemExit(f"attested agent trust domain mismatch: {trust_domain!r}")
if not isinstance(path, str) or not path.startswith("/spire/agent/join_token/"):
    raise SystemExit(f"attested agent path is outside join_token backend namespace: {path!r}")
print(f"spiffe://{trust_domain}{path}")
PY
)"
unset agent_json

"${SERVER_BIN}" entry create \
  -socketPath "${SERVER_SOCKET}" \
  -parentID "${ATTESTED_NODE_ID}" \
  -spiffeID "${WORKLOAD_ID}" \
  -selector "unix:uid:${CURRENT_UID}" \
  -selector "unix:path:${WORKLOAD_BIN_PATH}" \
  -x509SVIDTTL 30 >/dev/null

initial_ready=0
for _ in $(seq 1 30); do
  rm -rf "${WORK_DIR}/initial-output"/*
  if "${AGENT_BIN}" api fetch x509 \
       -socketPath "${AGENT_SOCKET}" \
       -timeout 2s \
       -write "${WORK_DIR}/initial-output" >"${FETCH_LOG}" 2>&1; then
    INITIAL_SVID="$(single_svid_cert "${WORK_DIR}/initial-output" || true)"
    if [[ -n "${INITIAL_SVID}" ]]; then
      initial_ready=1
      break
    fi
  fi
  sleep 0.5
done
if [[ "${initial_ready}" != "1" ]]; then
  echo "authorized workload SVID did not propagate within bounded 15s evidence window" >&2
  cat "${FETCH_LOG}" >&2 || true
  exit 1
fi

INITIAL_TEXT="$(openssl x509 -in "${INITIAL_SVID}" -noout -text)"
printf '%s\n' "${INITIAL_TEXT}" | grep -F "URI:${WORKLOAD_ID}" >/dev/null
NOT_BEFORE="$(openssl x509 -in "${INITIAL_SVID}" -noout -startdate | cut -d= -f2-)"
NOT_AFTER="$(openssl x509 -in "${INITIAL_SVID}" -noout -enddate | cut -d= -f2-)"
NOT_BEFORE_EPOCH="$(date -u -d "${NOT_BEFORE}" +%s)"
NOT_AFTER_EPOCH="$(date -u -d "${NOT_AFTER}" +%s)"
LIFETIME="$((NOT_AFTER_EPOCH - NOT_BEFORE_EPOCH))"
if (( LIFETIME <= 0 || LIFETIME > 45 )); then
  echo "X.509-SVID lifetime is outside bounded short-lived evidence profile: ${LIFETIME}s" >&2
  exit 1
fi

# Prove ordinary short-lived renewal first. The agent rotates around half-life with jitter;
# a 45s bounded window spans a complete 30s credential lifetime without assuming success.
INITIAL_FINGERPRINT="$(cert_fingerprint "${INITIAL_SVID}")"
natural_rotation=0
for _ in $(seq 1 45); do
  rm -rf "${WORK_DIR}/rotation-output"/*
  if "${AGENT_BIN}" api fetch x509 \
       -socketPath "${AGENT_SOCKET}" \
       -timeout 2s \
       -write "${WORK_DIR}/rotation-output" >/dev/null 2>&1; then
    ROTATED_CERT="$(single_svid_cert "${WORK_DIR}/rotation-output" || true)"
    if [[ -n "${ROTATED_CERT}" ]]; then
      ROTATED_FINGERPRINT="$(cert_fingerprint "${ROTATED_CERT}")"
      if [[ "${ROTATED_FINGERPRINT}" != "${INITIAL_FINGERPRINT}" ]]; then
        natural_rotation=1
        cp "${ROTATED_CERT}" "${PRE_CA_SVID}"
        break
      fi
    fi
  fi
  sleep 1
done
if [[ "${natural_rotation}" != "1" ]]; then
  echo "short-lived X.509-SVID did not rotate within bounded 45s evidence window" >&2
  exit 1
fi
PRE_CA_FINGERPRINT="$(cert_fingerprint "${PRE_CA_SVID}")"

# Mirror SPIRE's supported force-rotation integration lifecycle instead of injecting a
# synthetic second root: prepare -> activate -> taint old -> rotate workloads -> revoke old.
authority_before="$("${SERVER_BIN}" localauthority x509 show -socketPath "${SERVER_SOCKET}" -output json)"
OLD_CA_ID="$(AUTHORITY_JSON="${authority_before}" python3 - <<'PY'
import json
import os
payload = json.loads(os.environ["AUTHORITY_JSON"])
authority_id = (payload.get("active") or {}).get("authority_id")
if not authority_id:
    raise SystemExit("no active X.509 authority before rotation")
print(authority_id)
PY
)"

prepare_output="$("${SERVER_BIN}" localauthority x509 prepare -socketPath "${SERVER_SOCKET}" -output json)"
PREPARED_CA_ID="$(AUTHORITY_JSON="${prepare_output}" python3 - <<'PY'
import json
import os
payload = json.loads(os.environ["AUTHORITY_JSON"])
authority_id = (payload.get("prepared_authority") or {}).get("authority_id")
if not authority_id:
    raise SystemExit("SPIRE did not return a prepared X.509 authority")
print(authority_id)
PY
)"
if [[ "${PREPARED_CA_ID}" == "${OLD_CA_ID}" ]]; then
  echo "prepared X.509 authority unexpectedly reused the active authority ID" >&2
  exit 1
fi

"${SERVER_BIN}" localauthority x509 activate \
  -socketPath "${SERVER_SOCKET}" \
  -authorityID "${PREPARED_CA_ID}" \
  -output json >/dev/null

authority_after_activate="$("${SERVER_BIN}" localauthority x509 show -socketPath "${SERVER_SOCKET}" -output json)"
AUTHORITY_JSON="${authority_after_activate}" OLD_CA_ID="${OLD_CA_ID}" NEW_CA_ID="${PREPARED_CA_ID}" python3 - <<'PY'
import json
import os
payload = json.loads(os.environ["AUTHORITY_JSON"])
active = (payload.get("active") or {}).get("authority_id")
old = (payload.get("old") or {}).get("authority_id")
if active != os.environ["NEW_CA_ID"]:
    raise SystemExit(f"active authority mismatch after activation: {active!r}")
if old != os.environ["OLD_CA_ID"]:
    raise SystemExit(f"old authority mismatch after activation: {old!r}")
PY

"${SERVER_BIN}" localauthority x509 taint \
  -socketPath "${SERVER_SOCKET}" \
  -authorityID "${OLD_CA_ID}" \
  -output json >/dev/null

bundle_after_taint="$("${SERVER_BIN}" bundle show -socketPath "${SERVER_SOCKET}" -output json)"
BUNDLE_JSON="${bundle_after_taint}" ACTIVE_CA_DER="${ACTIVE_CA_DER}" python3 - <<'PY'
import base64
import json
import os
payload = json.loads(os.environ["BUNDLE_JSON"])
authorities = payload.get("x509_authorities", [])
tainted = [item for item in authorities if item.get("tainted") is True]
active = [item for item in authorities if item.get("tainted") is False]
if len(tainted) != 1 or len(active) != 1:
    raise SystemExit(f"expected one tainted and one active authority, got tainted={len(tainted)} active={len(active)}")
asn1 = active[0].get("asn1")
if not isinstance(asn1, str) or not asn1:
    raise SystemExit("active authority did not expose ASN.1 material")
with open(os.environ["ACTIVE_CA_DER"], "wb") as handle:
    handle.write(base64.b64decode(asn1, validate=True))
PY
openssl x509 -inform der -in "${ACTIVE_CA_DER}" -out "${ACTIVE_CA_PEM}"

ca_rotation=0
for _ in $(seq 1 30); do
  rm -rf "${WORK_DIR}/rotation-output"/*
  if "${AGENT_BIN}" api fetch x509 \
       -socketPath "${AGENT_SOCKET}" \
       -timeout 2s \
       -write "${WORK_DIR}/rotation-output" >/dev/null 2>&1; then
    POST_TAINT_CERT="$(single_svid_cert "${WORK_DIR}/rotation-output" || true)"
    if [[ -n "${POST_TAINT_CERT}" ]]; then
      POST_TAINT_FINGERPRINT="$(cert_fingerprint "${POST_TAINT_CERT}")"
      if [[ "${POST_TAINT_FINGERPRINT}" != "${PRE_CA_FINGERPRINT}" ]] && \
         openssl verify -no_check_time -CAfile "${ACTIVE_CA_PEM}" "${POST_TAINT_CERT}" >/dev/null 2>&1; then
        ca_rotation=1
        cp "${POST_TAINT_CERT}" "${POST_CA_SVID}"
        break
      fi
    fi
  fi
  sleep 1
done
if [[ "${ca_rotation}" != "1" ]]; then
  echo "workload SVID did not rotate onto the active non-tainted CA within bounded 30s" >&2
  cat "${AGENT_LOG}" >&2 || true
  exit 1
fi

"${SERVER_BIN}" localauthority x509 revoke \
  -socketPath "${SERVER_SOCKET}" \
  -authorityID "${OLD_CA_ID}" \
  -output json >/dev/null

# Require server and Workload API bundle convergence. -no_check_time makes the historical
# SVID negative a trust-retirement assertion instead of an expiration assertion.
retired_bundle=0
for _ in $(seq 1 30); do
  server_bundle_json="$("${SERVER_BIN}" bundle show -socketPath "${SERVER_SOCKET}" -output json)"
  server_bundle_count="$(BUNDLE_JSON="${server_bundle_json}" python3 - <<'PY'
import json
import os
payload = json.loads(os.environ["BUNDLE_JSON"])
print(len(payload.get("x509_authorities", [])))
PY
)"
  if [[ "${server_bundle_count}" != "1" ]]; then
    sleep 1
    continue
  fi

  rm -rf "${WORK_DIR}/final-output"/*
  if ! "${AGENT_BIN}" api fetch x509 \
       -socketPath "${AGENT_SOCKET}" \
       -timeout 2s \
       -write "${WORK_DIR}/final-output" >/dev/null 2>&1; then
    sleep 1
    continue
  fi

  FINAL_SVID="$(single_svid_cert "${WORK_DIR}/final-output" || true)"
  FINAL_BUNDLE_SOURCE="$(find "${WORK_DIR}/final-output" -maxdepth 1 -type f -name 'bundle.*.pem' | sort | head -n1)"
  if [[ -z "${FINAL_SVID}" || -z "${FINAL_BUNDLE_SOURCE}" ]]; then
    sleep 1
    continue
  fi
  FINAL_BUNDLE_COUNT="$(grep -c -- '-----BEGIN CERTIFICATE-----' "${FINAL_BUNDLE_SOURCE}" || true)"
  if [[ "${FINAL_BUNDLE_COUNT}" != "1" ]]; then
    sleep 1
    continue
  fi
  cp "${FINAL_BUNDLE_SOURCE}" "${FINAL_BUNDLE}"

  if ! openssl verify -no_check_time -CAfile "${FINAL_BUNDLE}" "${FINAL_SVID}" >/dev/null 2>&1; then
    sleep 1
    continue
  fi
  if openssl verify -no_check_time -CAfile "${FINAL_BUNDLE}" "${PRE_CA_SVID}" >/dev/null 2>&1; then
    echo "pre-rotation SVID still validated after old authority revocation" >&2
    exit 1
  fi
  retired_bundle=1
  break
done
if [[ "${retired_bundle}" != "1" ]]; then
  echo "revoked X.509 authority did not disappear from the Workload API bundle within bounded 30s" >&2
  exit 1
fi

printf 'spire_rotation_candidate_evaluation=PASS version=%s trust_domain=%s\n' "${SPIRE_VERSION}" "${TRUST_DOMAIN}"
printf 'short_lived_x509_svid=PASS lifetime_seconds=%s natural_rotation=true\n' "${LIFETIME}"
printf 'rotation_retired_bundle=PASS old_authority=%s active_authority=%s historical_svid_rejected_no_check_time=true current_bundle_authorities=1\n' \
  "${OLD_CA_ID}" "${PREPARED_CA_ID}"
printf 'conformance_claim=exploratory_only evidence_credited=false ledger_change=false\n'
printf 'wave4=not_granted production=none d4=not_selected_not_granted\n'
