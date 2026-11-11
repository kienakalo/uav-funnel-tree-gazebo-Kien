#!/usr/bin/env python3
"""
Build triangle/vertex adjacency for the preprocessed Funnel Tree mesh.

Input:
  generated/funnel_input_y2p00.geom

Outputs:
  generated/funnel_topology_y2p00.npz
  generated/funnel_topology_y2p00_report.json

This is preprocessing only. It does NOT run the Funnel Tree algorithm.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict, Counter, deque
from pathlib import Path

import numpy as np


def read_geom(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("Input .geom file is empty.")

    n_vertices, n_faces, declared_edges = map(int, lines[0].split())

    vertex_lines = lines[1:1 + n_vertices]
    face_lines = lines[1 + n_vertices:1 + n_vertices + n_faces]

    if len(vertex_lines) != n_vertices or len(face_lines) != n_faces:
        raise ValueError("The .geom file has fewer rows than declared in its header.")

    vertices = np.asarray(
        [[float(v) for v in line.split()] for line in vertex_lines],
        dtype=np.float64
    )

    faces = []
    for row_no, line in enumerate(face_lines, start=1):
        values = list(map(int, line.split()))
        if len(values) != 4 or values[0] != 3:
            raise ValueError(f"Face row {row_no} must have format: 3 i j k")
        faces.append(values[1:])

    faces = np.asarray(faces, dtype=np.int64)

    if vertices.shape != (n_vertices, 3):
        raise ValueError(f"Expected {n_vertices} 3D vertices, got {vertices.shape}.")
    if faces.shape != (n_faces, 3):
        raise ValueError(f"Expected {n_faces} triangles, got {faces.shape}.")
    if faces.min() < 0 or faces.max() >= n_vertices:
        raise ValueError("Face index outside valid zero-based vertex range.")

    return vertices, faces, declared_edges


def build_topology(vertices, faces):
    n_vertices = len(vertices)
    n_faces = len(faces)

    edge_to_faces = defaultdict(list)
    vertex_faces = [set() for _ in range(n_vertices)]
    vertex_neighbors = [set() for _ in range(n_vertices)]

    for fi, tri in enumerate(faces):
        a, b, c = map(int, tri)

        for v in (a, b, c):
            vertex_faces[v].add(fi)

        for u, v in ((a, b), (b, c), (c, a)):
            vertex_neighbors[u].add(v)
            vertex_neighbors[v].add(u)
            edge_to_faces[tuple(sorted((u, v)))].append(fi)

    face_adjacency = np.full((n_faces, 3), -1, dtype=np.int64)
    boundary_rows = []
    nonmanifold_edges = []

    for fi, tri in enumerate(faces):
        local_edges = (
            (int(tri[0]), int(tri[1])),
            (int(tri[1]), int(tri[2])),
            (int(tri[2]), int(tri[0])),
        )
        for local_edge_id, (u, v) in enumerate(local_edges):
            incident = edge_to_faces[tuple(sorted((u, v)))]

            if len(incident) == 1:
                boundary_rows.append((u, v, fi, local_edge_id))
            elif len(incident) == 2:
                other = incident[0] if incident[1] == fi else incident[1]
                face_adjacency[fi, local_edge_id] = other
            else:
                face_adjacency[fi, local_edge_id] = -2
                nonmanifold_edges.append(tuple(sorted((u, v))))

    # Face-connected components.
    face_labels = np.full(n_faces, -1, dtype=np.int64)
    component_sizes = []
    component_id = 0

    for start in range(n_faces):
        if face_labels[start] != -1:
            continue

        queue = deque([start])
        face_labels[start] = component_id
        count = 0

        while queue:
            fi = queue.popleft()
            count += 1

            for nb in face_adjacency[fi]:
                if nb >= 0 and face_labels[nb] == -1:
                    face_labels[nb] = component_id
                    queue.append(int(nb))

        component_sizes.append(count)
        component_id += 1

    # Boundary graph and connected boundary loops/chains.
    boundary_graph = defaultdict(set)
    for u, v, _, _ in boundary_rows:
        boundary_graph[u].add(v)
        boundary_graph[v].add(u)

    boundary_degree_counts = Counter(len(nbs) for nbs in boundary_graph.values())
    boundary_components = []
    boundary_seen = set()

    for start in boundary_graph:
        if start in boundary_seen:
            continue

        queue = [start]
        boundary_seen.add(start)
        comp = []

        while queue:
            u = queue.pop()
            comp.append(u)

            for v in boundary_graph[u]:
                if v not in boundary_seen:
                    boundary_seen.add(v)
                    queue.append(v)

        degrees = [len(boundary_graph[v]) for v in comp]
        boundary_components.append({
            "vertices": len(comp),
            "all_degree_two": all(d == 2 for d in degrees),
            "degree_min": min(degrees),
            "degree_max": max(degrees),
        })

    # Sum of incident triangle angles around each vertex, projected to X-Z.
    angle_sums = np.zeros(n_vertices, dtype=np.float64)

    for tri in faces:
        pts = vertices[tri][:, [0, 2]]

        for local_i, vertex_id in enumerate(tri):
            p = pts[local_i]
            q = pts[(local_i + 1) % 3]
            r = pts[(local_i + 2) % 3]

            a = q - p
            b = r - p
            denom = np.linalg.norm(a) * np.linalg.norm(b)

            if denom == 0:
                continue

            cosang = np.clip(np.dot(a, b) / denom, -1.0, 1.0)
            angle_sums[int(vertex_id)] += np.arccos(cosang)

    boundary_vertex_mask = np.zeros(n_vertices, dtype=bool)
    if boundary_graph:
        boundary_vertex_mask[list(boundary_graph.keys())] = True

    return {
        "edge_to_faces": edge_to_faces,
        "face_adjacency": face_adjacency,
        "boundary_rows": np.asarray(boundary_rows, dtype=np.int64).reshape(-1, 4),
        "nonmanifold_edges": nonmanifold_edges,
        "face_labels": face_labels,
        "component_sizes": component_sizes,
        "boundary_graph": boundary_graph,
        "boundary_degree_counts": boundary_degree_counts,
        "boundary_components": boundary_components,
        "vertex_faces": vertex_faces,
        "vertex_neighbors": vertex_neighbors,
        "angle_sums": angle_sums,
        "boundary_vertex_mask": boundary_vertex_mask,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="generated/funnel_input_y2p00.geom")
    parser.add_argument("--source", type=int, default=8236)
    parser.add_argument("--goal", type=int, default=8237)
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path("generated")
    out_dir.mkdir(exist_ok=True)

    vertices, faces, declared_edges = read_geom(input_path)

    if not (0 <= args.source < len(vertices)):
        raise ValueError("Source vertex index is outside the mesh.")
    if not (0 <= args.goal < len(vertices)):
        raise ValueError("Goal vertex index is outside the mesh.")

    topo = build_topology(vertices, faces)
    source_faces = sorted(topo["vertex_faces"][args.source])
    goal_faces = sorted(topo["vertex_faces"][args.goal])

    root_initial_edges = []
    for fi in source_faces:
        tri = list(map(int, faces[fi]))
        opposite = [v for v in tri if v != args.source]

        if len(opposite) != 2:
            raise RuntimeError("Could not identify edge opposite to source.")

        root_initial_edges.append({
            "face": int(fi),
            "edge": opposite
        })

    cross_y = np.cross(
        vertices[faces[:, 1]] - vertices[faces[:, 0]],
        vertices[faces[:, 2]] - vertices[faces[:, 0]]
    )[:, 1]

    orientation = {
        "positive_y_faces": int(np.sum(cross_y > 1e-12)),
        "negative_y_faces": int(np.sum(cross_y < -1e-12)),
        "degenerate_projection_faces": int(np.sum(np.abs(cross_y) <= 1e-12)),
    }

    source_angle = float(topo["angle_sums"][args.source])
    goal_angle = float(topo["angle_sums"][args.goal])

    report = {
        "input": str(input_path),
        "vertices": int(len(vertices)),
        "triangles": int(len(faces)),
        "unique_edges": int(len(topo["edge_to_faces"])),
        "declared_edges_in_header": int(declared_edges),
        "boundary_edges": int(len(topo["boundary_rows"])),
        "nonmanifold_edges": int(len(topo["nonmanifold_edges"])),
        "face_connected_components": int(len(topo["component_sizes"])),
        "face_component_sizes_desc": sorted(
            map(int, topo["component_sizes"]), reverse=True
        ),
        "boundary_vertex_degree_distribution": {
            str(k): int(v)
            for k, v in sorted(topo["boundary_degree_counts"].items())
        },
        "boundary_components": topo["boundary_components"],
        "boundary_loop_count": int(sum(
            item["all_degree_two"] for item in topo["boundary_components"]
        )),
        "orientation_cross_y": orientation,
        "source": {
            "vertex": int(args.source),
            "coordinates": vertices[args.source].tolist(),
            "valence": int(len(topo["vertex_neighbors"][args.source])),
            "incident_faces": source_faces,
            "angle_sum_radians": source_angle,
            "root_initial_funnels": root_initial_edges,
        },
        "goal": {
            "vertex": int(args.goal),
            "coordinates": vertices[args.goal].tolist(),
            "valence": int(len(topo["vertex_neighbors"][args.goal])),
            "incident_faces": goal_faces,
            "angle_sum_radians": goal_angle,
        },
        "face_adjacency_convention": (
            "columns correspond to edges (v0,v1), (v1,v2), (v2,v0); "
            "-1 means boundary, -2 means non-manifold"
        ),
        "status": (
            "Adjacency preprocessing only. This mesh is a planar domain "
            "with boundary loops, not a closed convex polytope. "
            "The paper's Funnel Tree theorem is not automatically certified "
            "for this input."
        ),
    }

    npz_path = out_dir / "funnel_topology_y2p00.npz"

    np.savez_compressed(
        npz_path,
        vertices=vertices,
        faces=faces,
        face_adjacency=topo["face_adjacency"],
        boundary_edges=topo["boundary_rows"][:, :2],
        boundary_edge_faces=topo["boundary_rows"][:, 2],
        face_component_labels=topo["face_labels"],
        vertex_angle_sums=topo["angle_sums"],
        boundary_vertex_mask=topo["boundary_vertex_mask"],
        source_vertex=np.asarray(args.source),
        goal_vertex=np.asarray(args.goal),
        source_faces=np.asarray(source_faces, dtype=np.int64),
        goal_faces=np.asarray(goal_faces, dtype=np.int64),
    )

    json_path = out_dir / "funnel_topology_y2p00_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("========== FUNNEL TOPOLOGY ==========")
    print(f"Vertices: {len(vertices)}")
    print(f"Triangles: {len(faces)}")
    print(f"Unique edges: {len(topo['edge_to_faces'])}")
    print(f"Boundary edges: {len(topo['boundary_rows'])}")
    print(f"Non-manifold edges: {len(topo['nonmanifold_edges'])}")
    print(f"Face-connected components: {len(topo['component_sizes'])}")
    print(f"Boundary loops: {report['boundary_loop_count']}")
    print(
        "Boundary vertex degree distribution:",
        dict(topo["boundary_degree_counts"])
    )
    print("Orientation:", orientation)

    print(f"\nSTART {args.source}:")
    print("  coordinates:", vertices[args.source].tolist())
    print("  valence:", len(topo["vertex_neighbors"][args.source]))
    print("  incident faces:", source_faces)
    print("  angle sum:", f"{source_angle:.12f} rad")
    print("  root initial funnels:")

    for item in root_initial_edges:
        print(f"    face {item['face']}, opposite edge {item['edge']}")

    print(f"\nGOAL {args.goal}:")
    print("  coordinates:", vertices[args.goal].tolist())
    print("  valence:", len(topo["vertex_neighbors"][args.goal]))
    print("  incident faces:", goal_faces)
    print("  angle sum:", f"{goal_angle:.12f} rad")

    print("\nSaved:", npz_path)
    print("Saved:", json_path)
    print("NOTE: preprocessing only; Funnel Tree has not run.")


if __name__ == "__main__":
    main()
