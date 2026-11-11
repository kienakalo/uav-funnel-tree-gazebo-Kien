import csv
import numpy as np
import trimesh

from pathlib import Path

CITY = Path("data/input/city.glb")
OUT = Path("generated/city_topology_welded.csv")


def get_topology(mesh):
    faces = mesh.faces
    n = len(faces)

    if n == 0:
        return 0, 0, 0, 0

    edges = np.concatenate([
        faces[:, [0, 1]],
        faces[:, [1, 2]],
        faces[:, [2, 0]]
    ])

    face_ids = np.tile(np.arange(n), 3)
    edges = np.sort(edges, axis=1)

    order = np.lexsort((edges[:, 1], edges[:, 0]))
    edges = edges[order]
    face_ids = face_ids[order]

    mask = np.ones(len(edges), dtype=bool)
    mask[1:] = np.any(edges[1:] != edges[:-1], axis=1)

    starts = np.flatnonzero(mask)
    ends = np.r_[starts[1:], len(edges)]
    counts = ends - starts

    parent = np.arange(n)
    size = np.ones(n)

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

    return (
        len(component_sizes),
        int(component_sizes.max()),
        int(np.sum(counts == 1)),
        int(np.sum(counts > 2))
    )


scene = trimesh.load(CITY, force="scene", process=False)

rows = []

for node in scene.graph.nodes_geometry:

    transform, name = scene.graph[node]

    original = scene.geometry[name].copy()
    original.apply_transform(transform)

    raw_components = get_topology(original)[0]

    mesh = original.copy()

    # Merge vertices with coincident coordinates.
    mesh.merge_vertices(
        digits_vertex=6,
        merge_tex=False,
        merge_norm=False
    )

    # Remove degenerate faces created by merging.
    faces = mesh.faces

    valid = (
        (faces[:, 0] != faces[:, 1]) &
        (faces[:, 1] != faces[:, 2]) &
        (faces[:, 2] != faces[:, 0])
    )

    removed_degenerate = int(np.sum(~valid))
    mesh.update_faces(valid)

    # Remove duplicate triangles in the analysis copy.
    canonical = np.sort(mesh.faces, axis=1)

    _, first = np.unique(
        canonical,
        axis=0,
        return_index=True
    )

    keep = np.sort(first)
    removed_duplicate = len(mesh.faces) - len(keep)

    mesh.update_faces(keep)
    mesh.remove_unreferenced_vertices()

    components, largest, boundary, nonmanifold = (
        get_topology(mesh)
    )

    rows.append({
        "object": node,
        "raw_vertices": len(original.vertices),
        "welded_vertices": len(mesh.vertices),
        "triangles": len(mesh.faces),
        "raw_components": raw_components,
        "welded_components": components,
        "largest_component": largest,
        "largest_component_percent": round(
            largest / len(mesh.faces) * 100, 2
        ) if len(mesh.faces) else 0,
        "boundary_edges": boundary,
        "nonmanifold_edges": nonmanifold,
        "removed_degenerate": removed_degenerate,
        "removed_duplicate": removed_duplicate
    })


OUT.parent.mkdir(exist_ok=True)

with OUT.open("w", newline="", encoding="utf-8") as f:

    writer = csv.DictWriter(
        f,
        fieldnames=rows[0].keys()
    )

    writer.writeheader()
    writer.writerows(rows)


print("\n========== VERTEX WELDING RESULTS ==========")

for r in sorted(
    rows,
    key=lambda x: x["largest_component"],
    reverse=True
)[:15]:

    print(
        f'{r["object"]}: '
        f'raw={r["raw_components"]}, '
        f'welded={r["welded_components"]}, '
        f'largest={r["largest_component"]}, '
        f'share={r["largest_component_percent"]}%, '
        f'boundary={r["boundary_edges"]}, '
        f'nonmanifold={r["nonmanifold_edges"]}'
    )

print("\nSaved:", OUT)
