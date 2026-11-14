# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy, Shapely; Python stdlib (hashlib, heapq, json, math, pathlib, time);
# local modules (funnel_tree, mesh, prepare_funnel_gazebo, prepare_funnel_physics,
# run_funnel_benchmark, run_funnel_route).
"""Find the farthest feasible delivery vertex and connect it with Funnel paths."""
import hashlib
import heapq
import json
import math
from pathlib import Path
import time

import numpy as np
from shapely import polygons
from shapely.geometry import LineString, Point as GeoPoint, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from prepare_funnel_physics import ROOT, CITY_STL_RECORD, benchmark_route
from prepare_funnel_gazebo import simplify
from run_funnel_benchmark import verify
from run_funnel_route import candidate_route, write_json
from mesh import Mesh, Point, read_geom
from funnel_tree import propagate, reconstruct

OUT = ROOT / 'generated/funnel_physics/delivery'


def recorded_mesh(manifest):
    """Rebuild recorded face splits without reselecting tied nearest faces."""
    base = read_geom(ROOT / 'generated/funnel_input_y2p00.geom')
    vertices = [(p.x, p.y, p.z) for p in base.points]
    centres = np.array(vertices)[np.array(base.faces)].mean(axis=1)
    endpoints = {}
    for case in manifest['cases'][1:]:
        endpoints[case['source']] = case['start_xyz']
        endpoints[case['goal']] = case['goal_xyz']
    splits = {}
    for index, coordinate in sorted(endpoints.items()):
        face = int(np.linalg.norm(centres - coordinate, axis=1).argmin())
        if index != len(vertices) or math.dist(centres[face], coordinate) > 1e-9 or face in splits:
            raise ValueError('Recorded benchmark face splits do not match the base mesh')
        splits[face] = index
        vertices.append(tuple(coordinate))
    faces = []
    for index, (a, b, c) in enumerate(base.faces):
        if index in splits:
            v = splits[index]
            faces.extend([(a, b, v), (b, c, v), (c, a, v)])
        else:
            faces.append((a, b, c))
    return Mesh([Point(*p) for p in vertices], faces), len(base.points)


def farthest_site(world_vertices, start):
    triangles = np.fromfile(ROOT / 'generated/funnel_preview/city.stl',
                            dtype=CITY_STL_RECORD, offset=84)['triangle']
    low, high = triangles.min(axis=1), triangles.max(axis=1)
    spatial = STRtree(polygons(triangles[:, :, :2]))
    distances = np.linalg.norm(world_vertices[:, :2] - start[:2], axis=1)
    for rank, index in enumerate(np.argsort(-distances)):
        x, y, z = world_vertices[index]
        footprint = box(x - .5, y - .5, x + .5, y + .5)
        near = spatial.query(footprint)
        if not len(near):
            continue
        ground = float(high[near, 2].max())
        # Restrict this delivery mission to the street-level layer in this asset.
        if not 2.85 < ground < 3.1:
            continue
        flat = near[(abs(triangles[near, :, 2] - ground) < 1e-5).all(axis=1)]
        floor = unary_union([Polygon(face[:, :2]) for face in triangles[flat]])
        if footprint.difference(floor).area > 1e-6:
            continue
        column = spatial.query(box(x - 1.6, y - 1.6, x + 1.6, y + 1.6))
        if ((high[column, 2] > ground + 1e-4) & (low[column, 2] < z + .5)).any():
            continue
        nearby = spatial.query(box(x - 6, y - 6, x + 6, y + 6))
        walls = nearby[(high[nearby, 2] > 5.2) & (high[nearby, 2] - low[nearby, 2] > .7)]
        options = []
        for wall in walls:
            projection = Polygon(triangles[wall, :, :2])
            if projection.area < 1e-8:
                projection = LineString(triangles[wall, :, :2])
            distance = projection.distance(GeoPoint(x, y))
            if 1.6 < distance < 6:
                options.append((distance, int(wall)))
        if not options:
            continue
        wall_distance, wall = min(options)
        return dict(vertex=int(index), world=world_vertices[index].tolist(),
                    distance=float(distances[index]), ground_z=ground,
                    wall_distance=wall_distance, wall_triangle=wall,
                    wall=triangles[wall].tolist(), candidates_considered=len(world_vertices),
                    rank=int(rank), selection_scope='farthest eligible navigation vertex by planar Euclidean distance')
    raise ValueError('No street-level delivery vertex with a clear descent and nearby facade')


