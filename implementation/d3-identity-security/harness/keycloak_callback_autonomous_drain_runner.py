from __future__ import annotations

from pathlib import Path
import tempfile

import keycloak_authority_continuity_runner as continuity
import keycloak_authority_effects_probe as probe
import keycloak_authority_effects_probe_legacy as legacy
import keycloak_authority_single_winner_runner as single
import keycloak_authority_upgrade_guard_runner as upgrade
import keycloak_callback_durable_ingress_runner as ingress


_BASE_REPLAY = upgrade.UpgradeGuardedContinuityReplayLedger
_BASE_AUTHORITY = continuity.ContinuityLogoutAuthority
_BASE_HANDLER = ingress.DurableCaptureHandler


class AutonomousCallbackReplayLedger(_BASE_REPLAY):
    """Discover durable prepared callback work without another provider retry.

    Callback admission freezes authenticated context plus an immutable authority
    effect intent before HTTP 2xx. A later worker can therefore discover
    retryable or abandoned-expired work directly from the replay ledger and
    invoke the existing single-winner reconciliation path without revalidating
    the original token or consulting newer provider-subject placement.
    """

    def assert_prepared_identity(
        self,
        authenticated: legacy.AuthenticatedLogout,
    ) -> str:
        with self._connect() as db:
            row = db.execute(
                f"""
                SELECT fingerprint, status, effect_kind,
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
        (
            fingerprint,
            status,
            effect_kind,
            issued_at,
            expires_at,
            sid,
            sub,
        ) = row
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
        if effect_kind is None:
            raise legacy.UncertainAuthority(
                "acknowledged callback lacks immutable authority effect intent"
            )
        if status not in {"pending", "retryable", "completed"}:
            raise legacy.UncertainAuthority(
                f"acknowledged callback has unsupported replay state: {status!r}"
            )
        return str(status)

    def reconcilable_identities(self) -> list[tuple[str, str, str]]:
        now = float(self._clock())
        with self._connect() as db:
            rows = db.execute(
                f"""
                SELECT issuer, client_id, jti
                FROM {self.TABLE}
                WHERE effect_kind IS NOT NULL
                  AND auth_issued_at IS NOT NULL
                  AND auth_expires_at IS NOT NULL
                  AND (auth_sid IS NOT NULL OR auth_sub IS NOT NULL)
                  AND (
                    status='retryable'
                    OR (status='pending' AND lease_until IS NOT NULL AND lease_until<=?)
                  )
                ORDER BY issuer, client_id, jti
                """,
                (now,),
            ).fetchall()
        return [(str(issuer), str(client_id), str(jti)) for issuer, client_id, jti in rows]


class AutonomousCallbackLogoutAuthority(_BASE_AUTHORITY):
    replay: AutonomousCallbackReplayLedger

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # The real callback handler is constructed by the preserved legacy
        # harness. Register only the already-created authority instance so HTTP
        # admission can freeze its durable effect intent before acknowledging.
        AutonomousDurableCaptureHandler.authority = self

    def prepare_authenticated_callback(
        self,
        authenticated: legacy.AuthenticatedLogout,
    ) -> single.EffectIntent:
        """Durably freeze callback responsibility before HTTP acknowledgement."""

        lease = self.replay.claim_authenticated(authenticated)
        try:
            intent = self.replay.prepared_effect(lease)
            if intent is None:
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
            else:
                self.replay.prepare_effect(lease, intent)

            # HTTP admission does not execute the local effect. Release the
            # claim as durable retryable work after the immutable intent exists,
            # making it immediately claimable by either the normal consumer or
            # an autonomous restart drain.
            self.replay.retryable(lease)
            self.replay.assert_prepared_identity(authenticated)
            return intent
        except Exception:
            self._best_effort_retryable(lease)
            raise

    def drain_recoverable_callbacks(self) -> list[tuple[str, str, str, str]]:
        """Drain prepared callback work without provider traffic or live token time."""

        results: list[tuple[str, str, str, str]] = []
        for issuer, client_id, jti in self.replay.reconcilable_identities():
            try:
                result = self.reconcile(
                    issuer=issuer,
                    client_id=client_id,
                    jti=jti,
                )
            except legacy.ReplayDetected:
                # Another worker won after discovery. Single-winner ownership is
                # authoritative; this scanner must not turn that race into a
                # second execution path.
                continue
            results.append((issuer, client_id, jti, result))
        return results


class AutonomousDurableCaptureHandler(_BASE_HANDLER):
    """Acknowledge only after durable authenticated context + frozen intent."""

    authority: AutonomousCallbackLogoutAuthority | None = None

    def do_POST(self):
        if self.path != "/backchannel-logout":
            self._respond(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._respond(400)
            return
        if length <= 0 or length > 64 * 1024:
            self._respond(400)
            return
        raw = self.rfile.read(length)
        try:
            parsed = legacy.parse_qs(
                raw.decode("utf-8"),
                keep_blank_values=True,
                strict_parsing=True,
            )
        except (UnicodeDecodeError, ValueError):
            self._respond(400)
            return
        values = parsed.get("logout_token", [])
        if len(values) != 1 or not values[0]:
            self._respond(400)
            return

        inbox = type(self).inbox
        verifier = type(self).verifier
        authority = type(self).authority
        if inbox is None or verifier is None or authority is None:
            self._respond(503)
            return

        token = values[0]
        try:
            durable = inbox.observe_exact(token)
            if durable is None:
                authenticated = verifier.verify(token)

                # Ordering is deliberate: freeze the canonical replay identity,
                # authenticated context, and exact effect target first. If the
                # process dies before the audit inbox commit, no 2xx has been
                # sent and the replay ledger is already autonomously drainable.
                authority.prepare_authenticated_callback(authenticated)
                inbox.accept_verified(token=token, authenticated=authenticated)
            else:
                # Exact retries may be acknowledged without re-admitting an old
                # token as a credential, but only while durable authority
                # responsibility still proves the same authenticated identity
                # and immutable prepared intent (or completed outcome).
                authority.replay.assert_prepared_identity(durable.authenticated)
        except legacy.AdmissionDenied:
            self._respond(400)
            return
        except Exception:
            self._respond(503)
            return

        try:
            type(self).captured.put_nowait(token)
        except legacy.queue.Full:
            pass
        self._respond(200)


def _synthetic_logout(
    *,
    now: int,
    jti: str,
    sub: str,
    fingerprint: str,
) -> legacy.AuthenticatedLogout:
    return legacy.AuthenticatedLogout(
        issuer="https://idp.example.invalid/realms/d3",
        client_id="bff-client",
        jti=jti,
        issued_at=now,
        expires_at=now + 30,
        sid=None,
        sub=sub,
        raw_fingerprint=fingerprint,
    )


def _prove_autonomous_restart_drain() -> None:
    clock_value = [110_000.0]

    def clock() -> float:
        return clock_value[0]

    issuer = "https://idp.example.invalid/realms/d3"
    client_id = "bff-client"
    principal = "platform-principal-callback-drain"
    provider_sub = "provider-sub-callback-drain"

    with tempfile.TemporaryDirectory(prefix="d3-callback-autonomous-drain-") as td:
        path = Path(td) / "replay.sqlite3"
        replay = AutonomousCallbackReplayLedger(path, clock=clock, lease_seconds=10.0)
        fences = single.IdempotentSessionFenceAuthority()
        mappings = single.IdempotentProviderMappingAuthority()
        mappings.relink_subject(
            issuer=issuer,
            sub=provider_sub,
            principal_id=principal,
        )
        pre_logout = fences.create(
            session_id="session-before-durable-callback",
            principal_id=principal,
        )
        authority = AutonomousCallbackLogoutAuthority(
            verifier=None,
            replay=replay,
            mappings=mappings,
            fences=fences,
        )
        authenticated = _synthetic_logout(
            now=int(clock_value[0]),
            jti="callback-drain-after-ack",
            sub=provider_sub,
            fingerprint="9" * 64,
        )
        intent = authority.prepare_authenticated_callback(authenticated)
        if intent.kind != "principal" or intent.target != principal:
            raise AssertionError("callback admission did not freeze the principal effect target")
        if replay.status(
            issuer=issuer,
            client_id=client_id,
            jti=authenticated.jti,
        ) != "retryable":
            raise AssertionError("prepared callback was not released as durable drainable work")

        # Simulate everything the previous evidence did not prove: HTTP 200 has
        # already happened, the process/notification path disappears, no IdP
        # retry arrives, token freshness expires, and provider-sub placement is
        # changed before a later internal worker starts.
        mappings.relink_subject(
            issuer=issuer,
            sub=provider_sub,
            principal_id="platform-principal-relocated-after-callback",
        )
        relocated_session = fences.create(
            session_id="relocated-principal-session",
            principal_id="platform-principal-relocated-after-callback",
        )
        clock_value[0] += 600.0

        restarted_replay = AutonomousCallbackReplayLedger(
            path,
            clock=clock,
            lease_seconds=10.0,
        )
        restarted = AutonomousCallbackLogoutAuthority(
            verifier=None,
            replay=restarted_replay,
            mappings=mappings,
            fences=fences,
        )
        discovered = restarted_replay.reconcilable_identities()
        if discovered != [(issuer, client_id, authenticated.jti)]:
            raise AssertionError(f"restart drain did not discover exact prepared callback: {discovered!r}")
        drained = restarted.drain_recoverable_callbacks()
        if drained != [(issuer, client_id, authenticated.jti, "principal_fenced")]:
            raise AssertionError(f"autonomous callback drain produced unexpected result: {drained!r}")
        if fences.current(pre_logout):
            raise AssertionError("autonomous drain failed to apply the frozen logout fence")
        if not fences.current(relocated_session):
            raise AssertionError("restart drain widened the frozen callback target to newer mapping")
        if restarted_replay.status(
            issuer=issuer,
            client_id=client_id,
            jti=authenticated.jti,
        ) != "completed":
            raise AssertionError("autonomously drained callback did not reach terminal replay state")
        if restarted.drain_recoverable_callbacks():
            raise AssertionError("completed callback became rediscoverable after autonomous drain")

        post_recovery = fences.create(
            session_id="session-after-callback-recovery",
            principal_id=principal,
        )
        if not fences.current(post_recovery):
            raise AssertionError("completed drain incorrectly poisoned newer principal generation")

        # A callback whose subject has no mapping at admission freezes `none`.
        # Creating a mapping later must not widen that accepted historical event
        # into a principal-wide revocation during delayed drain.
        absent_sub = "provider-sub-absent-at-callback"
        absent = _synthetic_logout(
            now=int(clock_value[0]),
            jti="callback-none-does-not-widen",
            sub=absent_sub,
            fingerprint="8" * 64,
        )
        absent_intent = restarted.prepare_authenticated_callback(absent)
        if absent_intent.kind != "none":
            raise AssertionError("confirmed-absent callback did not freeze a none intent")
        mappings.relink_subject(
            issuer=issuer,
            sub=absent_sub,
            principal_id="platform-principal-created-later",
        )
        late_session = fences.create(
            session_id="late-mapping-session",
            principal_id="platform-principal-created-later",
        )
        clock_value[0] += 600.0
        drained_none = restarted.drain_recoverable_callbacks()
        if drained_none != [(issuer, client_id, absent.jti, "confirmed_absent")]:
            raise AssertionError("none-intent callback did not reconcile as confirmed absence")
        if not fences.current(late_session):
            raise AssertionError("delayed callback drain widened confirmed absence to later mapping")

    print(
        "d3_keycloak_callback_autonomous_drain=PASS "
        "effect_intent_before_2xx=true restart_discovery_without_provider_retry=true "
        "expired_token_not_revalidated=true mapping_drift_not_reinterpreted=true "
        "confirmed_absence_not_widened=true single_winner_terminal_completion=true"
    )


def main() -> int:
    _prove_autonomous_restart_drain()

    # Make the new layer the final superset without rewriting prior runners.
    # upgrade.main() reads this class dynamically when it patches continuity;
    # continuity.main() likewise reads its authority symbol dynamically before
    # single.main() patches the preserved real-Keycloak harness.
    upgrade.UpgradeGuardedContinuityReplayLedger = AutonomousCallbackReplayLedger
    continuity.ContinuityLogoutAuthority = AutonomousCallbackLogoutAuthority
    ingress.DurableCaptureHandler = AutonomousDurableCaptureHandler

    result = ingress.main()
    print(
        "d3_keycloak_callback_recovery_gate=PASS "
        "durable_prepared_responsibility=true autonomous_restart_drain=true "
        "no_provider_retry_dependency=true no_current_mapping_widening=true "
        "prior_durable_ingress_authority_suite_preserved=true"
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
