#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (argparse, hashlib, heapq, json, math, pathlib, sys, time);
# local modules (funnel_tree, mesh).
"""Build a candidate route through secondary Funnel sources, with resumable runs.

Graph edges come only from reconstructed Funnel propagation results. The
priority queue joins these segments; it does not use the mesh edge graph as
a fallback. Optimality of the experimental propagation is not certified.
"""
import argparse
import hashlib
import heapq
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mesh import read_geom
from funnel_tree import propagate, reconstruct


def secondary_sources(mesh, source):
    boundary = {v for edge, adjacent in mesh.edge_faces.items() if len(adjacent) == 1 for v in edge}
    result = [source]
    for v, faces in enumerate(mesh.vertex_faces):
        if v == source:
            continue
        angle = 0.
        for fid in faces:
            a, b = [i for i in mesh.faces[fid] if i != v]
            angle += mesh.angle(a, v, b)
        if angle > (math.pi if v in boundary else 2 * math.pi) + 1e-5:
            result.append(v)
    return result


def write_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def candidate_route(mesh, source, goal, previous):
    chunks, chain, current = [], [goal], goal
    seen = set()
    while current != source:
        if current in seen:
            raise ValueError("Cycle in secondary-source route")
        seen.add(current)
        parent, edge = previous[current]
        path = edge["path"]
        if math.dist(path[0], vars_point(mesh.points[parent])) > 1e-7:
            raise ValueError("Segment start mismatch")
        if math.dist(path[-1], vars_point(mesh.points[current])) > 1e-7:
            raise ValueError("Segment end mismatch")
        chunks.append(path)
        current = parent
        chain.append(current)
    points = []
    for chunk in reversed(chunks):
        points.extend(chunk if not points else chunk[1:])
    return points, list(reversed(chain))


def vars_point(point):
    return (point.x, point.y, point.z)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-runs", type=int, default=5,
                        help="Maximum new source propagations this invocation (default 5)")
    parser.add_argument("--seconds", type=float, default=20,
                        help="Per-source time budget, without profiler")
    args = parser.parse_args()
    if args.max_runs < 1 or not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error("Arguments must be positive and finite")
    mesh_path = ROOT / "generated/funnel_input_y2p00.geom"
    report = json.loads((ROOT / "generated/funnel_input_y2p00_report.json").read_text())
    source, goal = report["source_vertex"], report["goal_vertex"]
    mesh = read_geom(mesh_path)
    sources = secondary_sources(mesh, source)
    targets = set(sources) | {goal}
    digest = hashlib.sha256()
    for path in (mesh_path, ROOT / "src/funnel_tree.py", ROOT / "src/mesh.py", Path(__file__)):
        digest.update(path.read_bytes())
    digest.update(json.dumps([source, goal, sorted(targets)]).encode())
    signature = digest.hexdigest()
    cache_path = ROOT / "generated/funnel_secondary_cache_y2p00.json"
    progress_path = ROOT / "generated/funnel_route_progress_y2p00.json"
    cache = {"signature": signature, "runs": {}}
    if cache_path.exists():
        old = json.loads(cache_path.read_text())
        if old.get("signature") == signature:
            cache = old
        else:
            print("Input or code changed: previous cache will not be reused.", flush=True)
    print(f"Sources: {len(sources)}; cached: {len(cache['runs'])}; new-run limit: {args.max_runs}", flush=True)
    distances, previous = {source: 0.}, {}
    queue = [(0., source)]
    settled = set()
    new_runs = 0
    started = time.monotonic()
    progress = {"signature": signature, "status": "running", "source": source, "goal": goal,
                "scope": "candidate route on experimental Funnel source graph",
                "optimality_certified": False}
    write_json(progress_path, progress)
    while queue:
        cost, s = heapq.heappop(queue)
        if s in settled:
            continue
        if s == goal:
            points, chain = candidate_route(mesh, source, goal, previous)
            length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
            if abs(length-cost) > 1e-6*max(1., cost):
                raise ValueError("Joined route length mismatch")
            route_path = ROOT / "generated/funnel_route_candidate_y2p00.json"
            write_json(route_path, {"signature": signature, "source": source, "goal": goal,
                                   "status": "candidate_requires_independent_validation",
                                   "coordinates": "original GLB units, Y up",
                                   "source_chain": chain, "points": points, "length": length,
                                   "optimality_certified": False, "gazebo_route_updated": False})
            progress.update(status="candidate_found", candidate_file=str(route_path),
                            candidate_length=length, source_chain=chain)
            print(f"CANDIDATE FOUND: length={length:.6f}; source chain={chain}", flush=True)
            break
        key = str(s)
        if key not in cache["runs"]:
            if new_runs >= args.max_runs:
                progress.update(status="checkpoint", next_source=s)
                print("CHECKPOINT: run the same command again to continue.", flush=True)
                break
            print(f"Run {new_runs+1}/{args.max_runs}: source {s}; route cost {cost:.6f}", flush=True)
            deadline = time.monotonic() + args.seconds
            try:
                local_dist, best, stats = propagate(mesh, s, deadline, 200000, True,
                                                    target_vertices=targets - {s})
                edges = {}
                for target in sorted(targets - {s}):
                    if best[target] is None:
                        continue
                    path = reconstruct(mesh, s, best[target], deadline=deadline)
                    length = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
                    if not math.isfinite(length) or abs(length-local_dist[target]) > 1e-6*max(1., length):
                        raise ValueError("Reconstructed source edge length mismatch")
                    edges[str(target)] = {"length": length, "path": path}
            except (TimeoutError, RuntimeError, ValueError) as exc:
                progress.update(status="source_stopped", stopped_source=s,
                                error_type=type(exc).__name__, error=str(exc))
                print(f"SOURCE STOPPED: {type(exc).__name__}: {exc}", flush=True)
                break
            cache["runs"][key] = {"edges": edges, "stats": stats}
            write_json(cache_path, cache)
            new_runs += 1
            print(f"  Saved {len(edges)} outgoing Funnel segments.", flush=True)
        settled.add(s)
        for target_text, edge in cache["runs"][key]["edges"].items():
            target = int(target_text)
            if target in settled:
                continue
            total = cost + edge["length"]
            if total < distances.get(target, math.inf):
                distances[target] = total
                previous[target] = (s, edge)
                heapq.heappush(queue, (total, target))
    else:
        progress.update(status="no_route_in_funnel_source_graph")
        print("No route in this Funnel source graph; this is not proof of no geometric path.", flush=True)
    progress.update(cached_sources=len(cache["runs"]), new_runs=new_runs,
                    settled_sources=len(settled), seconds=time.monotonic()-started)
    write_json(progress_path, progress)
    print(json.dumps(progress, indent=2), flush=True)


if __name__ == "__main__":
    main()
