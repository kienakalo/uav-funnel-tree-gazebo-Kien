#!/usr/bin/env python3
"""Compare Funnel candidates with an independent planar polygon visibility graph.

Visibility edges use the unexpanded union of navigation triangles and every
non-collinear boundary corner. No Funnel propagation or mesh-edge path is used
to construct the reference routes. Results are numerical evidence for these
cases, not a general certification of the experimental Funnel implementation.
"""
import hashlib
import heapq
import json
import math
from pathlib import Path
import sys
import time
import numpy as np
from shapely.geometry import LineString, Point as GeoPoint, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from mesh import read_geom


def make_domain(mesh):
    heights=[p.y for p in mesh.points]
    if max(heights)-min(heights)>1e-9:
        raise ValueError('This reference supports horizontal navigation surfaces only')
    triangles=[Polygon([(mesh.points[v].x,mesh.points[v].z) for v in face]) for face in mesh.faces]
    domain=unary_union(triangles)
    if domain.geom_type!='Polygon' or not domain.is_valid:
        raise ValueError('Expected one valid polygon with optional holes; no geometry repair is applied')
    if abs(domain.area-sum(triangle.area for triangle in triangles))>1e-8:
        raise ValueError('Triangle union area mismatch')
    return domain


def corners(domain):
    result=[]
    for ring in (domain.exterior,*domain.interiors):
        points=list(ring.coords)[:-1]
        for i,b in enumerate(points):
            a,c=points[i-1],points[(i+1)%len(points)]
            cross=(b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])
            if abs(cross)>1e-12:
                result.append(tuple(b))
    return result


def visibility_graph(domain,endpoints):
    vertices=list(dict.fromkeys(corners(domain)+[tuple(p) for p in endpoints]))
    lookup={p:i for i,p in enumerate(vertices)}
    surface=prep(domain)
    if any(not surface.covers(GeoPoint(p)) for p in endpoints):
        raise ValueError('Reference endpoint is outside the navigation polygon')
    graph=[[] for _ in vertices]
    edge_count=0
    for i,a in enumerate(vertices):
        for j in range(i):
            b=vertices[j]
            if surface.covers(LineString([a,b])):
                weight=math.dist(a,b)
                graph[i].append((j,weight));graph[j].append((i,weight))
                edge_count+=1
    return vertices,lookup,graph,edge_count


def shortest_path(vertices,lookup,graph,a,b):
    source,goal=lookup[tuple(a)],lookup[tuple(b)]
    distances={source:0.};previous={}
    queue=[(0.,source)]
    while queue:
        cost,v=heapq.heappop(queue)
        if cost!=distances[v]:
            continue
        if v==goal:
            path=[v]
            while path[-1]!=source:
                path.append(previous[path[-1]])
            return [vertices[i] for i in reversed(path)],cost
        for target,weight in graph[v]:
            total=cost+weight
            if total<distances.get(target,math.inf):
                distances[target]=total;previous[target]=v
                heapq.heappush(queue,(total,target))
    raise ValueError('Visibility graph found no reference route')


def self_test():
    rectangle=Polygon([(0,0),(2,0),(2,2),(0,2)])
    v,index,g,_=visibility_graph(rectangle,[(0,0),(2,2)])
    _,length=shortest_path(v,index,g,(0,0),(2,2))
    if abs(length-math.sqrt(8))>1e-10:
        raise AssertionError('Rectangle analytic test failed')
    ring=Polygon([(0,0),(6,0),(6,6),(0,6)],holes=[[(2,2),(4,2),(4,4),(2,4)]])
    if ring.covers(LineString([(1,3),(5,3)])):
        raise AssertionError('Hole failed to block direct segment')
    v,index,g,_=visibility_graph(ring,[(1,3),(5,3)])
    path,length=shortest_path(v,index,g,(1,3),(5,3))
    if abs(length-(2+2*math.sqrt(2)))>1e-10 or not ring.covers(LineString(path)):
        raise AssertionError('Polygon-hole analytic test failed')
    print('Independent reference self-tests: PASS',flush=True)


