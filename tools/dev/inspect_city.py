# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy, trimesh; Python stdlib (csv, pathlib).
from pathlib import Path
import csv
import numpy as np
import trimesh

CITY = Path("data/input/city.glb")
OUT = Path("generated/city_mesh_report.csv")

if not CITY.exists():
    raise FileNotFoundError(CITY)

scene = trimesh.load(CITY, force="scene", process=False)

rows = []
total_v = 0
total_f = 0
total_boundary = 0
total_nonmanifold = 0
watertight = 0
upward = 0

for node in scene.graph.nodes_geometry:
    transform, geom_name = scene.graph[node]

    mesh = scene.geometry[geom_name].copy()
    mesh.apply_transform(transform)

    v = len(mesh.vertices)
    f = len(mesh.faces)

    edge_count = np.bincount(
        mesh.edges_unique_inverse,
        minlength=len(mesh.edges_unique)
    )

    boundary = int(np.sum(edge_count == 1))
    nonmanifold = int(np.sum(edge_count > 2))

    up = int(np.sum(mesh.face_normals[:, 1] > 0.9))

    total_v += v
    total_f += f
    total_boundary += boundary
    total_nonmanifold += nonmanifold
    watertight += int(mesh.is_watertight)
    upward += up

    rows.append({
        "object": node,
        "vertices": v,
        "triangles": f,
        "watertight": mesh.is_watertight,
        "boundary_edges": boundary,
        "nonmanifold_edges": nonmanifold,
        "upward_faces": up,
        "min_x": mesh.bounds[0, 0],
        "min_y": mesh.bounds[0, 1],
        "min_z": mesh.bounds[0, 2],
        "max_x": mesh.bounds[1, 0],
        "max_y": mesh.bounds[1, 1],
        "max_z": mesh.bounds[1, 2],
    })

OUT.parent.mkdir(exist_ok=True)

with OUT.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print("\n========== CITY INSPECTION ==========")
print("Mesh objects:", len(rows))
print("Vertices:", f"{total_v:,}")
print("Triangles:", f"{total_f:,}")
print("Watertight objects:", watertight)
print("Boundary edges:", f"{total_boundary:,}")
print("Non-manifold edges:", f"{total_nonmanifold:,}")
print("Faces facing upward (+Y):", f"{upward:,}")

print("\n10 objects with most triangles:")

for r in sorted(
    rows, key=lambda x: x["triangles"], reverse=True
)[:10]:
    print(
        r["object"],
        "| triangles:", r["triangles"],
        "| watertight:", r["watertight"],
        "| boundary:", r["boundary_edges"]
    )

print("\nSaved report:", OUT)
