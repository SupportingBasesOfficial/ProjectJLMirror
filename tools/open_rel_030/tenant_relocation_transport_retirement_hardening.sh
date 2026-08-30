# ---------------------------------------------------------------------------
# #48 — effective relocation verifier timeout cleanup / session retirement.
#
# The earlier verifier module establishes capability stores, verifier roles and
# verification APIs. This ordered hardening module replaces only the raw bounded
# transport before subsequent relocation authority operations. On timeout,
# send-error or uncertainty there is no synchronous remote cancel/disconnect;
# the evidence harness invokes the verifier through one-shot psql backends whose
# retirement closes any abandoned connection. Successful calls disconnect
# normally. Production transport remains unselected and must preserve the same
# independently bounded cleanup/session-retirement property.
# ---------------------------------------------------------------------------
relocation_blackhole_rule_installed=0
relocation_blackhole_chain=""
relocation_blackhole_server_ip=""
relocation_blackhole_client_ip=""

cleanup() {
  if [[ "$relocation_blackhole_rule_installed" == "1" && -n "$relocation_blackhole_chain" && -n "$relocation_blackhole_server_ip" && -n "$relocation_blackhole_client_ip" ]]; then
    sudo iptables -D "$relocation_blackhole_chain" -s "$relocation_blackhole_server_ip" -d "$relocation_blackhole_client_ip" \
      -p tcp --sport 5432 -j DROP >/dev/null 2>&1 || true
    relocation_blackhole_rule_installed=0
  fi
  rm -f "$race_out" "$seal_out" "$seal_mutation_out" >/dev/null 2>&1 || true
}
trap cleanup EXIT

pg_sql "
  CREATE OR REPLACE FUNCTION relocation_evidence.bounded_remote_boolean(
    p_conn text,p_sql text,p_timeout_ms integer
  ) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
  SET search_path=pg_catalog,public
  AS \$\$
  DECLARE v_name text; v_deadline timestamptz; v_verified boolean;
  BEGIN
    IF p_timeout_ms < 50 OR p_timeout_ms > 5000 THEN RETURN false; END IF;
    v_name := 'or030_' || pg_backend_pid()::text || '_' || substr(md5(clock_timestamp()::text || random()::text),1,12);
    v_deadline := clock_timestamp() + (p_timeout_ms::text || ' milliseconds')::interval;
    PERFORM public.dblink_connect(v_name,p_conn);
    IF public.dblink_send_query(v_name,p_sql) <> 1 THEN RETURN false; END IF;
    LOOP
      EXIT WHEN public.dblink_is_busy(v_name)=0;
      IF clock_timestamp() >= v_deadline THEN RETURN false; END IF;
      PERFORM pg_catalog.pg_sleep(0.025);
    END LOOP;
    SELECT verified INTO v_verified FROM public.dblink_get_result(v_name,false) AS r(verified boolean) LIMIT 1;
    PERFORM public.dblink_disconnect(v_name);
    RETURN coalesce(v_verified,false);
  EXCEPTION WHEN OTHERS THEN
    RETURN false;
  END;
  \$\$;
  REVOKE ALL ON FUNCTION relocation_evidence.bounded_remote_boolean(text,text,integer)
    FROM PUBLIC,relocation_tier1_verifier;
" >/dev/null

ts_sql "
  CREATE OR REPLACE FUNCTION relocation_evidence.bounded_remote_boolean(
    p_conn text,p_sql text,p_timeout_ms integer
  ) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
  SET search_path=pg_catalog,public
  AS \$\$
  DECLARE v_name text; v_deadline timestamptz; v_verified boolean;
  BEGIN
    IF p_timeout_ms < 50 OR p_timeout_ms > 5000 THEN RETURN false; END IF;
    v_name := 'or030_' || pg_backend_pid()::text || '_' || substr(md5(clock_timestamp()::text || random()::text),1,12);
    v_deadline := clock_timestamp() + (p_timeout_ms::text || ' milliseconds')::interval;
    PERFORM public.dblink_connect(v_name,p_conn);
    IF public.dblink_send_query(v_name,p_sql) <> 1 THEN RETURN false; END IF;
    LOOP
      EXIT WHEN public.dblink_is_busy(v_name)=0;
      IF clock_timestamp() >= v_deadline THEN RETURN false; END IF;
      PERFORM pg_catalog.pg_sleep(0.025);
    END LOOP;
    SELECT verified INTO v_verified FROM public.dblink_get_result(v_name,false) AS r(verified boolean) LIMIT 1;
    PERFORM public.dblink_disconnect(v_name);
    RETURN coalesce(v_verified,false);
  EXCEPTION WHEN OTHERS THEN
    RETURN false;
  END;
  \$\$;
  ALTER FUNCTION relocation_evidence.bounded_remote_boolean(text,text,integer) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.bounded_remote_boolean(text,text,integer)
    FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b,ts_automation_owner,relocation_target_verifier;
" >/dev/null

