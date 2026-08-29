pg_canonical_separator="$(pg_sql "SELECT relocation_evidence.canonical_field(E'obs\\x1fmid\\x1etail');")"
ts_canonical_separator="$(ts_sql "SELECT relocation_evidence.canonical_field(E'obs\\x1fmid\\x1etail');")"
assert_exact "relocation_canonical_field_cross_store" "$pg_canonical_separator" "$ts_canonical_separator"

checkpoint_probe_id="11111111-1111-1111-1111-111111111111"
checkpoint_probe_digest="$(printf 'ab%.0s' $(seq 1 32))"
pg_checkpoint_payload="$(pg_sql "SELECT relocation_evidence.canonical_checkpoint_payload('$tenant',3,'$checkpoint_probe_id',1,true,3,'$checkpoint_probe_digest',3);")"
ts_checkpoint_payload="$(ts_sql "SELECT relocation_evidence.canonical_checkpoint_payload('$tenant',3,'$checkpoint_probe_id',1,true,3,'$checkpoint_probe_digest',3);")"
assert_exact "relocation_checkpoint_hmac_payload_cross_store" "$pg_checkpoint_payload" "$ts_checkpoint_payload"

expect_ts_reject "relocation_projection_writer_cannot_read_attestation_key" "permission denied" \
  "SET ROLE ts_automation_owner; SELECT key_material FROM relocation_evidence.target_attestation_key;"
expect_ts_reject "relocation_target_verifier_cannot_read_attestation_key" "permission denied" \
  "SET ROLE relocation_target_verifier; SELECT key_material FROM relocation_evidence.target_attestation_key;"
expect_ts_reject "relocation_projection_writer_cannot_disable_freeze" "must be owner" \
  "SET ROLE ts_automation_owner; ALTER TABLE relocation_evidence.target_history DISABLE TRIGGER target_history_freeze;"

# ---------------------------------------------------------------------------
# Source lock-before-F race.
# ---------------------------------------------------------------------------
set +e
docker exec -e PGPASSWORD="$password" "$pg_container" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c \
  "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-race-pre-fence','$metric','2026-08-28T10:01:30Z',12.5,2.0)::text;" \
  >"$race_out" 2>&1 &
race_pid=$!
set -e

race_sleeping=0
for _ in $(seq 1 100); do
  sleeping="$(pg_sql "SELECT count(*) FROM pg_stat_activity WHERE datname='jlmirror' AND query LIKE '%obs-race-pre-fence%' AND wait_event='PgSleep';")"
  if [[ "$sleeping" -ge 1 ]]; then race_sleeping=1; break; fi
  sleep 0.02
done
if [[ "$race_sleeping" != "1" ]]; then
  cat "$race_out" >&2 || true; kill "$race_pid" >/dev/null 2>&1 || true; wait "$race_pid" >/dev/null 2>&1 || true
  echo "relocation fence race setup never observed acceptance sleeping after placement lock" >&2; exit 1
fi
printf '%s\n' 'relocation_acceptance_lock_race_setup=PASS'

fence="$(pg_sql "SELECT relocation_evidence.fence_source('$tenant');")"
wait "$race_pid"
race_result="$(tr -d '[:space:]' < "$race_out")"
assert_exact "relocation_racing_acceptance_committed" "true" "$race_result"
ord_race="$(pg_sql "SELECT accepted_ordinal FROM relocation_evidence.acceptance WHERE observation_id='obs-race-pre-fence';")"
assert_exact "relocation_fence_includes_inflight_acceptance" "$ord_race" "$fence"
stale_during_fence="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-stale-during-fence','$metric','2026-08-28T10:01:45Z',99)::text;")"
assert_exact "relocation_source_blocked_after_fence" "false" "$stale_during_fence"
premature_no_receipt="$(pg_sql "SELECT relocation_evidence.activate_target('$tenant')::text;")"
assert_exact "relocation_target_cannot_activate_without_receipt" "false" "$premature_no_receipt"

