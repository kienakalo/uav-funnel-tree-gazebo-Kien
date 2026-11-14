# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main libraries: Matplotlib, NumPy; Python stdlib (argparse, hashlib, json, math, pathlib);
# local modules (inspect_flight_levels_fixed).
"""Intersect city triangles with original-scene Y=h and audit contour topology.

Open or branched contours are reported, not silently closed into obstacles.
"""
import argparse,json,math,hashlib
from pathlib import Path
import numpy as np
from inspect_flight_levels_fixed import transformed_objects


def triangle_section(triangle,height,epsilon):
    d=triangle[:,1]-height
    on=np.abs(d)<=epsilon
    if on.all():
        return [(triangle[a,[0,2]],triangle[b,[0,2]]) for a,b in [(0,1),(1,2),(2,0)]],True
    points=[triangle[i,[0,2]] for i in range(3) if on[i]]
    for a,b in [(0,1),(1,2),(2,0)]:
        if not on[a] and not on[b] and d[a]*d[b]<0:
            t=-d[a]/(d[b]-d[a])
            points.append((triangle[a]+t*(triangle[b]-triangle[a]))[[0,2]])
    unique=[]
    for p in points:
        if not any(np.linalg.norm(p-q)<=epsilon for q in unique):unique.append(p)
    if len(unique)<2:return [],False
    # Tolerance can produce >2 points; retain maximal section segment.
    a,b=max(((a,b) for a in range(len(unique)) for b in range(a+1,len(unique))),
            key=lambda pair:np.linalg.norm(unique[pair[0]]-unique[pair[1]]))
    return [(unique[a],unique[b])],False


def audit_segments(segments,weld):
    vertices=[];lookup={};edges=set()
    def vertex(p):
        key=tuple(np.rint(np.asarray(p)/weld).astype(np.int64))
        if key not in lookup:lookup[key]=len(vertices);vertices.append(tuple(map(float,p)))
        return lookup[key]
    for a,b in segments:
        a,b=vertex(a),vertex(b)
        if a!=b:edges.add(tuple(sorted((a,b))))
    edges=sorted(edges);adj=[set() for _ in vertices]
    for a,b in edges:adj[a].add(b);adj[b].add(a)
    pending=set(i for i,n in enumerate(adj) if n);components=[]
    while pending:
        first=min(pending);stack=[first];component=[];pending.remove(first)
        while stack:
            v=stack.pop();component.append(v)
            for w in adj[v]:
                if w in pending:pending.remove(w);stack.append(w)
        degrees=[len(adj[v]) for v in component]
        closed=all(d==2 for d in degrees)
        ordered=[]
        if closed:
            current=component[0];previous=None
            for _ in range(len(component)):
                ordered.append(current)
                nxt=next(v for v in sorted(adj[current]) if v!=previous)
                previous,current=current,nxt
            if current!=ordered[0]:raise ValueError('Cycle ordering failed.')
        components.append({'id':len(components),'vertices':len(component),'edges':sum(degrees)//2,
            'endpoints':sum(d==1 for d in degrees),'branch_vertices':sum(d>2 for d in degrees),
            'closed_cycle':closed,'vertex_ids':component,'ordered_vertex_ids':ordered})
    return np.asarray(vertices),edges,components


def main():
    root=Path(__file__).resolve().parents[1]
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--height',type=float,default=2.);p.add_argument('--city',type=Path)
    p.add_argument('--out',type=Path,default=root/'generated');p.add_argument('--weld',type=float,default=1e-5)
    args=p.parse_args()
    if args.weld<=0:p.error('--weld must be positive')
    city=args.city or next((q for q in [root/'data/input/city.glb',root/'assets/city.glb'] if q.is_file()),None)
    if city is None or not city.is_file():p.error('Cannot find city.glb; use --city PATH')
    raw=[];coplanar=0;crossing=0;objects=0;outline=[];eps=1e-6
    for name,triangles in transformed_objects(city):
        outline.append(triangles[::max(1,len(triangles)//300)][:,:,[0,2]])
        low=triangles[:,:,1].min(axis=1);high=triangles[:,:,1].max(axis=1)
        candidates=triangles[(low<=args.height+eps)&(high>=args.height-eps)]
        before=len(raw)
        for triangle in candidates:
            segments,flat=triangle_section(triangle,args.height,eps)
            raw.extend(segments);coplanar+=int(flat)
            crossing+=int(not flat and triangle[:,1].max()-triangle[:,1].min()>eps)
        objects+=int(len(raw)>before)
    if not raw:raise SystemExit('No intersection segments at this height.')
    vertices,edges,components=audit_segments(raw,args.weld)
    report={'height':args.height,'coordinates':'original transformed GLB scene, Y-up; section axes X/Z',
            'units':'model units, not verified metres','sha256':hashlib.sha256(city.read_bytes()).hexdigest(),
            'triangle_plane_epsilon':eps,'endpoint_quantization':args.weld,'objects_with_sections':objects,
            'crossing_faces':crossing,'coplanar_faces':coplanar,'raw_segments':len(raw),'unique_edges':len(edges),
            'components':len(components),'closed_cycle_components':sum(c['closed_cycle'] for c in components),
            'open_or_branched_components':sum(not c['closed_cycle'] for c in components),
            'endpoint_count':sum(c['endpoints'] for c in components),'branch_vertex_count':sum(c['branch_vertices'] for c in components),
            'status':'section contours only; no obstacle interiors, UAV clearance or free-space mesh certified'}
    args.out.mkdir(parents=True,exist_ok=True);tag=f'{args.height:.2f}'.replace('.','p');prefix=f'flight_slice_y{tag}'
    payload={'metadata':report,'vertices_xz':vertices.tolist(),'edges':edges,'components':components}
    (args.out/(prefix+'.json')).write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    (args.out/(prefix+'_report.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection,PolyCollection
    from matplotlib.lines import Line2D
    fig,ax=plt.subplots(figsize=(12,10))
    ax.add_collection(PolyCollection(np.concatenate(outline),facecolors='#e2e8ed',edgecolors='none',alpha=.5))
    is_closed={v:c['closed_cycle'] for c in components for v in c['vertex_ids']}
    for closed,color in [(True,'#137b9b'),(False,'#df632b')]:
        pairs=[(vertices[a],vertices[b]) for a,b in edges if is_closed[a]==closed]
        if pairs:ax.add_collection(LineCollection(pairs,colors=color,linewidths=1.1))
    ax.autoscale_view();ax.set_aspect('equal');ax.set_xlabel('X (original model units)');ax.set_ylabel('Z (original model units)')
    ax.set_title(f'City section at Y={args.height:g}\nClosed cycles: {report["closed_cycle_components"]}; open/branched: {report["open_or_branched_components"]}')
    ax.legend(handles=[Line2D([0],[0],color='#137b9b',label='Degree-2 closed cycle'),Line2D([0],[0],color='#df632b',label='Open or branched contour')])
    fig.tight_layout();fig.savefig(args.out/(prefix+'.png'),dpi=150);plt.close(fig)
    print('=== FLIGHT SLICE (original model units; not a Gazebo flight level) ===')
    for key in ['height','objects_with_sections','crossing_faces','coplanar_faces','raw_segments','unique_edges','components','closed_cycle_components','open_or_branched_components','endpoint_count','branch_vertex_count']:
        print(f'{key}: {report[key]}')
    print('Contour cycles are graph candidates, NOT certified obstacle polygons.')
    print('Saved:',args.out/(prefix+'.png'));print('Saved:',args.out/(prefix+'_report.json'))


if __name__=='__main__':main()
