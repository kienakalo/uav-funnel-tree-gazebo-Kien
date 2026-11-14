# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main libraries: NumPy, trimesh; Python stdlib (collections, csv, pathlib).
import csv
import numpy as np
import trimesh
from collections import defaultdict
from pathlib import Path

CITY = Path("data/input/city.glb")
OUT = Path("generated")
OUT.mkdir(exist_ok=True)

BIN_SIZE = 0.25

scene = trimesh.load(
    CITY,
    force="scene",
    process=False
)

bins = defaultdict(lambda: {
    "faces": 0,
    "area": 0.0,
    "objects": set()
})

object_stats = []

for i, node in enumerate(scene.graph.nodes_geometry):

    transform, name = scene.graph[node]

    mesh = scene.geometry[name].copy()
    mesh.apply_transform(transform)

    mesh.merge_vertices(
        digits_vertex=6,
        merge_tex=False,
        merge_norm=False
    )

    faces = mesh.faces

    valid = (
        (faces[:, 0] != faces[:, 1]) &
        (faces[:, 1] != faces[:, 2]) &
        (faces[:, 2] != faces[:, 0])
    )

    mesh.update_faces(valid)

    canonical = np.sort(mesh.faces, axis=1)
    _, idx = np.unique(
        canonical,
        axis=0,
        return_index=True
    )

    mesh.update_faces(np.sort(idx))
    mesh.remove_unreferenced_vertices()

    normals = mesh.face_normals
    areas = mesh.area_faces
    centers = mesh.triangles_center

    upward = normals[:, 1] > 0.9

    y = centers[upward, 1]
    a = areas[upward]

    for height, area in zip(y, a):

        key = int(np.floor(height / BIN_SIZE))

        bins[key]["faces"] += 1
        bins[key]["area"] += float(area)
        bins[key]["objects"].add(node)

    object_stats.append({
        "object": node,
        "upward_faces": int(upward.sum()),
        "upward_area": float(a.sum()) if len(a) else 0,
        "min_height": float(y.min()) if len(y) else np.nan,
        "max_height": float(y.max()) if len(y) else np.nan
    })

    print(
        f"{i+1}/{len(scene.graph.nodes_geometry)} "
        f"{node}: upward_faces={upward.sum()}",
        flush=True
    )

# Save height distribution

rows = []

for key, value in sorted(bins.items()):

    rows.append({
        "height_min": key * BIN_SIZE,
        "height_max": (key + 1) * BIN_SIZE,
        "face_count": value["faces"],
        "total_area": value["area"],
        "object_count": len(value["objects"])
    })

with open(
    OUT / "city_height_distribution.csv",
    "w",
    newline="",
    encoding="utf-8"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=rows[0].keys()
    )

    writer.writeheader()
    writer.writerows(rows)

# Print results

print("\n========== HEIGHT DISTRIBUTION ==========")

for r in sorted(
    rows,
    key=lambda x: x["total_area"],
    reverse=True
)[:20]:

    print(
        f'Y={r["height_min"]:.2f} - '
        f'{r["height_max"]:.2f} | '
        f'faces={r["face_count"]} | '
        f'area={r["total_area"]:.3f} | '
        f'objects={r["object_count"]}'
    )

print("\n========== OBJECT HEIGHTS ==========")

for r in sorted(
    object_stats,
    key=lambda x: x["upward_area"],
    reverse=True
)[:10]:

    print(r)

print("\nSaved: generated/city_height_distribution.csv")
