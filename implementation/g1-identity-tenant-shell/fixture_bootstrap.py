from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class G1FixtureBootstrap:
    principal_id: str = "principal-a"
    tenant_id: str = "tenant-a"
    cell_id: str = "cell-a"
    membership_action: str = "organization.memberships.read"
    authentication_strength_policy_id: str = "shell-access-v1"

    def __post_init__(self) -> None:
        for field in (
            "principal_id",
            "tenant_id",
            "cell_id",
            "membership_action",
            "authentication_strength_policy_id",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value or value != value.strip():
                raise ValueError(f"{field} must be a canonical non-empty fixture binding")


FIXTURE = G1FixtureBootstrap()
