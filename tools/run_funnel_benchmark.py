#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main libraries: Matplotlib, NumPy; Python stdlib (argparse, hashlib, heapq, json, math,
# pathlib, sys, time); local modules (funnel_tree, mesh, run_funnel_route, verification).
"""Four reproducible route tests on one mesh, with a shared resumable Funnel cache.

This tests planning and geometric coverage, not Gazebo flight or global
optimality. Cached and newly computed source runs are reported separately.
"""
import argparse
import hashlib
import heapq
import json
import math
from pathlib import Path
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from mesh import Mesh, Point, read_geom
from funnel_tree import propagate, reconstruct
from verification import segment_on_mesh, edge_distances, path_length
from run_funnel_route import secondary_sources, candidate_route, write_json

OUT=ROOT/'generated/funnel_benchmark'


def choose_corridor():
    """Find a short straight run with nearby blocked cells on both cross sides."""
    with np.load(ROOT/'generated/navigation_y2p00_grid.npz') as data:
        free=data['labels']==int(data['component'])
        origin=data['origin'].copy()
        cell=float(data['cell'])
    options=[]
    centre=np.array(free.shape)/2
    for i,j in zip(*np.where(free)):
        for axis in (0,1):
            along=np.eye(2,dtype=int)[axis]
            across=np.eye(2,dtype=int)[1-axis]
            p=np.array([i,j])
            def available(q):
                return bool(np.all(q>=0) and np.all(q<free.shape) and free[tuple(q)])
            if not all(available(p+offset*along) for offset in range(-2,3)):
                continue
            widths=[]
            for sign in (-1,1):
                width=0
                while width<6 and available(p+sign*(width+1)*across):
                    width+=1
                widths.append(width)
            if max(widths)>=6:
                continue
            options.append((sum(widths)+1,float(np.linalg.norm(p-centre)),int(i),int(j),axis))
    if not options:
        raise ValueError('No narrow straight run found; do not silently substitute another case')
    width,_,i,j,axis=min(options)
    p=np.array([i,j]);direction=np.eye(2,dtype=int)[axis]
    a=origin+(p-2*direction+.5)*cell
    b=origin+(p+2*direction+.5)*cell
    return a,b,{'cross_section_free_cells':width,'cross_section_width_model_units':width*cell,
                'grid_cell':[i,j],'along_axis':'X' if axis==0 else 'Z',
                'scope':'local grid cross-section; not UAV clearance certification'}


def prepare_cases():
    base=read_geom(ROOT/'generated/funnel_input_y2p00.geom')
    old=json.loads((ROOT/'generated/funnel_input_y2p00_report.json').read_text())
    narrow_a,narrow_b,narrow_info=choose_corridor()
    specifications=[
        ('short_open','Short route in an open area',(5.,-5.),(8.,-8.)),
        ('cross_city','Detour across the central obstacle region',(8.,-20.),(45.,-20.)),
        ('narrow_corridor','Short route along a narrow grid corridor',narrow_a,narrow_b)]
    vertices=[(p.x,p.y,p.z) for p in base.points]
    centres=np.array([[sum(vertices[v][k] for v in face)/3 for k in (0,2)] for face in base.faces])
    chosen={}
    cases=[{'id':'original','description':'Original validated START-GOAL pair',
            'source':old['source_vertex'],'goal':old['goal_vertex']}]
    for name,description,a,b in specifications:
        pair=[]
        for requested in (a,b):
            distances=np.linalg.norm(centres-np.array(requested),axis=1)
            face_id=next(int(fid) for fid in np.argsort(distances) if int(fid) not in chosen)
            face=base.faces[face_id]
            coordinate=tuple(sum(vertices[v][k] for v in face)/3 for k in range(3))
            index=len(vertices)
            vertices.append(coordinate)
            chosen[face_id]=index
            pair.append(index)
        row={'id':name,'description':description,'source':pair[0],'goal':pair[1],
             'requested_xz':[list(map(float,a)),list(map(float,b))]}
        if name=='narrow_corridor':
            row['corridor_selection']=narrow_info
        cases.append(row)
    faces=[]
    for fid,(a,b,c) in enumerate(base.faces):
        if fid in chosen:
            v=chosen[fid]
            faces.extend([(a,b,v),(b,c,v),(c,a,v)])
        else:
            faces.append((a,b,c))
    mesh=Mesh([Point(*p) for p in vertices],faces)
    for case in cases:
        case['start_xyz']=vertices[case['source']]
        case['goal_xyz']=vertices[case['goal']]
    return mesh,cases


