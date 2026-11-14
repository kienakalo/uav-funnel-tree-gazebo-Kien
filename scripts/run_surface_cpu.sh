#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main runtime: Bash, Python + NumPy/Shapely, Gazebo Harmonic (gz.sim8/gz.math7).
# Analysis uses Matplotlib; MMP verification uses pygeodesic independently.
# Python dependency versions: requirements-demo.txt and requirements-reference.txt.
# Explicit CPU rendering. Change FUNNEL_DEMO_CASE to select another mission.
set -euo pipefail
cd "$(dirname "$0")/.."
demo_case="${FUNNEL_DEMO_CASE:-surface_delivery}"
unset LIBGL_ALWAYS_INDIRECT
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
echo 'Graphics mode: CPU / Mesa llvmpipe'
exec bash scripts/run_funnel_physics.sh "$demo_case" "$@" --software