ord1="$(pg_sql "SELECT accepted_ordinal FROM relocation_evidence.acceptance WHERE observation_id='obs-pre-1';")"
ord2="$(pg_sql "SELECT accepted_ordinal FROM relocation_evidence.acceptance WHERE observation_id='obs-pre-2';")"

# max(target)=F with lower gap remains incomplete.
ts_sql "SET ROLE ts_automation_owner; INSERT INTO relocation_evidence.target_history(tenant_id,observation_id,metric_definition_id,accepted_ordinal,observed_at,numeric_value) VALUES('$tenant','obs-race-pre-fence','$metric',$ord_race,'2026-08-28T10:01:30Z',12.5); RESET ROLE;" >/dev/null

gap_attestation="$(ts_sql "SET ROLE ts_automation_owner; SELECT checkpoint_id||'|'||checkpoint_generation||'|'||target_sealed||'|'||target_count||'|'||target_digest||'|'||target_max_ordinal||'|'||attestation FROM relocation_evidence.attest_target_checkpoint('$tenant',$fence,false,0); RESET ROLE;")"
IFS='|' read -r gap_cp gap_gen gap_sealed gap_count gap_digest gap_max gap_hmac <<< "$gap_attestation"
assert_exact "relocation_incomplete_target_still_reaches_F" "$fence" "$gap_max"
gap_receipt="$(pg_sql "SELECT relocation_evidence.record_projection_receipt('$tenant',$fence,'$gap_cp',$gap_gen,$gap_sealed,$gap_count,'$gap_digest',$gap_max,'$gap_hmac');")"
assert_exact "relocation_gap_receipt_detected" "incomplete" "$gap_receipt"
assert_exact "relocation_target_cannot_activate_with_gap_at_F" "false" "$(pg_sql "SELECT relocation_evidence.activate_target('$tenant')::text;")"

ts_sql "SET ROLE ts_automation_owner;
  INSERT INTO relocation_evidence.target_history(tenant_id,observation_id,metric_definition_id,accepted_ordinal,observed_at,numeric_value) VALUES
    ('$tenant','obs-pre-1','$metric',$ord1,'2026-08-28T10:00:00Z',10.5),
    ('$tenant','obs-pre-2','$metric',$ord2,'2026-08-28T10:01:00Z',11.5)
  ON CONFLICT DO NOTHING; RESET ROLE;" >/dev/null

ts_sql "SET ROLE ts_automation_owner; UPDATE relocation_evidence.target_history SET observed_at=observed_at+interval '1 second' WHERE tenant_id='$tenant' AND observation_id='obs-pre-1'; RESET ROLE;" >/dev/null
payload_attestation="$(ts_sql "SET ROLE ts_automation_owner; SELECT checkpoint_id||'|'||checkpoint_generation||'|'||target_sealed||'|'||target_count||'|'||target_digest||'|'||target_max_ordinal||'|'||attestation FROM relocation_evidence.attest_target_checkpoint('$tenant',$fence,false,0); RESET ROLE;")"
IFS='|' read -r payload_cp payload_gen payload_sealed payload_count payload_digest payload_max payload_hmac <<< "$payload_attestation"
payload_receipt="$(pg_sql "SELECT relocation_evidence.record_projection_receipt('$tenant',$fence,'$payload_cp',$payload_gen,$payload_sealed,$payload_count,'$payload_digest',$payload_max,'$payload_hmac');")"
assert_exact "relocation_canonical_payload_mismatch_detected" "incomplete" "$payload_receipt"
ts_sql "SET ROLE ts_automation_owner; UPDATE relocation_evidence.target_history SET observed_at='2026-08-28T10:00:00Z' WHERE tenant_id='$tenant' AND observation_id='obs-pre-1'; RESET ROLE;" >/dev/null

future_ordinal=$((fence + 1))
ts_sql "SET ROLE ts_automation_owner; INSERT INTO relocation_evidence.target_history(tenant_id,observation_id,metric_definition_id,accepted_ordinal,observed_at,numeric_value) VALUES('$tenant','obs-uncheckpointed-future','$metric',$future_ordinal,'2026-08-28T10:01:50Z',77); RESET ROLE;" >/dev/null
expect_ts_reject "relocation_preseal_future_row_blocks_checkpoint" "target contains uncheckpointed rows above fence" \
  "SET ROLE ts_automation_owner; SELECT * FROM relocation_evidence.attest_target_checkpoint('$tenant',$fence,true,0);"
