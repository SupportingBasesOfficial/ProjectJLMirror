from policy_probe import RawPayloadException, consume_semantically, encode_transport_payload, map_transport


def must_fail(fn, label: str) -> None:
    try:
        fn()
    except Exception:
        return
    raise AssertionError(f"negative control did not fail: {label}")


def main() -> None:
    must_fail(
        lambda: encode_transport_payload(
            data_class="sensitive_or_regulated", raw_value=b"secret", opaque_reference=None
        ),
        "raw regulated leak",
    )

    good_reference = encode_transport_payload(
        data_class="sensitive_or_regulated", raw_value=None, opaque_reference="vault://tenant/t1/object/o1"
    )
    assert good_reference["raw_value_present"] is False
    assert good_reference["opaque_reference"]

    base = dict(
        max_segment_retention_ceiling_seconds=300,
        governed_erasure_sla_seconds=600,
        erasure_governance_signoff=True,
        per_tenant_assignment=True,
    )
    for missing in (
        "per_tenant_assignment",
        "max_segment_retention_ceiling_seconds",
        "governed_erasure_sla_seconds",
        "erasure_governance_signoff",
    ):
        values = dict(base)
        if missing in {"per_tenant_assignment", "erasure_governance_signoff"}:
            values[missing] = False
        else:
            values[missing] = None
        must_fail(
            lambda values=values: encode_transport_payload(
                data_class="regulated",
                raw_value=b"exceptional",
                opaque_reference=None,
                exception=RawPayloadException(**values),
            ),
            f"missing exception control {missing}",
        )

    must_fail(
        lambda: encode_transport_payload(
            data_class="regulated",
            raw_value=b"exceptional",
            opaque_reference=None,
            exception=RawPayloadException(True, 900, 600, True),
        ),
        "retention exceeds erasure SLA",
    )

    accepted = encode_transport_payload(
        data_class="regulated",
        raw_value=b"exceptional",
        opaque_reference=None,
        exception=RawPayloadException(True, 300, 600, True),
    )
    assert accepted["raw_value_present"] is True

    mapping_v1 = {"cell-a:monitoring.alert-raised": "kafka.topic.alpha"}
    mapping_v2 = {"cell-a:monitoring.alert-raised": "replacement.stream.beta"}
    must_fail(
        lambda: map_transport(
            tenant_authorized=False,
            logical_channel="monitoring.alert-raised",
            cell="cell-a",
            mapping=mapping_v1,
        ),
        "mapping before tenant authorization",
    )
    first = map_transport(
        tenant_authorized=True,
        logical_channel="monitoring.alert-raised",
        cell="cell-a",
        mapping=mapping_v1,
    )
    second = map_transport(
        tenant_authorized=True,
        logical_channel="monitoring.alert-raised",
        cell="cell-a",
        mapping=mapping_v2,
    )
    assert first["physical_destination"] != second["physical_destination"]
    assert consume_semantically(first) == consume_semantically(second) == "monitoring.alert-raised"

    print("d4a_data_topology_negative_controls=PASS raw_leak=blocked exception_all_controls=required auth_before_mapping=required physical_mapping=replaceable")


if __name__ == "__main__":
    main()
