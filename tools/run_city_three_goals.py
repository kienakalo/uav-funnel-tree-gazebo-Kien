# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Matplotlib, NumPy; Python stdlib (argparse, contextlib, csv, hashlib, heapq,
# io, json, math, os, pathlib, shutil, subprocess, sys, time, xml); local modules
# (analyze_surface_delivery, compare_surface_geodesic, funnel_tree, mesh,
# plan_funnel_delivery, prepare_funnel_gazebo, run_funnel_benchmark, run_funnel_route,
# trajectory).
"""Three independent surface routes from one fixed START on an identical city mesh."""
import argparse
import contextlib
import hashlib
import heapq
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from mesh import read_geom
from funnel_tree import propagate, reconstruct
from trajectory import Trajectory
from run_funnel_route import secondary_sources, candidate_route, write_json
from run_funnel_benchmark import verify
from prepare_funnel_gazebo import simplify
from plan_funnel_delivery import farthest_site
import compare_surface_geodesic as reference
import analyze_surface_delivery as analysis

OUT = ROOT/'generated/city_three_goals'
BASE = ROOT/'generated/funnel_physics/surface_delivery'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def select_cases(mesh, base):
    vertices = np.array([(p.x, p.y, p.z) for p in mesh.points])
    start = np.array(base['fixed_start'])
    existing_selection = dict(base['selection'], vertex=base['surface_goal'],
                              original_navigation_vertex=base['selection']['vertex'])
    cases = [dict(id='g1', region='existing far destination', goal=base['surface_goal'],
                  selection=existing_selection)]
    for name in ('g2', 'g3'):
        mask = np.linalg.norm(vertices[:, :2]-start[:2], axis=1) > 30
        for selected in cases:
            mask &= np.linalg.norm(vertices[:, :2]-vertices[selected['goal'], :2], axis=1) > 45
        indices = np.flatnonzero(mask)
        print(f'Selecting {name}: {len(indices)} spatially separated candidates', flush=True)
        site = farthest_site(vertices[indices], start)
        goal = int(indices[site['vertex']])
        site.update(vertex=goal, selection_scope='farthest eligible mesh vertex at least 45 units from previously selected goals and 30 units from START')
        cases.append(dict(id=name, region='spatially separated city destination', goal=goal, selection=site))
    for i, case in enumerate(cases):
        assert math.dist(vertices[case['goal']][:2], start[:2]) > 30
        for other in cases[:i]:
            assert math.dist(vertices[case['goal']][:2], vertices[other['goal']][:2]) > 40
    return vertices, cases


def solve(mesh, vertices, source, goal, targets, cache, signature, seconds):
    costs, previous, settled = {source: 0.}, {}, set()
    heuristic = np.linalg.norm(vertices-vertices[goal], axis=1)
    queue = [(float(heuristic[source]), 0., source)]
    new_sources, expanded_nodes, cache_hits = 0, 0, 0
    while queue:
        _, cost, s = heapq.heappop(queue)
        if s in settled:
            continue
        if s == goal:
            points, chain = candidate_route(mesh, source, goal, previous)
            return simplify(points), chain, dict(new_sources=new_sources,
                newly_propagated_tree_nodes=expanded_nodes, cached_sources_used=cache_hits,
                settled_sources=len(settled))
        key = str(s)
        if key not in cache['runs']:
            print(f'GOAL {goal}: propagating {s}; cached sources {len(cache["runs"])}', flush=True)
            deadline = time.monotonic()+seconds
            distances, best, stats = propagate(mesh, s, deadline, 200000, True,
                                               target_vertices=targets-{s})
            edges = {}
            for t in sorted(targets-{s}):
                if best[t] is None:
                    continue
                path = reconstruct(mesh, s, best[t], deadline=deadline)
                length = sum(math.dist(a,b) for a,b in zip(path,path[1:]))
                if abs(length-distances[t]) > 1e-6*max(1.,length):
                    raise ValueError('Reconstructed Funnel length differs from propagated distance')
                edges[str(t)] = dict(length=length, path=path)
            cache['runs'][key] = dict(edges=edges, stats=stats)
            write_json(OUT/'funnel_cache.json', cache)
            new_sources += 1
            expanded_nodes += stats['nodes']
        else:
            cache_hits += 1
        settled.add(s)
        for target, edge in cache['runs'][key]['edges'].items():
            t = int(target)
            total = cost+edge['length']
            if t not in settled and total < costs.get(t,math.inf):
                costs[t] = total
                previous[t] = (s,edge)
                heapq.heappush(queue,(total+heuristic[t],total,t))
    raise ValueError(f'Funnel did not reach goal {goal}')


