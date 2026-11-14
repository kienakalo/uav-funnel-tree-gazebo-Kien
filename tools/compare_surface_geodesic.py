# Main libraries: NumPy; pygeodesic (independent exact MMP reference only);
# hashlib, importlib.metadata, json, math, pathlib, time (Python stdlib).
# Funnel candidates are computed separately by the local Funnel Tree code.
"""Compare the saved 3D Funnel path with an independent exact MMP solver."""
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'generated/funnel_surface_reference'
sys.path.insert(0, str(OUT / 'runtime'))
sys.path.insert(0, str(ROOT / 'src'))
from mesh import read_geom
from verification import path_length
from run_funnel_benchmark import verify


def oriented_path(path, start, goal):
    path = np.asarray(path, dtype=float)
    if math.dist(path[-1], start) < math.dist(path[0], start):
        path = path[::-1]
    if math.dist(path[0], start) > 1e-7 or math.dist(path[-1], goal) > 1e-7:
        raise ValueError('Reference path endpoints do not match the Funnel endpoints')
    return path


def reference_self_tests(geodesic):
    tests = [
        ('flat_square', [[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [1., 1., 0.]],
         [[0, 1, 2], [1, 3, 2]], 0, 3, math.sqrt(2)),
        ('folded_triangles', [[0., 0., 0.], [2., 0., 0.], [.5, 1., 0.], [1.5, 0., 1.]],
         [[0, 1, 2], [1, 0, 3]], 2, 3, math.sqrt(5)),
    ]
    results = []
    for name, vertices, faces, source, goal, expected in tests:
        solver = geodesic.PyGeodesicAlgorithmExact(np.array(vertices), np.array(faces, dtype=np.int32))
        length, path = solver.geodesicDistance(source, goal)
        if abs(length - expected) > 1e-8 or abs(path_length(path) - length) > 1e-8:
            raise ValueError(f'Independent reference self-test failed: {name}')
        results.append(dict(case=name, expected=expected, measured=float(length), passed=True))
    return results


def main(folder=None, output=None):
    global OUT
    if output is not None:
        OUT = Path(output)
    from pygeodesic import geodesic
    folder = Path(folder) if folder is not None else ROOT / 'generated/funnel_physics/surface_delivery'
    plan_bytes = (folder / 'surface_plan.json').read_bytes()
    plan = json.loads(plan_bytes)
    for relative, expected in plan['input_sha256'].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Surface plan is stale: {relative}')
    tests = reference_self_tests(geodesic)
    mesh = read_geom(folder / 'surface.geom')
    vertices = np.array([(p.x, p.y, p.z) for p in mesh.points])
    faces = np.array(mesh.faces, dtype=np.int32)
    source, goal = plan['surface_source'], plan['surface_goal']
    funnel_path = np.array(plan['surface_waypoints'])
    if math.dist(funnel_path[0], vertices[source]) > 1e-7 or math.dist(funnel_path[-1], vertices[goal]) > 1e-7:
        raise ValueError('Funnel source/goal mismatch')
    solver = geodesic.PyGeodesicAlgorithmExact(vertices, faces)
    started = time.monotonic()
    length, path = solver.geodesicDistance(source, goal)
    seconds = time.monotonic() - started
    path = oriented_path(path, vertices[source], vertices[goal])
    reverse_length, reverse_path = solver.geodesicDistance(goal, source)
    reverse_path = oriented_path(reverse_path, vertices[goal], vertices[source])
    # Rotate/translate the same geometry to detect axis-specific reference issues.
    angle = .73
    rotation = np.array([[math.cos(angle), 0., math.sin(angle)], [0., 1., 0.],
                         [-math.sin(angle), 0., math.cos(angle)]])
    transformed = vertices @ rotation.T + [17., -11., 6.]
    rotated_solver = geodesic.PyGeodesicAlgorithmExact(transformed, faces)
    rotated_length, _ = rotated_solver.geodesicDistance(source, goal)
    tolerance = 1e-6 + 1e-8 * length
    if (abs(path_length(path) - length) > tolerance or abs(reverse_length - length) > tolerance
            or abs(path_length(reverse_path) - reverse_length) > tolerance
            or abs(rotated_length - length) > tolerance):
        raise ValueError('Independent reference consistency checks failed')
    reference_membership = verify(mesh, vertices.tolist(), path.tolist())
    funnel_membership = verify(mesh, vertices.tolist(), funnel_path.tolist())
    if not reference_membership or not funnel_membership:
        raise ValueError('Reference or Funnel path leaves the identical 3D mesh')
    funnel_length = path_length(funnel_path)
    excess = funnel_length - length
    matches = bool(abs(excess) <= tolerance)
    if excess < -tolerance:
        raise ValueError('Funnel is shorter than the independent exact solver; investigate both implementations')
    report = dict(status='MATCHES_EXACT_REFERENCE' if matches else 'LONGER_THAN_EXACT_REFERENCE',
                  matches_reference=matches, mesh_vertices=len(vertices), mesh_faces=len(faces),
                  source=source, goal=goal, funnel_length=funnel_length, exact_reference_length=float(length),
                  excess_length=float(excess), excess_percent=float(100 * excess / length),
                  numerical_tolerance=float(tolerance), euclidean_lower_bound=math.dist(vertices[source], vertices[goal]),
                  funnel_surface_membership_passed=funnel_membership,
                  reference_surface_membership_passed=reference_membership,
                  reverse_reference_length=float(reverse_length), rotated_reference_length=float(rotated_length),
                  reference_method='Kirsanov exact MMP geodesic algorithm through pygeodesic',
                  reference_version=importlib.metadata.version('pygeodesic'), reference_seconds=seconds,
                  reference_self_tests=tests,
                  comparison_scope='surface segment only, identical mesh and endpoints; excludes entry and delivery descent',
                  numerical_optimality_verified_for_this_case=matches,
                  formal_arithmetic_certificate=False, general_funnel_implementation_correctness_certified=False,
                  mesh_sha256=hashlib.sha256((folder / 'surface.geom').read_bytes()).hexdigest(),
                  surface_plan_sha256=hashlib.sha256(plan_bytes).hexdigest())
    OUT.mkdir(exist_ok=True, parents=True)
    outputs = {
        'comparison.json': report,
        'reference_route.json': dict(points=path.tolist(), length=float(length), source=source, goal=goal,
                                     mesh_sha256=report['mesh_sha256']),
    }
    for name, data in outputs.items():
        (OUT / name).write_text(json.dumps(data, indent=2) + '\n')
    summary = [
        '# Đối chiếu đường đi trên bề mặt 3D', '',
        f'- Kết quả: `{report["status"]}`.',
        f'- Funnel: {funnel_length:.12f} đơn vị mô phỏng.',
        f'- Tham chiếu MMP: {length:.12f} đơn vị mô phỏng.',
        f'- Chênh lệch: {excess:.12g} ({report["excess_percent"]:.9g}%).',
        f'- Dung sai so sánh: {tolerance:.12g}.',
        '- Hai đường đều đã kiểm tra nằm trên cùng bề mặt 3D.',
        '- Tham chiếu vượt qua hai ca giải tích, kiểm tra đảo chiều và phép quay/tịnh tiến.',
        '- Chỉ đối chiếu chặng trên bề mặt với cùng START/GOAL. Đoạn tiếp cận và đoạn hạ giao hàng nằm ngoài phép so sánh.',
        '- Bộ giải độc lập: https://github.com/mhogg/pygeodesic .',
        '- Đây là kiểm chứng số cho ca cụ thể, không phải chứng minh đúng cho mọi đầu vào.',
    ]
    (OUT / 'comparison.md').write_text('\n'.join(summary) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    for name in (*outputs, 'comparison.md'):
        print(f'Save at: {OUT / name}')


if __name__ == '__main__':
    main()
