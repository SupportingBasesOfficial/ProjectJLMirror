from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time

import keycloak_mfa_step_up_probe as probe


_USED_COUNTERS: list[int] = []


def _fresh_single_use_totp(secret: str) -> str:
    """Issue only a non-replayed TOTP counter for the evidence browser flow."""

    while True:
        timestamp = int(time.time())
        counter = timestamp // 30
        remainder = 30 - (timestamp % 30)

        if _USED_COUNTERS and counter <= _USED_COUNTERS[-1]:
            time.sleep(remainder + 1)
            continue
        if remainder <= 3:
            time.sleep(remainder + 1)
            continue

        code = probe._totp(secret, now=timestamp)
        _USED_COUNTERS.append(counter)
        return code


def _expect_denied(callable_, label: str) -> None:
    try:
        callable_()
    except probe.AdmissionDenied:
        return
    raise AssertionError(f"{label}: expected fail-closed AdmissionDenied")


def _complete_login(initiation, code: str, state: str, port, binding: str):
    return probe._complete(initiation, code, state, port, binding)


def main() -> int:
    # Keycloak 26.7.2 defaults TOTP codes to single-use. Keep enrollment and
    # subsequent reauthentication on distinct counters, then prove that the
    # fresh MFA result upgrades the *same* platform principal/session boundary.
    probe._stable_totp = _fresh_single_use_totp
    probe.wait_ready()

    mfa_user_id, basic_user_id = probe.configure_realm()
    issuer = f"{probe.BASE}/realms/{probe.REALM}"
    port = probe.VerificationPort(
        {
            (issuer, mfa_user_id): probe.MFA_PRINCIPAL,
            (issuer, basic_user_id): probe.BASIC_PRINCIPAL,
        }
    )

    # The required-action enrollment authenticates the MFA user with password
    # and configures TOTP, but the authentication flow itself has not yet
    # executed the OTP authenticator. That gives us a genuine weak session for
    # the same principal that will later perform step-up.
    enroll_binding = "mfa-enroll-session"
    enroll_init = probe._initiation(enroll_binding)
    enroll_code, enroll_state, secret = probe.enroll_totp_and_get_code(
        state=enroll_init.state,
        nonce=enroll_init.nonce,
        code_challenge=enroll_init.pkce_challenge,
    )
    weak_principal, weak_strength = _complete_login(
        enroll_init,
        enroll_code,
        enroll_state,
        port,
        enroll_binding,
    )
    if weak_principal.principal_id != probe.MFA_PRINCIPAL:
        raise AssertionError("TOTP enrollment mapped to wrong platform principal")
    if weak_strength.amr != frozenset({"password"}):
        raise AssertionError(
            "required-action enrollment must establish password-only weak evidence; "
            f"got={sorted(weak_strength.amr)!r}"
        )

    authority = probe.MemorySessionAuthority()
    now = datetime.now(timezone.utc)
    weak_handle = probe.issue_browser_session(
        authority=authority,
        principal=weak_principal,
        now=now,
        lifetime=timedelta(minutes=30),
        authentication_strength=weak_strength,
    )
    weak_record = probe.resolve_browser_session(
        authority=authority,
        handle=weak_handle,
        now=now,
    )
    _expect_denied(
        lambda: probe.require_authentication_strength(
            policy=probe.MfaPolicy(),
            policy_id="security.mfa.admin@1",
            evidence=weak_record.authentication_strength,
            principal=weak_record.principal,
            now=now,
        ),
        "same_principal_password_only_before_step_up",
    )

    # Perform a brand-new browser authorization for the same provider subject.
    # A new cookie jar in login_with_totp forces an actual Keycloak password +
    # TOTP authentication, rather than reusing an existing IdP browser session.
    reauth_binding = "mfa-fresh-step-up-session"
    reauth_init = probe._initiation(reauth_binding)
    reauth_code, reauth_state = probe.login_with_totp(
        state=reauth_init.state,
        nonce=reauth_init.nonce,
        code_challenge=reauth_init.pkce_challenge,
        secret=secret,
    )
    reauthenticated_principal, fresh_mfa_strength = _complete_login(
        reauth_init,
        reauth_code,
        reauth_state,
        port,
        reauth_binding,
    )
    if reauthenticated_principal.principal_id != weak_record.principal.principal_id:
        raise AssertionError("fresh step-up reauthentication changed platform principal")
    if reauthenticated_principal.kind is not weak_record.principal.kind:
        raise AssertionError("fresh step-up reauthentication changed principal kind")
    if fresh_mfa_strength.amr != frozenset({"password", "totp"}):
        raise AssertionError(
            "fresh reauthentication did not prove password+totp; "
            f"got={sorted(fresh_mfa_strength.amr)!r}"
        )
    if not isinstance(fresh_mfa_strength.acr, str) or not fresh_mfa_strength.acr:
        raise AssertionError("fresh reauthentication did not provide trusted ACR context")

    step_up_time = datetime.now(timezone.utc)
    upgraded_handle = probe.rotate_browser_session(
        authority=authority,
        predecessor=weak_handle,
        now=step_up_time,
        lifetime=timedelta(minutes=30),
        authentication_strength=fresh_mfa_strength,
        reauthenticated_principal=reauthenticated_principal,
    )
    upgraded = probe.resolve_browser_session(
        authority=authority,
        handle=upgraded_handle,
        now=step_up_time,
    )

    if upgraded.principal.principal_id != weak_record.principal.principal_id:
        raise AssertionError("step-up rotation changed the platform principal")
    if upgraded.session_generation == weak_record.session_generation:
        raise AssertionError("step-up did not create a new session generation")
    if upgraded.authentication_strength is None:
        raise AssertionError("step-up successor lost fresh MFA evidence")
    if (
        upgraded.authentication_strength.principal_credential_generation
        != upgraded.session_generation
    ):
        raise AssertionError("fresh MFA evidence is not rebound to exact successor generation")
    if upgraded.authentication_strength.amr != frozenset({"password", "totp"}):
        raise AssertionError("step-up successor did not retain the fresh MFA methods")

    probe.require_authentication_strength(
        policy=probe.MfaPolicy(),
        policy_id="security.mfa.admin@1",
        evidence=upgraded.authentication_strength,
        principal=upgraded.principal,
        now=step_up_time,
    )
    _expect_denied(
        lambda: probe.resolve_browser_session(
            authority=authority,
            handle=weak_handle,
            now=step_up_time,
        ),
        "pre_step_up_session_must_be_retired",
    )
    _expect_denied(
        lambda: probe.require_authentication_strength(
            policy=probe.MfaPolicy(),
            policy_id="security.mfa.admin@1",
            evidence=weak_record.authentication_strength,
            principal=upgraded.principal,
            now=step_up_time,
        ),
        "weak_generation_evidence_cannot_authorize_upgraded_session",
    )

    # Prove that a valid fresh identity for another human cannot be attached to
    # an existing MFA user's session even when both OIDC verifications succeed.
    basic_binding = "basic-other-principal-session"
    basic_init = probe._initiation(basic_binding)
    basic_code, basic_state = probe.login_password_only(
        state=basic_init.state,
        nonce=basic_init.nonce,
        code_challenge=basic_init.pkce_challenge,
    )
    other_principal, other_strength = _complete_login(
        basic_init,
        basic_code,
        basic_state,
        port,
        basic_binding,
    )
    if other_principal.principal_id == upgraded.principal.principal_id:
        raise AssertionError("cross-principal negative control collapsed to same principal")

    _expect_denied(
        lambda: probe.rotate_browser_session(
            authority=authority,
            predecessor=upgraded_handle,
            now=datetime.now(timezone.utc),
            lifetime=timedelta(minutes=30),
            authentication_strength=other_strength,
            reauthenticated_principal=other_principal,
        ),
        "cross_principal_reauthentication_attachment",
    )

    # Routine renewal may preserve the already-established assurance, but it
    # must rebind that assurance to another exact session generation. Evidence
    # from the predecessor generation must not authorize the successor.
    renewal_time = datetime.now(timezone.utc)
    renewed_handle = probe.rotate_browser_session(
        authority=authority,
        predecessor=upgraded_handle,
        now=renewal_time,
        lifetime=timedelta(minutes=30),
    )
    renewed = probe.resolve_browser_session(
        authority=authority,
        handle=renewed_handle,
        now=renewal_time,
    )
    if renewed.authentication_strength is None:
        raise AssertionError("routine renewal lost established MFA assurance")
    _expect_denied(
        lambda: probe.require_authentication_strength(
            policy=probe.MfaPolicy(),
            policy_id="security.mfa.admin@1",
            evidence=upgraded.authentication_strength,
            principal=renewed.principal,
            now=renewal_time,
        ),
        "stale_predecessor_strength_after_renewal",
    )
    probe.require_authentication_strength(
        policy=probe.MfaPolicy(),
        policy_id="security.mfa.admin@1",
        evidence=renewed.authentication_strength,
        principal=renewed.principal,
        now=renewal_time,
    )

    if len(_USED_COUNTERS) != 2:
        raise AssertionError(
            f"expected exactly two TOTP uses (enroll/reauth), got {len(_USED_COUNTERS)}"
        )
    if _USED_COUNTERS[1] <= _USED_COUNTERS[0]:
        raise AssertionError("MFA reauthentication did not advance beyond enrollment TOTP counter")

    print(
        "d3_keycloak_mfa_step_up=PASS "
        f"acr={fresh_mfa_strength.acr} amr={','.join(sorted(fresh_mfa_strength.amr))} "
        "same_principal_password_only_denied=true fresh_reauthentication=true "
        "atomic_session_upgrade=true exact_session_generation=true "
        "cross_principal_attachment_rejected=true stale_generation_rejected=true real_totp=true"
    )
    print(
        "d3_keycloak_totp_single_use_freshness=PASS "
        "enrollment_and_reauthentication_distinct_counters=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
