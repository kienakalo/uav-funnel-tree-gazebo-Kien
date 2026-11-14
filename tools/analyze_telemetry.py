# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main libraries: Python stdlib (csv, math, pathlib).
"""Read Gazebo's actual CSV, preserving moving/hold distinction when available."""
import csv,math
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with (root/'generated/physics_telemetry.csv').open() as f:
    rows=list(csv.DictReader(f))
if not rows:raise SystemExit('No telemetry rows yet.')
for name in ['x','y','z']:
    values=[float(r[name]) for r in rows]
    print(f'{name}: min={min(values):.6f}, max={max(values):.6f}')
errors=[float(r['error']) for r in rows]
print(f'Max position error: {max(errors):.6f}')
print(f'Final position error: {errors[-1]:.9f}')
moving=[float(r['error']) for r in rows if r.get('phase')=='moving']
if moving:
    print(f'RMSE during movement: {math.sqrt(sum(e*e for e in moving)/len(moving)):.6f}')
    print('Last phase:',rows[-1]['phase'])
    print('Visited dwell segment IDs:',sorted({int(r['segment']) for r in rows if r.get('phase')=='dwell'}))
