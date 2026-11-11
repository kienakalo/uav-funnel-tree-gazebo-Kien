#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v gz >/dev/null || { echo 'Gazebo must already be installed.'; exit 1; }
python3 -c 'from gz.sim8 import Model,Link; import numpy'
python3 prepare_urban.py
if [[ -f generated/physics_telemetry.csv ]]; then
  cp generated/physics_telemetry.csv "generated/physics_telemetry_before_urban_$(date +%Y%m%d_%H%M%S).csv"
fi
export GZ_SIM_RESOURCE_PATH="$PWD/generated${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$PWD/src${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
if [[ "${1:-}" == --software ]]; then export LIBGL_ALWAYS_SOFTWARE=1; fi
exec gz sim -r -v 3 generated/hcm_demo.sdf
