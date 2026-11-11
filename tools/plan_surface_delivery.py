"""Build a safe 3D polyhedral envelope and run Funnel propagation on that surface."""
import argparse
import hashlib
import heapq
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
from shapely import polygons
from shapely.geometry import box
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from city import write_stl
from mesh import Mesh, Point
from funnel_tree import propagate, reconstruct
from run_funnel_route import secondary_sources, candidate_route, write_json
from run_funnel_benchmark import verify
from prepare_funnel_gazebo import simplify
from prepare_funnel_physics import CITY_STL_RECORD
from build_navigation_surface import inspect_mesh, write_geom

OUT = ROOT / 'generated/funnel_physics/surface_delivery'
CLEARANCE = 1.5
HALF_WIDTH = 1.6
MAX_AXIS_SLOPE = .5


def build_surface(start, goal, step):
    """Every whole mesh cell clears all inflated city-triangle AABBs below it."""
    triangles = np.fromfile(ROOT / 'generated/funnel_preview/city.stl',
                            dtype=CITY_STL_RECORD, offset=84)['triangle']
    low, high = triangles.min(axis=1), triangles.max(axis=1)
    spatial = STRtree(polygons(triangles[:, :, :2]))
    xy = np.array([start[:2], goal[:2]])
    minimum = np.floor((xy.min(axis=0) - 16.) / step) * step
    maximum = np.ceil((xy.max(axis=0) + 16.) / step) * step
    xs = np.unique(np.r_[np.arange(minimum[0], maximum[0] + step / 2, step), xy[:, 0]])
    ys = np.unique(np.r_[np.arange(minimum[1], maximum[1] + step / 2, step), xy[:, 1]])
    required = np.empty((len(xs) - 1, len(ys) - 1))
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            query = box(xs[i] - HALF_WIDTH, ys[j] - HALF_WIDTH,
                        xs[i + 1] + HALF_WIDTH, ys[j + 1] + HALF_WIDTH)
            ids = spatial.query(query)
            required[i, j] = (float(high[ids, 2].max()) if len(ids) else 0.) + CLEARANCE
    heights = np.full((len(xs), len(ys)), CLEARANCE)
    for di, dj in ((0, 0), (1, 0), (0, 1), (1, 1)):
        section = heights[di:di + len(xs) - 1, dj:dj + len(ys) - 1]
        np.maximum(section, required, out=section)

    # Spread roof heights outward to make ramps. This only raises the envelope.
    queue = [(-float(h), i, j) for (i, j), h in np.ndenumerate(heights)]
    heapq.heapify(queue)
    while queue:
        negative_height, i, j = heapq.heappop(queue)
        height = -negative_height
        if height < heights[i, j] - 1e-10:
            continue
        for a, b in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
            if not (0 <= a < len(xs) and 0 <= b < len(ys)):
                continue
            distance = math.hypot(xs[a] - xs[i], ys[b] - ys[j])
            candidate = height - MAX_AXIS_SLOPE * distance
            if candidate > heights[a, b] + 1e-10:
                heights[a, b] = candidate
                heapq.heappush(queue, (-candidate, a, b))

    points = np.array([(x, y, heights[i, j]) for i, x in enumerate(xs) for j, y in enumerate(ys)])
    faces = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            a = i * len(ys) + j
            b, c, d = a + len(ys), a + 1, a + len(ys) + 1
            faces.extend([(a, b, c), (b, d, c)])
            if min(heights[i, j], heights[i + 1, j], heights[i, j + 1], heights[i + 1, j + 1]) < required[i, j] - 1e-9:
                raise ValueError('Surface clearance construction failed')
    faces = np.array(faces, dtype=int)
    mesh = Mesh([Point(*p) for p in points], [tuple(f) for f in faces])
    stats = inspect_mesh(points, faces)
    for key in ('nonmanifold_edges', 'bad_boundary_vertices', 'disconnected_vertex_fans', 'degenerate_triangles'):
        if stats[key]:
            raise ValueError(f'Invalid surface topology: {key}')
    source = int(np.linalg.norm(points[:, :2] - xy[0], axis=1).argmin())
    target = int(np.linalg.norm(points[:, :2] - xy[1], axis=1).argmin())
    # Entry and delivery descent must also have clear vertical columns.
    for location, surface_index in ((start, source), (goal, target)):
        x, y, bottom = location
        ids = spatial.query(box(x - HALF_WIDTH, y - HALF_WIDTH, x + HALF_WIDTH, y + HALF_WIDTH))
        top = points[surface_index, 2]
        overlap = (high[ids, 2] >= min(bottom, top) - .2) & (low[ids, 2] <= max(bottom, top) + .2)
        if overlap.any():
            raise ValueError('The vertical surface entry or delivery descent intersects city geometry')
    return mesh, points, faces, source, target, stats


