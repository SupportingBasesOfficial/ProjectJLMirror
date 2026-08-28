\set ON_ERROR_STOP on

DROP SCHEMA IF EXISTS tel_recovery_evidence CASCADE;
CREATE SCHEMA tel_recovery_evidence;

-- This schema deliberately separates rollback-subject local poll state from the
-- current admission/recovery authority that cannot be trusted merely because it
-- was present in the same snapshot restored to R.
CREATE TABLE tel_recovery_evidence.placement_authority (
    tenant_id uuid PRIMARY KEY,
    placement_version bigint NOT NULL CHECK (placement_version > 0),
    cell_id text NOT NULL,
    admitted boolean NOT NULL,
    authority_generation bigint NOT NULL CHECK (authority_generation > 0)
);

CREATE TABLE tel_recovery_evidence.recovery_admission (
    tenant_id uuid PRIMARY KEY,
    recovery_generation bigint NOT NULL CHECK (recovery_generation > 0),
    recovery_point bigint NOT NULL,
    reconciliation_fence bigint NOT NULL,
    reconciled_through bigint NOT NULL,
    admitted boolean NOT NULL,
    CHECK (recovery_point <= reconciliation_fence),
    CHECK (reconciled_through <= reconciliation_fence)
);

CREATE TABLE tel_recovery_evidence.poll_authority (
    tenant_id uuid NOT NULL,
    monitoring_source_id uuid NOT NULL,
    source_instance_generation uuid NOT NULL,
    placement_version bigint NOT NULL,
    cell_id text NOT NULL,
    poll_epoch bigint NOT NULL CHECK (poll_epoch > 0),
    poll_generation bigint NOT NULL CHECK (poll_generation >= 0),
    recovery_generation bigint NOT NULL CHECK (recovery_generation > 0),
    PRIMARY KEY (tenant_id, monitoring_source_id, source_instance_generation)
);

CREATE TABLE tel_recovery_evidence.poll_claim (
    tenant_id uuid NOT NULL,
    monitoring_source_id uuid NOT NULL,
    source_instance_generation uuid NOT NULL,
    poll_epoch bigint NOT NULL,
    poll_generation bigint NOT NULL,
    placement_version bigint NOT NULL,
    cell_id text NOT NULL,
    recovery_generation bigint NOT NULL,
    claimed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (
        tenant_id,
        monitoring_source_id,
        source_instance_generation,
        poll_epoch,
        poll_generation
    )
);

CREATE OR REPLACE FUNCTION tel_recovery_evidence.claim_next_poll(
    p_tenant_id uuid,
    p_monitoring_source_id uuid,
    p_source_instance_generation uuid,
    p_cell_id text,
    p_expected_placement_version bigint,
    p_expected_recovery_generation bigint
)
RETURNS TABLE (poll_epoch bigint, poll_generation bigint)
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, tel_recovery_evidence
AS $$
DECLARE
    v_placement tel_recovery_evidence.placement_authority%ROWTYPE;
    v_recovery tel_recovery_evidence.recovery_admission%ROWTYPE;
    v_poll tel_recovery_evidence.poll_authority%ROWTYPE;
