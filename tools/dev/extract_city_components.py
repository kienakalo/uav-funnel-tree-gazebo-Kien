# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Matplotlib, mpl_toolkits, NumPy, trimesh; Python stdlib (csv, pathlib).
from pathlib import Path
import csv
import numpy as np
import trimesh
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

CITY = Path("data/input/city.glb")
OUT = Path("generated")
OUT.mkdir(exist_ok=True)

scene = trimesh.load(CITY, force="scene", process=False)

components = []

for node in scene.graph.nodes_geometry:
    transform, name = scene.graph[node]

    mesh = scene.geometry[name].copy()
    mesh.apply_transform(transform)

    # Merge coincident vertices on an analysis copy.
    mesh.merge_vertices(
        digits_vertex=6,
        merge_tex=False,
        merge_norm=False
    )

    # Remove degenerate faces.
    faces = mesh.faces

    valid = (
        (faces[:, 0] != faces[:, 1]) &
        (faces[:, 1] != faces[:, 2]) &
        (faces[:, 2] != faces[:, 0])
    )

    mesh.update_faces(valid)

    # Remove duplicate triangles.
    canonical = np.sort(mesh.faces, axis=1)
    _, indices = np.unique(
        canonical, axis=0, return_index=True
    )

    mesh.update_faces(np.sort(indices))
    mesh.remove_unreferenced_vertices()

    # Split into edge-connected components.
    parts = mesh.split(only_watertight=False)

    for component_id, part in enumerate(parts):
        if len(part.faces) == 0:
            continue

        normals = part.face_normals
        areas = part.area_faces

        edge_counts = np.bincount(
            part.edges_unique_inverse,
            minlength=len(part.edges_unique)
        )

        boundary = int(np.sum(edge_counts == 1))
        nonmanifold = int(np.sum(edge_counts > 2))

        up_area = areas[normals[:, 1] > 0.9].sum()
        down_area = areas[normals[:, 1] < -0.9].sum()
        horizontal_area = areas[
            np.abs(normals[:, 1]) > 0.9
        ].sum()

        total_area = areas.sum()

        row = {
            "object": node,
            "component_id": component_id,
            "vertices": len(part.vertices),
            "triangles": len(part.faces),
            "area": total_area,
            "boundary_edges": boundary,
            "nonmanifold_edges": nonmanifold,
            "upward_area_percent": (
                up_area / total_area * 100
                if total_area else 0
            ),
            "downward_area_percent": (
                down_area / total_area * 100
                if total_area else 0
            ),
            "horizontal_area_percent": (
                horizontal_area / total_area * 100
                if total_area else 0
            ),
            "min_x": part.bounds[0, 0],
            "min_y": part.bounds[0, 1],
            "min_z": part.bounds[0, 2],
            "max_x": part.bounds[1, 0],
            "max_y": part.bounds[1, 1],
            "max_z": part.bounds[1, 2],
        }

        components.append((row, part.copy()))


# Save all components to CSV.
components.sort(
    key=lambda x: x[0]["area"],
    reverse=True
)

csv_path = OUT / "city_components_report.csv"

with csv_path.open(
    "w", newline="", encoding="utf-8"
) as f:
    writer = csv.DictWriter(
        f, fieldnames=components[0][0].keys()
    )
    writer.writeheader()

    for row, part in components:
        writer.writerow(row)


# Select top components by area and triangle count.
top_area = components[:12]

top_faces = sorted(
    components,
    key=lambda x: x[0]["triangles"],
    reverse=True
)[:12]

selected = {}

for row, part in top_area + top_faces:
    key = (row["object"], row["component_id"])
    selected[key] = (row, part)


# Export selected components into a separate GLB.
preview_scene = trimesh.Scene()

for i, (row, part) in enumerate(selected.values()):
    normals = part.face_normals

    colors = np.tile(
        [150, 150, 150, 255],
        (len(part.faces), 1)
    )

    colors[normals[:, 1] > 0.9] = [50, 150, 240, 255]
    colors[normals[:, 1] < -0.9] = [240, 150, 60, 255]

    part.visual.face_colors = colors

    preview_scene.add_geometry(
        part,
        geom_name=f"component_{i}",
        node_name=f"component_{i}"
    )

preview_scene.export(
    OUT / "city_top_components.glb"
)


# Top view, colored by height.
fig, ax = plt.subplots(figsize=(12, 10))

all_vertices = np.vstack([
    part.vertices for _, part in selected.values()
])

y_min = all_vertices[:, 1].min()
y_max = all_vertices[:, 1].max()

cmap = plt.get_cmap("viridis")
norm = plt.Normalize(y_min, y_max)

for row, part in selected.values():
    triangles = part.triangles

    colors = cmap(
        norm(triangles[:, :, 1].mean(axis=1))
    )

    pc = PolyCollection(
        triangles[:, :, [0, 2]],
        facecolors=colors,
        edgecolors="none"
    )

    ax.add_collection(pc)

ax.autoscale_view()
ax.set_aspect("equal")
ax.set_xlabel("X")
ax.set_ylabel("Z")
ax.set_title("Largest connected city components")

fig.colorbar(
    plt.cm.ScalarMappable(norm=norm, cmap=cmap),
    ax=ax,
    label="Y height"
)

fig.savefig(
    OUT / "city_components_top.png",
    dpi=160
)

plt.close(fig)


# 3D view of the eight largest components by area.
fig = plt.figure(figsize=(12, 9))
ax = fig.add_subplot(111, projection="3d")

for row, part in top_area[:8]:
    triangles = part.triangles

    colors = cmap(
        norm(triangles[:, :, 1].mean(axis=1))
    )

    pc = Poly3DCollection(
        triangles[:, :, [0, 2, 1]],
        facecolors=colors,
        edgecolors="none"
    )

    ax.add_collection3d(pc)

xyz = all_vertices[:, [0, 2, 1]]

ax.auto_scale_xyz(
    xyz[:, 0], xyz[:, 1], xyz[:, 2]
)

ax.set_xlabel("X")
ax.set_ylabel("Z")
ax.set_zlabel("Y")
ax.set_title("3D view - largest connected components")

fig.savefig(
    OUT / "city_components_3d.png",
    dpi=160
)

plt.close(fig)


print("\n========== COMPONENT EXTRACTION ==========")
print("Total connected components:", len(components))
print("Selected for visualization:", len(selected))

print("\nTOP 15 COMPONENTS BY AREA:")

for row, _ in components[:15]:
    print(
        f'{row["object"]} / {row["component_id"]}: '
        f'faces={row["triangles"]}, '
        f'area={row["area"]:.3f}, '
        f'upward={row["upward_area_percent"]:.1f}%, '
        f'boundary={row["boundary_edges"]}, '
        f'nonmanifold={row["nonmanifold_edges"]}'
    )

print("\nSaved files:")
print("generated/city_components_report.csv")
print("generated/city_top_components.glb")
print("generated/city_components_top.png")
print("generated/city_components_3d.png")
