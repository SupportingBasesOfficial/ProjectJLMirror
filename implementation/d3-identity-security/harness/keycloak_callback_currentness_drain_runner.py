from __future__ import annotations

from pathlib import Path
import secrets
import tempfile

import keycloak_authority_effects_probe as probe
import keycloak_authority_effects_probe_legacy as legacy
import keycloak_authority_single_winner_runner as single
import keycloak_callback_autonomous_drain_runner as autonomous


_BASE_REPLAY = autonomous.AutonomousCallbackReplayLedger
_BASE_AUTHORITY = autonomous.AutonomousCallbackLogoutAuthority


class CurrentnessAwareCallbackReplayLedger(_BASE_REPLAY):
    """Allow safe delayed resolution only for an exact authenticated SID selector."""

    def _identity_row(
        self,
        authenticated: legacy.AuthenticatedLogout,
    ) -> tuple:
        with self._connect() as db:
            row = db.execute(
                f"""
                SELECT fingerprint, status, lease_until, effect_kind,
                       auth_issued_at, auth_expires_at, auth_sid, auth_sub
                FROM {self.TABLE}
                WHERE issuer=? AND client_id=? AND jti=?
                """,
                (
                    authenticated.issuer,
                    authenticated.client_id,
                    authenticated.jti,
                ),
            ).fetchone()
        if row is None:
            raise legacy.UncertainAuthority(
                "acknowledged callback lacks durable replay responsibility"
            )
        return row

    def assert_prepared_identity(
        self,
        authenticated: legacy.AuthenticatedLogout,
    ) -> str:
        (
            fingerprint,
            status,
            _lease_until,
            effect_kind,
            issued_at,
            expires_at,
            sid,
            sub,
        ) = self._identity_row(authenticated)
        if str(fingerprint) != authenticated.raw_fingerprint:
            raise legacy.UncertainAuthority(
                "acknowledged callback replay fingerprint drifted"
            )
        if (
            issued_at != authenticated.issued_at
            or expires_at != authenticated.expires_at
            or sid != authenticated.sid
            or sub != authenticated.sub
        ):
            raise legacy.UncertainAuthority(
                "acknowledged callback authenticated context drifted"
            )
        if status not in {"pending", "retryable", "completed"}:
            raise legacy.UncertainAuthority(
                f"acknowledged callback has unsupported replay state: {status!r}"
            )
        if effect_kind is None:
            # Delayed target resolution is safe only for a provider session
            # selector. Strict SID scope later resolves that immutable SID or
            # confirmed absence; it never widens to a newer subject mapping.
            if authenticated.sid is None:
                raise legacy.UncertainAuthority(
                    "sub-only callback cannot be acknowledged without a frozen effect intent"
                )
            if status == "completed":
                raise legacy.UncertainAuthority(
                    "completed callback cannot lack a durable effect intent"
                )
        return str(status)

    def unresolved_sid_identities(self) -> list[tuple[str, str, str]]:
        now = float(self._clock())
        with self._connect() as db:
            rows = db.execute(
                f"""
                SELECT issuer, client_id, jti
                FROM {self.TABLE}
                WHERE effect_kind IS NULL
                  AND auth_issued_at IS NOT NULL
                  AND auth_expires_at IS NOT NULL
                  AND auth_sid IS NOT NULL
                  AND (
                    status='retryable'
                    OR (status='pending' AND lease_until IS NOT NULL AND lease_until<=?)
                  )
                ORDER BY issuer, client_id, jti
                """,
                (now,),
            ).fetchall()
        return [(str(issuer), str(client_id), str(jti)) for issuer, client_id, jti in rows]

    def claim_unresolved_sid(
        self,
        *,
        issuer: str,
        client_id: str,
        jti: str,
    ) -> tuple[legacy.ReplayLease, legacy.AuthenticatedLogout]:
        owner = secrets.token_hex(16)
        now = float(self._clock())
        lease_until = now + self._lease_seconds
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                f"""
                SELECT fingerprint, status, lease_until, effect_kind,
                       auth_issued_at, auth_expires_at, auth_sid, auth_sub
                FROM {self.TABLE}
                WHERE issuer=? AND client_id=? AND jti=?
                """,
                (issuer, client_id, jti),
            ).fetchone()
            if row is None:
                raise legacy.UncertainAuthority("unresolved callback identity is absent")
            (
                fingerprint,
                status,
                existing_lease_until,
                effect_kind,
                issued_at,
                expires_at,
                sid,
                sub,
            ) = row
            if effect_kind is not None:
                raise legacy.ReplayDetected(
                    "callback target was prepared after unresolved discovery"
                )
            if issued_at is None or expires_at is None or sid is None:
                raise legacy.UncertainAuthority(
                    "unresolved callback lacks exact durable SID context"
                )
            if status == "retryable":
                cursor = db.execute(
                    f"""
                    UPDATE {self.TABLE}
                    SET status='pending', owner=?, lease_until=?
                    WHERE issuer=? AND client_id=? AND jti=?
                      AND status='retryable' AND effect_kind IS NULL
                    """,
                    (owner, lease_until, issuer, client_id, jti),
                )
            elif status == "pending":
                if not isinstance(existing_lease_until, (int, float)):
                    raise legacy.UncertainAuthority(
                        "unresolved pending callback lacks lease boundary"
                    )
                if float(existing_lease_until) > now:
                    raise legacy.ReplayDetected(
                        "live unresolved callback executor still owns the claim"
                    )
                cursor = db.execute(
                    f"""
                    UPDATE {self.TABLE}
                    SET owner=?, lease_until=?
                    WHERE issuer=? AND client_id=? AND jti=?
                      AND status='pending' AND effect_kind IS NULL
                      AND lease_until<=?
                    """,
                    (owner, lease_until, issuer, client_id, jti, now),
                )
            elif status == "completed":
                raise legacy.ReplayDetected("completed callback is not unresolved work")
            else:
                raise legacy.UncertainAuthority(
                    f"unsupported unresolved callback state: {status!r}"
                )
            if cursor.rowcount != 1:
                raise legacy.ReplayDetected(
                    "unresolved callback lost single-winner ownership race"
                )
            db.execute("COMMIT")
        except Exception:
            try:
                db.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            db.close()

        authenticated = legacy.AuthenticatedLogout(
            issuer=issuer,
            client_id=client_id,
            jti=jti,
            issued_at=int(issued_at),
            expires_at=int(expires_at),
            sid=str(sid),
            sub=None if sub is None else str(sub),
            raw_fingerprint=str(fingerprint),
        )
        return legacy.ReplayLease(issuer, client_id, jti, owner), authenticated