BEGIN
    SELECT * INTO v_placement
      FROM tel_recovery_evidence.placement_authority
     WHERE tenant_id = p_tenant_id
     FOR UPDATE;

    IF NOT FOUND
       OR NOT v_placement.admitted
       OR v_placement.cell_id <> p_cell_id
       OR v_placement.placement_version <> p_expected_placement_version THEN
        RAISE EXCEPTION 'placement authority is stale or not admitted';
    END IF;

    SELECT * INTO v_recovery
      FROM tel_recovery_evidence.recovery_admission
     WHERE tenant_id = p_tenant_id
     FOR UPDATE;

    IF NOT FOUND
       OR NOT v_recovery.admitted
       OR v_recovery.recovery_generation <> p_expected_recovery_generation
       OR v_recovery.reconciled_through <> v_recovery.reconciliation_fence THEN
        RAISE EXCEPTION 'recovery authority is quarantined or reconciliation incomplete';
    END IF;

    SELECT * INTO v_poll
      FROM tel_recovery_evidence.poll_authority
     WHERE tenant_id = p_tenant_id
       AND monitoring_source_id = p_monitoring_source_id
       AND source_instance_generation = p_source_instance_generation
     FOR UPDATE;

    IF NOT FOUND THEN
        INSERT INTO tel_recovery_evidence.poll_authority (
            tenant_id,
            monitoring_source_id,
            source_instance_generation,
            placement_version,
            cell_id,
            poll_epoch,
            poll_generation,
            recovery_generation
        ) VALUES (
            p_tenant_id,
            p_monitoring_source_id,
            p_source_instance_generation,
            v_placement.placement_version,
            v_placement.cell_id,
            1,
            1,
            v_recovery.recovery_generation
        )
        RETURNING poll_authority.poll_epoch, poll_authority.poll_generation
             INTO poll_epoch, poll_generation;
    ELSE
        -- Any change in placement or recovery generation creates a successor
        -- epoch. The local/restored generation sequence is never allowed to
        -- self-certify continuity across that boundary.
        IF v_poll.placement_version <> v_placement.placement_version
           OR v_poll.cell_id <> v_placement.cell_id
           OR v_poll.recovery_generation <> v_recovery.recovery_generation THEN
            UPDATE tel_recovery_evidence.poll_authority
               SET placement_version = v_placement.placement_version,
                   cell_id = v_placement.cell_id,
                   poll_epoch = v_poll.poll_epoch + 1,
                   poll_generation = 1,
                   recovery_generation = v_recovery.recovery_generation
             WHERE tenant_id = p_tenant_id
               AND monitoring_source_id = p_monitoring_source_id
               AND source_instance_generation = p_source_instance_generation
            RETURNING poll_authority.poll_epoch, poll_authority.poll_generation
                 INTO poll_epoch, poll_generation;
        ELSE
            UPDATE tel_recovery_evidence.poll_authority
               SET poll_generation = v_poll.poll_generation + 1
             WHERE tenant_id = p_tenant_id
               AND monitoring_source_id = p_monitoring_source_id
               AND source_instance_generation = p_source_instance_generation
            RETURNING poll_authority.poll_epoch, poll_authority.poll_generation
                 INTO poll_epoch, poll_generation;
        END IF;
    END IF;

    INSERT INTO tel_recovery_evidence.poll_claim (
        tenant_id,
        monitoring_source_id,
        source_instance_generation,
        poll_epoch,
        poll_generation,
        placement_version,
        cell_id,
        recovery_generation
    ) VALUES (
        p_tenant_id,
        p_monitoring_source_id,
        p_source_instance_generation,
        poll_epoch,
        poll_generation,
        v_placement.placement_version,
        v_placement.cell_id,
        v_recovery.recovery_generation
    );

    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION tel_recovery_evidence.poll_claim_is_current(
    p_tenant_id uuid,
    p_monitoring_source_id uuid,
    p_source_instance_generation uuid,
    p_poll_epoch bigint,
    p_poll_generation bigint,
    p_cell_id text,
    p_placement_version bigint,
    p_recovery_generation bigint
)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = pg_catalog, tel_recovery_evidence
AS $$
    SELECT EXISTS (
        SELECT 1
          FROM tel_recovery_evidence.poll_claim AS c
          JOIN tel_recovery_evidence.placement_authority AS p
            ON p.tenant_id = c.tenant_id
          JOIN tel_recovery_evidence.recovery_admission AS r
            ON r.tenant_id = c.tenant_id
          JOIN tel_recovery_evidence.poll_authority AS a
            ON a.tenant_id = c.tenant_id
           AND a.monitoring_source_id = c.monitoring_source_id
           AND a.source_instance_generation = c.source_instance_generation
         WHERE c.tenant_id = p_tenant_id
           AND c.monitoring_source_id = p_monitoring_source_id
           AND c.source_instance_generation = p_source_instance_generation
           AND c.poll_epoch = p_poll_epoch
           AND c.poll_generation = p_poll_generation
           AND c.cell_id = p_cell_id
           AND c.placement_version = p_placement_version
           AND c.recovery_generation = p_recovery_generation
           AND p.admitted
           AND p.cell_id = c.cell_id
           AND p.placement_version = c.placement_version
           AND r.admitted
           AND r.recovery_generation = c.recovery_generation
           AND r.reconciled_through = r.reconciliation_fence
           AND a.cell_id = c.cell_id
           AND a.placement_version = c.placement_version
           AND a.recovery_generation = c.recovery_generation
           AND a.poll_epoch = c.poll_epoch
           AND a.poll_generation = c.poll_generation
    )
$$;

-- Initial live authority before recovery/relocation.
INSERT INTO tel_recovery_evidence.placement_authority
VALUES (
    '10000000-0000-0000-0000-000000000001',
    7,
    'cell-a',
    true,
    7
);
INSERT INTO tel_recovery_evidence.recovery_admission
VALUES (
    '10000000-0000-0000-0000-000000000001',
    3,
    100,
    100,
    100,
    true
);

SELECT * FROM tel_recovery_evidence.claim_next_poll(
    '10000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000001',
    '30000000-0000-0000-0000-000000000001',
    'cell-a',
    7,
    3
);
SELECT * FROM tel_recovery_evidence.claim_next_poll(
    '10000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000001',
    '30000000-0000-0000-0000-000000000001',
    'cell-a',
    7,
    3
);

DO $$
DECLARE
    v_epoch bigint;
    v_generation bigint;
BEGIN
    SELECT poll_epoch, poll_generation
      INTO v_epoch, v_generation
      FROM tel_recovery_evidence.poll_authority
     WHERE tenant_id = '10000000-0000-0000-0000-000000000001';
    IF (v_epoch, v_generation) <> (1, 2) THEN
        RAISE EXCEPTION 'initial poll continuity unexpected: epoch %, generation %', v_epoch, v_generation;
    END IF;
END;
$$;

