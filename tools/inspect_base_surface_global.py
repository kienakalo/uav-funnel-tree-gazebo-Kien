
import csv
import gc
import numpy as np
import trimesh
from pathlib import Path

CITY = Path("data/input/city.glb")
OUT = Path("generated")
OUT.mkdir(exist_ok=True)

Y_MIN = 0.75
Y_MAX = 1.00

triangle_blocks = []

scene = trimesh.load(
    CITY, force="scene", process=False
)

print("Extracting triangles from all objects...")

for i, node in enumerate(scene.graph.nodes_geometry):

    transform, name = scene.graph[node]

    mesh = scene.geometry[name].copy()
    mesh.apply_transform(transform)

    centers = mesh.triangles_center
    normals = mesh.face_normals
    areas = mesh.area_faces

    selected = (
        (normals[:, 1] > 0.9) &
        (centers[:, 1] >= Y_MIN) &
        (centers[:, 1] < Y_MAX) &
        (areas > 1e-12) &
        np.isfinite(areas)
    )

    if selected.any():
        triangle_blocks.append(
            mesh.triangles[selected].copy()
        )

    print(
        f"{i+1}/{len(scene.graph.nodes_geometry)} "
        f"{node}: selected={selected.sum()}",
        flush=True
    )

    del mesh
    gc.collect()


triangles = np.concatenate(triangle_blocks)

print("\nTotal selected triangles:", len(triangles))

# Build one mesh from all objects.
vertices = triangles.reshape(-1, 3)

faces = np.arange(
    len(vertices), dtype=np.int32
).reshape(-1, 3)

mesh = trimesh.Trimesh(
    vertices=vertices,
    faces=faces,
    process=False
)

del triangles, vertices, faces, triangle_blocks
gc.collect()

print("\nWelding vertices globally...")

# Merge coincident vertices across different objects.
mesh.merge_vertices(
    digits_vertex=6,
    merge_tex=False,
    merge_norm=False
)

# Remove degenerate faces.
f = mesh.faces

valid = (
    (f[:, 0] != f[:, 1]) &
    (f[:, 1] != f[:, 2]) &
    (f[:, 2] != f[:, 0])
)

mesh.update_faces(valid)

# Remove duplicate triangles.
canonical = np.sort(mesh.faces, axis=1)

_, indices = np.unique(
    canonical,
    axis=0,
    return_index=True
)

mesh.update_faces(np.sort(indices))
mesh.remove_unreferenced_vertices()

print("Vertices after welding:", len(mesh.vertices))
print("Triangles after cleaning:", len(mesh.faces))


# Find connected components using shared edges.
f = mesh.faces
n = len(f)

edges = np.concatenate([
    f[:, [0, 1]],
    f[:, [1, 2]],
    f[:, [2, 0]]
])

face_ids = np.tile(
    np.arange(n, dtype=np.int32), 3
)

edges.sort(axis=1)

order = np.lexsort((edges[:, 1], edges[:, 0]))

edges = edges[order]
face_ids = face_ids[order]

mask = np.ones(len(edges), dtype=bool)
mask[1:] = np.any(
    edges[1:] != edges[:-1], axis=1
)

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

_, labels = np.unique(
    roots, return_inverse=True
)

k = labels.max() + 1

face_counts = np.bincount(
    labels, minlength=k
)

areas = mesh.area_faces

component_areas = np.bincount(
    labels, weights=areas, minlength=k
)

edge_labels = labels[face_ids[starts]]

boundary = np.bincount(
    edge_labels[counts == 1],
    minlength=k
)

nonmanifold = np.bincount(
    edge_labels[counts > 2],
    minlength=k
)

rows = []

for i in range(k):
    rows.append({
        "component": i,
        "faces": int(face_counts[i]),
        "area": float(component_areas[i]),
        "boundary_edges": int(boundary[i]),
        "nonmanifold_edges": int(nonmanifold[i])
    })

rows.sort(
    key=lambda x: x["faces"],
    reverse=True
)

with open(
    OUT / "base_surface_global_components.csv",
    "w", newline="", encoding="utf-8"
) as file:

    writer = csv.DictWriter(
        file, fieldnames=rows[0].keys()
    )

    writer.writeheader()
    writer.writerows(rows)


print("\n========== GLOBAL CONNECTIVITY ==========")
print("Total components:", k)
print("Single-face components:", np.sum(face_counts == 1))
print("Components below 10 faces:", np.sum(face_counts < 10))
print("Largest component:", face_counts.max())

print(
    "Largest component share:",
    round(face_counts.max() / n * 100, 2),
    "%"
)

print("\nTOP 20 GLOBAL COMPONENTS:")

for r in rows[:20]:
    print(
        f'Component {r["component"]}: '
        f'faces={r["faces"]}, '
        f'area={r["area"]:.3f}, '
        f'boundary={r["boundary_edges"]}, '
        f'nonmanifold={r["nonmanifold_edges"]}'
    )


# Export top 20 components for visual inspection.
top_ids = np.array([
    r["component"] for r in rows[:20]
])

face_mask = np.isin(labels, top_ids)

preview = trimesh.Trimesh(
    vertices=mesh.vertices.copy(),
    faces=mesh.faces[face_mask].copy(),
    process=False
)

preview.remove_unreferenced_vertices()

preview.export(
    OUT / "base_surface_global_top20.glb"
)

print("\nSaved:")
print("generated/base_surface_global_components.csv")
print("generated/base_surface_global_top20.glb")