pg_bounded_source="$(pg_sql "SELECT pg_get_functiondef('relocation_evidence.bounded_remote_boolean(text,text,integer)'::regprocedure);")"
ts_bounded_source="$(ts_sql "SELECT pg_get_functiondef('relocation_evidence.bounded_remote_boolean(text,text,integer)'::regprocedure);")"
for source in "$pg_bounded_source" "$ts_bounded_source"; do
  [[ "$source" == *"dblink_send_query"* && "$source" == *"dblink_is_busy"* ]] || {
    echo "effective relocation verifier transport is not asynchronous" >&2; exit 1;
  }
  [[ "$source" != *"dblink_cancel_query"* ]] || {
    echo "effective relocation verifier timeout path contains synchronous cancel" >&2; exit 1;
  }
  disconnect_count="$(grep -o 'dblink_disconnect' <<<"$source" | wc -l | tr -d ' ')"
  [[ "$disconnect_count" == "1" ]] || {
    echo "effective relocation verifier contains synchronous timeout/exception cleanup" >&2; exit 1;
  }
done
printf '%s\n' 'relocation_response_deadline_has_no_synchronous_timeout_cleanup=PASS'
printf '%s\n' 'relocation_effective_verifier_transport_uses_session_retirement=PASS'

# Re-run the cooperative stalled-response checks against the effective final
# transport, not merely the bootstrap definition from the preceding module.
pg_delay_start="$(date +%s%3N)"
pg_delay_result="$(pg_sql "
  SELECT relocation_evidence.bounded_remote_boolean(
    format('hostaddr=%s port=5432 dbname=jlmirror user=relocation_target_verifier password=%s connect_timeout=1',hostaddr,password),
    'SELECT relocation_evidence.verifier_delay_probe()',500
  )::text FROM relocation_evidence.target_verifier_connection WHERE singleton;
")"
pg_delay_end="$(date +%s%3N)"
pg_delay_ms=$((pg_delay_end - pg_delay_start))
assert_exact "relocation_target_verifier_retirement_stalled_peer_fails_closed" "false" "$pg_delay_result"
[[ "$pg_delay_ms" -lt 1800 ]] || { echo "effective Tier 1 verifier deadline not authoritative: ${pg_delay_ms}ms" >&2; exit 1; }
printf 'relocation_target_verifier_retirement_local_deadline=PASS elapsed_ms=%s\n' "$pg_delay_ms"

ts_delay_start="$(date +%s%3N)"
ts_delay_result="$(ts_sql "
  SELECT relocation_evidence.bounded_remote_boolean(
    format('hostaddr=%s port=5432 dbname=jlmirror user=relocation_tier1_verifier password=%s connect_timeout=1',hostaddr,password),
    'SELECT relocation_evidence.verifier_delay_probe()',500
  )::text FROM relocation_evidence.tier1_verifier_connection WHERE singleton;
")"
ts_delay_end="$(date +%s%3N)"
ts_delay_ms=$((ts_delay_end - ts_delay_start))
assert_exact "relocation_tier1_verifier_retirement_stalled_peer_fails_closed" "false" "$ts_delay_result"
[[ "$ts_delay_ms" -lt 1800 ]] || { echo "effective Tier 2 verifier deadline not authoritative: ${ts_delay_ms}ms" >&2; exit 1; }
printf 'relocation_tier1_verifier_retirement_local_deadline=PASS elapsed_ms=%s\n' "$ts_delay_ms"

if sudo iptables -nL DOCKER-USER >/dev/null 2>&1; then
  relocation_blackhole_chain="DOCKER-USER"
else
  relocation_blackhole_chain="FORWARD"
fi

# Tier 1 PostgreSQL client -> Tier 2 verifier server. Wait until the authenticated
# query is established, then blackhole only server->client response packets.
(
  set +e
  timeout 5s docker exec -e PGPASSWORD="$password" "$pg_container" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c "
      SELECT relocation_evidence.bounded_remote_boolean(
        format('hostaddr=%s port=5432 dbname=jlmirror user=relocation_target_verifier password=%s connect_timeout=1',hostaddr,password),
        'SELECT relocation_evidence.verifier_delay_probe()',500
      )::text FROM relocation_evidence.target_verifier_connection WHERE singleton;" \
    >"$race_out.relocation-target-blackhole.out" 2>"$race_out.relocation-target-blackhole.err"
  printf '%s\n' "$?" >"$race_out.relocation-target-blackhole.rc"
) & relocation_blackhole_pid=$!
relocation_blackhole_active=0
for _ in $(seq 1 40); do
  relocation_blackhole_active="$(ts_sql "SELECT count(*)::text FROM pg_stat_activity WHERE usename='relocation_target_verifier' AND state='active' AND query LIKE '%verifier_delay_probe%';")"
  [[ "$relocation_blackhole_active" -ge 1 ]] && break
  sleep 0.05
