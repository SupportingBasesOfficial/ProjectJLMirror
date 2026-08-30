#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: physical_pitr_active_authority_hardening.sh <external-control-container> <postgres-image>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the base PITR vector so its temporary restored instances and surviving
# authority remain alive until this wrapper exits. The base cleanup trap remains
# authoritative and runs once after the hardening vectors below complete.
# shellcheck source=tools/open_rel_030/physical_pitr.sh
source "$SCRIPT_DIR/physical_pitr.sh" "$@"

psql_stdin() {
  local container="$1"
  docker exec -i -e PGPASSWORD="$password" "$container" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq
}

# ---------------------------------------------------------------------------
# #45: bind every recovery grant to the active surviving authority tuple.
#
# A valid signature is necessary but not sufficient. The surviving singleton is
# the authority for this recovery event and is locked before a winner key is
# derived. claim/verify/material-fetch all fail closed unless the grant exactly
# matches domain, R, F, successor epoch, placement version and required receipt.
# ---------------------------------------------------------------------------
psql_stdin "$control_container" <<'SQL'
ALTER TABLE pitr_external_evidence.authority
  ADD COLUMN IF NOT EXISTS expected_domain text;
UPDATE pitr_external_evidence.authority
   SET expected_domain='open-rel-030-recovery-v1'
 WHERE singleton AND expected_domain IS NULL;
ALTER TABLE pitr_external_evidence.authority
  ALTER COLUMN expected_domain SET NOT NULL;

CREATE OR REPLACE FUNCTION pitr_external_evidence.claim_grant(
  p_grant_id text,p_instance_id uuid,p_instance_secret text
) RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
SET search_path=pg_catalog,pitr_external_evidence,public
AS $$
DECLARE v_authority pitr_external_evidence.authority%ROWTYPE;
        v_grant pitr_external_evidence.recovery_grant%ROWTYPE;
        v_claim pitr_external_evidence.recovery_boundary_claim%ROWTYPE;
        v_principal name := session_user; v_instance_fp text; v_boundary_fp text;
BEGIN
  SELECT * INTO STRICT v_authority FROM pitr_external_evidence.authority
   WHERE singleton FOR UPDATE;
  SELECT * INTO v_grant FROM pitr_external_evidence.recovery_grant
   WHERE grant_id=p_grant_id FOR UPDATE;
  IF NOT FOUND THEN RETURN false; END IF;
  IF v_grant.domain IS DISTINCT FROM v_authority.expected_domain
     OR v_grant.boundary_r IS DISTINCT FROM v_authority.boundary_r
     OR v_grant.boundary_f IS DISTINCT FROM v_authority.boundary_f
     OR v_grant.successor_epoch IS DISTINCT FROM v_authority.expected_successor_epoch
     OR v_grant.placement_version IS DISTINCT FROM v_authority.expected_placement_version
     OR v_grant.required_receipt IS DISTINCT FROM v_authority.required_receipt THEN
    RETURN false;
  END IF;
  IF NOT pitr_external_evidence.stored_grant_is_valid(p_grant_id) THEN RETURN false; END IF;

  v_instance_fp := pitr_external_evidence.instance_fingerprint(p_instance_secret);
  v_boundary_fp := pitr_external_evidence.boundary_fingerprint(
    v_authority.expected_domain,v_authority.boundary_r,v_authority.boundary_f,
    v_authority.expected_successor_epoch,v_authority.expected_placement_version,
    v_authority.required_receipt
  );

  INSERT INTO pitr_external_evidence.recovery_boundary_claim(
    boundary_fingerprint,domain,boundary_r,boundary_f,successor_epoch,
    placement_version,required_receipt,effect_digest,winning_grant_id,
    claimed_principal,claimed_instance_id,claimed_instance_fingerprint
  ) VALUES (
    v_boundary_fp,v_authority.expected_domain,v_authority.boundary_r,v_authority.boundary_f,
    v_authority.expected_successor_epoch,v_authority.expected_placement_version,
    v_authority.required_receipt,v_grant.effect_digest,v_grant.grant_id,
    v_principal,p_instance_id,v_instance_fp
  ) ON CONFLICT(boundary_fingerprint) DO NOTHING;

  SELECT * INTO STRICT v_claim FROM pitr_external_evidence.recovery_boundary_claim
   WHERE boundary_fingerprint=v_boundary_fp FOR UPDATE;

  IF v_claim.domain IS DISTINCT FROM v_authority.expected_domain
     OR v_claim.boundary_r IS DISTINCT FROM v_authority.boundary_r
     OR v_claim.boundary_f IS DISTINCT FROM v_authority.boundary_f
     OR v_claim.successor_epoch IS DISTINCT FROM v_authority.expected_successor_epoch
     OR v_claim.placement_version IS DISTINCT FROM v_authority.expected_placement_version
     OR v_claim.required_receipt IS DISTINCT FROM v_authority.required_receipt
     OR v_claim.claimed_principal IS DISTINCT FROM v_principal
     OR v_claim.claimed_instance_id IS DISTINCT FROM p_instance_id
     OR v_claim.claimed_instance_fingerprint IS DISTINCT FROM v_instance_fp
     OR v_claim.effect_digest IS DISTINCT FROM v_grant.effect_digest THEN
    RETURN false;
  END IF;

  UPDATE pitr_external_evidence.recovery_grant
     SET claimed_principal=v_principal,claimed_instance_id=p_instance_id,
         claimed_instance_fingerprint=v_instance_fp,
         claimed_at=coalesce(claimed_at,clock_timestamp())
   WHERE grant_id=p_grant_id
     AND (claimed_principal IS NULL OR
          (claimed_principal=v_principal AND claimed_instance_id=p_instance_id
           AND claimed_instance_fingerprint=v_instance_fp));
  RETURN true;
