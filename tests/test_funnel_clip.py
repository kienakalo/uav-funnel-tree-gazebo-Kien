#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (pathlib, sys); local modules (funnel_clip).
"""Run the Procedure 2 unit tests."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from funnel_clip import _self_test

if __name__ == "__main__":
    _self_test()