phase_after_failed_seal="$(ts_sql "SELECT phase FROM relocation_evidence.target_control WHERE tenant_id='$tenant';")"
assert_exact "relocation_failed_future_seal_remains_open" "open" "$phase_after_failed_seal"
ts_sql "SET ROLE ts_automation_owner; DELETE FROM relocation_evidence.target_history WHERE tenant_id='$tenant' AND observation_id='obs-uncheckpointed-future'; RESET ROLE;" >/dev/null

# Final seal race.
set +e
docker exec -e PGPASSWORD="$password" "$ts_container" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c \
  "SET ROLE ts_automation_owner; SELECT checkpoint_id||'|'||checkpoint_generation||'|'||target_sealed||'|'||target_count||'|'||target_digest||'|'||target_max_ordinal||'|'||attestation FROM relocation_evidence.attest_target_checkpoint('$tenant',$fence,true,2.0); RESET ROLE;" \
  >"$seal_out" 2>&1 &
seal_pid=$!
set -e

seal_sleeping=0
for _ in $(seq 1 100); do
  sleeping="$(ts_sql "SELECT count(*) FROM pg_stat_activity WHERE datname='jlmirror' AND query LIKE '%attest_target_checkpoint%true,2.0%' AND wait_event='PgSleep';")"
  if [[ "$sleeping" -ge 1 ]]; then seal_sleeping=1; break; fi
  sleep 0.02
done
if [[ "$seal_sleeping" != "1" ]]; then
  cat "$seal_out" >&2 || true; kill "$seal_pid" >/dev/null 2>&1 || true; wait "$seal_pid" >/dev/null 2>&1 || true
  echo "relocation target seal race never observed checkpoint authority sleeping after FOR UPDATE" >&2; exit 1
fi
printf '%s\n' 'relocation_target_seal_lock_race_setup=PASS'

set +e
docker exec -e PGPASSWORD="$password" "$ts_container" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c \
  "SET ROLE ts_automation_owner; UPDATE relocation_evidence.target_history SET numeric_value=numeric_value+1 WHERE tenant_id='$tenant' AND observation_id='obs-pre-1'; RESET ROLE;" \
  >"$seal_mutation_out" 2>&1 &
seal_mutation_pid=$!
set -e
sleep 0.10
if ! kill -0 "$seal_mutation_pid" >/dev/null 2>&1; then
  cat "$seal_mutation_out" >&2 || true; wait "$seal_mutation_pid" >/dev/null 2>&1 || true
  echo "relocation concurrent target mutation did not block behind checkpoint seal" >&2; exit 1
fi
printf '%s\n' 'relocation_target_seal_blocks_concurrent_mutation=PASS'

wait "$seal_pid"
sealed_attestation="$(tr -d '\r\n' < "$seal_out")"
IFS='|' read -r sealed_cp sealed_gen sealed_flag sealed_count sealed_digest sealed_max sealed_hmac <<< "$sealed_attestation"
assert_exact "relocation_target_checkpoint_is_sealed" "true" "$sealed_flag"

set +e
wait "$seal_mutation_pid"; seal_mutation_rc=$?
set -e
seal_mutation_result="$(cat "$seal_mutation_out")"
if [[ $seal_mutation_rc -eq 0 || "$seal_mutation_result" != *"sealed target checkpoint forbids all pre-activation mutation"* ]]; then
  printf 'relocation_target_seal_rejects_concurrent_mutation rc=%s output=%q\n' "$seal_mutation_rc" "$seal_mutation_result" >&2; exit 1
fi
printf '%s\n' 'relocation_target_seal_rejects_concurrent_mutation=PASS'

expect_ts_reject "relocation_postseal_future_insert_rejected" "sealed target checkpoint forbids all pre-activation mutation" \
  "SET ROLE ts_automation_owner; INSERT INTO relocation_evidence.target_history(tenant_id,observation_id,metric_definition_id,accepted_ordinal,observed_at,numeric_value) VALUES('$tenant','obs-postseal-future','$metric',$future_ordinal,'2026-08-28T10:01:55Z',78);"

