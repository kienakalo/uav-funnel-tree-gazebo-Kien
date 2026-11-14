# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (heapq, math, pathlib).
"""Read mesh inputs and bracketed path outputs. Python standard library only."""
import heapq
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_mesh(filename):
    lines = [s.strip() for s in Path(filename).read_text(encoding="utf-8").splitlines() if s.strip()]
    nv, nf, declared_edges = map(int, lines[0].split())
    if len(lines) != 1 + nv + nf:
        raise ValueError("Mesh line count does not match header")
    points = [tuple(map(float, line.split())) for line in lines[1:1+nv]]
    faces = []
    for line in lines[1+nv:]:
        n, *face = map(int, line.split())
        if n != 3 or len(face) != 3 or any(i < 0 or i >= nv for i in face):
            raise ValueError("Invalid triangle")
        faces.append(tuple(face))
    if any(len(p) != 3 or not all(map(math.isfinite, p)) for p in points):
        raise ValueError("Invalid coordinates")
    return points, faces, declared_edges


def read_paths(filename):
    paths = []
    for number, line in enumerate(Path(filename).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        tokens = line.replace("[", " ").replace("]", " ").split()
        count, *coords = tokens
        count = int(count)
        coords = list(map(float, coords))
        if count < 2 or len(coords) != 3*count or not all(map(math.isfinite, coords)):
            raise ValueError(f"Invalid path at line {number}")
        paths.append([tuple(coords[i:i+3]) for i in range(0, len(coords), 3)])
    return paths


def path_length(path):
    return sum(math.dist(a, b) for a, b in zip(path, path[1:]))


def edge_distances(points, faces, source):
    graph = [dict() for _ in points]
    for face in faces:
        for a, b in zip(face, face[1:] + face[:1]):
            graph[a][b] = graph[b][a] = math.dist(points[a], points[b])
    distances = [math.inf]*len(points)
    distances[source] = 0.0
    queue = [(0.0, source)]
    while queue:
        cost, a = heapq.heappop(queue)
        if cost > distances[a]:
            continue
        for b, weight in graph[a].items():
            new = cost + weight
            if new < distances[b]:
                distances[b] = new
                heapq.heappush(queue, (new, b))
    return distances


def segment_on_mesh(a, b, points, faces, tolerance):
    """Check full segment coverage by the union of coplanar triangle intervals.

    This verifies surface membership, not shortest-path optimality.
    """
    def sub(u, v): return tuple(x-y for x, y in zip(u, v))
    def dot(u, v): return sum(x*y for x, y in zip(u, v))
    def cross(u, v): return (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
    intervals = []
    for face in faces:
        p, q, r = [points[i] for i in face]
        e0, e1 = sub(q, p), sub(r, p)
        normal = cross(e0, e1)
        norm = math.sqrt(dot(normal, normal))
        if norm == 0:
            continue
        if max(abs(dot(sub(a,p),normal)), abs(dot(sub(b,p),normal))) > tolerance*norm:
            continue
        d00, d01, d11 = dot(e0,e0), dot(e0,e1), dot(e1,e1)
        denom = d00*d11-d01*d01
        if denom <= 0:
            continue
        def bary(x):
            w = sub(x,p)
            u = (d11*dot(w,e0)-d01*dot(w,e1))/denom
            v = (d00*dot(w,e1)-d01*dot(w,e0))/denom
            return (1-u-v,u,v)
        ba, bb = bary(a), bary(b)
        btol = tolerance / max(math.sqrt(d00), math.sqrt(d11), tolerance)
        low, high = 0.0, 1.0
        for x, y in zip(ba,bb):
            slope = y-x
            if abs(slope) < 1e-15:
                if x < -btol:
                    high = -1
                    break
            elif slope > 0:
                low = max(low, (-btol-x)/slope)
            else:
                high = min(high, (-btol-x)/slope)
        if low <= high:
            intervals.append((low,high))
    reached = 0.0
    for low, high in sorted(intervals):
        if low > reached + 1e-9:
            return False
        reached = max(reached,high)
        if reached >= 1.0-1e-9:
            return True
    return False
