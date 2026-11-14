# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main libraries: Python stdlib (math, pathlib, sys, time); local modules (funnel_tree, mesh).
"""Check diagnostic target filtering against unrestricted propagation."""
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mesh import read_geom
from funnel_tree import propagate, reconstruct


for name in ("cliff", "L", "star"):
    mesh = read_geom(ROOT / f"data/input/{name}.geom")
    source = 1
    full, _, full_stats = propagate(mesh, source, time.monotonic() + 10, 200000)
    for goal in range(len(mesh.points)):
        scoped, best, stats = propagate(mesh, source, time.monotonic() + 10, 200000,
                                       target_vertices={goal})
        assert scoped[goal] == full[goal], (name, goal, scoped[goal], full[goal])
        assert stats["nodes"] == full_stats["nodes"]
        assert all(not math.isfinite(d) for v, d in enumerate(scoped) if v not in {source, goal})
        if goal != source and math.isfinite(scoped[goal]):
            path = reconstruct(mesh, source, best[goal])
            length = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
            assert abs(length - scoped[goal]) <= 1e-6 * max(1., length)
    print(name, "target scope PASS")

try:
    reconstruct(mesh, source, None, deadline=time.monotonic() - 1)
except TimeoutError:
    print("Expired reconstruction deadline PASS")
else:
    raise AssertionError("Expired deadline was ignored")
