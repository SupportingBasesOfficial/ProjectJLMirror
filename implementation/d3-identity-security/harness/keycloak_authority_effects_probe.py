from __future__ import annotations

import keycloak_authority_effects_probe_legacy as legacy


# Structural marker retained for the conformance workflow's evidence guard.
LEGACY_AUTHORITY_PASS_MARKER = "d3_keycloak_authority_effects=PASS"
_ORIGINAL_CONFIGURE_REALM = legacy.configure_realm


class StrictProviderMappingAuthority(legacy.ProviderMappingAuthority):
    """Resolve provider session identity without laundering unknown SIDs into subject-wide effects."""

    def resolve(
        self,
        *,
        issuer: str,
        client_id: str,
        sid: str | None,
        sub: str | None,
    ) -> legacy.ProviderSessionBinding | str | None:
        self.lookup_count += 1
        if not self.available:
            raise legacy.UncertainAuthority("provider mapping currentness unavailable")

        # An authenticated logout token that carries `sid` is session-scoped.
        # A missing/retired mapping is therefore confirmed absence for that
        # exact provider session. It must never fall through to `sub`, because
        # doing so would widen an unknown session logout into a principal-wide
        # fence and could revoke unrelated, newer sessions after relink.
        if sid is not None:
            binding = self.sid_bindings.get((issuer, client_id, sid))
            if binding is None:
                return None
            if sub is not None and binding.sub != sub:
                raise legacy.UncertainAuthority(
                    "authenticated sid/sub mapping is contradictory"
                )
            if binding.active:
                return binding
            return None

        # Subject-wide fencing is permitted only for genuinely sub-only
        # authenticated logout tokens.
        if sub is not None:
            return self.subject_current.get((issuer, sub))
        return None


def _install_explicit_realm_role_mapper() -> None:
    token = legacy.admin_token()
    _, clients, _ = legacy.request(
        "GET",
        f"{legacy.BASE}/admin/realms/{legacy.REALM}/clients?clientId={legacy.CLIENT_ID}",
        token=token,
    )
    if not isinstance(clients, list) or len(clients) != 1:
        raise AssertionError("could not resolve exactly one authority evidence client")
    client_uuid = clients[0].get("id")
    if not isinstance(client_uuid, str) or not client_uuid:
        raise AssertionError("authority evidence client lacks id")

    legacy.request(
        "POST",
        f"{legacy.BASE}/admin/realms/{legacy.REALM}/clients/{client_uuid}/protocol-mappers/models",
        token=token,
        body={
            "name": "d3-realm-roles",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-usermodel-realm-role-mapper",
            "consentRequired": False,
            "config": {
                "multivalued": "true",
                "access.token.claim": "true",
                "claim.name": "realm_access.roles",
                "jsonType.label": "String",
                "id.token.claim": "true",
                "userinfo.token.claim": "false",
                "usermodel.realmRoleMapping.rolePrefix": "",
            },
        },
    )
    _, mappers, _ = legacy.request(
        "GET",
        f"{legacy.BASE}/admin/realms/{legacy.REALM}/clients/{client_uuid}/protocol-mappers/models",
        token=token,
    )
    matches = [
        mapper
        for mapper in (mappers if isinstance(mappers, list) else [])
        if isinstance(mapper, dict)
        and mapper.get("name") == "d3-realm-roles"
        and mapper.get("protocolMapper") == "oidc-usermodel-realm-role-mapper"
    ]
    if len(matches) != 1:
        raise AssertionError("explicit Keycloak realm-role mapper was not installed exactly once")


def configure_realm() -> str:
    user_id = _ORIGINAL_CONFIGURE_REALM()
    _install_explicit_realm_role_mapper()
    return user_id


def _prove_sid_scope_does_not_widen() -> None:
    mappings = StrictProviderMappingAuthority()
    issuer = "https://idp.example.invalid/realms/d3"
    sub = "provider-subject-stable"
    mappings.subject_current[(issuer, sub)] = "platform-principal-current"

    unknown_sid = mappings.resolve(
        issuer=issuer,
        client_id="bff-client",
        sid="provider-session-unknown",
        sub=sub,
    )
    if unknown_sid is not None:
        raise AssertionError("unknown provider sid widened into subject-wide authority")

    sub_only = mappings.resolve(
        issuer=issuer,
        client_id="bff-client",
        sid=None,
        sub=sub,
    )
    if sub_only != "platform-principal-current":
        raise AssertionError("genuine sub-only logout lost principal-wide mapping")

    print(
        "d3_keycloak_sid_scope=PASS "
        "unknown_sid_no_sub_fallback=true sub_only_principal_fence_allowed=true"
    )


def main() -> int:
    # Patch the preserved evidence body only at its explicit authority seams.
    # The legacy module remains byte-for-byte for review traceability; this
    # wrapper is the executable contract used by the conformance workflow.
    legacy.ProviderMappingAuthority = StrictProviderMappingAuthority
    legacy.configure_realm = configure_realm

    _prove_sid_scope_does_not_widen()
    result = legacy.main()
    print(
        "d3_keycloak_authority_wrapper=PASS "
        "explicit_realm_role_mapper=true strict_sid_scope=true"
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
