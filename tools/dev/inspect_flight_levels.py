import trimesh
import numpy as np
import csv

from pathlib import Path

CITY = Path("data/input/city.glb")
OUT = Path("generated")
OUT.mkdir(exist_ok=True)

scene = trimesh.load(
    CITY, force="scene", process=False
)

objects = []
levels = np.arange(0.5, 5.51, 0.5)

for i, node in enumerate(scene.graph.nodes_geometry):

    transform, name = scene.graph[node]

    mesh = scene.geometry[name].copy()
    mesh.apply_transform(transform)

    bounds = mesh.bounds
    y_min, y_max = bounds[:, 1]

    triangles_y = mesh.triangles[:, :, 1]

    tri_min = triangles_y.min(axis=1)
    tri_max = triangles_y.max(axis=1)

    row = {
        "object": node,
        "faces": len(mesh.faces),
        "y_min": float(y_min),
        "y_max": float(y_max),
        "x_min": float(bounds[0, 0]),
        "x_max": float(bounds[1, 0]),
        "z_min": float(bounds[0, 2]),
        "z_max": float(bounds[1, 2])
    }

    objects.append(row)

    print(
        f"{i+1}/{len(scene.graph.nodes_geometry)} "
        f"{node}: Y={y_min:.3f} -> {y_max:.3f}",
        flush=True
    )

with open(
    OUT / "city_object_height_bounds.csv",
    "w", newline="", encoding="utf-8"
) as f:

    writer = csv.DictWriter(
        f, fieldnames=objects[0].keys()
    )

    writer.writeheader()
    writer.writerows(objects)

print("\n========== FLIGHT LEVEL ANALYSIS ==========")

level_rows = []

for h in levels:

    intersect_objects = 0
    intersect_faces = 0
    coplanar_faces = 0

    for node in scene.graph.nodes_geometry:

        transform, name = scene.graph[node]

        mesh = scene.geometry[name]
        bounds = mesh.bounds

        if not (
            bounds[0, 1] <= h <= bounds[1, 1]
        ):
            continue

        transform, name = scene.graph[node]
        mesh = scene.geometry[name].copy()
        mesh.apply_transform(transform)

        y = mesh.triangles[:, :, 1]

        low = y.min(axis=1)
        high = y.max(axis=1)

        crossing = (
            (low <= h + 1e-6) &
            (high >= h - 1e-6) &
            ((high - low) > 1e-6)
        )

        coplanar = (
            np.abs(y - h) < 1e-6
        ).all(axis=1)

        if crossing.any() or coplanar.any():
            intersect_objects += 1

        intersect_faces += int(crossing.sum())
        coplanar_faces += int(coplanar.sum())

    row = {
        "flight_height": float(h),
        "intersect_objects": intersect_objects,
        "crossing_faces": intersect_faces,
        "coplanar_faces": coplanar_faces
    }

    level_rows.append(row)

    print(
        f"Y={h:.2f} | "
        f"objects={intersect_objects} | "
        f"crossing_faces={intersect_faces} | "
        f"coplanar_faces={coplanar_faces}"
    )

with open(
    OUT / "flight_level_candidates.csv",
    "w", newline="", encoding="utf-8"
) as f:

    writer = csv.DictWriter(
        f, fieldnames=level_rows[0].keys()
    )

    writer.writeheader()
    writer.writerows(level_rows)

print("\nSaved:")
print("generated/city_object_height_bounds.csv")
print("generated/flight_level_candidates.csv")
