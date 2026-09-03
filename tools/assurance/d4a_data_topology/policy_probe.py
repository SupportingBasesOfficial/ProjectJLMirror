from __future__ import annotations

from dataclasses import dataclass


REGULATED = {"sensitive", "regulated", "sensitive_or_regulated"}


@dataclass(frozen=True)
class RawPayloadException:
    per_tenant_assignment: bool
    max_segment_retention_ceiling_seconds: int | None
    governed_erasure_sla_seconds: int | None
    erasure_governance_signoff: bool

    def valid(self) -> bool:
        if not self.per_tenant_assignment:
            return False
        if self.max_segment_retention_ceiling_seconds is None or self.governed_erasure_sla_seconds is None:
            return False
        if self.max_segment_retention_ceiling_seconds > self.governed_erasure_sla_seconds:
            return False
        return self.erasure_governance_signoff


def encode_transport_payload(*, data_class: str, raw_value: bytes | None, opaque_reference: str | None,
                             exception: RawPayloadException | None = None) -> dict[str, object]:
    if data_class in REGULATED:
        if raw_value:
            if exception is None or not exception.valid():
                raise ValueError("regulated raw payload denied")
        elif not opaque_reference:
            raise ValueError("regulated payload requires opaque governed reference")
    return {
        "data_class": data_class,
        "raw_value_present": bool(raw_value),
        "opaque_reference": opaque_reference,
    }


def map_transport(*, tenant_authorized: bool, logical_channel: str, cell: str, mapping: dict[str, str]) -> dict[str, str]:
    if not tenant_authorized:
        raise PermissionError("tenant authorization required before physical mapping")
    key = f"{cell}:{logical_channel}"
    if key not in mapping:
        raise KeyError(key)
    return {"logical_channel": logical_channel, "physical_destination": mapping[key]}


def consume_semantically(mapped: dict[str, str]) -> str:
    # Consumer semantics are keyed only by logical identity. Physical names stay adapter-owned.
    return mapped["logical_channel"]