done
[[ "$relocation_blackhole_active" -ge 1 ]] || { echo "target verifier blackhole probe never became active" >&2; kill "$relocation_blackhole_pid" >/dev/null 2>&1 || true; wait "$relocation_blackhole_pid" >/dev/null 2>&1 || true; exit 1; }
relocation_blackhole_server_ip="$ts_ip"; relocation_blackhole_client_ip="$pg_ip"
sudo iptables -I "$relocation_blackhole_chain" 1 -s "$relocation_blackhole_server_ip" -d "$relocation_blackhole_client_ip" -p tcp --sport 5432 -j DROP
relocation_blackhole_rule_installed=1
relocation_blackhole_rule_at="$(date +%s%3N)"
wait "$relocation_blackhole_pid"
relocation_blackhole_rc="$(cat "$race_out.relocation-target-blackhole.rc")"
sudo iptables -D "$relocation_blackhole_chain" -s "$relocation_blackhole_server_ip" -d "$relocation_blackhole_client_ip" -p tcp --sport 5432 -j DROP
relocation_blackhole_rule_installed=0
relocation_blackhole_end="$(date +%s%3N)"
relocation_blackhole_ms=$((relocation_blackhole_end - relocation_blackhole_rule_at))
[[ "$relocation_blackhole_rc" == "0" ]] || { echo "target verifier blackhole exceeded watchdog rc=$relocation_blackhole_rc" >&2; cat "$race_out.relocation-target-blackhole.err" >&2 || true; exit 1; }
assert_exact "relocation_target_verifier_real_blackhole_fails_closed" "false" "$(cat "$race_out.relocation-target-blackhole.out")"
[[ "$relocation_blackhole_ms" -lt 1800 ]] || { echo "target verifier blackhole deadline not authoritative: ${relocation_blackhole_ms}ms" >&2; exit 1; }
printf 'relocation_target_verifier_real_blackhole_local_deadline=PASS elapsed_ms=%s\n' "$relocation_blackhole_ms"

# Tier 2 client -> Tier 1 verifier server, symmetric blackhole proof.
(
  set +e
  timeout 5s docker exec -e PGPASSWORD="$password" "$ts_container" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c "
      SELECT relocation_evidence.bounded_remote_boolean(
        format('hostaddr=%s port=5432 dbname=jlmirror user=relocation_tier1_verifier password=%s connect_timeout=1',hostaddr,password),
        'SELECT relocation_evidence.verifier_delay_probe()',500
      )::text FROM relocation_evidence.tier1_verifier_connection WHERE singleton;" \
    >"$race_out.relocation-tier1-blackhole.out" 2>"$race_out.relocation-tier1-blackhole.err"
  printf '%s\n' "$?" >"$race_out.relocation-tier1-blackhole.rc"
) & relocation_blackhole_pid=$!
relocation_blackhole_active=0
for _ in $(seq 1 40); do
  relocation_blackhole_active="$(pg_sql "SELECT count(*)::text FROM pg_stat_activity WHERE usename='relocation_tier1_verifier' AND state='active' AND query LIKE '%verifier_delay_probe%';")"
  [[ "$relocation_blackhole_active" -ge 1 ]] && break
  sleep 0.05
done
[[ "$relocation_blackhole_active" -ge 1 ]] || { echo "Tier 1 verifier blackhole probe never became active" >&2; kill "$relocation_blackhole_pid" >/dev/null 2>&1 || true; wait "$relocation_blackhole_pid" >/dev/null 2>&1 || true; exit 1; }
relocation_blackhole_server_ip="$pg_ip"; relocation_blackhole_client_ip="$ts_ip"
sudo iptables -I "$relocation_blackhole_chain" 1 -s "$relocation_blackhole_server_ip" -d "$relocation_blackhole_client_ip" -p tcp --sport 5432 -j DROP
relocation_blackhole_rule_installed=1
relocation_blackhole_rule_at="$(date +%s%3N)"
wait "$relocation_blackhole_pid"
relocation_blackhole_rc="$(cat "$race_out.relocation-tier1-blackhole.rc")"
sudo iptables -D "$relocation_blackhole_chain" -s "$relocation_blackhole_server_ip" -d "$relocation_blackhole_client_ip" -p tcp --sport 5432 -j DROP
relocation_blackhole_rule_installed=0
relocation_blackhole_end="$(date +%s%3N)"
relocation_blackhole_ms=$((relocation_blackhole_end - relocation_blackhole_rule_at))
[[ "$relocation_blackhole_rc" == "0" ]] || { echo "Tier 1 verifier blackhole exceeded watchdog rc=$relocation_blackhole_rc" >&2; cat "$race_out.relocation-tier1-blackhole.err" >&2 || true; exit 1; }
assert_exact "relocation_tier1_verifier_real_blackhole_fails_closed" "false" "$(cat "$race_out.relocation-tier1-blackhole.out")"
[[ "$relocation_blackhole_ms" -lt 1800 ]] || { echo "Tier 1 verifier blackhole deadline not authoritative: ${relocation_blackhole_ms}ms" >&2; exit 1; }
printf 'relocation_tier1_verifier_real_blackhole_local_deadline=PASS elapsed_ms=%s\n' "$relocation_blackhole_ms"
printf '%s\n' 'relocation_timeout_backend_retirement=PASS one_shot_sql_session=true'