def plan_route(mesh, source, goal, cache):
    coordinates = np.array([(p.x, p.y, p.z) for p in mesh.points])
    edges = {}

    def add(a, b, path):
        length = sum(math.dist(x, y) for x, y in zip(path, path[1:]))
        old = edges.setdefault(a, {}).get(b)
        if old is None or length < old['length']:
            edges[a][b] = dict(length=length, path=path)
            edges.setdefault(b, {})[a] = dict(length=length, path=list(reversed(path)))

    for s, run in cache['runs'].items():
        for t, edge in run['edges'].items():
            add(int(s), int(t), edge['path'])
    targets = sorted(edges, key=lambda v: math.dist(coordinates[v], coordinates[goal]))[:20]
    deadline = time.monotonic() + 45
    print(f'Funnel propagation from delivery GOAL {goal}; fixed START {source}', flush=True)
    _, best, stats = propagate(mesh, goal, deadline, 200000, True, target_vertices=targets)
    for target in targets:
        if best[target] is not None:
            add(goal, target, reconstruct(mesh, goal, best[target], deadline=deadline))
    costs, previous, queue = {source: 0.}, {}, [(0., source)]
    while queue:
        cost, s = heapq.heappop(queue)
        if cost != costs[s]:
            continue
        if s == goal:
            points, chain = candidate_route(mesh, source, goal, previous)
            points = simplify(points)
            if not verify(mesh, coordinates.tolist(), points):
                raise ValueError('Delivery Funnel route leaves the navigation mesh')
            return points, chain, stats
        for target, edge in edges.get(s, {}).items():
            total = cost + edge['length']
            if total < costs.get(target, math.inf):
                costs[target] = total
                previous[target] = (s, edge)
                heapq.heappush(queue, (total, target))
    raise ValueError('No delivery route in the available Funnel source graph')


def main():
    preview = json.loads((ROOT / 'generated/funnel_preview/route.json').read_text())
    benchmark_route('original', preview)  # Check current benchmark provenance.
    manifest = json.loads((ROOT / 'generated/funnel_benchmark/cases.json').read_text())
    cache = json.loads((ROOT / 'generated/funnel_benchmark/source_cache.json').read_text())
    if cache['signature'] != manifest['signature']:
        raise ValueError('Stale benchmark source cache')
    mesh, base_count = recorded_mesh(manifest)
    coordinates = np.array([(p.x, p.y, p.z) for p in mesh.points])
    scale = preview['transform']['scale']
    origin = np.array(preview['transform']['origin'])
    world = (coordinates[:, [0, 2, 1]] * [1, -1, 1] - origin) * scale
    start = np.array(preview['waypoints'][1])
    source = int(np.linalg.norm(world - start, axis=1).argmin())
    if math.dist(world[source], start) > 1e-7:
        raise ValueError('Fixed START is not a navigation vertex')
    selected = farthest_site(world[:base_count], start)
    print(f'Farthest checked delivery site: {selected["distance"]:.2f} from START', flush=True)
    points, chain, stats = plan_route(mesh, source, selected['vertex'], cache)
    waypoints = (np.array(points)[:, [0, 2, 1]] * [1, -1, 1] - origin) * scale
    inputs = ('generated/funnel_input_y2p00.geom', 'generated/funnel_preview/city.stl',
              'generated/funnel_preview/route.json', 'src/funnel_tree.py', 'src/mesh.py',
              'tools/run_funnel_benchmark.py', 'tools/plan_funnel_delivery.py',
              'generated/funnel_benchmark/cases.json', 'generated/funnel_benchmark/source_cache.json')
    plan = dict(waypoints=waypoints.tolist(), original_waypoints=points,
                horizontal_length=sum(math.dist(a, b) for a, b in zip(waypoints, waypoints[1:])),
                original_model_length=sum(math.dist(a, b) for a, b in zip(points, points[1:])),
                fixed_start=start.tolist(), source=source, goal=selected['vertex'],
                source_chain=chain, selection=selected, goal_propagation_stats=stats,
                source_graph_method='cached reversible Funnel segments plus one new goal propagation',
                optimality_certified=False,
                input_sha256={path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in inputs})
    OUT.mkdir(exist_ok=True, parents=True)
    write_json(OUT / 'horizontal_plan.json', plan)
    print(f'Horizontal route length: {plan["horizontal_length"]:.2f}', flush=True)
    print(f'Save at: {OUT / "horizontal_plan.json"}', flush=True)


if __name__ == '__main__':
    main()
