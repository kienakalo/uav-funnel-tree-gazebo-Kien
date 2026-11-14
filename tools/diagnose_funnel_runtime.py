#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (argparse, cProfile, faulthandler, io, json, math, pathlib,
# pstats, subprocess, sys, time); local modules (funnel_tree, mesh).
"""Profile one START propagation, without changing the solver or Gazebo route."""
import argparse
import cProfile
import faulthandler
import io
import json
import math
from pathlib import Path
import pstats
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def worker(seconds, goal_only=False):
    from mesh import read_geom
    from funnel_tree import propagate

    report = json.loads((ROOT / "generated/funnel_input_y2p00_report.json").read_text())
    source, goal = report["source_vertex"], report["goal_vertex"]
    mesh = read_geom(ROOT / "generated/funnel_input_y2p00.geom")
    print(f"Mesh: {len(mesh.points)} vertices, {len(mesh.faces)} triangles", flush=True)
    print(f"START: {source}; GOAL: {goal}; clipping: enabled", flush=True)
    boundary = {v for edge, faces in mesh.edge_faces.items() if len(faces) == 1 for v in edge}
    extra_sources = 0
    for v, faces in enumerate(mesh.vertex_faces):
        if v == source:
            continue
        total = 0.0
        for fid in faces:
            a, b = [i for i in mesh.faces[fid] if i != v]
            total += mesh.angle(a, v, b)
        if total > (math.pi if v in boundary else 2 * math.pi) + 1e-5:
            extra_sources += 1
    print(f"Full solve would use {1 + extra_sources} propagation sources.", flush=True)
    print(f"Profiling START only; propagation budget: {seconds:g}s", flush=True)
    if goal_only:
        print("Reconstruction scope: GOAL only. Secondary sources are not included.", flush=True)
    result = {"source": source, "goal": goal, "full_solve_sources": 1 + extra_sources,
              "scope": "one source only; not a complete shortest-path solution",
              "profiling_enabled": True}
    result['reconstruction_scope'] = 'goal_only' if goal_only else 'all_vertices'
    profile = cProfile.Profile()
    # This timer runs independently of the Python propagation deadline.
    # Keep the file open until process exit so forced termination retains stacks.
    stack_path = ROOT / "generated/funnel_runtime_stacks.txt"
    stack_file = stack_path.open("w", encoding="utf-8")
    faulthandler.dump_traceback_later(5, repeat=True, file=stack_file)
    print(f"Stack snapshots every 5s: {stack_path}", flush=True)
    started = time.monotonic()
    profile.enable()
    try:
        distances, best, stats = propagate(mesh, source, time.monotonic() + seconds, 200000, True,
                                          target_vertices={goal} if goal_only else None)
        result.update(status="completed", stats=stats,
                      reached_vertices=sum(math.isfinite(d) for d in distances),
                      goal_reached=best[goal] is not None,
                      goal_candidate_length=distances[goal] if math.isfinite(distances[goal]) else None)
    except (TimeoutError, RuntimeError, ValueError) as exc:
        result.update(status="stopped", error_type=type(exc).__name__, error=str(exc))
    finally:
        profile.disable()
        faulthandler.cancel_dump_traceback_later()
        stack_file.close()
    result["propagation_seconds_with_profiler"] = time.monotonic() - started
    output = ROOT / "generated/funnel_runtime_diagnostic.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(15)
    profile_path = ROOT / "generated/funnel_runtime_profile.txt"
    profile_path.write_text(stream.getvalue(), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    print(stream.getvalue(), flush=True)
    print(f"Saved: {output}\nSaved: {profile_path}", flush=True)
    print("Profiler adds overhead. No route exported; Gazebo files unchanged.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--goal-only", action="store_true",
                        help="Reconstruct only GOAL candidates; not a full solve")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error("--seconds must be a finite positive number")
    if args.worker:
        worker(args.seconds, args.goal_only)
        return
    # The core checks its deadline during expansion, but not reconstruction.
    # A separate process also bounds reconstruction and preprocessing time.
    hard_limit = args.seconds + 15
    output = ROOT / "generated/funnel_runtime_diagnostic.json"
    output.write_text(json.dumps({"status": "running", "hard_limit_seconds": hard_limit,
                                 "profile_from_this_run_available": False}, indent=2) + "\n",
                      encoding="utf-8")
    print(f"Diagnostic hard limit: {hard_limit:g}s", flush=True)
    try:
        completed = subprocess.run(
            [sys.executable, "-u", str(Path(__file__).resolve()),
             "--worker", "--seconds", str(args.seconds)] + (["--goal-only"] if args.goal_only else []),
            cwd=ROOT, timeout=hard_limit)
    except subprocess.TimeoutExpired:
        output.write_text(json.dumps({"status": "hard_timeout", "hard_limit_seconds": hard_limit,
                                     "profile_from_this_run_available": False,
                                     "stack_file": "generated/funnel_runtime_stacks.txt"}, indent=2) + "\n",
                          encoding="utf-8")
        print("HARD TIME LIMIT: worker stopped. Current status saved; any old profile is not from this run.")
        stack_path = ROOT / "generated/funnel_runtime_stacks.txt"
        if stack_path.exists():
            print(stack_path.read_text(encoding="utf-8"), flush=True)
        raise SystemExit(2)
    if completed.returncode:
        output.write_text(json.dumps({"status": "worker_failed", "returncode": completed.returncode,
                                     "profile_from_this_run_available": False,
                                     "stack_file": "generated/funnel_runtime_stacks.txt"}, indent=2) + "\n",
                          encoding="utf-8")
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