def plan(seconds):
    base = json.loads((BASE/'surface_plan.json').read_text())
    for name, expected in base['input_sha256'].items():
        if digest(ROOT/name) != expected:
            raise ValueError(f'Base surface provenance changed: {name}')
    mesh = read_geom(BASE/'surface.geom')
    vertices, cases = select_cases(mesh,base)
    source = base['surface_source']
    targets = set(secondary_sources(mesh,source)) | {c['goal'] for c in cases}
    signature = hashlib.sha256((BASE/'surface.geom').read_bytes()+
        (ROOT/'src/funnel_tree.py').read_bytes()+Path(__file__).read_bytes()+
        json.dumps([source,sorted(targets)]).encode()).hexdigest()
    cache = dict(signature=signature,runs={})
    if (OUT/'funnel_cache.json').exists():
        saved = json.loads((OUT/'funnel_cache.json').read_text())
        if saved['signature']==signature:
            cache=saved
    manifest = dict(fixed_start=base['fixed_start'],surface_source=source,
        mesh_sha256=digest(BASE/'surface.geom'),mesh_vertices=len(vertices),mesh_faces=len(mesh.faces),
        scope='three independent START-to-GOAL queries on an identical city safety-envelope mesh',
        planning_timing_scope='sequential queries sharing a checkpoint cache; includes reconstruction and checkpoint writes; not a cold-start performance comparison', cases=cases)
    write_json(OUT/'cases.json',manifest)
    preview = json.loads((ROOT/'generated/funnel_preview/route.json').read_text())
    for case in cases:
        folder = OUT/case['id']
        folder.mkdir(exist_ok=True)
        for name in ('surface.geom','surface.stl'):
            shutil.copy2(BASE/name,folder/name)
        started=time.perf_counter()
        path, chain, stats = solve(mesh,vertices,source,case['goal'],targets,cache,signature,seconds)
        planning_seconds=time.perf_counter()-started
        if not verify(mesh,vertices.tolist(),path):
            raise ValueError('Funnel path leaves the shared surface')
        mission=simplify([base['fixed_start'],*path])
        inverse=np.array(mission)/preview['transform']['scale']+preview['transform']['origin']
        original=inverse[:,[0,2,1]]*[1,1,-1]
        inputs=('generated/funnel_preview/city.stl','src/funnel_tree.py','src/mesh.py',
                'tools/run_city_three_goals.py',str((folder/'surface.geom').relative_to(ROOT)))
        result=dict(waypoints=mission,original_waypoints=original.tolist(),
            flight_length=sum(math.dist(a,b) for a,b in zip(mission,mission[1:])),
            original_model_length=sum(math.dist(a,b) for a,b in zip(original,original[1:])),
            surface_waypoints=path,surface_source=source,surface_goal=case['goal'],
            source_chain=chain,fixed_start=base['fixed_start'],selection=case['selection'],
            optimality_certified=False,input_sha256={p:digest(ROOT/p) for p in inputs})
        write_json(folder/'surface_plan.json',result)
        stats.update(planning_seconds=planning_seconds,cache_signature=signature)
        write_json(folder/'planning_stats.json',stats)
        reference.main(folder,folder/'reference')
        compared=json.loads((folder/'reference/comparison.json').read_text())
        if not compared['matches_reference']:
            raise ValueError(f'{case["id"]}: Funnel differs from MMP')
        print(f'{case["id"]}: Funnel/MMP MATCH, length {compared["funnel_length"]:.9f}',flush=True)


def prepare(case):
    subprocess.run([sys.executable,str(ROOT/'tools/prepare_funnel_physics.py'),
        '--case','surface_delivery','--destination',case,'--show-surface'],cwd=ROOT,check=True)


