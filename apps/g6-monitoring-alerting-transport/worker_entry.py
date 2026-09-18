from __future__ import annotations

import argparse


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--self-check",action="store_true")
    args=parser.parse_args()
    if args.self_check:
        from consumer import CONSUMER_CONTRACT, HEALTH_CONTRACT, PROBLEM_CONTRACT
        if CONSUMER_CONTRACT!="alerting.monitoring-resync@1":
            raise RuntimeError("consumer contract drift")
        if {PROBLEM_CONTRACT,HEALTH_CONTRACT}!={
            "monitoring.problem-state.changed","monitoring.health-projection.changed"
        }:
            raise RuntimeError("Monitoring contract drift")
        print("g6_worker_boot=PASS transport_only=PASS")
        return 0
    raise RuntimeError("G6 production worker activation is not authorized by this proof entrypoint")


if __name__=="__main__":
    raise SystemExit(main())
