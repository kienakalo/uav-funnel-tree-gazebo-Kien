
from pathlib import Path
import csv
import heapq
import numpy as np
import trimesh
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

CITY = Path("data/input/city.glb")
OUT = Path("generated")
OUT.mkdir(exist_ok=True)

TOP_K = 15


def find_components(mesh):
    """Find connected triangle components using shared edges."""

    faces = mesh.faces
    n = len(faces)

    edges = np.concatenate([
        faces[:, [0, 1]],
        faces[:, [1, 2]],
        faces[:, [2, 0]]
    ])

    face_ids = np.tile(np.arange(n, dtype=np.int32), 3)
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
        a = find(a)
        b = find(b)

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

    _, labels = np.unique(
        roots, return_inverse=True
    )

    n_components = labels.max() + 1

    face_counts = np.bincount(
        labels, minlength=n_components
    )

    areas = mesh.area_faces
    normals = mesh.face_normals

    total_area = np.bincount(
        labels,
        weights=areas,
        minlength=n_components
    )

    upward_mask = normals[:, 1] > 0.9

    upward_area = np.bincount(
        labels,
        weights=areas * upward_mask,
        minlength=n_components
    )

    boundary_labels = labels[
        face_ids[starts[counts == 1]]
    ]

    nonmanifold_labels = labels[
        face_ids[starts[counts > 2]]
    ]

    boundary = np.bincount(
        boundary_labels,
        minlength=n_components
    )

    nonmanifold = np.bincount(
        nonmanifold_labels,
        minlength=n_components
    )

    return (
        labels,
        face_counts,
        total_area,
        upward_area,
        boundary,
        nonmanifold
    )


def clean_mesh(mesh):
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

    _, indices = np.unique(
        canonical,
        axis=0,
        return_index=True
    )

    mesh.update_faces(np.sort(indices))
    mesh.remove_unreferenced_vertices()

    return mesh


scene = trimesh.load(
    CITY,
    force="scene",
    process=False
)

mesh_cache = {}
top_candidates = []
serial = 0

csv_path = OUT / "city_components_report_safe.csv"

fields = [
    "object",
    "component_id",
    "triangles",
    "area",
    "upward_area",
    "upward_area_percent",
    "boundary_edges",
    "nonmanifold_edges"
]

with csv_path.open(
    "w", newline="", encoding="utf-8"
) as f:

    writer = csv.DictWriter(
        f, fieldnames=fields
    )
    writer.writeheader()

    for object_index, node in enumerate(
        scene.graph.nodes_geometry
    ):

        print(
            f"Processing {object_index + 1}/"
            f"{len(scene.graph.nodes_geometry)}: {node}",
            flush=True
        )

        transform, name = scene.graph[node]

        mesh = scene.geometry[name].copy()
        mesh.apply_transform(transform)
        mesh = clean_mesh(mesh)

        if len(mesh.faces) == 0:
            continue

        (
            labels,
            face_counts,
            total_area,
            upward_area,
            boundary,
            nonmanifold
        ) = find_components(mesh)

        mesh_cache[node] = (mesh, labels)

        n_components = len(face_counts)

        for k in range(n_components):

            pct = (
                upward_area[k] / total_area[k] * 100
                if total_area[k] > 0 else 0
            )

            writer.writerow({
                "object": node,
                "component_id": k,
                "triangles": int(face_counts[k]),
                "area": float(total_area[k]),
                "upward_area": float(upward_area[k]),
                "upward_area_percent": float(pct),
                "boundary_edges": int(boundary[k]),
                "nonmanifold_edges": int(nonmanifold[k])
            })

            if upward_area[k] <= 0:
                continue

            candidate = (
                float(upward_area[k]),
                serial,
                node,
                k,
                int(face_counts[k]),
                float(total_area[k]),
                float(pct),
                int(boundary[k]),
                int(nonmanifold[k])
            )

            serial += 1

            if len(top_candidates) < TOP_K:
                heapq.heappush(
                    top_candidates, candidate
                )
            elif candidate[0] > top_candidates[0][0]:
                heapq.heapreplace(
                    top_candidates, candidate
                )

        print(
            f"  Components: {n_components}",
            flush=True
        )


# Keep only the top 15 components for visualization.
selected = sorted(
    top_candidates,
    reverse=True
)

preview_scene = trimesh.Scene()
polygons = []
heights = []

print("\n========== TOP UPWARD COMPONENTS ==========")

for rank, item in enumerate(selected, 1):

    (
        up_area, _, node, component_id,
        n_faces, area, pct, boundary, nonmanifold
    ) = item

    mesh, labels = mesh_cache[node]

    face_mask = labels == component_id

    part = trimesh.Trimesh(
        vertices=mesh.vertices.copy(),
        faces=mesh.faces[face_mask].copy(),
        process=False
    )

    part.remove_unreferenced_vertices()

    colors = np.tile(
        [150, 150, 150, 255],
        (len(part.faces), 1)
    )

    colors[
        part.face_normals[:, 1] > 0.9
    ] = [50, 180, 100, 255]

    part.visual.face_colors = colors

    preview_scene.add_geometry(
        part,
        geom_name=f"component_{rank}",
        node_name=f"component_{rank}"
    )

    triangles = part.triangles

    polygons.append(triangles[:, :, [0, 2]])
    heights.append(
        triangles[:, :, 1].mean(axis=1)
    )

    print(
        f"{rank}. {node}/{component_id}: "
        f"faces={n_faces}, "
        f"area={area:.3f}, "
        f"upward={pct:.1f}%, "
        f"boundary={boundary}, "
        f"nonmanifold={nonmanifold}"
    )


preview_scene.export(
    OUT / "city_top_components_safe.glb"
)

if polygons:

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
    ax.set_title("Top upward-facing components")

    fig.colorbar(pc, ax=ax, label="Y height")
    fig.tight_layout()

    fig.savefig(
        OUT / "city_top_components_safe.png",
        dpi=120
    )

    plt.close(fig)


print("\n========== COMPLETED ==========")
print("CSV:", csv_path)
print("GLB:", OUT / "city_top_components_safe.glb")
print("PNG:", OUT / "city_top_components_safe.png")


