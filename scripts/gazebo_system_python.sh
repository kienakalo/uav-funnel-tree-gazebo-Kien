#!/usr/bin/env bash
# Gazebo embeds the Ubuntu Python runtime and needs apt-installed gz bindings.
# Isolate the Gazebo subprocess so it can import the system gz bindings.
set -euo pipefail
cd "$(dirname "$0")/.."
unset VIRTUAL_ENV PYTHONHOME
export PATH="/usr/bin:/bin:$PATH"
export PYTHONPATH="$PWD/src:/usr/lib/python3/dist-packages"
export PYTHONNOUSERSITE=1
exec /usr/bin/gz "$@"
