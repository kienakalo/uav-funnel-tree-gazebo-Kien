#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main libraries: NumPy, Shapely; Python stdlib (collections, json, pathlib).
"""
Build and validate only the first child level of the Funnel Tree.

Inputs:
  generated/funnel_topology_y2p00.npz
  generated/funnel_root_check_y2p00.json

Output:
  generated/funnel_level1_y2p00.json

This script is deliberately limited to the first expansion from START.
It does NOT implement recursive expansion or Procedure 2 (clipping).
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

try:
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union
except ImportError as exc:
    raise SystemExit(
        "Shapely is required. Install it in the active .venv with: "
        "python -m pip install shapely"
    ) from exc


TOL = 1e-8


def edge_key(a: int, b: int):
    return tuple(sorted((int(a), int(b))))


def main():
    topology_path = Path("generated/funnel_topology_y2p00.npz")
    root_check_path = Path("generated/funnel_root_check_y2p00.json")

    if not topology_path.exists():
        raise FileNotFoundError(f"Missing input: {topology_path}")
    if not root_check_path.exists():
        raise FileNotFoundError(f"Missing input: {root_check_path}")

    data = np.load(topology_path)
    root_check = json.loads(root_check_path.read_text(encoding="utf-8"))

    vertices = data["vertices"]
    faces = data["faces"]
    source = int(data["source_vertex"])

    # This project currently uses a horizontal X-Z navigation surface.
    points_2d = vertices[:, [0, 2]]

    edge_to_faces = defaultdict(list)
    for face_id, tri in enumerate(faces):
        a, b, c = map(int, tri)
        for u, v in ((a, b), (b, c), (c, a)):
            edge_to_faces[edge_key(u, v)].append(int(face_id))

    result = {
        "input_mesh": str(topology_path),
        "source_vertex": source,
        "level": 1,
        "roots": [],
        "children": [],
        "summary": {},
        "status": (
            "First-level expansion only. Recursive Funnel Tree expansion "
            "and Procedure 2 clipping are not implemented in this script."
        ),
    }

    for root_index, row in enumerate(root_check["root_checks"]):
        root_face = int(row["root_face"])
        p = int(row["p"])
        q = int(row["q"])
        v = int(row["direct_destination_v"])
        next_face = int(row["next_face"])

        beta_ok = bool(row["condition_5_beta_lt_pi"])
        split_ok = bool(row["condition_6_psv_lt_psw"])

        # Confirm the two triangles share the expected edge [p,q].
        shared = edge_key(p, q)
        if root_face not in edge_to_faces[shared]:
            raise RuntimeError(
                f"Root face {root_face} does not contain edge {shared}."
            )
        if next_face not in edge_to_faces[shared]:
            raise RuntimeError(
                f"Next face {next_face} does not contain edge {shared}."
            )

        # S' = S union triangle pqv. Here S initially contains root_face.
        s_faces = [root_face, next_face]
        triangle_polygons = [
            Polygon(points_2d[faces[fi]])
            for fi in s_faces
        ]
        region = unary_union(triangle_polygons)

        path_sv = LineString([
            points_2d[source],
            points_2d[v],
        ])
        same_cusp = bool(region.buffer(TOL).covers(path_sv))

        root_record = {
            "root_id": f"R{root_index}",
            "root_face": root_face,
            "p": p,
            "q": q,
            "direct_destination_v": v,
            "next_face": next_face,
            "S_prime_faces": s_faces,
            "beta_degrees": float(row["beta_degrees"]),
            "condition_5_beta_lt_pi": beta_ok,
            "condition_6_psv_lt_psw": split_ok,
            "same_cusp_segment_sv_inside_S_prime": same_cusp,
        }
        result["roots"].append(root_record)

        if not beta_ok:
            root_record["children_created"] = 0
            root_record["reason"] = "beta_v >= pi"
            continue

        if not same_cusp:
            root_record["children_created"] = 0
            root_record["reason"] = (
                "The straight segment s-v is not contained in S'. "
                "The same-cusp condition needs a more general path check."
            )
            continue

        if split_ok:
            child_pairs = [
                (p, v, "F_p_v"),
                (v, q, "F_v_q"),
            ]
        else:
            # Article: if condition (6) does not hold, the one child is F_{v,p}.
            child_pairs = [
                (v, p, "F_v_p"),
            ]

        created_for_root = 0

        for child_index, (a, b, notation) in enumerate(child_pairs):
            child_edge = edge_key(a, b)
            incident = edge_to_faces[child_edge]
            inside_faces = [fi for fi in incident if fi in s_faces]
            outside_faces = [fi for fi in incident if fi not in s_faces]

            if len(inside_faces) != 1:
                boundary_status = (
                    "Could not identify exactly one S' face incident "
                    "to the child boundary edge."
                )
                next_child_face = None
                next_destination = None
            elif len(outside_faces) == 0:
                boundary_status = (
                    "No outside adjacent face: this edge is a mesh boundary "
                    "or the sequence cannot be extended."
                )
                next_child_face = None
                next_destination = None
            elif len(outside_faces) == 1:
                next_child_face = int(outside_faces[0])
                third_vertices = [
                    int(x) for x in faces[next_child_face]
                    if int(x) not in child_edge
                ]
                if len(third_vertices) != 1:
                    raise RuntimeError(
                        f"Cannot find third vertex for face {next_child_face}."
                    )
                next_destination = third_vertices[0]
                boundary_status = "One next face found across child edge."
            else:
                boundary_status = (
                    "More than one outside face found; inspect topology."
                )
                next_child_face = None
                next_destination = None

            child = {
                "child_id": f"{root_record['root_id']}_C{child_index}",
                "parent_root_id": root_record["root_id"],
                "notation": notation,
                "p": int(a),
                "q": int(b),
                "cusp": source,
                "S_faces": s_faces,
                "boundary_edge": [int(a), int(b)],
                "next_face_candidate": next_child_face,
                "next_direct_destination_candidate": next_destination,
                "extension_status": boundary_status,
            }
            result["children"].append(child)
            created_for_root += 1

        root_record["children_created"] = created_for_root

    result["summary"] = {
        "root_count": len(result["roots"]),
        "roots_with_beta_less_than_pi": sum(
            r["condition_5_beta_lt_pi"] for r in result["roots"]
        ),
        "roots_passing_same_cusp_check": sum(
            r["same_cusp_segment_sv_inside_S_prime"] for r in result["roots"]
        ),
        "children_created": len(result["children"]),
        "children_with_next_face_candidate": sum(
            c["next_face_candidate"] is not None for c in result["children"]
        ),
    }

    output_path = Path("generated/funnel_level1_y2p00.json")
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("========== FUNNEL LEVEL 1 ==========")
    print("Source:", source)
    print("Root funnels:", result["summary"]["root_count"])
    print(
        "Roots passing beta < pi:",
        result["summary"]["roots_with_beta_less_than_pi"]
    )
    print(
        "Roots passing same-cusp segment check:",
        result["summary"]["roots_passing_same_cusp_check"]
    )
    print("Children created:", result["summary"]["children_created"])
    print(
        "Children with a next-face candidate:",
        result["summary"]["children_with_next_face_candidate"]
    )

    for root in result["roots"]:
        print(
            f"\n{root['root_id']}: face={root['root_face']}, "
            f"(p,q,v)=({root['p']},{root['q']},"
            f"{root['direct_destination_v']}), "
            f"children={root['children_created']}"
        )

    for child in result["children"]:
        print(
            f"  {child['child_id']} {child['notation']}: "
            f"edge={child['boundary_edge']}, "
            f"next_face={child['next_face_candidate']}, "
            f"next_v={child['next_direct_destination_candidate']}"
        )

    print("\nSaved:", output_path)
    print("NOTE: first-level test only; no recursive expansion or clipping.")


if __name__ == "__main__":
    main()
