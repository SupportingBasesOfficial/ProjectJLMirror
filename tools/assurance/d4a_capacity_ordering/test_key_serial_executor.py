from __future__ import annotations

from threading import Barrier, Event, Lock
from time import sleep

from key_serial_executor import KeySerialExecutor


def prove_same_key_serialization() -> None:
    executor = KeySerialExecutor(max_workers=4)
    first_started = Event()
    release_first = Event()
    second_started = Event()
    order: list[str] = []
    guard = Lock()

    def first() -> str:
        first_started.set()
        release_first.wait(timeout=5)
        with guard:
            order.append("first")
        return "first"

    def second() -> str:
        second_started.set()
        with guard:
            order.append("second")
        return "second"

    a = executor.submit("tenant-a:subject-1", first)
    assert first_started.wait(timeout=2), "first same-key task did not start"
    b = executor.submit("tenant-a:subject-1", second)
    sleep(0.15)
    assert not second_started.is_set(), "same-key task overlapped instead of serializing"
    release_first.set()
    assert a.result(timeout=3) == "first"
    assert b.result(timeout=3) == "second"
    executor.shutdown()
    assert order == ["first", "second"], order


def prove_independent_key_overlap() -> None:
    executor = KeySerialExecutor(max_workers=4)
    barrier = Barrier(2, timeout=3)

    def task(name: str) -> str:
        barrier.wait()
        sleep(0.05)
        return name

    left = executor.submit("tenant-a:subject-1", lambda: task("left"))
    right = executor.submit("tenant-a:subject-2", lambda: task("right"))
    assert {left.result(timeout=4), right.result(timeout=4)} == {"left", "right"}
    executor.shutdown()


def prove_global_serial_negative_control() -> None:
    # A one-worker executor is deliberately rejected by the component so a future
    # refactor cannot silently turn key-level sequencing into global serialization.
    try:
        KeySerialExecutor(max_workers=1)
    except ValueError as exc:
        assert ">= 2" in str(exc)
    else:
        raise AssertionError("global-serialization negative control unexpectedly passed")


def main() -> int:
    prove_same_key_serialization()
    prove_independent_key_overlap()
    prove_global_serial_negative_control()
    print("d4a_key_serial_executor=PASS same_key=serial independent_keys=overlap global_serialization=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
