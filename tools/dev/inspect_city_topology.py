# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Matplotlib, NumPy, trimesh; Python stdlib (csv, pathlib).
from pathlib import Path
import csv
import numpy as np
import trimesh
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

CITY = Path("data/source/city.glb")
OUT = Path("generated")

OUT.mkdir(exist_ok=True)


def topology(mesh):
    faces = mesh.faces
    n = len(faces)

    edges = np.concatenate([
        faces[:, [0, 1]],
        faces[:, [1, 2]],
        faces[:, [2, 0]]
    ])

    edges = np.sort(edges, axis=1)
    face_ids = np.tile(np.arange(n, dtype=np.int32), 3)

    order = np.lexsort((edges[:, 1], edges[:, 0]))

    edges = edges[order]
    face_ids = face_ids[order]

    mask = np.ones(len(edges), dtype=bool)
    mask[1:] = np.any(edges[1:] != edges[:-1], axis=1)

    starts = np.flatnonzero(mask)
    ends = np.r_[starts[1:], len(edges)]
    counts = ends - starts

    parent = np.arange(n, dtype=np.int32)
    size = np.ones(n, dtype=np.int32)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        a, b = find(a), find(b)

        if a == b:
            return

        if size[a] < size[b]:
            a, b = b, a

        parent[b] = a
        size[a] += size[b]

    for start, end in zip(starts, ends):
        if end - start > 1:
            first = face_ids[start]

            for j in range(start + 1, end):
                union(first, face_ids[j])

    roots = np.array([find(i) for i in range(n)])
    _, component_sizes = np.unique(
        roots, return_counts=True
    )

    return {
        "components": len(component_sizes),
        "largest_component": int(component_sizes.max()),
        "boundary_edges": int(np.sum(counts == 1)),
        "nonmanifold_edges": int(np.sum(counts > 2))
    }


scene = trimesh.load(CITY, force="scene", process=False)

rows = []
polygons = []
heights = []
upward_centroids = []

for node in scene.graph.nodes_geometry:

    transform, name = scene.graph[node]

    mesh = scene.geometry[name].copy()
    mesh.apply_transform(transform)

    stats = topology(mesh)

    upward = mesh.face_normals[:, 1] > 0.9

    triangles = mesh.vertices[mesh.faces]

    polygons.append(triangles[:, :, [0, 2]])
    heights.append(triangles[:, :, 1].mean(axis=1))

    if upward.any():
        upward_centroids.append(
            mesh.triangles_center[upward]
        )

    rows.append({
        "object": node,
        "triangles": len(mesh.faces),
        **stats,
        "upward_faces": int(upward.sum())
    })


# Save topology report

with open(
    OUT / "city_topology_report.csv",
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


# Figure 1: Top view colored by height

polygons = np.concatenate(polygons)
heights = np.concatenate(heights)

fig, ax = plt.subplots(figsize=(12, 10))

pc = PolyCollection(
    polygons,
    array=heights,
    cmap="viridis",
    edgecolors="none",
    rasterized=True
)

ax.add_collection(pc)
ax.autoscale_view()
ax.set_aspect("equal")

ax.set_xlabel("X")
ax.set_ylabel("Z")
ax.set_title("City top view - color represents Y height")

fig.colorbar(pc, ax=ax, label="Y height")
fig.tight_layout()

fig.savefig(
    OUT / "city_top_height.png",
    dpi=160
)

plt.close(fig)


# Figure 2: Upward-facing surfaces

centroids = np.vstack(upward_centroids)

fig, ax = plt.subplots(figsize=(12, 10))

sc = ax.scatter(
    centroids[:, 0],
    centroids[:, 2],
    c=centroids[:, 1],
    s=1,
    cmap="viridis",
    rasterized=True
)

ax.set_aspect("equal")
ax.set_xlabel("X")
ax.set_ylabel("Z")
ax.set_title("Upward-facing surfaces")

fig.colorbar(sc, ax=ax, label="Y height")
fig.tight_layout()

fig.savefig(
    OUT / "city_upward_faces.png",
    dpi=160
)

plt.close(fig)


print("\n========== TOPOLOGY ANALYSIS ==========")

for r in sorted(
    rows,
    key=lambda x: x["largest_component"],
    reverse=True
)[:10]:

    print(
        f'{r["object"]}: '
        f'components={r["components"]}, '
        f'largest={r["largest_component"]}, '
        f'boundary={r["boundary_edges"]}, '
        f'nonmanifold={r["nonmanifold_edges"]}'
    )

print("\nSaved reports and images in generated/")