END;
$$;

CREATE OR REPLACE FUNCTION pitr_external_evidence.verify_claimed_grant(
  p_grant_id text,p_instance_id uuid,p_instance_secret text
) RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
SET search_path=pg_catalog,pitr_external_evidence,public
AS $$
DECLARE v_authority pitr_external_evidence.authority%ROWTYPE;
        v_grant pitr_external_evidence.recovery_grant%ROWTYPE;
        v_claim pitr_external_evidence.recovery_boundary_claim%ROWTYPE;
        v_principal name := session_user; v_instance_fp text; v_boundary_fp text;
BEGIN
  SELECT * INTO STRICT v_authority FROM pitr_external_evidence.authority
   WHERE singleton FOR SHARE;
  SELECT * INTO v_grant FROM pitr_external_evidence.recovery_grant
   WHERE grant_id=p_grant_id FOR SHARE;
  IF NOT FOUND THEN RETURN false; END IF;
  IF v_grant.domain IS DISTINCT FROM v_authority.expected_domain
     OR v_grant.boundary_r IS DISTINCT FROM v_authority.boundary_r
     OR v_grant.boundary_f IS DISTINCT FROM v_authority.boundary_f
     OR v_grant.successor_epoch IS DISTINCT FROM v_authority.expected_successor_epoch
     OR v_grant.placement_version IS DISTINCT FROM v_authority.expected_placement_version
     OR v_grant.required_receipt IS DISTINCT FROM v_authority.required_receipt
     OR NOT pitr_external_evidence.stored_grant_is_valid(p_grant_id) THEN
    RETURN false;
  END IF;

  v_instance_fp := pitr_external_evidence.instance_fingerprint(p_instance_secret);
  v_boundary_fp := pitr_external_evidence.boundary_fingerprint(
    v_authority.expected_domain,v_authority.boundary_r,v_authority.boundary_f,
    v_authority.expected_successor_epoch,v_authority.expected_placement_version,
    v_authority.required_receipt
  );
  SELECT * INTO v_claim FROM pitr_external_evidence.recovery_boundary_claim
   WHERE boundary_fingerprint=v_boundary_fp;
  IF NOT FOUND THEN RETURN false; END IF;
  RETURN v_claim.domain = v_authority.expected_domain
     AND v_claim.boundary_r = v_authority.boundary_r
     AND v_claim.boundary_f = v_authority.boundary_f
     AND v_claim.successor_epoch = v_authority.expected_successor_epoch
     AND v_claim.placement_version = v_authority.expected_placement_version
     AND v_claim.required_receipt = v_authority.required_receipt
     AND v_claim.claimed_principal = v_principal
     AND v_claim.claimed_instance_id = p_instance_id
     AND v_claim.claimed_instance_fingerprint = v_instance_fp
     AND v_claim.effect_digest = v_grant.effect_digest;
END;
$$;

