#!/usr/bin/env python3
"""Procedure 2: Clip off Funnels (decision logic from the paper).

Angles are in radians.  A and B are two funnels F_{p,q,S} and F_{p,q,S1}
that occupy the same vertex v.  Each measurement is:
    (l, angle) = (length of S_P(s,v), angle(p,v,z))

Returns the children to delete:
    ("A", "left")  -> left child F_{p,v,...} of A
    ("A", "right") -> right child F_{v,q,...} of A
    ("B", "left")  -> left child F_{p,v,...} of B
    ("B", "right") -> right child F_{v,q,...} of B

The comparisons follow Procedure 2, lines 1-16. A small tolerance is used
only to handle floating-point equality; it does not change the case logic.
"""
from __future__ import annotations

from math import isfinite
from typing import Literal

Side = Literal["left", "right"]
FunnelLabel = Literal["A", "B"]
Deletion = tuple[FunnelLabel, Side]


def _compare(a: float, b: float, eps: float) -> int:
    """-1 if a < b, 0 if equal within tolerance, +1 if a > b."""
    if not isfinite(a) or not isfinite(b):
        raise ValueError("Clip measurements must be finite numbers.")
    if a < b - eps:
        return -1
    if a > b + eps:
        return 1
    return 0


def clip_off_funnels(
    meas_a: tuple[float, float],
    meas_b: tuple[float, float],
    *,
    eps_length: float = 1e-9,
    eps_angle: float = 1e-9,
) -> list[Deletion]:
    """Return the child funnel(s) removed by Procedure 2.

    meas_a = (l, angle_pvz) for funnel A
    meas_b = (l1, angle_pvz1) for funnel B

    When both length and angle are equal within tolerance, the paper specifies
    no deletion in lines 12-16; this function therefore returns [].
    """
    l, angle_a = meas_a
    l1, angle_b = meas_b

    cmp_length = _compare(l, l1, eps_length)
    cmp_angle = _compare(angle_a, angle_b, eps_angle)

    if cmp_length < 0:
        # l < l1: A has the shorter path; clip one child of B.
        if cmp_angle > 0:
            return [("B", "right")]
        if cmp_angle < 0:
            return [("B", "left")]
        return []

    if cmp_length > 0:
        # l1 < l: B has the shorter path; clip one child of A.
        if cmp_angle > 0:
            return [("A", "left")]
        if cmp_angle < 0:
            return [("A", "right")]
        return []

    # l == l1: compare the two angles; one child of each funnel may be clipped.
    if cmp_angle > 0:
        return [("A", "left"), ("B", "right")]
    if cmp_angle < 0:
        return [("A", "right"), ("B", "left")]

    # Equal length and equal angle: Procedure 2 does not specify a deletion.
    return []


def _self_test() -> None:
    # Values are deliberately simple; angle values are in radians.
    tests = [
        ("A shorter, angle A larger", (1.0, 1.2), (2.0, 0.8),
         [("B", "right")]),
        ("A shorter, angle A smaller", (1.0, 0.8), (2.0, 1.2),
         [("B", "left")]),
        ("B shorter, angle A larger", (2.0, 1.2), (1.0, 0.8),
         [("A", "left")]),
        ("B shorter, angle A smaller", (2.0, 0.8), (1.0, 1.2),
         [("A", "right")]),
        ("Equal length, angle A larger", (1.0, 1.2), (1.0, 0.8),
         [("A", "left"), ("B", "right")]),
        ("Equal length, angle A smaller", (1.0, 0.8), (1.0, 1.2),
         [("A", "right"), ("B", "left")]),
        ("Equal length and angle", (1.0, 1.0), (1.0, 1.0), []),
        ("Near-equal values within tolerance", (1.0, 1.0),
         (1.0 + 1e-10, 1.0 - 1e-10), []),
    ]

    print("========== PROCEDURE 2 SELF-TEST ==========")
    failed = 0
    for name, a, b, expected in tests:
        actual = clip_off_funnels(a, b)
        ok = actual == expected
        print(f"{name}: {'PASS' if ok else 'FAIL'} | got={actual}")
        if not ok:
            failed += 1

    print(f"\nTests: {len(tests)} | Passed: {len(tests) - failed} | Failed: {failed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    _self_test()
