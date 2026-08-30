# ---------------------------------------------------------------------------
# Target signing-key provenance.
# The trusted test controller may administer both disposable databases for
# setup/fault injection, but it does not provision or retain the protocol's
# effective checkpoint signing key. That key is generated inside Tier 2.
# ---------------------------------------------------------------------------
if [[ ${attestation_key+x} == x ]]; then
  echo "controller retained an attestation_key variable after target initialization" >&2
  exit 1
fi
printf '%s\n' 'relocation_controller_does_not_retain_target_signing_key=PASS'

target_key_shape="$(ts_sql "
  SELECT (
    count(*) = 1
    AND bool_and(length(key_material) = 64)
    AND bool_and(key_material ~ '^[0-9a-f]{64}$')
  )::text
  FROM relocation_evidence.target_attestation_key;
")"
assert_exact "relocation_target_authority_generated_signing_key" "true" "$target_key_shape"

expect_ts_reject "relocation_projection_writer_still_cannot_read_generated_signing_key" "permission denied" \
  "SET ROLE ts_automation_owner; SELECT key_material FROM relocation_evidence.target_attestation_key;"
expect_ts_reject "relocation_target_verifier_still_cannot_read_generated_signing_key" "permission denied" \
  "SET ROLE relocation_target_verifier; SELECT key_material FROM relocation_evidence.target_attestation_key;"
