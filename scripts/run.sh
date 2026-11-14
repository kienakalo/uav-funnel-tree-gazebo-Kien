#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main runtime: Bash; local Python/Gazebo scripts and Ubuntu system commands.
# Python library roles and versions: README.md and requirements*.txt.
set -euo pipefail
cd "$(dirname "$0")/.."
mode="${1:-pose}"
if [[ "$mode" != pose && "$mode" != physics ]]; then echo 'Usage: bash scripts/run.sh [pose|physics] [--software]'; exit 2; fi
command -v gz >/dev/null || { echo 'Install first: bash scripts/install_ubuntu.sh'; exit 1; }
python3 -c 'import numpy' || { echo 'Install python3-numpy using apt.'; exit 1; }
if [[ "$mode" == physics ]]; then
  python3 -c 'from gz.sim8 import Model, Link; from gz.math7 import Vector3d' || { echo 'Install python3-gz-sim8 using apt.'; exit 1; }
fi
python3 prepare.py --mode "$mode"
export GZ_SIM_RESOURCE_PATH="$PWD/generated${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$PWD/src${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
if [[ "${2:-}" == --software ]]; then export LIBGL_ALWAYS_SOFTWARE=1; fi
if [[ "$mode" == physics ]]; then
  echo 'Physics PD flight: telemetry in generated/physics_telemetry.csv.'
  exec gz sim -r -v 3 generated/hcm_demo.sdf
fi
echo 'Opening Gazebo; waiting for service, then starting pose preview automatically.'
gz sim -r -v 3 generated/hcm_demo.sdf &
gazebo_pid=$!
trap 'kill "$gazebo_pid" 2>/dev/null || true' EXIT INT TERM
ready=false
for attempt in $(seq 1 40); do
  if ! kill -0 "$gazebo_pid" 2>/dev/null; then echo 'Gazebo exited. Read errors above.'; exit 1; fi
  if timeout 3 gz service -l 2>/dev/null | grep -F '/world/hcm_demo/set_pose' >/dev/null; then ready=true; break; fi
  sleep 1
done
if [[ "$ready" != true ]]; then echo 'Service did not appear. Check Gazebo logs.'; exit 1; fi
sleep 2
python3 animate.py
echo 'Route completed. Close Gazebo or press Ctrl+C in this terminal to finish.'
wait "$gazebo_pid"
