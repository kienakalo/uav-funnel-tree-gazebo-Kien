#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main runtime: Bash; local Python/Gazebo scripts and Ubuntu system commands.
# Python library roles and versions: README.md and requirements*.txt.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != --software ) ]]; then
  echo 'Usage: bash scripts/run_funnel.sh [--software]'; exit 2
fi
command -v gz >/dev/null || { echo 'Gazebo is not available in this Ubuntu terminal.'; exit 1; }
python3 tools/prepare_funnel_gazebo.py
export GZ_SIM_RESOURCE_PATH="$PWD/generated/funnel_preview${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
if [[ "${1:-}" == --software ]]; then export LIBGL_ALWAYS_SOFTWARE=1; fi
if timeout 3 gz service -l 2>/dev/null | grep -F '/world/funnel_demo/set_pose' >/dev/null; then
  echo 'A funnel_demo world is already running. Close that session first.'; exit 1
fi
echo 'Opening the validated Funnel route in Gazebo (pose preview).'
gz sim -r -v 3 generated/funnel_preview/funnel_demo.sdf \
  > >(tee generated/funnel_preview/gazebo_gui.log) 2>&1 &
gazebo_pid=$!
trap 'kill "$gazebo_pid" 2>/dev/null || true' EXIT
trap 'exit 130' INT TERM
ready=false
for attempt in $(seq 1 40); do
  if ! kill -0 "$gazebo_pid" 2>/dev/null; then echo 'Gazebo exited; read errors above.'; exit 1; fi
  if timeout 3 gz service -l 2>/dev/null | grep -F '/world/funnel_demo/set_pose' >/dev/null; then ready=true; break; fi
  sleep 1
done
if [[ "$ready" != true ]]; then echo 'The funnel_demo set_pose service did not appear.'; exit 1; fi
sleep 2
if python3 animate.py --route generated/funnel_preview/route.json --world funnel_demo \
  --log generated/funnel_preview/pose_commands.csv --speed 10; then
  echo 'Preview finished. Close Gazebo or press Ctrl+C to finish this session.'
else
  echo 'Preview stopped after retries. Gazebo will stay open if it is still running.'
  echo 'Logs: generated/funnel_preview/pose_commands.csv and gazebo_gui.log'
  echo 'Use a second Ubuntu terminal to resume at the frame reported above:'
  echo 'python3 animate.py --route generated/funnel_preview/route.json --world funnel_demo --log generated/funnel_preview/pose_resume.csv --speed 10 --start-frame FRAME'
fi
wait "$gazebo_pid"
