# ---------------------------------------------------------------------------
# Isolated activation-commit rollback proof.
# A pre-existing conflicting grant forces the Tier 1 grant INSERT to fail after
# the placement UPDATE executes inside the function. PostgreSQL must roll back
# both effects, leaving placement fenced and the target sealed.
# ---------------------------------------------------------------------------
atomic_tenant="aaaaaaaa-0000-0000-0000-000000000003"
atomic_observation="obs-atomicity-1"
atomic_checkpoint_conflict="22222222-2222-2222-2222-222222222222"

pg_sql "INSERT INTO relocation_evidence.placement(tenant_id,phase,current_writer,placement_version) VALUES('$atomic_tenant','active','source',1);" >/dev/null
atomic_accept="$(pg_sql "SELECT relocation_evidence.accept_observation('$atomic_tenant','source',1,'$atomic_observation','$metric','2026-08-28T09:00:00Z',7.25)::text;")"
assert_exact "relocation_atomicity_source_accept" "true" "$atomic_accept"
atomic_fence="$(pg_sql "SELECT relocation_evidence.fence_source('$atomic_tenant');")"
atomic_ordinal="$(pg_sql "SELECT accepted_ordinal FROM relocation_evidence.acceptance WHERE tenant_id='$atomic_tenant' AND observation_id='$atomic_observation';")"
assert_exact "relocation_atomicity_fence_covers_accept" "$atomic_ordinal" "$atomic_fence"

ts_sql "
  INSERT INTO relocation_evidence.target_control(tenant_id,phase) VALUES('$atomic_tenant','open');
  SET ROLE ts_automation_owner;
  INSERT INTO relocation_evidence.target_history(
    tenant_id,observation_id,metric_definition_id,accepted_ordinal,observed_at,numeric_value
  ) VALUES(
    '$atomic_tenant','$atomic_observation','$metric',$atomic_ordinal,'2026-08-28T09:00:00Z',7.25
  );
  RESET ROLE;
" >/dev/null

atomic_attestation="$(ts_sql "SET ROLE ts_automation_owner; SELECT checkpoint_id||'|'||checkpoint_generation||'|'||target_sealed||'|'||target_count||'|'||target_digest||'|'||target_max_ordinal||'|'||attestation FROM relocation_evidence.attest_target_checkpoint('$atomic_tenant',$atomic_fence,true,0); RESET ROLE;")"
IFS='|' read -r atomic_cp atomic_gen atomic_sealed atomic_count atomic_digest atomic_max atomic_hmac <<< "$atomic_attestation"
assert_exact "relocation_atomicity_checkpoint_sealed" "true" "$atomic_sealed"
atomic_receipt="$(pg_sql "SELECT relocation_evidence.record_projection_receipt('$atomic_tenant',$atomic_fence,'$atomic_cp',$atomic_gen,$atomic_sealed,$atomic_count,'$atomic_digest',$atomic_max,'$atomic_hmac');")"
assert_exact "relocation_atomicity_receipt_complete" "complete" "$atomic_receipt"

# Occupy the unique grant slot with an invalid grant. It cannot authorize the
# target because verify_activation_grant also requires exact checkpoint facts
# and an already-active matching placement version.
pg_sql "
  INSERT INTO relocation_evidence.activation_grant(
    tenant_id,fence_ordinal,checkpoint_id,checkpoint_generation,target_attestation,
    placement_version,state
  ) VALUES(
    '$atomic_tenant',$atomic_fence,'$atomic_checkpoint_conflict',999,'forged',2,'committed'
  );
" >/dev/null

expect_pg_reject "relocation_activation_commit_conflict_rolls_back" "duplicate key value violates unique constraint" \
  "SELECT relocation_evidence.activate_target('$atomic_tenant')::text;"

atomic_placement_after_conflict="$(pg_sql "SELECT phase||'|'||current_writer||'|'||placement_version||'|'||fence_ordinal FROM relocation_evidence.placement WHERE tenant_id='$atomic_tenant';")"
assert_exact "relocation_activation_conflict_preserves_fenced_placement" "fenced|none|1|$atomic_fence" "$atomic_placement_after_conflict"
atomic_conflict_grant="$(pg_sql "SELECT checkpoint_id||'|'||checkpoint_generation||'|'||target_attestation||'|'||placement_version FROM relocation_evidence.activation_grant WHERE tenant_id='$atomic_tenant' AND fence_ordinal=$atomic_fence;")"
assert_exact "relocation_activation_conflict_did_not_replace_grant" "$atomic_checkpoint_conflict|999|forged|2" "$atomic_conflict_grant"
atomic_target_mark="$(ts_sql "SET ROLE ts_automation_owner; SELECT relocation_evidence.mark_target_checkpoint_activated('$atomic_tenant','$atomic_cp',2)::text; RESET ROLE;")"
assert_exact "relocation_conflicting_grant_cannot_activate_target" "false" "$atomic_target_mark"
atomic_target_phase="$(ts_sql "SELECT phase FROM relocation_evidence.target_control WHERE tenant_id='$atomic_tenant';")"
assert_exact "relocation_activation_conflict_keeps_target_sealed" "sealed" "$atomic_target_phase"

# Remove only the injected conflict so it cannot affect the main relocation
# scenario. The isolated tenant remains safely fenced/sealed.
pg_sql "DELETE FROM relocation_evidence.activation_grant WHERE tenant_id='$atomic_tenant' AND fence_ordinal=$atomic_fence;" >/dev/null
printf '%s\n' 'relocation_activation_grant_placement_atomicity=PASS'