class CurrentnessAwareCallbackLogoutAuthority(_BASE_AUTHORITY):
    replay: CurrentnessAwareCallbackReplayLedger

    def prepare_authenticated_callback(
        self,
        authenticated: legacy.AuthenticatedLogout,
    ) -> single.EffectIntent | None:
        lease = self.replay.claim_authenticated(authenticated)
        try:
            intent = self.replay.prepared_effect(lease)
            if intent is not None:
                self.replay.prepare_effect(lease, intent)
                self.replay.retryable(lease)
                self.replay.assert_prepared_identity(authenticated)
                return intent

            try:
                resolved = self.mappings.resolve(
                    issuer=authenticated.issuer,
                    client_id=authenticated.client_id,
                    sid=authenticated.sid,
                    sub=authenticated.sub,
                )
            except legacy.UncertainAuthority:
                # Do not invent a target while mapping currentness is unknown.
                # An exact SID is nevertheless a stable historical selector, so
                # its authenticated callback may be durably acknowledged as
                # resolution-pending and retried internally after currentness
                # returns. A sub-only selector is mutable placement and is not
                # safe to acknowledge without a frozen target.
                self._best_effort_retryable(lease)
                if authenticated.sid is None:
                    raise
                self.replay.assert_prepared_identity(authenticated)
                return None

            intent = self.replay.prepare_effect(
                lease,
                self._intent_from_resolution(resolved),
            )
            self.replay.retryable(lease)
            self.replay.assert_prepared_identity(authenticated)
            return intent
        except Exception:
            self._best_effort_retryable(lease)
            raise

    def resolve_unprepared_sid_callback(
        self,
        *,
        issuer: str,
        client_id: str,
        jti: str,
    ) -> str:
        lease, authenticated = self.replay.claim_unresolved_sid(
            issuer=issuer,
            client_id=client_id,
            jti=jti,
        )
        try:
            resolved = self.mappings.resolve(
                issuer=authenticated.issuer,
                client_id=authenticated.client_id,
                sid=authenticated.sid,
                sub=authenticated.sub,
            )
            intent = self.replay.prepare_effect(
                lease,
                self._intent_from_resolution(resolved),
            )
            self.replay.renew_for_effect(lease)
            result = self._apply_effect_intent(
                authenticated=authenticated,
                intent=intent,
            )
            self.replay.complete(lease)
            return result
        except Exception:
            self._best_effort_retryable(lease)
            raise

    def drain_recoverable_callbacks(self) -> list[tuple[str, str, str, str]]:
        results = super().drain_recoverable_callbacks()
        for issuer, client_id, jti in self.replay.unresolved_sid_identities():
            try:
                result = self.resolve_unprepared_sid_callback(
                    issuer=issuer,
                    client_id=client_id,
                    jti=jti,
                )
            except (legacy.ReplayDetected, legacy.UncertainAuthority):
                # Live ownership races and still-unavailable currentness both
                # leave durable work for a later pass; neither may guess an
                # authority target or turn into a second executor.
                continue
            results.append((issuer, client_id, jti, result))
        return results


