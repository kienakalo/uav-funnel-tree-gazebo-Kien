# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main libraries: NumPy, Matplotlib, Shapely (via surface builder), pygeodesic;
# Python stdlib: argparse, hashlib, json, math, pathlib, platform, resource,
# subprocess, sys, time; local planning and verification modules.
"""Evaluate three city-surface cell sizes without changing the delivery demo."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import plan_surface_delivery as planner
import compare_surface_geodesic as reference
from city import write_stl
from build_navigation_surface import write_geom
from run_funnel_benchmark import verify
from run_funnel_route import write_json

OUT=ROOT/'generated/surface_sensitivity'
CELLS=(5.,7.5,15.)


def case(cell):
    folder=OUT/f'cell_{cell:g}'
    folder.mkdir(parents=True,exist_ok=True)
    flat=json.loads((ROOT/'generated/funnel_physics/delivery/horizontal_plan.json').read_text())
    start=np.array(flat['fixed_start'])
    goal=np.r_[flat['waypoints'][-1][:2],flat['selection']['ground_z']+1.1]
    begin=time.perf_counter()
    mesh,points,faces,source,target,stats=planner.build_surface(start,goal,cell,'city')
    build_seconds=time.perf_counter()-begin
    write_geom(folder/'surface.geom',points,faces,stats['edges'])
    write_stl(folder/'surface.stl',points,faces)
    signature=hashlib.sha256((folder/'surface.geom').read_bytes()+
        (ROOT/'src/funnel_tree.py').read_bytes()+(ROOT/'src/mesh.py').read_bytes()+
        json.dumps([source,target]).encode()).hexdigest()
    # A fresh cache per subprocess makes the reported solve a cold computation.
    # Retain previous attempts as separate files rather than counting them as cold.
    cache=folder/'funnel_cache.json'
    if cache.exists():
        cache.rename(folder/f'funnel_cache_previous_{time.time_ns()}.json')
    planner.OUT=folder
    begin=time.perf_counter()
    path,chain,runs=planner.funnel_route(mesh,source,target,signature,60.)
    funnel_seconds=time.perf_counter()-begin
    if not verify(mesh,points.tolist(),path):
        raise ValueError('Funnel route is not on the constructed mesh')
    plan=dict(surface_source=source,surface_goal=target,surface_waypoints=path,
        input_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
        ('src/funnel_tree.py','src/mesh.py','tools/plan_surface_delivery.py','tools/run_surface_sensitivity.py')})
    write_json(folder/'surface_plan.json',plan)
    reference.main(folder,folder/'reference')
    ref=json.loads((folder/'reference/comparison.json').read_text())
    if not ref['matches_reference']:
        raise ValueError(f'Cell {cell}: Funnel differs from MMP')
    cache_data=json.loads(cache.read_text())
    total_nodes=sum(r['stats']['nodes'] for r in cache_data['runs'].values())
    length=sum(math.dist(a,b) for a,b in zip(path,path[1:]))
    result=dict(cell_size=cell,mesh=stats,source=source,goal=target,
        fixed_start=start.tolist(),delivery_goal=goal.tolist(),
        surface_start=path[0],surface_goal=path[-1],
        xy_bounds=[points[:,:2].min(axis=0).tolist(),points[:,:2].max(axis=0).tolist()],
        vertical_clearance=planner.CLEARANCE,horizontal_half_width=planner.HALF_WIDTH,
        max_axis_slope=planner.MAX_AXIS_SLOPE,
        funnel_length=length,reference_length=ref['exact_reference_length'],
        excess=ref['excess_length'],matches_reference=ref['matches_reference'],
        route_altitude_range=[min(p[2] for p in path),max(p[2] for p in path)],
        surface_altitude_range=[float(points[:,2].min()),float(points[:,2].max())],
        entry_length=math.dist(start,path[0]),descent_length=math.dist(path[-1],goal),
        total_geometric_mission_length=math.dist(start,path[0])+length+math.dist(path[-1],goal),
        build_seconds=build_seconds,funnel_seconds=funnel_seconds,source_runs=runs,
        propagated_tree_nodes=total_nodes,
        process_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        memory_scope='Linux process high-water RSS through build, Funnel and MMP; includes imported libraries, city data, reference solver and cache; not Funnel-only memory',
        timing_scope='one cold computation per cell; Funnel time includes reconstruction and checkpoint writes; no repetitions or statistical speedup claim',
        mesh_sha256=hashlib.sha256((folder/'surface.geom').read_bytes()).hexdigest())
    write_json(folder/'results.json',result)
    print(json.dumps(result,indent=2),flush=True)


def summarize():
    rows=[json.loads((OUT/f'cell_{c:g}/results.json').read_text()) for c in CELLS]
    assert all(r['xy_bounds']==rows[0]['xy_bounds'] for r in rows)
    assert all(r['fixed_start']==rows[0]['fixed_start'] and r['delivery_goal']==rows[0]['delivery_goal'] for r in rows)
    report=dict(cases=rows,all_match_reference=all(r['matches_reference'] for r in rows),
        scope='cell-size sensitivity on conservative height envelopes; fixed city, XY domain, physical START and delivery point; geodesic endpoint Z changes with each envelope; different meshes are different optimization domains',
        environment=dict(platform=platform.platform(),python=sys.version,
            cpu=subprocess.check_output(['lscpu'],text=True),
            memory=subprocess.check_output(['free','-b'],text=True)))
    write_json(OUT/'results.json',report)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    axes[0].plot(CELLS,[r['funnel_length'] for r in rows],'o-',label='Surface geodesic')
    axes[0].plot(CELLS,[r['total_geometric_mission_length'] for r in rows],'s--',label='Entry + surface + descent')
    axes[0].set(xlabel='Nominal cell size (simulation units)',ylabel='Geometric length',title='Effect on the planning geometry')
    axes[0].legend()
    for r in rows:
        p=np.array(json.loads((OUT/f'cell_{r["cell_size"]:g}/surface_plan.json').read_text())['surface_waypoints'])
        cumulative=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
        axes[1].plot(cumulative,p[:,2],label=f'Cell {r["cell_size"]:g}')
    axes[1].set(xlabel='Distance along surface route',ylabel='Gazebo Z',title='Surface-route altitude')
    axes[1].legend()
    for ax in axes: ax.grid(alpha=.25)
    fig.tight_layout();fig.savefig(OUT/'comparison.png',dpi=180);plt.close(fig)
    lines=['# Ảnh hưởng của kích thước ô','',
        'Giữ nguyên mô hình thành phố, miền ngang, tọa độ START và điểm giao hàng; khoảng hở đứng 1,5, dự phòng ngang 1,6 và hệ số dốc theo trục 0,5.',
        'Cao độ hai đầu chặng geodesic thay đổi theo bề mặt. Vì vậy đây là so sánh các miền tối ưu khác nhau, không phải kiểm tra hội tụ trên một bề mặt cố định.', '',
        '| Ô | Đỉnh | Tam giác | Funnel | MMP | Tổng hình học nhiệm vụ | Thời gian Funnel (s) | Nguồn | Nút cây mới | Peak RSS tiến trình (MiB) |',
        '|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f'| {r["cell_size"]:g} | {r["mesh"]["vertices"]} | {r["mesh"]["triangles"]} | {r["funnel_length"]:.6f} | {r["reference_length"]:.6f} | {r["total_geometric_mission_length"]:.6f} | {r["funnel_seconds"]:.3f} | {r["source_runs"]} | {r["propagated_tree_nodes"]} | {r["process_peak_rss_mib"]:.1f} |')
    lines+=['','Mỗi cấu hình được tính trong một tiến trình riêng, cache mới. Chỉ đo một lượt; thời gian gồm ghi checkpoint, không suy ra mức tăng tốc thống kê.',
        'Peak RSS là high-water mark của cả tiến trình đến sau MMP, không phải bộ nhớ riêng của Funnel.',
        'Thí nghiệm này kiểm tra hình học và MMP, chưa chạy lại mô phỏng bám tuyến cho từng kích thước ô.']
    (OUT/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for name in ('results.json','summary.md','comparison.png'):
        print(f'Save at: {OUT/name}',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cell',type=float,choices=CELLS)
    args=parser.parse_args()
    OUT.mkdir(exist_ok=True)
    if args.cell is not None:
        case(args.cell);return
    for cell in CELLS:
        subprocess.run([sys.executable,str(Path(__file__).resolve()),'--cell',str(cell)],cwd=ROOT,check=True)
    summarize()


if __name__=='__main__':main()