# The Tier 1 database has no target signing key. A locally minted HMAC with an
# arbitrary key must fail when Tier 1 asks the target authority to verify it.
forged_hmac="$(pg_sql "SELECT encode(public.hmac(convert_to(relocation_evidence.canonical_checkpoint_payload('$tenant',$fence,'$sealed_cp',$sealed_gen,true,$sealed_count,'$sealed_digest',$sealed_max),'UTF8'),decode(repeat('00',32),'hex'),'sha256'),'hex');")"
expect_pg_reject "relocation_tier1_cannot_mint_target_attestation" "target checkpoint not verified by target authority" \
  "SELECT relocation_evidence.record_projection_receipt('$tenant',$fence,'$sealed_cp',$sealed_gen,true,$sealed_count,'$sealed_digest',$sealed_max,'$forged_hmac');"
expect_pg_reject "relocation_fabricated_target_attestation_rejected" "target checkpoint not verified by target authority" \
  "SELECT relocation_evidence.record_projection_receipt('$tenant',$fence,'$sealed_cp',$sealed_gen,$sealed_flag,$sealed_count,'00$sealed_digest',$sealed_max,'$sealed_hmac');"
complete_receipt="$(pg_sql "SELECT relocation_evidence.record_projection_receipt('$tenant',$fence,'$sealed_cp',$sealed_gen,$sealed_flag,$sealed_count,'$sealed_digest',$sealed_max,'$sealed_hmac');")"
assert_exact "relocation_authenticated_complete_projection_receipt" "complete" "$complete_receipt"

expect_ts_reject "relocation_sealed_target_delete_rejected" "sealed target checkpoint forbids all pre-activation mutation" \
  "SET ROLE ts_automation_owner; DELETE FROM relocation_evidence.target_history WHERE tenant_id='$tenant' AND observation_id='obs-pre-2';"
expect_ts_reject "relocation_sealed_target_tenant_move_rejected" "target history tenant identity is immutable" \
  "SET ROLE ts_automation_owner; UPDATE relocation_evidence.target_history SET tenant_id='$other_tenant' WHERE tenant_id='$tenant' AND observation_id='obs-pre-2';"

# Target cannot leave sealed state until Tier 1 has durably committed the exact
# checkpoint activation grant and new placement version.
premature_target_mark="$(ts_sql "SET ROLE ts_automation_owner; SELECT relocation_evidence.mark_target_checkpoint_activated('$tenant','$sealed_cp',2)::text; RESET ROLE;")"
assert_exact "relocation_target_cannot_self_activate_before_tier1_grant" "false" "$premature_target_mark"
expect_ts_reject "relocation_premature_mark_keeps_future_insert_blocked" "sealed target checkpoint forbids all pre-activation mutation" \
  "SET ROLE ts_automation_owner; INSERT INTO relocation_evidence.target_history(tenant_id,observation_id,metric_definition_id,accepted_ordinal,observed_at,numeric_value) VALUES('$tenant','obs-premature-future','$metric',$future_ordinal,'2026-08-28T10:01:56Z',79);"

activated="$(pg_sql "SELECT relocation_evidence.activate_target('$tenant')::text;")"
assert_exact "relocation_target_activate_after_authenticated_checkpoint" "true" "$activated"
activation_grant="$(pg_sql "SELECT state||'|'||checkpoint_id||'|'||checkpoint_generation||'|'||placement_version FROM relocation_evidence.activation_grant WHERE tenant_id='$tenant' AND fence_ordinal=$fence;")"
assert_exact "relocation_tier1_activation_grant_committed" "committed|$sealed_cp|$sealed_gen|2" "$activation_grant"
target_marked="$(ts_sql "SET ROLE ts_automation_owner; SELECT relocation_evidence.mark_target_checkpoint_activated('$tenant','$sealed_cp',2)::text; RESET ROLE;")"
assert_exact "relocation_target_checkpoint_marked_activated" "true" "$target_marked"

