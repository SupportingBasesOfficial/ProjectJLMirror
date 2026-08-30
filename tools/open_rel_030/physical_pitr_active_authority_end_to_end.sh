#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: physical_pitr_active_authority_end_to_end.sh <external-control-container> <postgres-image>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Execute the complete base recovery vector and install the #45 active-authority
# definitions while keeping its restored instances/control authority alive.
# shellcheck source=tools/open_rel_030/physical_pitr_active_authority_hardening.sh
source "$SCRIPT_DIR/physical_pitr_active_authority_hardening.sh" "$@"

# #46: the hardened definitions themselves must complete a legitimate admission,
# not merely verify the admission that happened before they were installed.
# Reset only the local winner to the exact R state. The surviving authenticated
# effect, active authority, grant signatures and canonical boundary winner remain
# durable outside this restored database and must drive the replay.
psql_in "$restored_container" "
  DELETE FROM pitr_continuity_receipt WHERE receipt_id='$required_receipt';
  UPDATE pitr_local_state SET
    business_state='state_at_R',
    poll_epoch=5,
    poll_generation=10,
    placement_version=7,
    reconciled_through_f=false,
    external_grant_id=NULL,
    external_grant_fingerprint=NULL,
    external_effect_digest=NULL,
    external_grant_principal=NULL,
    external_grant_instance_id=NULL,
    external_grant_instance_fingerprint=NULL
  WHERE singleton;
" >/dev/null

assert_exact "physical_pitr_active_authority_replay_reset_to_R" \
  "state_at_R|5|10|7|false|0|" \
  "$(psql_in "$restored_container" "SELECT business_state||'|'||poll_epoch||'|'||poll_generation||'|'||placement_version||'|'||reconciled_through_f::text||'|'||(SELECT count(*) FROM pitr_continuity_receipt)||'|'||coalesce(external_grant_id,'') FROM pitr_local_state WHERE singleton;")"

assert_exact "physical_pitr_active_authority_hardened_claim" "true" \
  "$(psql_in "$restored_container" "SELECT pitr_local_claim_external('$primary_conn','grant-F-1')::text;")"
assert_exact "physical_pitr_active_authority_hardened_verify_before_apply" "true" \
  "$(psql_in "$restored_container" "SELECT pitr_local_verify_external('$primary_conn','grant-F-1')::text;")"
assert_exact "physical_pitr_active_authority_hardened_claim_stays_at_R" \
  "state_at_R|false|0" \
  "$(psql_in "$restored_container" "SELECT business_state||'|'||reconciled_through_f::text||'|'||(SELECT count(*) FROM pitr_continuity_receipt) FROM pitr_local_state WHERE singleton;")"

# This call necessarily traverses the newly installed
# fetch_claimed_recovery_material(...), revalidates active authority and then
# atomically applies the authenticated post-R effect through the existing local
# digest verifier. A broken hardened fetch therefore fails the vector.
assert_exact "physical_pitr_active_authority_hardened_fetch_apply" "true" \
  "$(psql_in "$restored_container" "SELECT pitr_local_apply_external('$primary_conn','grant-F-1')::text;")"
assert_exact "physical_pitr_active_authority_hardened_verify_after_apply" "true" \
  "$(psql_in "$restored_container" "SELECT pitr_local_verify_external('$primary_conn','grant-F-1')::text;")"

assert_exact "physical_pitr_active_authority_hardened_reconciled_state" \
  "post_R_business_change|6|1|8|true|1|grant-F-1|$main_effect_digest" \
  "$(psql_in "$restored_container" "SELECT business_state||'|'||poll_epoch||'|'||poll_generation||'|'||placement_version||'|'||reconciled_through_f::text||'|'||(SELECT count(*) FROM pitr_continuity_receipt)||'|'||external_grant_id||'|'||external_effect_digest FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_active_authority_hardened_boundary_single_claim" "1" \
  "$(psql_in "$control_container" "SELECT count(*)::text FROM pitr_external_evidence.recovery_boundary_claim WHERE boundary_r='R' AND boundary_f='F';")"
assert_exact "physical_pitr_active_authority_hardened_clone_still_rejected" "false" \
  "$(psql_in "$clone_container" "SELECT pitr_local_verify_external('$primary_conn','grant-F-1')::text;")"

printf '%s\n' 'physical_pitr_active_authority_end_to_end_replay=PASS'
printf '%s\n' 'physical_pitr_active_authority_claim_fetch_apply_chain=PASS'
