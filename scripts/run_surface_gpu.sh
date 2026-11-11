#!/usr/bin/env bash
# WSLg D3D12 rendering. Change FUNNEL_DEMO_CASE to select another mission.
set -euo pipefail
cd "$(dirname "$0")/.."
demo_case="${FUNNEL_DEMO_CASE:-surface_delivery}"
for argument in "$@"; do
  if [[ "$argument" == --software ]]; then
    echo 'The GPU launcher cannot be combined with --software.' >&2
    exit 2
  fi
done
unset LIBGL_ALWAYS_SOFTWARE LIBGL_ALWAYS_INDIRECT
export GALLIUM_DRIVER=d3d12
echo 'Graphics mode: WSLg / Mesa D3D12 (requires compatible GPU drivers)'
exec bash scripts/run_funnel_physics.sh "$demo_case" "$@"