CREATE OR REPLACE FUNCTION pitr_external_evidence.fetch_claimed_recovery_material(
  p_grant_id text,p_instance_id uuid,p_instance_secret text
) RETURNS text LANGUAGE plpgsql STRICT SECURITY DEFINER
SET search_path=pg_catalog,pitr_external_evidence,public
AS $$
DECLARE v_authority pitr_external_evidence.authority%ROWTYPE;
        v_grant pitr_external_evidence.recovery_grant%ROWTYPE;
        v_effect pitr_external_evidence.recovery_effect%ROWTYPE;
        v_claim pitr_external_evidence.recovery_boundary_claim%ROWTYPE;
        v_boundary_fp text; v_principal name := session_user; v_instance_fp text;
BEGIN
  SELECT * INTO STRICT v_authority FROM pitr_external_evidence.authority
   WHERE singleton FOR SHARE;
  SELECT * INTO v_grant FROM pitr_external_evidence.recovery_grant
   WHERE grant_id=p_grant_id FOR UPDATE;
  IF NOT FOUND THEN RETURN NULL; END IF;
  IF v_grant.domain IS DISTINCT FROM v_authority.expected_domain
     OR v_grant.boundary_r IS DISTINCT FROM v_authority.boundary_r
     OR v_grant.boundary_f IS DISTINCT FROM v_authority.boundary_f
     OR v_grant.successor_epoch IS DISTINCT FROM v_authority.expected_successor_epoch
     OR v_grant.placement_version IS DISTINCT FROM v_authority.expected_placement_version
     OR v_grant.required_receipt IS DISTINCT FROM v_authority.required_receipt THEN
    RETURN NULL;
  END IF;

  v_instance_fp := pitr_external_evidence.instance_fingerprint(p_instance_secret);
  v_boundary_fp := pitr_external_evidence.boundary_fingerprint(
    v_authority.expected_domain,v_authority.boundary_r,v_authority.boundary_f,
    v_authority.expected_successor_epoch,v_authority.expected_placement_version,
    v_authority.required_receipt
  );

  SELECT * INTO v_claim FROM pitr_external_evidence.recovery_boundary_claim
   WHERE boundary_fingerprint=v_boundary_fp FOR UPDATE;
  IF NOT FOUND THEN RETURN NULL; END IF;
  SELECT * INTO v_effect FROM pitr_external_evidence.recovery_effect
   WHERE effect_digest=v_grant.effect_digest FOR UPDATE;
  IF NOT FOUND THEN RETURN NULL; END IF;
  PERFORM 1 FROM pitr_external_evidence.signing_key WHERE singleton FOR SHARE;

  IF v_claim.domain IS DISTINCT FROM v_authority.expected_domain
     OR v_claim.boundary_r IS DISTINCT FROM v_authority.boundary_r
     OR v_claim.boundary_f IS DISTINCT FROM v_authority.boundary_f
     OR v_claim.successor_epoch IS DISTINCT FROM v_authority.expected_successor_epoch
     OR v_claim.placement_version IS DISTINCT FROM v_authority.expected_placement_version
     OR v_claim.required_receipt IS DISTINCT FROM v_authority.required_receipt
     OR v_claim.effect_digest IS DISTINCT FROM v_grant.effect_digest
     OR v_claim.claimed_principal IS DISTINCT FROM v_principal
     OR v_claim.claimed_instance_id IS DISTINCT FROM p_instance_id
     OR v_claim.claimed_instance_fingerprint IS DISTINCT FROM v_instance_fp THEN
    RETURN NULL;
  END IF;
  IF v_effect.domain IS DISTINCT FROM v_grant.domain
     OR v_effect.boundary_r IS DISTINCT FROM v_grant.boundary_r
     OR v_effect.boundary_f IS DISTINCT FROM v_grant.boundary_f
     OR v_effect.required_receipt IS DISTINCT FROM v_grant.required_receipt THEN
    RETURN NULL;
  END IF;
  IF NOT pitr_external_evidence.stored_effect_is_valid(v_effect.effect_digest)
     OR NOT pitr_external_evidence.stored_grant_is_valid(v_grant.grant_id) THEN
    RETURN NULL;
  END IF;

  RETURN jsonb_build_object(
    'domain',v_grant.domain,'boundary_r',v_grant.boundary_r,'boundary_f',v_grant.boundary_f,
    'successor_epoch',v_grant.successor_epoch,'placement_version',v_grant.placement_version,
    'required_receipt',v_grant.required_receipt,'business_state',v_effect.business_state,
    'source_poll_generation',v_effect.source_poll_generation,'effect_digest',v_effect.effect_digest,
    'canonical_grant',v_grant.canonical_payload,'claimed_principal',v_claim.claimed_principal::text,
    'claimed_instance_id',v_claim.claimed_instance_id::text,
    'claimed_instance_fingerprint',v_claim.claimed_instance_fingerprint
  )::text;