def verify(mesh,points,path):
    triangles=np.array(points)[np.array(mesh.faces)]
    lows,highs=triangles.min(axis=1),triangles.max(axis=1)
    for a,b in zip(path,path[1:]):
        low,high=np.minimum(a,b)-1e-7,np.maximum(a,b)+1e-7
        ids=np.flatnonzero(np.all(highs>=low,axis=1)&np.all(lows<=high,axis=1))
        if not segment_on_mesh(a,b,points,[mesh.faces[int(i)] for i in ids],1e-7):
            return False
    return True


def plot_results(mesh,results):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    vertices=np.array([(p.x,p.z) for p in mesh.points])
    triangles=vertices[np.array(mesh.faces)]
    fig,axes=plt.subplots(2,2,figsize=(13,11))
    for ax,row in zip(axes.flat,results):
        ax.set_facecolor('#e3e6e9')
        ax.add_collection(PolyCollection(triangles,facecolors='#d7eadc',edgecolors='none'))
        a,b=np.array(row['start_xyz'])[[0,2]],np.array(row['goal_xyz'])[[0,2]]
        ax.scatter(*a,color='#167a40',s=25,zorder=4)
        ax.scatter(*b,color='#b51f41',s=25,zorder=4)
        if row.get('route_file'):
            path=np.array(json.loads((OUT/row['route_file']).read_text())['points'])
            ax.plot(path[:,0],path[:,2],color='#db6a0e',linewidth=2)
        ax.autoscale()
        ax.set_aspect('equal')
        ax.set(xlabel='X (model units)',ylabel='Z (model units)',
               title=f"{row['id']}: {row['status']}"+(f" | L={row['length']:.3f}" if 'length' in row else ''))
        if row['id'] in ('short_open','narrow_corridor'):
            low=np.minimum(a,b)-2;high=np.maximum(a,b)+2
            ax.set_xlim(low[0],high[0]);ax.set_ylim(low[1],high[1])
    fig.suptitle('Funnel planning regression cases | original Y = 2\nGeometric tests only; global optimality is not certified')
    fig.tight_layout(rect=(0,0,1,.94))
    path=OUT/'benchmark_routes.png'
    fig.savefig(path,dpi=160)
    plt.close(fig)
    print(f'Save at: {path}',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-runs',type=int,default=150,help='Maximum new source runs across all cases')
    parser.add_argument('--seconds',type=float,default=20.,help='Time budget per source')
    args=parser.parse_args()
    if args.max_runs<1 or not math.isfinite(args.seconds) or args.seconds<=0:
        parser.error('Budgets must be finite and positive')
    OUT.mkdir(exist_ok=True)
    mesh,cases=prepare_cases()
    points=[(p.x,p.y,p.z) for p in mesh.points]
    sources=set(secondary_sources(mesh,cases[0]['source']))
    endpoints={case[key] for case in cases for key in ('source','goal')}
    targets=sources|endpoints
    signature=hashlib.sha256()
    for path in (ROOT/'generated/funnel_input_y2p00.geom',ROOT/'generated/navigation_y2p00_grid.npz',
                 ROOT/'src/funnel_tree.py',ROOT/'src/mesh.py',Path(__file__),ROOT/'tools/run_funnel_route.py',
                 ROOT/'src/verification.py'):
        signature.update(path.read_bytes())
    signature.update(json.dumps(cases,sort_keys=True).encode())
    token=signature.hexdigest()
    cache_path=OUT/'source_cache.json'
    cache={'signature':token,'runs':{}}
    if cache_path.exists():
        saved=json.loads(cache_path.read_text())
        if saved.get('signature')==token:
            cache=saved
    write_json(OUT/'cases.json',{'signature':token,'cases':cases,'vertices':len(points),'faces':len(mesh.faces)})
    results=[]
    new_runs=0
    interrupted=False
    for case in cases:
        row=dict(case)
        if interrupted:
            row['status']='pending'
            results.append(row)
            continue
        source,goal=case['source'],case['goal']
        distances,previous={source:0.},{}
        queue=[(0.,source)]
        settled=set()
        allowed=(sources-{cases[0]['source']})|{source,goal}
        started=time.monotonic()
        before=new_runs
        print(f"CASE {case['id']}: START {source} -> GOAL {goal}",flush=True)
        while queue:
            cost,s=heapq.heappop(queue)
            if s in settled:
                continue
            if s==goal:
                path,chain=candidate_route(mesh,source,goal,previous)
                length=path_length(path)
                covered=verify(mesh,points,path)
                lower=math.dist(points[source],points[goal])
                upper=edge_distances(points,mesh.faces,source)[goal]
                endpoints_ok=math.dist(path[0],points[source])<1e-7 and math.dist(path[-1],points[goal])<1e-7
                covered=covered and endpoints_ok and abs(length-cost)<=1e-6*max(1.,cost) and length>=lower-1e-7
                quality=length<=upper+1e-6
                row.update(status='PASS' if covered and quality else 'WARN' if covered else 'FAIL',
                           length=length,surface_membership_passed=covered,euclidean_lower_bound=lower,
                           mesh_edge_reference_length=upper,no_longer_than_mesh_edge_reference=quality,
                           source_chain=chain,segments=len(path)-1,route_file=f"{case['id']}_route.json")
                write_json(OUT/row['route_file'],{'signature':token,'points':path,'case':case,
                                               'length':length,'optimality_certified':False})
                break
            key=str(s)
            if key not in cache['runs']:
                if new_runs>=args.max_runs:
                    row.update(status='checkpoint',next_source=s)
                    interrupted=True
                    break
                deadline=time.monotonic()+args.seconds
                try:
                    ds,best,stats=propagate(mesh,s,deadline,200000,True,target_vertices=targets-{s})
                    edges={}
                    for target in sorted(targets-{s}):
                        if best[target] is None:
                            continue
                        path=reconstruct(mesh,s,best[target],deadline=deadline)
                        length=path_length(path)
                        if not math.isfinite(length) or abs(length-ds[target])>1e-6*max(1.,length):
                            raise ValueError('Source edge length mismatch')
                        edges[str(target)]={'path':path,'length':length}
                except (RuntimeError,TimeoutError,ValueError) as exc:
                    row.update(status='source_stopped',stopped_source=s,error=f'{type(exc).__name__}: {exc}')
                    interrupted=True
                    break
                cache['runs'][key]={'edges':edges,'stats':stats}
                write_json(cache_path,cache)
                new_runs+=1
                if new_runs%10==0 or new_runs==1:
                    print(f"  New source runs: {new_runs}; cached sources: {len(cache['runs'])}",flush=True)
            settled.add(s)
            for text,edge in cache['runs'][key]['edges'].items():
                target=int(text)
                if target not in allowed or target in settled:
                    continue
                total=cost+edge['length']
                if total<distances.get(target,math.inf):
                    distances[target]=total
                    previous[target]=(s,edge)
                    heapq.heappush(queue,(total,target))
        else:
            row.update(status='no_route_in_funnel_graph')
        row.update(seconds_including_validation=time.monotonic()-started,new_source_runs=new_runs-before,
                   settled_sources=len(settled))
        results.append(row)
        print(f"  {row['status']}"+(f" | length={row['length']:.6f}" if 'length' in row else ''),flush=True)
        write_json(OUT/'benchmark_results.json',{'signature':token,'cases':results,'complete':False})
    complete=not interrupted
    passed=complete and all(row['status']=='PASS' for row in results)
    report={'signature':token,'complete':complete,'all_cases_passed':passed,'cases':results,
            'cached_sources':len(cache['runs']),'new_source_runs':new_runs,
            'timing_scope':'shared cache, sequential cases, includes validation; not an uncached runtime comparison',
            'optimality_certified':False,'gazebo_flight_tested_for_new_cases':False}
    write_json(OUT/'benchmark_results.json',report)
    lines=['FUNNEL PLANNING REGRESSION TESTS','']
    for row in results:
        lines.append(f"{row['id']}: {row['status']}"+(f" | length={row['length']:.6f} | mesh-edge reference={row['mesh_edge_reference_length']:.6f}" if 'length' in row else ''))
    lines.extend(['',f'Complete: {complete}',f'All cases passed: {passed}',
                  'Scope: candidate route geometry only; no global optimality or new Gazebo flight certification.',
                  'Timing uses shared cache; do not compare case times as uncached planner performance.'])
    (OUT/'benchmark_summary.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    plot_results(mesh,results)
    for filename in ('cases.json','benchmark_results.json','benchmark_summary.txt'):
        print(f'Save at: {OUT / filename}',flush=True)
    print(f'Complete: {complete}; all cases passed: {passed}',flush=True)
    if interrupted:
        print('Progress saved. Repeat this command to resume; inspect source_stopped errors before increasing budgets.',flush=True)
    elif not passed:
        raise SystemExit(1)


if __name__=='__main__':
    main()
