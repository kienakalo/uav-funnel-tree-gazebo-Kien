#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main runtime: Bash; local Python/Gazebo scripts and Ubuntu system commands.
# Python library roles and versions: README.md and requirements*.txt.
# Gazebo embeds the Ubuntu Python runtime and needs apt-installed gz bindings.
# Isolate the Gazebo subprocess so it can import the system gz bindings.
set -euo pipefail
cd "$(dirname "$0")/.."
unset VIRTUAL_ENV PYTHONHOME
export PATH="/usr/bin:/bin:$PATH"
export PYTHONPATH="$PWD/src:/usr/lib/python3/dist-packages"
export PYTHONNOUSERSITE=1
exec /usr/bin/gz "$@"
