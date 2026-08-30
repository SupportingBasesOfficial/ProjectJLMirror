# ---------------------------------------------------------------------------
# Tier 1 activation commit protocol.
#
# This deliberately replaces the earlier evidence function so the durable
# activation grant and the placement-authority transition are all-or-nothing.
# Remote target verification has already completed before any local authority
# row is locked. Once local locking begins, no external call is made.
# ---------------------------------------------------------------------------
pg_sql "
  CREATE OR REPLACE FUNCTION relocation_evidence.activate_target(p_tenant uuid)
  RETURNS boolean LANGUAGE plpgsql
  SET search_path=pg_catalog,relocation_evidence
  AS \$\$
  DECLARE
    v_f bigint; v_version bigint; v_new_version bigint;
    v_source_count bigint; v_source_digest text;
    v_before relocation_evidence.projection_receipt%ROWTYPE;
    v_receipt relocation_evidence.projection_receipt%ROWTYPE;
  BEGIN
    SELECT * INTO v_before FROM relocation_evidence.projection_receipt
     WHERE tenant_id=p_tenant AND state='complete' AND target_sealed
     ORDER BY verified_at DESC LIMIT 1;
    IF NOT FOUND THEN RETURN false; END IF;

    -- Cross-authority verification happens before local authority locks.
    IF NOT relocation_evidence.target_attestation_is_valid(
      v_before.tenant_id,v_before.fence_ordinal,v_before.checkpoint_id,
      v_before.checkpoint_generation,v_before.target_sealed,v_before.target_count,
      v_before.target_digest,v_before.target_max_ordinal,v_before.target_attestation
    ) THEN
      RETURN false;
    END IF;

    SELECT fence_ordinal,placement_version INTO v_f,v_version
      FROM relocation_evidence.placement
     WHERE tenant_id=p_tenant AND phase='fenced' AND current_writer='none' FOR UPDATE;
    IF NOT FOUND OR v_f IS NULL OR v_f<>v_before.fence_ordinal THEN RETURN false; END IF;

    SELECT * INTO v_receipt FROM relocation_evidence.projection_receipt
     WHERE tenant_id=p_tenant AND fence_ordinal=v_f AND state='complete' AND target_sealed
     FOR UPDATE;
    IF NOT FOUND
       OR v_receipt.checkpoint_id<>v_before.checkpoint_id
       OR v_receipt.checkpoint_generation<>v_before.checkpoint_generation
       OR v_receipt.target_attestation<>v_before.target_attestation THEN
      RETURN false;
    END IF;

    SELECT count(*),relocation_evidence.authoritative_digest(p_tenant,v_f)
      INTO v_source_count,v_source_digest
      FROM relocation_evidence.acceptance WHERE tenant_id=p_tenant AND accepted_ordinal<=v_f;
    IF v_receipt.authoritative_count<>v_source_count
       OR v_receipt.authoritative_digest<>v_source_digest
       OR v_receipt.target_count<>v_source_count
       OR v_receipt.target_digest<>v_source_digest
       OR v_receipt.target_max_ordinal<>v_f THEN RETURN false; END IF;

    v_new_version:=v_version+1;

    -- First move the owner-controlled placement under its locked generation.
    -- Any later error in this function rolls the statement/transaction back.
    UPDATE relocation_evidence.placement
       SET phase='active',current_writer='target',placement_version=v_new_version
     WHERE tenant_id=p_tenant AND phase='fenced' AND current_writer='none'
       AND placement_version=v_version AND fence_ordinal=v_f;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'placement activation CAS lost';
    END IF;

    -- Plain INSERT is intentional. A conflicting grant is a protocol error and
    -- raises, rolling back the placement transition above. There is therefore
    -- no committed placement without its exact durable grant, nor vice versa.
    INSERT INTO relocation_evidence.activation_grant(
      tenant_id,fence_ordinal,checkpoint_id,checkpoint_generation,target_attestation,
      placement_version,state
    ) VALUES(
      p_tenant,v_f,v_receipt.checkpoint_id,v_receipt.checkpoint_generation,
      v_receipt.target_attestation,v_new_version,'committed'
    );

    RETURN true;
  END;
  \$\$;
" >/dev/null