def _authenticated_sid(
    *,
    now: int,
    jti: str,
    sid: str,
    sub: str,
    fingerprint: str,
) -> legacy.AuthenticatedLogout:
    return legacy.AuthenticatedLogout(
        issuer="https://idp.example.invalid/realms/d3",
        client_id="bff-client",
        jti=jti,
        issued_at=now,
        expires_at=now + 30,
        sid=sid,
        sub=sub,
        raw_fingerprint=fingerprint,
    )


def _prove_sid_resolution_pending_currentness_recovery() -> None:
    clock_value = [130_000.0]

    def clock() -> float:
        return clock_value[0]

    issuer = "https://idp.example.invalid/realms/d3"
    client_id = "bff-client"
    provider_sid = "provider-sid-currentness-pending"
    provider_sub = "provider-sub-currentness-pending"
    principal = "platform-principal-currentness-pending"

    with tempfile.TemporaryDirectory(prefix="d3-callback-currentness-drain-") as td:
        path = Path(td) / "replay.sqlite3"
        replay = CurrentnessAwareCallbackReplayLedger(
            path,
            clock=clock,
            lease_seconds=10.0,
        )
        fences = single.IdempotentSessionFenceAuthority()
        mappings = single.IdempotentProviderMappingAuthority()
        local = fences.create(
            session_id="session-currentness-pending",
            principal_id=principal,
        )
        mappings.bind(
            issuer=issuer,
            client_id=client_id,
            sid=provider_sid,
            sub=provider_sub,
            principal_id=principal,
            local_session_id=local.session_id,
        )
        mappings.available = False
        authority = CurrentnessAwareCallbackLogoutAuthority(
            verifier=None,
            replay=replay,
            mappings=mappings,
            fences=fences,
        )
        authenticated = _authenticated_sid(
            now=int(clock_value[0]),
            jti="sid-currentness-resolution-pending",
            sid=provider_sid,
            sub=provider_sub,
            fingerprint="7" * 64,
        )
        if authority.prepare_authenticated_callback(authenticated) is not None:
            raise AssertionError("unavailable mapping unexpectedly produced a frozen target")
        replay.assert_prepared_identity(authenticated)
        if replay.status(
            issuer=issuer,
            client_id=client_id,
            jti=authenticated.jti,
        ) != "retryable":
            raise AssertionError("resolution-pending SID callback was not durable retryable work")

        clock_value[0] += 600.0
        restarted_replay = CurrentnessAwareCallbackReplayLedger(
            path,
            clock=clock,
            lease_seconds=10.0,
        )
        restarted = CurrentnessAwareCallbackLogoutAuthority(
            verifier=None,
            replay=restarted_replay,
            mappings=mappings,
            fences=fences,
        )
        if restarted.drain_recoverable_callbacks():
            raise AssertionError("currentness outage guessed a delayed SID authority target")
        if not fences.current(local):
            raise AssertionError("currentness outage applied an unproven logout effect")

        # Subject placement changes while currentness is unavailable. Once the
        # authority recovers, exact SID scope must still retire only the frozen
        # historical session binding and must not widen to the newer subject.
        relocated_principal = "platform-principal-currentness-relocated"
        mappings.relink_subject(
            issuer=issuer,
            sub=provider_sub,
            principal_id=relocated_principal,
        )
        relocated = fences.create(
            session_id="session-currentness-relocated",
            principal_id=relocated_principal,
        )
        mappings.available = True
        drained = restarted.drain_recoverable_callbacks()
        if drained != [(issuer, client_id, authenticated.jti, "sid_retired")]:
            raise AssertionError(f"recovered SID callback drain mismatch: {drained!r}")
        if fences.current(local):
            raise AssertionError("recovered exact SID did not retire its historical local session")
        if not fences.current(relocated):
            raise AssertionError("recovered SID callback widened to newer subject placement")

        # Mutable sub-only placement cannot receive a 2xx-worthy durable state
        # when currentness is unavailable and no immutable effect was frozen.
        sub_only = legacy.AuthenticatedLogout(
            issuer=issuer,
            client_id=client_id,
            jti="sub-only-currentness-unavailable",
            issued_at=int(clock_value[0]),
            expires_at=int(clock_value[0]) + 30,
            sid=None,
            sub="provider-sub-only-currentness-unavailable",
            raw_fingerprint="6" * 64,
        )
        mappings.available = False
        try:
            restarted.prepare_authenticated_callback(sub_only)
        except legacy.UncertainAuthority:
            pass
        else:
            raise AssertionError("sub-only callback was acknowledgeable without a frozen target")
        try:
            restarted_replay.assert_prepared_identity(sub_only)
        except legacy.UncertainAuthority:
            pass
        else:
            raise AssertionError("sub-only unresolved callback became 2xx-worthy durable work")

    print(
        "d3_keycloak_callback_currentness_drain=PASS "
        "sid_resolution_pending_ack_safe=true no_target_guess_during_outage=true "
        "restart_drain_after_currentness_recovery=true exact_sid_no_subject_widening=true "
        "sub_only_unresolved_not_acknowledgeable=true"
    )


def main() -> int:
    _prove_sid_resolution_pending_currentness_recovery()

    # Replace the immediately prior layer's explicit seams, then run its whole
    # synthetic + real-Keycloak superset. The base HTTP handler dynamically
    # calls the patched authority and replay methods, so no older proof is lost.
    autonomous.AutonomousCallbackReplayLedger = CurrentnessAwareCallbackReplayLedger
    autonomous.AutonomousCallbackLogoutAuthority = CurrentnessAwareCallbackLogoutAuthority

    result = autonomous.main()
    print(
        "d3_keycloak_callback_currentness_gate=PASS "
        "prepared_or_exact_sid_pending_before_2xx=true autonomous_drain=true "
        "mapping_outage_fail_closed=true sub_only_mutable_target_not_guessed=true "
        "prior_callback_recovery_suite_preserved=true"
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
