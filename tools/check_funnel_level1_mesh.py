#!/usr/bin/env python3
"""Mesh adjacency helpers and a validation check for Funnel Tree level 1.

Run from the project root:
    python tools/check_funnel_level1_mesh.py

Inputs:
    generated/funnel_topology_y2p00.npz
    generated/funnel_level1_y2p00.json

This is a topology validation step only. It does not expand the Funnel Tree.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np


class Mesh:
    def __init__(self, vertices: np.ndarray, faces: np.ndarray):
        self.vertices = np.asarray(vertices, dtype=np.float64)
        self.faces = np.asarray(faces, dtype=np.int64)

        if self.vertices.ndim != 2 or self.vertices.shape[1] != 3:
            raise ValueError("vertices must have shape (N, 3)")
        if self.faces.ndim != 2 or self.faces.shape[1] != 3:
            raise ValueError("faces must have shape (M, 3)")
        if self.faces.min() < 0 or self.faces.max() >= len(self.vertices):
            raise ValueError("Face index outside vertex array")

        self.edge_to_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
        self.vertex_to_faces: list[list[int]] = [
            [] for _ in range(len(self.vertices))
        ]

        for face_id, tri in enumerate(self.faces):
            a, b, c = map(int, tri)

            for vertex_id in (a, b, c):
                self.vertex_to_faces[vertex_id].append(face_id)

            for u, v in ((a, b), (b, c), (c, a)):
                self.edge_to_faces[self.edge_key(u, v)].append(face_id)

    @staticmethod
    def edge_key(u: int, v: int) -> tuple[int, int]:
        return (u, v) if u < v else (v, u)

    def incident_faces(self, u: int, v: int) -> list[int]:
        return self.edge_to_faces.get(self.edge_key(u, v), [])

    def other_face(self, u: int, v: int, current_face: int) -> int | None:
        """Return the face across edge (u,v); None means a mesh boundary."""
        incident = self.incident_faces(u, v)

        if current_face not in incident:
            raise ValueError(
                f"Face {current_face} is not incident to edge ({u}, {v})"
            )

        if len(incident) == 1:
            return None
        if len(incident) != 2:
            raise ValueError(
                f"Non-manifold edge ({u}, {v}) has {len(incident)} incident faces"
            )

        return incident[0] if incident[1] == current_face else incident[1]

    def third_vertex(self, face_id: int, u: int, v: int) -> int:
        tri = list(map(int, self.faces[face_id]))

        if u not in tri or v not in tri:
            raise ValueError(
                f"Face {face_id} does not contain both edge endpoints {u}, {v}"
            )

        remaining = [x for x in tri if x != u and x != v]
        if len(remaining) != 1:
            raise ValueError(f"Cannot identify third vertex in face {face_id}")

        return remaining[0]

    def dist(self, a: int, b: int) -> float:
        return float(np.linalg.norm(self.vertices[a] - self.vertices[b]))

    def angle(self, a: int, b: int, c: int) -> float:
        """Return angle ABC in radians."""
        ba = self.vertices[a] - self.vertices[b]
        bc = self.vertices[c] - self.vertices[b]
        denom = float(np.linalg.norm(ba) * np.linalg.norm(bc))

        if denom <= 1e-14:
            raise ValueError(f"Degenerate angle at vertex {b}")

        cosine = float(np.dot(ba, bc) / denom)
        return float(np.arccos(np.clip(cosine, -1.0, 1.0)))


def main() -> None:
    topology_path = Path("generated/funnel_topology_y2p00.npz")
    level_path = Path("generated/funnel_level1_y2p00.json")

    if not topology_path.exists():
        raise FileNotFoundError(f"Missing {topology_path}")
    if not level_path.exists():
        raise FileNotFoundError(f"Missing {level_path}")

    data = np.load(topology_path)
    level = json.loads(level_path.read_text(encoding="utf-8"))

    required = {
        "vertices", "faces", "source_vertex", "goal_vertex",
        "face_adjacency", "boundary_edges"
    }
    missing = required.difference(data.files)
    if missing:
        raise ValueError(f"NPZ is missing keys: {sorted(missing)}")

    mesh = Mesh(data["vertices"], data["faces"])
    source = int(data["source_vertex"])
    goal = int(data["goal_vertex"])

    print("========== MESH ADJACENCY CHECK ==========")
    print(f"Vertices: {len(mesh.vertices):,}")
    print(f"Triangles: {len(mesh.faces):,}")
    print(f"Unique edges: {len(mesh.edge_to_faces):,}")
    print(f"Boundary edges: {sum(len(x) == 1 for x in mesh.edge_to_faces.values()):,}")
    print(f"Non-manifold edges: {sum(len(x) > 2 for x in mesh.edge_to_faces.values()):,}")
    print(f"START: {source}; GOAL: {goal}")

    if source != 8236 or goal != 8237:
        print("WARNING: source/goal differ from the currently planned pair 8236 -> 8237.")

    children = level.get("children", [])
    passed = 0

    print("\n========== LEVEL-1 CHILD CHECK ==========")

    for child in children:
        child_id = child["child_id"]
        u, v = map(int, child["boundary_edge"])
        inside_faces = set(map(int, child["S_faces"]))
        expected_face = child.get("next_face_candidate")
        expected_vertex = child.get("next_direct_destination_candidate")

        incident = mesh.incident_faces(u, v)
        inside = [fi for fi in incident if fi in inside_faces]
        outside = [fi for fi in incident if fi not in inside_faces]

        ok = (
            len(incident) == 2
            and len(inside) == 1
            and len(outside) == 1
            and expected_face is not None
            and int(expected_face) == outside[0]
        )

        actual_vertex = None
        if len(outside) == 1:
            actual_vertex = mesh.third_vertex(outside[0], u, v)
            ok = ok and expected_vertex is not None
            if expected_vertex is not None:
                ok = ok and actual_vertex == int(expected_vertex)

        status = "PASS" if ok else "FAIL"
        print(
            f"{child_id}: edge=({u},{v}), incident={incident}, "
            f"next_face={expected_face}, "
            f"next_vertex={actual_vertex} -> {status}"
        )

        if ok:
            passed += 1

    print("\n========== SUMMARY ==========")
    print(f"Children checked: {len(children)}")
    print(f"Passed: {passed}")
    print(f"Failed: {len(children) - passed}")

    if passed != len(children):
        raise SystemExit(
            "Topology validation failed. Do not start recursive expansion yet."
        )

    print("\nAll level-1 child edge/face relationships are consistent.")
    print("NOTE: this validates adjacency only, not shortest-path correctness.")


if __name__ == "__main__":
    main()
