from pathlib import Path
from collections import defaultdict, deque
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1] if False else Path.cwd()
INPUT = ROOT / "generated" / "navigation_y2p00.geom"
OUTPUT = ROOT / "generated" / "funnel_input_y2p00.geom"
REPORT = ROOT / "generated" / "funnel_input_y2p00_report.json"

# Coordinates are in the original GLB scene: X/Y/Z, with Y up.
POINTS = {
    "START": np.array([5.15, 2.0, -4.85], dtype=float),
    "GOAL": np.array([50.15, 2.0, -44.85], dtype=float),
}
EPS = 1e-9


def read_geom(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    nv, nf, ne = map(int, lines[0].split())
    vlines = lines[1:1 + nv]
    flines = lines[1 + nv:1 + nv + nf]
    if len(vlines) != nv or len(flines) != nf:
        raise ValueError(".geom file length does not match its header")
    vertices = np.asarray([[float(x) for x in line.split()] for line in vlines], dtype=float)
    faces = []
    for line in flines:
        row = list(map(int, line.split()))
        if len(row) != 4 or row[0] != 3:
            raise ValueError(f"Expected triangular face record '3 i j k', got: {line}")
        faces.append(row[1:])
    faces = np.asarray(faces, dtype=np.int64)
    if vertices.shape != (nv, 3) or faces.shape != (nf, 3):
        raise ValueError("Unexpected vertex/face array shape")
    if faces.min() < 0 or faces.max() >= nv:
        raise ValueError("Face index outside vertex array")
    return vertices, faces, ne


def barycentric_xz(point, triangle):
    # Barycentric coordinates in the X-Z plane.
    p = point[[0, 2]]
    a, b, c = triangle[:, [0, 2]]
    den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(den) < 1e-15:
        return None
    wa = ((b[1] - c[1]) * (p[0] - c[0]) + (c[0] - b[0]) * (p[1] - c[1])) / den
    wb = ((c[1] - a[1]) * (p[0] - c[0]) + (a[0] - c[0]) * (p[1] - c[1])) / den
    wc = 1.0 - wa - wb
    return np.array([wa, wb, wc])


def locate_point(point, vertices, faces):
    hits = []
    for fi, face in enumerate(faces):
        tri = vertices[face]
        # This navigation mesh is intended to lie on one horizontal Y level.
        if abs(float(np.mean(tri[:, 1])) - point[1]) > 1e-7:
            continue
        bc = barycentric_xz(point, tri)
        if bc is not None and np.min(bc) >= -EPS and np.max(bc) <= 1.0 + EPS:
            hits.append((fi, bc))
    if len(hits) != 1:
        raise ValueError(
            f"Point {point.tolist()} belongs to {len(hits)} triangles; "
            "expected exactly one triangle (not on a shared edge/vertex)."
        )
    fi, bc = hits[0]
    if np.min(bc) <= 1e-7:
        raise ValueError(
            f"Point {point.tolist()} is too close to a triangle edge; "
            "edge insertion needs a separate case."
        )
    return fi, bc


def topology(vertices, faces):
    edge_faces = defaultdict(list)
    for fi, (a, b, c) in enumerate(faces):
        for u, v in ((a, b), (b, c), (c, a)):
            edge_faces[(int(min(u, v)), int(max(u, v)))].append(fi)

    counts = np.fromiter((len(x) for x in edge_faces.values()), dtype=np.int64)
    adjacency = [[] for _ in range(len(faces))]
    for incident in edge_faces.values():
        if len(incident) == 2:
            a, b = incident
            adjacency[a].append(b)
            adjacency[b].append(a)

    seen = np.zeros(len(faces), dtype=bool)
    component_sizes = []
    for start in range(len(faces)):
        if seen[start]:
            continue
        q = deque([start])
        seen[start] = True
        size = 0
        while q:
            u = q.popleft()
            size += 1
            for v in adjacency[u]:
                if not seen[v]:
                    seen[v] = True
                    q.append(v)
        component_sizes.append(size)

    return {
        "vertices": int(len(vertices)),
        "triangles": int(len(faces)),
        "edges": int(len(edge_faces)),
        "boundary_edges": int(np.sum(counts == 1)),
        "nonmanifold_edges": int(np.sum(counts > 2)),
        "face_components": len(component_sizes),
        "component_sizes_desc": sorted(component_sizes, reverse=True),
        "face_adjacency": adjacency,
    }


def main():
    if not INPUT.exists():
        raise FileNotFoundError(f"Cannot find {INPUT}. Run from the project root.")

    vertices, faces, header_edges = read_geom(INPUT)
    print(f"Input: {INPUT}")
    print(f"Read {len(vertices)} vertices, {len(faces)} triangles, header edges={header_edges}")

    located = {}
    for name, point in POINTS.items():
        fi, bc = locate_point(point, vertices, faces)
        located[name] = {"face": int(fi), "barycentric": bc.tolist(), "vertex_index": int(len(vertices) + len(located))}
        print(f"{name}: containing face={fi}, barycentric={np.round(bc, 6).tolist()}")

    if len({item["face"] for item in located.values()}) != len(located):
        raise ValueError("START and GOAL are in the same triangle; handle this case separately.")

    # Split each containing triangle into three triangles by inserting the point as a vertex.
    new_vertices = vertices.tolist()
    point_vertex = {}
    face_to_point = {item["face"]: name for name, item in located.items()}
    new_faces = []

    for fi, (a, b, c) in enumerate(faces):
        if fi not in face_to_point:
            new_faces.append([int(a), int(b), int(c)])
            continue
        name = face_to_point[fi]
        point = POINTS[name]
        new_id = len(new_vertices)
        new_vertices.append(point.tolist())
        point_vertex[name] = new_id
        new_faces.extend([
            [int(a), int(b), new_id],
            [int(b), int(c), new_id],
            [int(c), int(a), new_id],
        ])

    new_vertices = np.asarray(new_vertices, dtype=float)
    new_faces = np.asarray(new_faces, dtype=np.int64)

    topo = topology(new_vertices, new_faces)
    if topo["nonmanifold_edges"] != 0:
        raise RuntimeError("Non-manifold edges appeared after inserting START/GOAL.")
    if topo["face_components"] != 1:
        raise RuntimeError("The resulting mesh is not one face-connected component.")

    unique_edges = set()
    for a, b, c in new_faces:
        unique_edges.add(tuple(sorted((int(a), int(b)))))
        unique_edges.add(tuple(sorted((int(b), int(c)))))
        unique_edges.add(tuple(sorted((int(c), int(a)))))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"{len(new_vertices)} {len(new_faces)} {len(unique_edges)}\n")
        for x, y, z in new_vertices:
            f.write(f"{x:.12g} {y:.12g} {z:.12g}\n")
        for a, b, c in new_faces:
            f.write(f"3 {a} {b} {c}\n")

    report = {
        "input": str(INPUT),
        "output": str(OUTPUT),
        "source_vertex": int(point_vertex["START"]),
        "goal_vertex": int(point_vertex["GOAL"]),
        "inserted_points": {
            name: {
                "coordinates_xyz": POINTS[name].tolist(),
                "original_containing_face_zero_based": located[name]["face"],
                "barycentric": located[name]["barycentric"],
                "new_vertex_index_zero_based": point_vertex[name],
            }
            for name in POINTS
        },
        "topology": {k: v for k, v in topo.items() if k != "face_adjacency"},
        "note": "Preprocessing only. This does not run Funnel Tree or certify collision-free UAV motion.",
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n========== FUNNEL INPUT MESH ==========")
    print(f"Vertices: {topo['vertices']}")
    print(f"Triangles: {topo['triangles']}")
    print(f"Unique edges: {topo['edges']}")
    print(f"Boundary edges: {topo['boundary_edges']}")
    print(f"Non-manifold edges: {topo['nonmanifold_edges']}")
    print(f"Face-connected components: {topo['face_components']}")
    print(f"START vertex index: {point_vertex['START']}")
    print(f"GOAL vertex index: {point_vertex['GOAL']}")
    print(f"Saved: {OUTPUT}")
    print(f"Saved: {REPORT}")


if __name__ == "__main__":
    main()