def main():
    self_test()
    benchmark=ROOT/'generated/funnel_benchmark'
    manifest=json.loads((benchmark/'cases.json').read_text())
    report=json.loads((benchmark/'benchmark_results.json').read_text())
    if not report['complete'] or manifest['signature']!=report['signature']:
        raise ValueError('Benchmark is incomplete or inconsistent')
    mesh_path=ROOT/'generated/funnel_input_y2p00.geom'
    mesh=read_geom(mesh_path)
    cases=manifest['cases']
    digest=hashlib.sha256()
    for path in (mesh_path,ROOT/'generated/navigation_y2p00_grid.npz',ROOT/'src/funnel_tree.py',
                 ROOT/'src/mesh.py',ROOT/'tools/run_funnel_benchmark.py',ROOT/'tools/run_funnel_route.py',
                 ROOT/'src/verification.py'):
        digest.update(path.read_bytes())
    digest.update(json.dumps(cases,sort_keys=True).encode())
    if digest.hexdigest()!=report['signature']:
        raise ValueError('Benchmark inputs changed; rerun the benchmark first')
    domain=make_domain(mesh)
    endpoints=[(case[key][0],case[key][2]) for case in cases for key in ('start_xyz','goal_xyz')]
    print(f'Navigation polygon: area={domain.area:.6f}; holes={len(domain.interiors)}; corners={len(corners(domain))}',flush=True)
    started=time.monotonic()
    vertices,index,graph,edge_count=visibility_graph(domain,endpoints)
    print(f'Visibility graph: {len(vertices)} vertices; {edge_count} edges; {time.monotonic()-started:.2f}s',flush=True)
    out=ROOT/'generated/funnel_reference'
    out.mkdir(exist_ok=True)
    rows=[]
    expanded=domain.buffer(1e-7)
    for case in cases:
        bench_row=next(row for row in report['cases'] if row['id']==case['id'])
        candidate_path=benchmark/bench_row['route_file']
        candidate=json.loads(candidate_path.read_text())
        if candidate['signature']!=report['signature']:
            raise ValueError('Stale Funnel route')
        a,b=[(case[key][0],case[key][2]) for key in ('start_xyz','goal_xyz')]
        reference,length=shortest_path(vertices,index,graph,a,b)
        funnel=[(p[0],p[2]) for p in candidate['points']]
        measured_length=sum(math.dist(p,q) for p,q in zip(funnel,funnel[1:]))
        if abs(measured_length-candidate['length'])>1e-8:
            raise ValueError('Funnel route length is inconsistent')
        valid=expanded.covers(LineString(funnel)) and math.dist(funnel[0],a)<1e-7 and math.dist(funnel[-1],b)<1e-7
        ref_valid=domain.covers(LineString(reference))
        delta=measured_length-length
        tolerance=1e-6+1e-8*length
        status=('INCONSISTENT' if not valid or not ref_valid or delta < -tolerance else
                'MATCHES_REFERENCE' if abs(delta)<=tolerance else 'LONGER_THAN_REFERENCE')
        row={'case':case['id'],'status':status,'funnel_length':measured_length,'reference_length':length,
             'excess_length':delta,'excess_percent':100*delta/length,'length_tolerance':tolerance,
             'funnel_covered_with_1e_minus_7_tolerance':bool(valid),'reference_covered_exactly':bool(ref_valid),
             'reference_points_xz':reference,'funnel_route_sha256':hashlib.sha256(candidate_path.read_bytes()).hexdigest()}
        rows.append(row)
        print(f"{case['id']}: {status} | Funnel={measured_length:.6f}; reference={length:.6f}; excess={row['excess_percent']:.4f}%",flush=True)
    output={'method':'polygon visibility graph over all non-collinear boundary corners and endpoints',
            'mesh_sha256':hashlib.sha256(mesh_path.read_bytes()).hexdigest(),'benchmark_signature':report['signature'],
            'domain_area':domain.area,'holes':len(domain.interiors),'graph_vertices':len(vertices),'graph_edges':edge_count,
            'cases':rows,'all_match_reference':all(row['status']=='MATCHES_REFERENCE' for row in rows),
            'scope':'numerical planar reference for these cases and this navigation polygon; not a universal Funnel correctness certification',
            'gazebo_routes_changed':False}
    path=out/'reference_comparison.json'
    path.write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    print(f'Save at: {path}',flush=True)
    lines=['# Đối chiếu tuyến Funnel với phương pháp độc lập','',
           'Tham chiếu: đồ thị nhìn thấy giữa các góc biên của miền đa giác, gồm cả các lỗ, và START/GOAL.',
           'Đồ thị tham chiếu không dùng lan truyền Funnel hoặc đường đi theo cạnh lưới. Không nới miền dẫn đường khi tính tuyến tham chiếu.',
           '', '| Ca thử | Funnel | Tham chiếu | Chênh lệch (%) | Kết quả |',
           '|---|---:|---:|---:|---|']
    for row in rows:
        lines.append(f"| {row['case']} | {row['funnel_length']:.9f} | {row['reference_length']:.9f} | {row['excess_percent']:.6f} | {row['status']} |")
    lines.extend(['','Độ dài dùng đơn vị mô hình gốc.',
                  '', '`MATCHES_REFERENCE`: độ dài trùng trong dung sai số. `LONGER_THAN_REFERENCE`: tuyến Funnel hợp lệ nhưng dài hơn tham chiếu. `INCONSISTENT`: cần điều tra tính hợp lệ hoặc sai lệch số.',
                  '', 'Kết quả là đối chiếu số cho bốn ca trên miền bay phẳng đã tạo. Không chứng nhận thuật toán Funnel thực nghiệm đúng trên mọi mesh hoặc bài toán 3D.',
                  'Các tuyến Gazebo hiện có không bị thay đổi.'])
    path=out/'reference_comparison.md'
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'Save at: {path}',flush=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    points=np.array([(p.x,p.z) for p in mesh.points])
    triangles=points[np.array(mesh.faces)]
    fig,axes=plt.subplots(2,2,figsize=(13,11))
    for ax,case,row in zip(axes.flat,cases,rows):
        ax.set_facecolor('#e3e6e9')
        ax.add_collection(PolyCollection(triangles,facecolors='#d7eadc',edgecolors='none'))
        path=np.array(json.loads((benchmark/next(r['route_file'] for r in report['cases'] if r['id']==case['id'])).read_text())['points'])
        reference=np.array(row['reference_points_xz'])
        ax.plot(path[:,0],path[:,2],color='#dc7919',linewidth=3,label='Funnel candidate')
        ax.plot(reference[:,0],reference[:,1],color='#165db5',linewidth=1.7,linestyle='--',label='Independent reference')
        ax.scatter(*reference[0],s=24,color='#13743e',zorder=4)
        ax.scatter(*reference[-1],s=24,color='#b71e41',zorder=4)
        ax.autoscale();ax.set_aspect('equal')
        ax.set(xlabel='X (model units)',ylabel='Z (model units)',
               title=f"{case['id']} | excess {row['excess_percent']:.3f}%")
        if case['id'] in ('short_open','narrow_corridor'):
            low=np.minimum(reference[0],reference[-1])-2;high=np.maximum(reference[0],reference[-1])+2
            ax.set_xlim(low[0],high[0]);ax.set_ylim(low[1],high[1])
        ax.legend(loc='lower left',fontsize=8)
    fig.suptitle('Funnel candidates vs independent planar reference\nSame navigation polygon; numerical comparison only')
    fig.tight_layout(rect=(0,0,1,.94))
    path=out/'reference_routes.png'
    fig.savefig(path,dpi=160);plt.close(fig)
    print(f'Save at: {path}',flush=True)
    print(f"All cases match reference: {output['all_match_reference']}",flush=True)
    if any(row['status']=='INCONSISTENT' for row in rows):
        raise SystemExit(1)


if __name__=='__main__':
    main()
