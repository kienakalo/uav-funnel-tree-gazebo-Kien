#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main runtime: Bash; local Python/Gazebo scripts and Ubuntu system commands.
# Python library roles and versions: README.md and requirements*.txt.
set -euo pipefail
. /etc/os-release
if [[ "${ID}" != ubuntu || "${VERSION_ID}" != 24.04 ]]; then
  echo 'This installer targets Ubuntu 24.04. Do not run in PowerShell.' >&2; exit 1
fi
sudo apt-get update
sudo apt-get install -y curl lsb-release gnupg python3 python3-venv python3-numpy unzip
sudo curl --fail --location https://packages.osrfoundation.org/gazebo.gpg --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
sudo apt-get update
sudo apt-get install -y gz-harmonic python3-gz-sim8
echo 'Gazebo installed. Follow README.md to create .venv and run surface_delivery.'
