#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy; Python stdlib (collections, json, math, pathlib).
"""Check the initial Funnel Tree fan and the first split at START."""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

PI = math.pi
EPS = 1e-10


def dist(V, a, b):
    return float(np.linalg.norm(V[a] - V[b]))


def angle(V, a, b, c):
    """Angle ABC."""
    u = V[a] - V[b]
    v = V[c] - V[b]
    den = float(np.linalg.norm(u) * np.linalg.norm(v))
    if den <= EPS:
        return 0.0
    cosine = float(np.dot(u, v) / den)
    return math.acos(max(-1.0, min(1.0, cosine)))


def angle_sss(opposite, side1, side2):
    if side1 <= EPS or side2 <= EPS:
        return 0.0
    cosine = (
        side1 * side1 + side2 * side2 - opposite * opposite
    ) / (2.0 * side1 * side2)
    return math.acos(max(-1.0, min(1.0, cosine)))


def law_cos_side(a, b, included_angle):
    value = a * a + b * b - 2.0 * a * b * math.cos(included_angle)
    return math.sqrt(max(0.0, value))


def main():
    input_path = Path("generated/funnel_topology_y2p00.npz")
    data = np.load(input_path)

    V = data["vertices"]
    F = data["faces"]
    source = int(data["source_vertex"])

    edge_faces = defaultdict(list)
    for face_id, tri in enumerate(F):
        a, b, c = map(int, tri)
        for u, v in ((a, b), (b, c), (c, a)):
            edge_faces[tuple(sorted((u, v)))].append(face_id)

    # Rotate each oriented face to [p, q, source].
    records = []
    for face_id in data["source_faces"]:
        face_id = int(face_id)
        tri = list(map(int, F[face_id]))
        k = tri.index(source)
        p = tri[(k + 1) % 3]
        q = tri[(k + 2) % 3]
        records.append((face_id, p, q))

    # Order the incident faces into a cycle around START.
    ordered = [records[0]]
    while len(ordered) < len(records):
        last_q = ordered[-1][2]
        candidates = [
            r for r in records
            if r not in ordered and r[1] == last_q
        ]
        if len(candidates) != 1:
            raise RuntimeError(
                f"Cannot order source fan at vertex {last_q}: {candidates}"
            )
        ordered.append(candidates[0])

    if ordered[-1][2] != ordered[0][1]:
        raise RuntimeError("Source fan is not a closed cycle.")

    rows = []
    for face_id, p, q in ordered:
        adjacent = edge_faces[tuple(sorted((p, q)))]
        next_faces = [fi for fi in adjacent if fi != face_id]

        if not next_faces:
            rows.append({
                "root_face": face_id,
                "p": p,
                "q": q,
                "status": "opposite edge is a boundary edge",
            })
            continue

        next_face = next_faces[0]
        v = next(
            int(x) for x in F[next_face]
            if int(x) not in (p, q)
        )

        sp = dist(V, source, p)
        pq = dist(V, p, q)
        vq = dist(V, v, q)

        spq = angle(V, source, p, q)
        psw = angle(V, p, source, q)
        pqv = angle(V, p, q, v)

        pv = law_cos_side(pq, vq, pqv)
        vpq = angle_sss(vq, pv, pq)
        beta = spq + vpq

        if beta < PI:
            sv = law_cos_side(sp, pv, beta)
            psv = angle_sss(pv, sp, sv)
            two_children = psv < psw
        else:
            sv = None
            psv = None
            two_children = False

        rows.append({
            "root_face": face_id,
            "p": p,
            "q": q,
            "next_face": next_face,
            "direct_destination_v": v,
            "beta_degrees": math.degrees(beta),
            "psv_degrees": (
                None if psv is None else math.degrees(psv)
            ),
            "psw_degrees": math.degrees(psw),
            "condition_5_beta_lt_pi": beta < PI,
            "condition_6_psv_lt_psw": two_children,
            "children_expected": 2 if two_children else (
                1 if beta < PI else 0
            ),
        })

    report = {
        "input": str(input_path),
        "source_vertex": source,
        "source_faces": [int(x) for x in data["source_faces"]],
        "ordered_root_fan": [
            {"face": fi, "p": p, "q": q}
            for fi, p, q in ordered
        ],
        "fan_is_closed_cycle": ordered[-1][2] == ordered[0][1],
        "root_checks": rows,
        "expected_first_level_children": sum(
            row.get("children_expected", 0) for row in rows
        ),
        "note": (
            "This checks root initialization and the first split only. "
            "It does not run the full Funnel Tree."
        ),
    }

    out_path = Path("generated/funnel_root_check_y2p00.json")
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("========== FUNNEL ROOT CHECK ==========")
    print("START:", source)
    print("Ordered source fan:")
    for fi, p, q in ordered:
        print(f"  face={fi}, p={p}, q={q}")

    print("\nFirst expansion:")
    for row in rows:
        if "direct_destination_v" not in row:
            print(row)
            continue
        print(
            f"  face {row['root_face']}: "
            f"v={row['direct_destination_v']}, "
            f"beta={row['beta_degrees']:.3f} deg, "
            f"psv={row['psv_degrees']:.3f} deg, "
            f"psw={row['psw_degrees']:.3f} deg, "
            f"children={row['children_expected']}"
        )

    print(
        "\nExpected first-level child funnels:",
        report["expected_first_level_children"]
    )
    print("Saved:", out_path)
    print("NOTE: this is a root check, not the full algorithm.")


if __name__ == "__main__":
    main()
