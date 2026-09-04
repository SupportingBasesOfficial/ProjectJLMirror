from __future__ import annotations

import copy

from validate_source_evidence import validate_objects, load_objects, EVIDENCE_ID


def must_fail(name: str, mutate, expected: str) -> None:
    source, profile, plan, state = (copy.deepcopy(obj) for obj in load_objects())
    mutate(source, profile, plan, state)
    errors = validate_objects(source, profile, plan, state)
    if not any(expected in error for error in errors):
        raise AssertionError(f"negative control {name!r} did not fail with {expected!r}: {errors!r}")


def main() -> int:
    d4a = lambda st: next(t for t in st["tracks"] if t["track_id"] == "D4-A")
    must_fail("mutable Kafka tag", lambda s,p,l,st: s.__setitem__("candidate_image", "apache/kafka:4.3.1"), "Kafka image pin drift")
    must_fail("synthetic recovery kind", lambda s,p,l,st: s["evidence_kinds"].__setitem__(EVIDENCE_ID, "synthetic_probe"), "source evidence kind drift")
    must_fail("source auto credit", lambda s,p,l,st: s.__setitem__("ledger_credit", [EVIDENCE_ID]), "source package self-promotion")
    must_fail("rewrite historical prior credit", lambda s,p,l,st: s["prior_promoted_ledger_credit"].append(EVIDENCE_ID), "source historical prior credit drift")
    must_fail("remove promoted global recovery credit", lambda s,p,l,st: l["credited_evidence"].remove(EVIDENCE_ID), "global promoted seven-of-seven credit drift")
    must_fail("duplicate eighth global credit", lambda s,p,l,st: l["credited_evidence"].append(EVIDENCE_ID), "global promoted seven-of-seven credit drift")
    must_fail("state loses recovery credit", lambda s,p,l,st: d4a(st)["evidence_completed"].remove(EVIDENCE_ID), "state completed seven-of-seven evidence drift")
    must_fail("state reopens recovery", lambda s,p,l,st: d4a(st)["evidence_remaining"].append(EVIDENCE_ID), "no D4-A evidence remaining")
    must_fail("state silently selects", lambda s,p,l,st: d4a(st).__setitem__("state", "candidate_selected"), "evidence-complete selection-pending")
    must_fail("disable outage", lambda s,p,l,st: s.__setitem__("outage_recovery_benchmark_claimed", False), "outage recovery benchmark claim missing")
    must_fail("tiny backlog", lambda s,p,l,st: p.__setitem__("committed_backlog_messages", 2), "outage backlog too weak")
    must_fail("no protected workload", lambda s,p,l,st: p.__setitem__("protected_current_messages", 0), "protected current workload too weak")
    must_fail("protected lower priority", lambda s,p,l,st: p.__setitem__("protected_priority", p["normal_priority"]), "protected priority must exceed backlog priority")
    must_fail("unbounded starvation", lambda s,p,l,st: p.__setitem__("max_backlog_dispatches_before_protected", 99), "anti-starvation bound invalid")
    must_fail("disable ack ambiguity", lambda s,p,l,st: p["ack_ambiguity"].__setitem__("enabled", False), "ack ambiguity probe disabled")
    must_fail("new identity on retry", lambda s,p,l,st: p["ack_ambiguity"].__setitem__("retry_same_logical_identity", False), "ack ambiguity must reuse same logical identity")
    must_fail("broker progress becomes effect truth", lambda s,p,l,st: p["fixed_invariants"].__setitem__("broker_progress_is_business_effect_truth", True), "broker progress promoted to business truth")
    must_fail("drop anti-starvation measurement", lambda s,p,l,st: p["required_measurements"].remove("max_backlog_before_each_protected_delivery"), "recovery measurement inventory drift")
    must_fail("select Kafka in source", lambda s,p,l,st: s.__setitem__("kafka_selection_state", "selected"), "source package selects Kafka")
    must_fail("select Kafka globally", lambda s,p,l,st: l.__setitem__("selection_state", "selected"), "plan must not select Kafka")
    must_fail("skip separate acceptance", lambda s,p,l,st: l.__setitem__("acceptance_state", "accepted"), "require separate acceptance")
    must_fail("grant production", lambda s,p,l,st: s.__setitem__("production_authority", "granted"), "source grants production authority")
    print("d4a_recovery_negative_controls=PASS real_outage=required source_credit=0 historical_prior=6 global_credit=7 evidence_reopen=blocked priority_starvation=blocked ack_identity_rewrite=blocked broker_progress_authority=blocked silent_selection=blocked production_authority=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
