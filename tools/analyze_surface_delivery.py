# Main libraries: NumPy (telemetry/mesh arrays), Shapely (spatial queries),
# Matplotlib (plots); csv, hashlib, json, pathlib (Python standard library).
"""Check measured tracking against the actual non-flat navigation mesh."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import sys

import numpy as np
from shapely import polygons
from shapely.geometry import box
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from mesh import read_geom
from prepare_funnel_physics import CITY_STL_RECORD

OUT = ROOT / 'generated/funnel_physics/surface_delivery'


def surface_deviation(positions, triangles):
    a, b, c = triangles.transpose(1, 0, 2)
    first, second = b - a, c - a
    determinant = first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0]
    errors = []
    for position in positions:
        relative = position[:2] - a[:, :2]
        u = (relative[:, 0] * second[:, 1] - relative[:, 1] * second[:, 0]) / determinant
        v = (first[:, 0] * relative[:, 1] - first[:, 1] * relative[:, 0]) / determinant
        inside = (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6)
        if not inside.any():
            raise ValueError('A measured surface-following position projects outside the navigation mesh')
        height = a[:, 2] + u * first[:, 2] + v * second[:, 2]
        errors.append(float(abs(position[2] - height[inside]).min()))
    return max(errors)


def main(folder=None):
    global OUT
    if folder is not None:
        OUT = Path(folder)
    route_bytes = (OUT / 'route.json').read_bytes()
    route = json.loads(route_bytes)
    plan_path = OUT / 'surface_plan.json'
    if hashlib.sha256(plan_path.read_bytes()).hexdigest() != route['surface_plan_sha256']:
        raise ValueError('The surface plan changed after the Gazebo world was prepared')
    plan = json.loads(plan_path.read_text())
    for relative, expected in plan['input_sha256'].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Surface input changed: {relative}')
    metadata = json.loads((OUT / 'telemetry_metadata.json').read_text())
    route_hash = hashlib.sha256(route_bytes).hexdigest()
    if metadata['route_sha256'] != route_hash:
        raise ValueError('Telemetry belongs to a different route')
    telemetry_bytes = (OUT / 'physics_telemetry.csv').read_bytes()
    rows = list(csv.DictReader(io.StringIO(telemetry_bytes.decode())))
    if not rows or rows[-1]['phase'] != 'complete':
        raise ValueError('The surface-delivery mission has not completed')
    positions = np.array([[float(r[k]) for k in 'xyz'] for r in rows])
    if not np.isfinite(positions).all():
        raise ValueError('Non-finite measured coordinates')
    first_surface = next(i for i, p in enumerate(route['waypoints'])
                         if math.dist(p, route['surface_waypoints'][0]) < 1e-7)
    selected = np.array([first_surface <= int(r['segment']) < len(route['waypoints']) - 2
                         and r['phase'] in ('moving', 'dwell') for r in rows])
    if not selected.any() or not any(r['phase'] == 'descending' for r in rows):
        raise ValueError('Missing surface-following or delivery-descent samples')
    mesh = read_geom(OUT / 'surface.geom')
    vertices = np.array([(p.x, p.y, p.z) for p in mesh.points])
    deviation = surface_deviation(positions[selected], vertices[np.array(mesh.faces)])

    city = np.fromfile(ROOT / 'generated/funnel_preview/city.stl',
                       dtype=CITY_STL_RECORD, offset=84)['triangle']
    spatial = STRtree(polygons(city[:, :, :2]))
    tops = city[:, :, 2].max(axis=1)
    clearances = []
    for x, y, z in positions:
        ids = spatial.query(box(x - .45, y - .3, x + .45, y + .3))
        if len(ids):
            clearances.append(float(z - tops[ids].max()))
    minimum_clearance = min(clearances) if clearances else None
    tracking = [float(r['error']) for r in rows]
    final_error = math.dist(positions[-1], route['waypoints'][-1])
    altitude_range = [float(positions[selected, 2].min()), float(positions[selected, 2].max())]
    checks_passed = (max(tracking) < .03 and final_error < .02 and deviation < .03
                     and minimum_clearance is not None and minimum_clearance > .3
                     and altitude_range[1] - altitude_range[0] > 1.)
    report = dict(checks_passed=checks_passed, samples=len(rows), surface_samples=int(selected.sum()),
                  max_tracking_error=max(tracking), final_goal_error=final_error,
                  measured_surface_altitude_range=altitude_range,
                  max_vertical_surface_deviation=deviation,
                  min_sampled_city_clearance_under_body=minimum_clearance,
                  route_sha256=route_hash, telemetry_sha256=hashlib.sha256(telemetry_bytes).hexdigest(),
                  surface_mesh_sha256=hashlib.sha256((OUT / 'surface.geom').read_bytes()).hexdigest(),
                  scope='measured point-mass trajectory against the 3D mesh and city triangle AABBs under the body footprint')
    target = OUT / 'surface_validation.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    print(f'Save at: {target}')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    times = np.array([float(r['sim_time']) for r in rows])
    reference = [float(r['target_z']) for r in rows]
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(times, reference, color='#db740f', linewidth=2.5, label='Planned 3D route')
    ax.plot(times, positions[:, 2], color='#1766ad', linestyle='--', linewidth=1.4, label='Measured altitude')
    ax.axvspan(times[selected][0], times[selected][-1], color='#57b8bc', alpha=.13, label='Following the polyhedral surface')
    ax.set(xlabel='Simulation time (s)', ylabel='Gazebo Z (simulation units)',
           title='Funnel route on a 3D surface, followed by delivery descent')
    ax.grid(alpha=.25)
    ax.legend(loc='best')
    fig.tight_layout()
    image = OUT / 'surface_altitude_profile.png'
    fig.savefig(image, dpi=160)
    plt.close(fig)
    print(f'Save at: {image}')
    if not checks_passed:
        raise SystemExit('Surface tracking validation failed')


if __name__ == '__main__':
    main()