def funnel_route(mesh, source, goal, signature, seconds):
    sources = secondary_sources(mesh, source)
    targets = set(sources) | {goal}
    cache_path = OUT / 'funnel_cache.json'
    cache = {'signature': signature, 'runs': {}}
    if cache_path.exists():
        saved = json.loads(cache_path.read_text())
        if saved.get('signature') == signature:
            cache = saved
    coordinates = np.array([(p.x, p.y, p.z) for p in mesh.points])
    # Straight 3D distance is a consistent lower bound for every surface edge.
    # A* avoids propagating sources that cannot improve the current goal route.
    heuristic = np.linalg.norm(coordinates - coordinates[goal], axis=1)
    costs, previous, queue, settled = {source: 0.}, {}, [(float(heuristic[source]), 0., source)], set()
    print(f'3D Funnel mesh: {len(mesh.points)} vertices, {len(mesh.faces)} faces, {len(sources)} sources', flush=True)
    while queue:
        _, cost, s = heapq.heappop(queue)
        if s in settled:
            continue
        if s == goal:
            points, chain = candidate_route(mesh, source, goal, previous)
            return simplify(points), chain, len(cache['runs'])
        key = str(s)
        if key not in cache['runs']:
            print(f'Propagating source {s}; reached cost {cost:.2f}', flush=True)
            deadline = time.monotonic() + seconds
            distances, best, stats = propagate(mesh, s, deadline, 200000, True, target_vertices=targets - {s})
            edges = {}
            for t in targets - {s}:
                if best[t] is None:
                    continue
                path = reconstruct(mesh, s, best[t], deadline=deadline)
                length = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
                if abs(length - distances[t]) > 1e-6 * max(1., length):
                    raise ValueError('3D Funnel reconstruction length mismatch')
                edges[str(t)] = dict(length=length, path=path)
            cache['runs'][key] = dict(edges=edges, stats=stats)
            write_json(cache_path, cache)
        settled.add(s)
        for target, edge in cache['runs'][key]['edges'].items():
            t = int(target)
            total = cost + edge['length']
            if t not in settled and total < costs.get(t, math.inf):
                costs[t] = total
                previous[t] = (s, edge)
                heapq.heappush(queue, (total + heuristic[t], total, t))
    raise ValueError('Experimental Funnel propagation did not find a route on the 3D surface')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cell', type=float, default=5.)
    parser.add_argument('--seconds', type=float, default=30.)
    args = parser.parse_args()
    if not math.isfinite(args.cell) or args.cell <= 0 or not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error('Cell size and time limit must be positive and finite')
    OUT.mkdir(exist_ok=True, parents=True)
    flat_plan_path = ROOT / 'generated/funnel_physics/delivery/horizontal_plan.json'
    flat = json.loads(flat_plan_path.read_text())
    for relative, expected in flat['input_sha256'].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f'The saved delivery endpoints have stale provenance: {relative}')
    start = np.array(flat['fixed_start'])
    ground = flat['selection']['ground_z']
    goal = np.r_[flat['waypoints'][-1][:2], ground + 1.1]
    mesh, points, faces, source, target, stats = build_surface(start, goal, args.cell)
    write_geom(OUT / 'surface.geom', points, faces, stats['edges'])
    write_stl(OUT / 'surface.stl', points, faces)
    signature = hashlib.sha256((OUT / 'surface.geom').read_bytes() + (ROOT / 'src/funnel_tree.py').read_bytes()
                               + (ROOT / 'src/mesh.py').read_bytes() + json.dumps([source, target]).encode()).hexdigest()
    path, chain, runs = funnel_route(mesh, source, target, signature, args.seconds)
    if not verify(mesh, points.tolist(), path):
        raise ValueError('The reconstructed route does not lie on the 3D navigation surface')
    if np.ptp(np.array(path)[:, 2]) < 1.:
        raise ValueError('The computed surface route has insufficient altitude variation')
    preview = json.loads((ROOT / 'generated/funnel_preview/route.json').read_text())
    mission_path = simplify([start.tolist(), *path])
    inverse_mission = np.array(mission_path) / preview['transform']['scale'] + preview['transform']['origin']
    original_mission = inverse_mission[:, [0, 2, 1]] * [1, 1, -1]
    inputs = ('generated/funnel_preview/city.stl', 'generated/funnel_preview/route.json',
              'generated/funnel_physics/delivery/horizontal_plan.json',
              'generated/funnel_physics/surface_delivery/surface.geom',
              'generated/funnel_physics/surface_delivery/surface.stl',
              'src/funnel_tree.py', 'src/mesh.py', 'tools/plan_surface_delivery.py')
    plan = dict(waypoints=mission_path, original_waypoints=original_mission.tolist(),
                flight_length=sum(math.dist(a, b) for a, b in zip(mission_path, mission_path[1:])),
                original_model_length=sum(math.dist(a, b) for a, b in zip(original_mission, original_mission[1:])),
                surface_waypoints=path, surface_source=source, surface_goal=target,
                source_chain=chain, source_runs=runs, fixed_start=start.tolist(),
                selection=flat['selection'], optimality_certified=False,
                input_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in inputs})
    report = dict(mesh=stats, cell_size=args.cell, vertical_clearance=CLEARANCE,
                  horizontal_half_width=HALF_WIDTH, max_axis_slope=MAX_AXIS_SLOPE,
                  surface_altitude_range=[float(points[:, 2].min()), float(points[:, 2].max())],
                  route_altitude_range=[min(p[2] for p in path), max(p[2] for p in path)],
                  surface_membership_passed=True, whole_surface_clearance_passed=True,
                  scope='3D geodesic candidate on a conservative roof-and-terrain envelope above the city',
                  optimality_certified=False, source_runs=runs)
    write_json(OUT / 'surface_plan.json', plan)
    write_json(OUT / 'surface_report.json', report)
    print(json.dumps(report, indent=2), flush=True)
    for name in ('surface.geom', 'surface.stl', 'surface_plan.json', 'surface_report.json'):
        print(f'Save at: {OUT / name}', flush=True)


if __name__ == '__main__':
    main()
