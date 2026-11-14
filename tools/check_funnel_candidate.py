#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main libraries: NumPy; Python stdlib (hashlib, json, math, pathlib, sys); local modules
# (mesh, verification).
"""Independently check full segment coverage of the candidate by the mesh."""
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mesh import read_geom
from verification import segment_on_mesh, path_length, edge_distances


def main():
    mesh_path = ROOT / "generated/funnel_input_y2p00.geom"
    route_path = ROOT / "generated/funnel_route_candidate_y2p00.json"
    report = json.loads((ROOT / "generated/funnel_input_y2p00_report.json").read_text())
    progress = json.loads((ROOT / "generated/funnel_route_progress_y2p00.json").read_text())
    route = json.loads(route_path.read_text())
    if progress.get("status") != "candidate_found" or route["signature"] != progress["signature"]:
        raise ValueError("Candidate does not match a completed current run")
    mesh = read_geom(mesh_path)
    points = [(p.x, p.y, p.z) for p in mesh.points]
    path = route["points"]
    if len(path) < 2 or any(len(p) != 3 or not all(math.isfinite(v) for v in p) for p in path):
        raise ValueError("Invalid route points")
    source, goal = report["source_vertex"], report["goal_vertex"]
    if (route["source"], route["goal"]) != (source, goal):
        raise ValueError("Source/goal mismatch")
    if math.dist(path[0], points[source]) > 1e-7 or math.dist(path[-1], points[goal]) > 1e-7:
        raise ValueError("Wrong route endpoints")
    triangles = np.array(points)[np.array(mesh.faces)]
    lows, highs = triangles.min(axis=1), triangles.max(axis=1)
    failed = []
    tolerance = 1e-7
    for i, (a, b) in enumerate(zip(path, path[1:])):
        # Broad phase only; the independent checker covers the entire segment
        # by triangle intervals rather than checking sampled route positions.
        low, high = np.minimum(a, b)-tolerance, np.maximum(a, b)+tolerance
        ids = np.flatnonzero(np.all(highs >= low, axis=1) & np.all(lows <= high, axis=1))
        faces = [mesh.faces[int(fid)] for fid in ids]
        if not segment_on_mesh(a, b, points, faces, tolerance):
            failed.append(i)
    length = path_length(path)
    if abs(length-route["length"]) > 1e-6*max(1., length):
        raise ValueError("Stored length mismatch")
    lower = math.dist(points[source], points[goal])
    upper = edge_distances(points, mesh.faces, source)[goal]
    result = {"surface_membership_passed": not failed, "failed_segment_indices": failed,
              "mesh_sha256": hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
              "route_sha256": hashlib.sha256(route_path.read_bytes()).hexdigest(),
              "segments_checked": len(path)-1, "candidate_length": length,
              "euclidean_lower_bound": lower, "mesh_edge_reference_length": upper,
              "no_longer_than_mesh_edge_reference": length <= upper+1e-6,
              "optimality_certified": False, "gazebo_route_updated": False}
    output = ROOT / "generated/funnel_route_candidate_validation_y2p00.json"
    output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
