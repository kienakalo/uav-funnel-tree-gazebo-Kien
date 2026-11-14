#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main libraries: Python stdlib (argparse, csv, json, math, os, pathlib, signal, subprocess,
# sys, time).
"""Check SDF, pose commands and measured Gazebo poses in an isolated headless world."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated/funnel_preview"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full-preview',action='store_true',help='Also send the complete animation and verify its final measured pose')
    args = parser.parse_args()
    if sys.platform != "linux":
        raise SystemExit("Run this check in Ubuntu.")
    env = dict(os.environ)
    env["GZ_PARTITION"] = f"funnel_check_{os.getpid()}"
    env["GZ_SIM_RESOURCE_PATH"] = str(OUT) + os.pathsep + env.get("GZ_SIM_RESOURCE_PATH", "")
    def command(args, timeout=10):
        return subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True, timeout=timeout, check=True)
    print(command(["gz", "sdf", "-k", str(OUT / "funnel_demo.sdf")]).stdout, flush=True)
    print(command([sys.executable, str(ROOT / "animate.py"), "--route", str(OUT / "route.json"),
                   "--world", "funnel_demo", "--dry-run"]).stdout, flush=True)
    route = json.loads((OUT / "route.json").read_text())["waypoints"]
    result = {"mode": "headless_pose_preview", "gui_render_tested": False,
              "physics_flight_tested": False, "checked_poses": []}
    report = OUT / "gazebo_runtime_check.json"
    write_report = lambda: report.write_text(json.dumps(result, indent=2)+"\n")
    result["status"] = "running"
    write_report()
    log_path = OUT / "gazebo_headless_check.log"
    with log_path.open("w") as log:
        server = subprocess.Popen(["gz", "sim", "-s", "-r", "-v", "3", str(OUT / "funnel_demo.sdf")],
                                  cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 40
            while True:
                if server.poll() is not None:
                    raise RuntimeError(f"Gazebo exited with {server.returncode}; see {log_path}")
                services = command(["gz", "service", "-l"], timeout=5).stdout
                if "/world/funnel_demo/set_pose" in services.splitlines():
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError("Gazebo set_pose service did not appear")
                time.sleep(.5)
            # Exercise corners and every segment midpoint, then read simulated
            # poses from the SceneBroadcaster instead of trusting service ACKs.
            samples = []
            for a, b in zip(route, route[1:]):
                samples.extend([a, [(x+y)/2 for x, y in zip(a, b)]])
            samples.append(route[-1])
            for i, point in enumerate(samples):
                request = f'name: "drone", position: {{x: {point[0]}, y: {point[1]}, z: {point[2]}}}, orientation: {{w: 1}}'
                reply = command(["gz", "service", "-s", "/world/funnel_demo/set_pose",
                                 "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
                                 "--timeout", "2000", "--req", request]).stdout
                if "true" not in reply.lower():
                    raise RuntimeError(f"Pose command rejected: {reply}")
                time.sleep(.05)
                raw = command(["gz", "topic", "-e", "-t", "/world/funnel_demo/dynamic_pose/info",
                               "-n", "1", "--json-output"]).stdout
                message = json.loads(raw)
                pose = next(p for p in message["pose"] if p.get("name") == "drone")
                position = pose.get("position", {})
                measured = [position.get(axis, 0.) for axis in ("x", "y", "z")]
                error = math.dist(point, measured)
                if error > 1e-6:
                    raise ValueError(f"Measured position mismatch: {error}")
                result["checked_poses"].append({"commanded": point, "measured": measured, "error": error})
                print(f"Measured pose {i+1}/{len(samples)} PASS", flush=True)
            if args.full_preview:
                command_log = OUT / 'pose_headless_check.csv'
                subprocess.run([sys.executable,str(ROOT/'animate.py'),'--route',str(OUT/'route.json'),
                                '--world','funnel_demo','--log',str(command_log),'--speed','10'],
                               cwd=ROOT,env=env,timeout=240,check=True)
                with command_log.open(newline='') as csv_file:
                    rows=list(csv.DictReader(csv_file))
                if not rows or any(row['service_accepted']!='True' for row in rows):
                    raise ValueError('Incomplete full-preview command log')
                raw=command(['gz','topic','-e','-t','/world/funnel_demo/dynamic_pose/info',
                             '-n','1','--json-output']).stdout
                pose=next(p for p in json.loads(raw)['pose'] if p.get('name')=='drone')
                measured=[pose.get('position',{}).get(axis,0.) for axis in ('x','y','z')]
                error=math.dist(route[-1],measured)
                if error>1e-6:
                    raise ValueError(f'Full preview final measured position mismatch: {error}')
                result['full_preview']={'frames_accepted':len(rows),'final_measured_position':measured,
                                        'final_error':error,'retried_frames':sum(int(r['attempts'])>1 for r in rows)}
            result["status"] = "passed"
        except Exception as exc:
            result.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            raise
        finally:
            if server.poll() is None:
                os.killpg(server.pid, signal.SIGTERM)
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(server.pid, signal.SIGKILL)
                    server.wait(timeout=5)
            write_report()
    print(f"Headless Gazebo checks PASS. Report: {report}", flush=True)


if __name__ == "__main__":
    main()
