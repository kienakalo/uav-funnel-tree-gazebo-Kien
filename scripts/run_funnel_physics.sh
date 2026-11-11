#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
case_name=original
software=false
show_surface=false
case_set=false
for argument in "$@"; do
  case "$argument" in
    --software) software=true ;;
    --show-surface) show_surface=true ;;
    original|cross_city|short_open|narrow_corridor|low_collision|delivery|surface_delivery)
      if [[ "$case_set" == true ]]; then echo 'Specify only one case.'; exit 2; fi
      case_name="$argument"; case_set=true ;;
    *) echo 'Usage: bash scripts/run_funnel_physics.sh [original|cross_city|short_open|narrow_corridor|low_collision|delivery|surface_delivery] [--software] [--show-surface]'; exit 2 ;;
  esac
done
output_dir=generated/funnel_physics
world_name=funnel_physics
if [[ "$case_name" != original ]]; then
  output_dir="$output_dir/$case_name"
  world_name="${world_name}_$case_name"
fi
command -v gz >/dev/null || { echo 'Gazebo is not available in this terminal.'; exit 1; }
/usr/bin/python3 -c 'from gz.sim8 import Model, Link; from gz.math7 import Vector3d'
planner_python=python3
if [[ -x .venv/bin/python ]]; then planner_python=.venv/bin/python; fi
prepare_options=(--case "$case_name")
if [[ "$show_surface" == true ]]; then prepare_options+=(--show-surface); fi
"$planner_python" tools/prepare_funnel_physics.py "${prepare_options[@]}"
export GZ_SIM_RESOURCE_PATH="$PWD/generated/funnel_preview:$PWD/generated/funnel_physics${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$PWD/src${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
if [[ "$software" == true ]]; then export LIBGL_ALWAYS_SOFTWARE=1; fi
if timeout 3 gz service -l 2>/dev/null | grep -F "/world/$world_name/" >/dev/null; then
  echo "A $world_name world is already running. Close that session first."; exit 1
fi
if [[ -f "$output_dir/physics_telemetry.csv" ]]; then
  cp "$output_dir/physics_telemetry.csv" "$output_dir/physics_telemetry_$(date +%Y%m%d_%H%M%S).csv"
fi
echo 'Opening force-feedback tracking. No set_pose animation is used.'
export FUNNEL_RUN_ID="$(date +%s%N)-$$"
export FUNNEL_PHYSICS_CASE="$case_name"
export FUNNEL_OUTPUT_DIR="$output_dir"
bash scripts/gazebo_system_python.sh sim -v 3 "$output_dir/funnel_physics.sdf" \
  > >(tee "$output_dir/gazebo_gui.log") 2>&1 &
gazebo_pid=$!
trap 'kill "$gazebo_pid" 2>/dev/null || true' EXIT
trap 'exit 130' INT TERM
controller_ready=false
for attempt in $(seq 1 20); do
  if ! kill -0 "$gazebo_pid" 2>/dev/null; then echo 'Gazebo exited; read gazebo_gui.log.'; exit 1; fi
  if /usr/bin/python3 -c 'import json,os,pathlib,sys; p=pathlib.Path(os.environ["FUNNEL_OUTPUT_DIR"])/"telemetry_metadata.json"; sys.exit(0 if p.exists() and json.loads(p.read_text()).get("run_id")==os.environ["FUNNEL_RUN_ID"] else 1)' 2>/dev/null; then
    controller_ready=true; break
  fi
  sleep 1
done
if [[ "$controller_ready" != true ]]; then
  echo 'ERROR: the Python flight controller did not initialize; stopping this session.'
  echo "Read $output_dir/gazebo_gui.log for the import or plugin error."
  exit 1
fi
echo 'Funnel controller loaded. Watch the drone and the periodic tracking-error messages.'
if [[ "$case_name" == low_collision ]]; then
  echo 'The reference is aimed at a wall. The controller keeps commanding the target after contact.'
fi
if [[ "$case_name" == low_collision || "$case_name" == delivery || "$case_name" == surface_delivery ]]; then
  echo "Save at: $PWD/$output_dir/physics_telemetry.csv"
fi
started=false
for attempt in $(seq 1 3); do
  if /usr/bin/gz service -s "/world/$world_name/control" --reqtype gz.msgs.WorldControl \
    --reptype gz.msgs.Boolean --timeout 5000 --req 'pause: false' | grep -F 'data: true' >/dev/null; then
    started=true; break
  fi
  sleep 1
done
if [[ "$started" != true ]]; then echo 'Could not start physics; stopping this session.'; exit 1; fi
wait "$gazebo_pid"