def simulate(case):
    folder=OUT/case
    prepare(case)
    route=json.loads((folder/'route.json').read_text())
    trajectory=Trajectory(route['waypoints'],route['speed'],dwell=route['dwell'],
        max_acceleration=route['max_acceleration'],descent_speed=route['descent_speed'])
    tree=ET.parse(folder/'funnel_physics.sdf')
    world=tree.getroot().find('world')
    world.find('physics/real_time_factor').text='0'
    gui=world.find('gui')
    if gui is not None:
        world.remove(gui)
    filename=folder/'headless.sdf'
    tree.write(filename,encoding='utf-8',xml_declaration=True)
    duration=trajectory.duration+route['start_delay']+10.
    step=float(world.findtext('physics/max_step_size'))
    env=dict(os.environ,GZ_PARTITION=f'city-three-goals-{case}-{time.time_ns()}',
        FUNNEL_PHYSICS_CASE='surface_delivery',FUNNEL_OUTPUT_DIR=str(folder.relative_to(ROOT)),
        FUNNEL_RUN_ID=f'city-three-goals-{case}-{time.time_ns()}')
    with (folder/'gazebo.log').open('w') as log:
        subprocess.run(['bash','scripts/gazebo_system_python.sh','sim','-s','-r',
            '--iterations',str(math.ceil(duration/step)),str(filename)],cwd=ROOT,env=env,
            stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
    analysis.main(folder)


def summarize():
    manifest=json.loads((OUT/'cases.json').read_text())
    rows=[]
    for case in manifest['cases']:
        folder=OUT/case['id']
        plan=json.loads((folder/'surface_plan.json').read_text())
        compared=json.loads((folder/'reference/comparison.json').read_text())
        physics=json.loads((folder/'surface_validation.json').read_text())
        stats=json.loads((folder/'planning_stats.json').read_text())
        route=json.loads((folder/'route.json').read_text())
        if not (digest(folder/'surface.geom')==manifest['mesh_sha256']==compared['mesh_sha256']==physics['surface_mesh_sha256']):
            raise ValueError('Mesh fingerprints differ between cases or results')
        if digest(folder/'route.json')!=physics['route_sha256'] or digest(folder/'physics_telemetry.csv')!=physics['telemetry_sha256']:
            raise ValueError('Telemetry or route fingerprint changed')
        if plan['surface_source']!=manifest['surface_source'] or plan['fixed_start']!=manifest['fixed_start']:
            raise ValueError('Cases do not share the fixed START')
        if not physics['checks_passed'] or not compared['matches_reference']:
            raise ValueError('An experiment failed')
        trajectory=Trajectory(route['waypoints'],route['speed'],dwell=route['dwell'],
            max_acceleration=route['max_acceleration'],descent_speed=route['descent_speed'])
        import csv
        telemetry=list(csv.DictReader((folder/'physics_telemetry.csv').open()))
        moving=[float(r['error']) for r in telemetry if r['phase'] in ('moving','descending')]
        rows.append(dict(id=case['id'],region=case['region'],goal_xyz=route['waypoints'][-1],
            surface_goal=case['goal'],funnel_length=compared['funnel_length'],
            exact_reference_length=compared['exact_reference_length'],excess=compared['excess_length'],
            reference_seconds=compared['reference_seconds'],**stats,
            nominal_simulation_seconds=trajectory.duration+route['start_delay'],
            moving_rmse=math.sqrt(sum(e*e for e in moving)/len(moving)),
            max_measured_speed=max(math.sqrt(sum(float(r[k])**2 for k in ('vx','vy','vz'))) for r in telemetry),
            validation=physics))
    result=dict(all_passed=True,mesh_sha256=manifest['mesh_sha256'],fixed_start=manifest['fixed_start'],
        mesh_vertices=manifest['mesh_vertices'],mesh_faces=manifest['mesh_faces'],
        scope=manifest['scope'],planning_timing_scope=manifest['planning_timing_scope'],cases=rows)
    write_json(OUT/'results.json',result)
    lines=['# Ba tuyến trên cùng bề mặt thành phố','',
        'Ba truy vấn độc lập, cùng START và cùng SHA256 lưới. Không phải hành trình ghé ba đích.',
        'Đối chiếu MMP chỉ gồm chặng trên bề mặt; mô phỏng gồm tiếp cận và hạ giao hàng.', '',
        '| Ca | Funnel | MMP | Thời gian kế hoạch bay (s) | Sai số bám lớn nhất | Khoảng hở lấy mẫu nhỏ nhất |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for row in rows:
        v=row['validation']
        lines.append(f'| {row["id"]} | {row["funnel_length"]:.9f} | {row["exact_reference_length"]:.9f} | {row["nominal_simulation_seconds"]:.3f} | {v["max_tracking_error"]:.6f} | {v["min_sampled_city_clearance_under_body"]:.6f} |')
    lines+=['','Thời gian lập tuyến trong JSON là các truy vấn nối tiếp dùng chung cache, bao gồm ghi checkpoint; không dùng để so sánh hiệu năng cold-start.',
        'Mô phỏng khối điểm 1 kg trong Gazebo không giao diện, bước vật lý 0,002 s. Khoảng hở là kiểm tra lấy mẫu, không phải chứng minh va chạm liên tục.',
        'Khớp MMP là kiểm chứng số cho ba ca trên bề mặt an toàn đã dựng, không phải chứng minh đúng tổng quát cho mọi lưới.']
    (OUT/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    plot(manifest,rows)
    for name in ('cases.json','results.json','summary.md','routes.png'):
        print(f'Save at: {OUT/name}',flush=True)


def plot(manifest,rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    mesh=read_geom(BASE/'surface.geom')
    p=np.array([(v.x,v.y,v.z) for v in mesh.points])
    fig=plt.figure(figsize=(13,6))
    ax=fig.add_subplot(121,projection='3d')
    ax.plot_trisurf(p[:,0],p[:,1],p[:,2],triangles=np.array(mesh.faces),color='#9ed9e5',alpha=.3,linewidth=.1)
    flat=fig.add_subplot(122)
    flat.triplot(p[:,0],p[:,1],np.array(mesh.faces),color='#bbd9df',linewidth=.25)
    for row,color in zip(rows,('#e07b19','#137eb0','#9c348c')):
        data=json.loads((OUT/row['id']/'route.json').read_text())
        path=np.array(data['waypoints'])
        ax.plot(*path.T,color=color,label=row['id'].upper(),linewidth=2)
        flat.plot(path[:,0],path[:,1],color=color,label=f'{row["id"].upper()}: {row["funnel_length"]:.3f}',linewidth=2)
        flat.scatter(*path[-1,:2],color=color)
        flat.annotate(row['id'].upper(),path[-1,:2],xytext=(5,5),textcoords='offset points')
    start=manifest['fixed_start']
    flat.scatter(*start[:2],color='black',marker='*',s=100,label='Fixed START')
    for axis in (ax,flat):
        axis.set_xlabel('Gazebo X (simulation units)')
        axis.set_ylabel('Gazebo Y (simulation units)')
        axis.legend()
    ax.set_zlabel('Gazebo Z')
    ax.set_title('Same 3D safety-envelope mesh')
    flat.set_title('Three independent routes from one START')
    flat.set_aspect('equal')
    fig.tight_layout()
    fig.savefig(OUT/'routes.png',dpi=160)
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('select','plan','simulate','analyze','all'),default='all')
    parser.add_argument('--destination',choices=('g1','g2','g3'))
    parser.add_argument('--seconds',type=float,default=40.)
    args=parser.parse_args()
    OUT.mkdir(exist_ok=True)
    if args.stage=='select':
        base=json.loads((BASE/'surface_plan.json').read_text())
        _,cases=select_cases(read_geom(BASE/'surface.geom'),base)
        print(json.dumps(cases,indent=2),flush=True)
        return
    if args.stage in ('all','plan'):
        plan(args.seconds)
    if args.stage in ('all','simulate'):
        for case in ([args.destination] if args.destination else ['g1','g2','g3']):
            simulate(case)
    if args.stage=='analyze':
        for case in ([args.destination] if args.destination else ['g1','g2','g3']):
            analysis.main(OUT/case)
    if args.stage in ('all','simulate','analyze'):
        summarize()


if __name__=='__main__':
    main()
