#!/usr/bin/env python3
"""Safely correct the two angle roles in src/funnel_tree.py.

The funnel-tree code needs:
- angle_sides(sp, sv, pv): angle at source s, used by Equation (6)
- angle_sides(pv, sv, sp): angle at destination v, used by clipping

The previous code computed the destination angle twice and used it for
Equation (6), which also corrupted the child funnel's psw state.
"""
from pathlib import Path

path = Path("src/funnel_tree.py")
if not path.is_file():
    raise SystemExit("Cannot find src/funnel_tree.py. Run this from the project root.")

source = path.read_text(encoding="utf-8")

old = """                psv = angle_sides(pv,sv,f.sp)
                if psv >= f.psw:
                    f.q,f.pq,f.spq = v,pv,beta
                    continue
                pvs = angle_sides(pv,sv,f.sp)
                svq = angle_sides(pv,vq,f.pq)-pvs
"""

new = """                # Equation (6): angle p-s-v, measured at the source s.
                psv = angle_sides(f.sp,sv,pv)
                # Procedure 2: angle p-v-z. In the current straight-segment
                # special case, z lies on the unfolded s-v segment, so this
                # is angle p-v-s. The general polyline case needs explicit z.
                pvs = angle_sides(pv,sv,f.sp)
                if psv >= f.psw:
                    f.q,f.pq,f.spq = v,pv,beta
                    continue
                svq = angle_sides(pv,vq,f.pq)-pvs
"""

if old in source:
    backup = path.with_name("funnel_tree.py.before_angle_fix.bak")
    if backup.exists():
        raise SystemExit(
            f"Backup already exists: {backup}. Inspect it before running again."
        )
    backup.write_text(source, encoding="utf-8")
    source = source.replace(old, new, 1)
    compile(source, str(path), "exec")
    path.write_text(source, encoding="utf-8")
    print("PATCH APPLIED")
    print(f"Backup: {backup}")
elif new in source:
    print("Already patched; no changes made.")
else:
    raise SystemExit(
        "Expected code block not found exactly. No file was changed. "
        "Please send the current section around 'psv = angle_sides'."
    )

print("Syntax check: PASS")