expect_ts_reject "relocation_activated_prefence_update_rejected" "activated target history is immutable" \
  "SET ROLE ts_automation_owner; UPDATE relocation_evidence.target_history SET numeric_value=99 WHERE tenant_id='$tenant' AND observation_id='obs-pre-1';"

post="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','target',2,'obs-post-1','$metric','2026-08-28T10:02:00Z',13.5)::text;")"
assert_exact "relocation_target_post_cutover_accept" "true" "$post"
stale_source="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-stale-source','$metric','2026-08-28T10:03:00Z',88)::text;")"
assert_exact "relocation_stale_source_rejected" "false" "$stale_source"
ord_post="$(pg_sql "SELECT accepted_ordinal FROM relocation_evidence.acceptance WHERE observation_id='obs-post-1';")"
assert_exact "relocation_postcutover_ordinal_above_F" "$future_ordinal" "$ord_post"
ts_sql "SET ROLE ts_automation_owner; INSERT INTO relocation_evidence.target_history(tenant_id,observation_id,metric_definition_id,accepted_ordinal,observed_at,numeric_value) VALUES('$tenant','obs-post-1','$metric',$ord_post,'2026-08-28T10:02:00Z',13.5); RESET ROLE;" >/dev/null

acceptance_count="$(pg_sql "SELECT count(*) FROM relocation_evidence.acceptance WHERE tenant_id='$tenant';")"
target_count="$(ts_sql "SELECT count(*) FROM relocation_evidence.target_history WHERE tenant_id='$tenant';")"
target_distinct="$(ts_sql "SELECT count(DISTINCT observation_id) FROM relocation_evidence.target_history WHERE tenant_id='$tenant';")"
placement="$(pg_sql "SELECT phase||'|'||current_writer||'|'||placement_version||'|'||fence_ordinal FROM relocation_evidence.placement WHERE tenant_id='$tenant';")"
receipt_state="$(pg_sql "SELECT state||'|'||authoritative_count||'|'||target_count||'|'||target_max_ordinal||'|'||target_sealed FROM relocation_evidence.projection_receipt WHERE tenant_id='$tenant' AND fence_ordinal=$fence;")"
target_checkpoint_state="$(ts_sql "SELECT phase||'|'||checkpoint_id||'|'||checkpoint_generation FROM relocation_evidence.target_control WHERE tenant_id='$tenant';")"
source_digest="$(pg_sql "SELECT relocation_evidence.authoritative_digest('$tenant',$fence);")"
sealed_target_digest="$(ts_sql "SELECT target_digest FROM relocation_evidence.target_checkpoint WHERE checkpoint_id='$sealed_cp';")"

assert_exact "relocation_authoritative_acceptance_count" "4" "$acceptance_count"
assert_exact "relocation_target_history_complete" "$acceptance_count" "$target_count"
assert_exact "relocation_target_history_no_duplicates" "$target_count" "$target_distinct"
assert_exact "relocation_final_authority" "active|target|2|$fence" "$placement"
assert_exact "relocation_durable_complete_receipt" "complete|3|3|$fence|true" "$receipt_state"
assert_exact "relocation_sha256_canonical_payload_digest" "$source_digest" "$sealed_target_digest"
assert_exact "relocation_target_checkpoint_current" "activated|$sealed_cp|$sealed_gen" "$target_checkpoint_state"

if docker exec -e PGPASSWORD=report-a-evidence-only "$ts_container" \
  psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -U ts_report_a -d jlmirror -Atq \
  -c "SELECT count(*) FROM relocation_evidence.target_history;" >/tmp/relocation-attack.out 2>&1; then
  echo "relocation tenant-facing direct target-history read unexpectedly succeeded" >&2
  cat /tmp/relocation-attack.out >&2 || true
  exit 1
fi
printf '%s\n' 'relocation_tier2_direct_tenant_read=PASS rejected'
printf 'tenant_relocation_tier1_tier2_continuity=PASS F=%s receipt=%s checkpoint=%s grant=%s\n' \
  "$fence" "$receipt_state" "$sealed_cp" "$activation_grant"