END;
$$;
SQL

# Local defense-in-depth: a reconciled restored database may only carry the exact
# successor authority selected by the bounded recovery profile. This prevents a
# drifted material document from becoming effective even if a future caller-side
# path were to bypass the external validation above.
for c in "$restored_container" "$clone_container"; do
  psql_stdin "$c" <<'SQL'
CREATE OR REPLACE FUNCTION pitr_enforce_recovery_successor_authority()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public
AS $$
BEGIN
  IF NEW.reconciled_through_f AND
     (NEW.poll_epoch IS DISTINCT FROM 6 OR NEW.placement_version IS DISTINCT FROM 8) THEN
    RAISE EXCEPTION 'reconciled state violates active successor authority';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS pitr_recovery_successor_authority_fence ON pitr_local_state;
CREATE TRIGGER pitr_recovery_successor_authority_fence
BEFORE INSERT OR UPDATE ON pitr_local_state
FOR EACH ROW EXECUTE FUNCTION pitr_enforce_recovery_successor_authority();
SQL
done

# Two grants are cryptographically valid and reuse the exact authenticated
# main R/F effect, but independently drift one active-authority dimension each.
psql_stdin "$control_container" <<'SQL'
WITH base AS (
  SELECT effect_digest FROM pitr_external_evidence.recovery_effect
   WHERE domain='open-rel-030-recovery-v1' AND boundary_r='R' AND boundary_f='F'
), facts(grant_id,successor_epoch,placement_version,nonce) AS (
  VALUES ('grant-F-alt-epoch',7::bigint,8::bigint,'alt-epoch-valid-signature'),
         ('grant-F-alt-placement',6::bigint,9::bigint,'alt-placement-valid-signature')
), c AS (
  SELECT f.grant_id,'open-rel-030-recovery-v1'::text domain,'R'::text boundary_r,'F'::text boundary_f,
         f.successor_epoch,f.placement_version,'effect|after-r'::text required_receipt,
         b.effect_digest,f.nonce,
         pitr_external_evidence.canonical_grant(
           'open-rel-030-recovery-v1','R','F',f.successor_epoch,f.placement_version,
           'effect|after-r',b.effect_digest,f.nonce
         ) canonical_payload
    FROM facts f CROSS JOIN base b
)
INSERT INTO pitr_external_evidence.recovery_grant(
  grant_id,domain,boundary_r,boundary_f,successor_epoch,placement_version,
  required_receipt,effect_digest,nonce,canonical_payload,attestation
)
SELECT c.grant_id,c.domain,c.boundary_r,c.boundary_f,c.successor_epoch,c.placement_version,
       c.required_receipt,c.effect_digest,c.nonce,c.canonical_payload,
       encode(public.hmac(convert_to(c.canonical_payload,'UTF8'),decode(k.key_material,'hex'),'sha256'),'hex')
  FROM c CROSS JOIN pitr_external_evidence.signing_key k WHERE k.singleton
ON CONFLICT(grant_id) DO NOTHING;
SQL

assert_exact "physical_pitr_alt_epoch_grant_signature_valid" "true" \
  "$(psql_in "$control_container" "SELECT pitr_external_evidence.stored_grant_is_valid('grant-F-alt-epoch')::text;")"
assert_exact "physical_pitr_alt_placement_grant_signature_valid" "true" \
  "$(psql_in "$control_container" "SELECT pitr_external_evidence.stored_grant_is_valid('grant-F-alt-placement')::text;")"
assert_exact "physical_pitr_active_authority_singleton" "open-rel-030-recovery-v1|R|F|6|8|effect|after-r" \
  "$(psql_in "$control_container" "SELECT expected_domain||'|'||boundary_r||'|'||boundary_f||'|'||expected_successor_epoch||'|'||expected_placement_version||'|'||required_receipt FROM pitr_external_evidence.authority WHERE singleton;")"

