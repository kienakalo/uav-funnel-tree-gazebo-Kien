#!/usr/bin/env bash
# Explicit CPU rendering. Change FUNNEL_DEMO_CASE to select another mission.
set -euo pipefail
cd "$(dirname "$0")/.."
demo_case="${FUNNEL_DEMO_CASE:-surface_delivery}"
unset LIBGL_ALWAYS_INDIRECT
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
echo 'Graphics mode: CPU / Mesa llvmpipe'
exec bash scripts/run_funnel_physics.sh "$demo_case" "$@" --software
