BEGIN;

CREATE SCHEMA IF NOT EXISTS g1_identity;

CREATE TABLE IF NOT EXISTS g1_identity.browser_auth_transaction (
    transaction_id TEXT PRIMARY KEY CHECK (transaction_id ~ '^[A-Za-z0-9_-]{32}$'),
    initiating_session_digest TEXT NOT NULL CHECK (initiating_session_digest ~ '^[0-9a-f]{64}$'),
    state_digest TEXT NOT NULL CHECK (state_digest ~ '^[0-9a-f]{64}$'),
    nonce_digest TEXT NOT NULL CHECK (nonce_digest ~ '^[0-9a-f]{64}$'),
    pkce_verifier TEXT NOT NULL CHECK (char_length(pkce_verifier) BETWEEN 43 AND 128),
    expected_issuer TEXT NOT NULL CHECK (btrim(expected_issuer) = expected_issuer AND expected_issuer <> ''),
    expected_client_id TEXT NOT NULL CHECK (btrim(expected_client_id) = expected_client_id AND expected_client_id <> ''),
    expected_redirect_uri TEXT NOT NULL CHECK (btrim(expected_redirect_uri) = expected_redirect_uri AND expected_redirect_uri <> ''),
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    CHECK (expires_at > created_at),
    CHECK (consumed_at IS NULL OR consumed_at >= created_at)
);

CREATE TABLE IF NOT EXISTS g1_identity.browser_session (
    handle_digest TEXT PRIMARY KEY CHECK (handle_digest ~ '^[0-9a-f]{64}$'),
    principal_id TEXT NOT NULL CHECK (btrim(principal_id) = principal_id AND principal_id <> ''),
    principal_kind TEXT NOT NULL CHECK (principal_kind = 'human_browser_session'),
    session_generation TEXT NOT NULL UNIQUE CHECK (btrim(session_generation) = session_generation AND session_generation <> ''),
    auth_issuer TEXT NOT NULL CHECK (btrim(auth_issuer) = auth_issuer AND auth_issuer <> ''),
    auth_authenticated_at TIMESTAMPTZ NOT NULL,
    auth_evidence_expires_at TIMESTAMPTZ NOT NULL,
    auth_acr TEXT CHECK (auth_acr IS NULL OR (btrim(auth_acr) = auth_acr AND auth_acr <> '')),
    auth_amr TEXT[] NOT NULL DEFAULT '{}',
    auth_policy_version TEXT NOT NULL CHECK (btrim(auth_policy_version) = auth_policy_version AND auth_policy_version <> ''),
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    retired_at TIMESTAMPTZ,
    CHECK (auth_evidence_expires_at > auth_authenticated_at),
    CHECK (auth_authenticated_at <= created_at),
    CHECK (auth_evidence_expires_at > created_at),
    CHECK (expires_at > created_at),
    CHECK (retired_at IS NULL OR retired_at >= created_at),
    CHECK (array_position(auth_amr, NULL) IS NULL)
);

CREATE OR REPLACE FUNCTION g1_identity.consume_browser_auth_transaction(
    p_transaction_id TEXT,
    p_now TIMESTAMPTZ
)
RETURNS SETOF g1_identity.browser_auth_transaction
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    UPDATE g1_identity.browser_auth_transaction AS t
       SET consumed_at = p_now
     WHERE t.transaction_id = p_transaction_id
       AND t.consumed_at IS NULL
       AND t.created_at <= p_now
       AND p_now < t.expires_at
     RETURNING t.*;
END;
$$;

CREATE OR REPLACE FUNCTION g1_identity.retire_browser_session(
    p_handle_digest TEXT,
    p_expected_generation TEXT,
    p_now TIMESTAMPTZ
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    affected INTEGER;
BEGIN
    UPDATE g1_identity.browser_session
       SET retired_at = p_now
     WHERE handle_digest = p_handle_digest
       AND session_generation = p_expected_generation
       AND retired_at IS NULL
       AND created_at <= p_now
       AND p_now < expires_at;
    GET DIAGNOSTICS affected = ROW_COUNT;
    RETURN affected = 1;
END;
$$;

REVOKE ALL ON SCHEMA g1_identity FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA g1_identity FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA g1_identity FROM PUBLIC;

COMMIT;