claim_rows_before="$(psql_in "$control_container" "SELECT count(*)::text FROM pitr_external_evidence.recovery_boundary_claim WHERE boundary_r='R' AND boundary_f='F';")"
assert_exact "physical_pitr_alt_epoch_grant_rejected_by_active_authority" "false" \
  "$(psql_in "$restored_container" "SELECT pitr_local_claim_external('$primary_conn','grant-F-alt-epoch')::text;")"
assert_exact "physical_pitr_alt_placement_grant_rejected_by_active_authority" "false" \
  "$(psql_in "$clone_container" "SELECT pitr_local_claim_external('$primary_conn','grant-F-alt-placement')::text;")"
assert_exact "physical_pitr_alt_epoch_verify_rejected" "false" \
  "$(psql_in "$restored_container" "SELECT pitr_local_verify_external('$primary_conn','grant-F-alt-epoch')::text;")"
assert_exact "physical_pitr_alt_placement_apply_rejected" "false" \
  "$(psql_in "$clone_container" "SELECT pitr_local_apply_external('$primary_conn','grant-F-alt-placement')::text;")"
assert_exact "physical_pitr_alt_grants_leave_claim_count_unchanged" "$claim_rows_before" \
  "$(psql_in "$control_container" "SELECT count(*)::text FROM pitr_external_evidence.recovery_boundary_claim WHERE boundary_r='R' AND boundary_f='F';")"
assert_exact "physical_pitr_alt_grants_remain_unclaimed" "2" \
  "$(psql_in "$control_container" "SELECT count(*)::text FROM pitr_external_evidence.recovery_grant WHERE grant_id IN ('grant-F-alt-epoch','grant-F-alt-placement') AND claimed_at IS NULL;")"

# Prove the local fence itself rejects a bad successor transition even without
# relying on external transport failure.
set +e
docker exec -e PGPASSWORD="$password" "$clone_container" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq \
  -c "UPDATE pitr_local_state SET reconciled_through_f=true,poll_epoch=7,placement_version=8 WHERE singleton;" \
  >"$tmpdir/local-authority-fence.out" 2>"$tmpdir/local-authority-fence.err"
local_fence_rc=$?
set -e
[[ "$local_fence_rc" -ne 0 ]] || { echo "local recovery successor-authority fence accepted drifted epoch" >&2; exit 1; }
printf '%s\n' 'physical_pitr_local_successor_authority_fence=PASS'

# Panoramic regression checks on the effective hardened definitions.
assert_exact "physical_pitr_main_grant_still_verifies_after_authority_hardening" "true" \
  "$(psql_in "$restored_container" "SELECT pitr_local_verify_external('$primary_conn','grant-F-1')::text;")"
assert_exact "physical_pitr_duplicate_grant_same_winner_retry_after_authority_hardening" "true" \
  "$(psql_in "$restored_container" "SELECT pitr_local_claim_external('$primary_conn','grant-F-duplicate')::text;")"
assert_exact "physical_pitr_clone_still_rejected_after_authority_hardening" "false" \
  "$(psql_in "$clone_container" "SELECT pitr_local_verify_external('$primary_conn','grant-F-1')::text;")"

claim_def="$(psql_in "$control_container" "SELECT pg_get_functiondef('pitr_external_evidence.claim_grant(text,uuid,text)'::regprocedure);")"
fetch_def="$(psql_in "$control_container" "SELECT pg_get_functiondef('pitr_external_evidence.fetch_claimed_recovery_material(text,uuid,text)'::regprocedure);")"
[[ "$claim_def" == *"FROM pitr_external_evidence.authority"* && "$claim_def" == *"FOR UPDATE"* ]] || {
  echo "effective claim_grant does not lock active authority" >&2; exit 1;
}
[[ "$fetch_def" == *"expected_successor_epoch"* && "$fetch_def" == *"expected_placement_version"* ]] || {
  echo "effective recovery material fetch does not revalidate active authority" >&2; exit 1;
}
printf '%s\n' 'physical_pitr_claim_locks_active_authority_before_winner_key=PASS'
printf '%s\n' 'physical_pitr_verify_fetch_revalidate_active_authority=PASS'
printf '%s\n' 'physical_pitr_active_authority_binding=PASS'
