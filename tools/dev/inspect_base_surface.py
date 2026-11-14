# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Matplotlib, NumPy, trimesh; Python stdlib (csv, pathlib).
import csv
import numpy as np
import trimesh
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from matplotlib.collections import PolyCollection
from pathlib import Path

CITY = Path("data/input/city.glb")
OUT = Path("generated")
OUT.mkdir(exist_ok=True)

Y_MIN = 0.75
Y_MAX = 1.00


def connected_components(faces, areas):
    n = len(faces)

    if n == 0:
        return []

    edges = np.concatenate([
        faces[:, [0, 1]],
        faces[:, [1, 2]],
        faces[:, [2, 0]]
    ])

    face_ids = np.tile(
        np.arange(n, dtype=np.int32), 3
    )

    edges.sort(axis=1)

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

    for s, e in zip(starts, ends):
        if e - s > 1:
            first = face_ids[s]
            for j in range(s + 1, e):
                union(first, face_ids[j])

    roots = np.array([find(i) for i in range(n)])
    _, labels = np.unique(roots, return_inverse=True)

    k = labels.max() + 1

    face_counts = np.bincount(labels, minlength=k)
    component_areas = np.bincount(
        labels, weights=areas, minlength=k
    )

    edge_labels = labels[face_ids[starts]]

    boundary = np.bincount(
        edge_labels[counts == 1], minlength=k
    )

    nonmanifold = np.bincount(
        edge_labels[counts > 2], minlength=k
    )

    return [
        {
            "label": i,
            "faces": int(face_counts[i]),
            "area": float(component_areas[i]),
            "boundary_edges": int(boundary[i]),
            "nonmanifold_edges": int(nonmanifold[i])
        }
        for i in range(k)
    ], labels


scene = trimesh.load(
    CITY, force="scene", process=False
)

object_rows = []
component_rows = []

preview = trimesh.Scene()

all_polygons = []
all_centers = []
all_object_ids = []

total_faces = 0
total_area = 0

for object_index, node in enumerate(
    scene.graph.nodes_geometry
):

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
        canonical, axis=0, return_index=True
    )

    mesh.update_faces(np.sort(idx))
    mesh.remove_unreferenced_vertices()

    centers = mesh.triangles_center
    normals = mesh.face_normals
    areas = mesh.area_faces

    selected = (
        (normals[:, 1] > 0.9) &
        (centers[:, 1] >= Y_MIN) &
        (centers[:, 1] < Y_MAX)
    )

    if not selected.any():
        continue

    selected_faces = mesh.faces[selected]
    selected_areas = areas[selected]
    selected_centers = centers[selected]

    stats, labels = connected_components(
        selected_faces, selected_areas
    )

    stats.sort(key=lambda x: x["area"], reverse=True)

    total_faces += len(selected_faces)
    total_area += selected_areas.sum()

    object_rows.append({
        "object": node,
        "faces": len(selected_faces),
        "area": float(selected_areas.sum()),
        "components": len(stats),
        "largest_component_faces": stats[0]["faces"],
        "largest_component_area": stats[0]["area"],
        "largest_boundary_edges": stats[0]["boundary_edges"],
        "largest_nonmanifold_edges": stats[0]["nonmanifold_edges"]
    })

    for item in stats:
        component_rows.append({
            "object": node,
            **item
        })

    # Export selected faces without duplicating unused vertices.
    used, inverse = np.unique(
        selected_faces, return_inverse=True
    )

    compact_faces = inverse.reshape(-1, 3)

    part = trimesh.Trimesh(
        vertices=mesh.vertices[used].copy(),
        faces=compact_faces,
        process=False
    )

    part.visual.face_colors = [70, 160, 220, 255]

    preview.add_geometry(
        part,
        geom_name=node,
        node_name=node
    )

    triangles = mesh.vertices[selected_faces]

    all_polygons.append(triangles[:, :, [0, 2]])
    all_centers.append(selected_centers)
    all_object_ids.append(
        np.full(len(selected_faces), object_index)
    )

    print(
        f"{node}: faces={len(selected_faces)}, "
        f"components={len(stats)}, "
        f"largest={stats[0]['faces']}",
        flush=True
    )


# Save object statistics.
object_rows.sort(
    key=lambda x: x["area"], reverse=True
)

with open(
    OUT / "base_surface_objects.csv",
    "w", newline="", encoding="utf-8"
) as f:

    writer = csv.DictWriter(
        f, fieldnames=object_rows[0].keys()
    )
    writer.writeheader()
    writer.writerows(object_rows)


# Save component statistics.
component_rows.sort(
    key=lambda x: x["area"], reverse=True
)

with open(
    OUT / "base_surface_components.csv",
    "w", newline="", encoding="utf-8"
) as f:

    writer = csv.DictWriter(
        f, fieldnames=component_rows[0].keys()
    )
    writer.writeheader()
    writer.writerows(component_rows)


# Export selected surface.
preview.export(
    OUT / "city_base_surface.glb"
)


# Top-view visualization.
polygons = np.concatenate(all_polygons)
centers = np.vstack(all_centers)
object_ids = np.concatenate(all_object_ids)

fig, ax = plt.subplots(figsize=(12, 10))

pc = PolyCollection(
    polygons,
    array=object_ids,
    cmap="tab20",
    edgecolors="none",
    rasterized=True
)

ax.add_collection(pc)
ax.autoscale_view()
ax.set_aspect("equal")

ax.set_xlabel("X")
ax.set_ylabel("Z")
ax.set_title("Upward surface candidates: Y = 0.75 to 1.00")

fig.colorbar(
    pc, ax=ax, label="Object index"
)

fig.tight_layout()

fig.savefig(
    OUT / "base_surface_top.png",
    dpi=150
)

plt.close(fig)


print("\n========== BASE SURFACE SUMMARY ==========")
print("Selected faces:", total_faces)
print("Total area:", round(float(total_area), 3))
print("Objects:", len(object_rows))
print("Components:", len(component_rows))

print("\nTOP 15 COMPONENTS:")

for r in component_rows[:15]:
    print(
        f'{r["object"]}/{r["label"]}: '
        f'faces={r["faces"]}, '
        f'area={r["area"]:.3f}, '
        f'boundary={r["boundary_edges"]}, '
        f'nonmanifold={r["nonmanifold_edges"]}'
    )

print("\nSaved files in generated/")