-- Recovery begins. Current admission is fenced before restored local state can
-- acquire any new current-state writer token.
UPDATE tel_recovery_evidence.recovery_admission
   SET recovery_generation = 4,
       recovery_point = 100,
       reconciliation_fence = 130,
       reconciled_through = 100,
       admitted = false
 WHERE tenant_id = '10000000-0000-0000-0000-000000000001';

DO $$
BEGIN
    BEGIN
        PERFORM * FROM tel_recovery_evidence.claim_next_poll(
            '10000000-0000-0000-0000-000000000001',
            '20000000-0000-0000-0000-000000000001',
            '30000000-0000-0000-0000-000000000001',
            'cell-a',
            7,
            3
        );
        RAISE EXCEPTION 'stale pre-recovery generation self-admitted';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'stale pre-recovery generation self-admitted' THEN RAISE; END IF;
    END;
END;
$$;

-- Even knowledge of the new recovery generation is insufficient while (R,F]
-- is incomplete and admission remains fenced.
DO $$
BEGIN
    BEGIN
        PERFORM * FROM tel_recovery_evidence.claim_next_poll(
            '10000000-0000-0000-0000-000000000001',
            '20000000-0000-0000-0000-000000000001',
            '30000000-0000-0000-0000-000000000001',
            'cell-a',
            7,
            4
        );
        RAISE EXCEPTION 'incomplete recovery interval admitted polling';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'incomplete recovery interval admitted polling' THEN RAISE; END IF;
    END;
END;
$$;

-- Reconcile through F, then admit recovery generation 4.
UPDATE tel_recovery_evidence.recovery_admission
   SET reconciled_through = 130,
       admitted = true
 WHERE tenant_id = '10000000-0000-0000-0000-000000000001';

SELECT * FROM tel_recovery_evidence.claim_next_poll(
    '10000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000001',
    '30000000-0000-0000-0000-000000000001',
    'cell-a',
    7,
    4
);

DO $$
DECLARE
    v_epoch bigint;
    v_generation bigint;
BEGIN
    SELECT poll_epoch, poll_generation
      INTO v_epoch, v_generation
      FROM tel_recovery_evidence.poll_authority
     WHERE tenant_id = '10000000-0000-0000-0000-000000000001';
    IF (v_epoch, v_generation) <> (2, 1) THEN
        RAISE EXCEPTION 'recovery did not create successor epoch: epoch %, generation %', v_epoch, v_generation;
    END IF;

    IF tel_recovery_evidence.poll_claim_is_current(
        '10000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000001',
        '30000000-0000-0000-0000-000000000001',
        1, 2, 'cell-a', 7, 3
    ) THEN
        RAISE EXCEPTION 'pre-recovery poll claim remained current';
    END IF;
END;
$$;

-- Relocate from cell-a placement v7 to cell-b placement v8. Source authority is
-- fenced first; target cannot claim until placement and recovery admission are
-- current. The change must create another successor epoch.
UPDATE tel_recovery_evidence.placement_authority
   SET admitted = false
 WHERE tenant_id = '10000000-0000-0000-0000-000000000001';

DO $$
BEGIN
    BEGIN
        PERFORM * FROM tel_recovery_evidence.claim_next_poll(
            '10000000-0000-0000-0000-000000000001',
            '20000000-0000-0000-0000-000000000001',
            '30000000-0000-0000-0000-000000000001',
            'cell-a',
            7,
            4
        );
        RAISE EXCEPTION 'fenced source placement continued polling';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'fenced source placement continued polling' THEN RAISE; END IF;
    END;
END;
$$;

UPDATE tel_recovery_evidence.placement_authority
   SET placement_version = 8,
       cell_id = 'cell-b',
       admitted = true,
       authority_generation = 8
 WHERE tenant_id = '10000000-0000-0000-0000-000000000001';

SELECT * FROM tel_recovery_evidence.claim_next_poll(
    '10000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000001',
    '30000000-0000-0000-0000-000000000001',
    'cell-b',
    8,
    4
);

DO $$
DECLARE
    v_epoch bigint;
    v_generation bigint;
BEGIN
    SELECT poll_epoch, poll_generation
      INTO v_epoch, v_generation
      FROM tel_recovery_evidence.poll_authority
     WHERE tenant_id = '10000000-0000-0000-0000-000000000001';
    IF (v_epoch, v_generation) <> (3, 1) THEN
        RAISE EXCEPTION 'relocation did not create successor epoch: epoch %, generation %', v_epoch, v_generation;
    END IF;

    IF tel_recovery_evidence.poll_claim_is_current(
        '10000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000001',
        '30000000-0000-0000-0000-000000000001',
        2, 1, 'cell-a', 7, 4
    ) THEN
        RAISE EXCEPTION 'retired source placement poll claim remained current';
    END IF;

    IF NOT tel_recovery_evidence.poll_claim_is_current(
        '10000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000001',
        '30000000-0000-0000-0000-000000000001',
        3, 1, 'cell-b', 8, 4
    ) THEN
        RAISE EXCEPTION 'target placement did not become current';
    END IF;
END;
$$;

SELECT 'tier1_recovery_authority=PASS' AS result;
