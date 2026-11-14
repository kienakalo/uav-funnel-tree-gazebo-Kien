# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: NumPy; Python stdlib (heapq, math, time); local modules (funnel_tree, mesh,
# verification).
"""Conservative obstacle columns -> grid corridor -> intrinsic Funnel Tree.

Funnel Tree optimizes within the chosen corridor only, not over all city routes.
"""
import heapq
import math
import time
import numpy as np
from mesh import Mesh, Point
from funnel_tree import solve


def obstacle_grid(vertices, faces, altitude=9., clearance=3.5, step=1.):
    triangles=vertices[faces]
    high=triangles[triangles[:,:,2].max(axis=1)>=altitude-clearance]
    boxes=np.stack([high[:,:,:2].min(axis=1)-clearance,high[:,:,:2].max(axis=1)+clearance],axis=1)
    lo=np.floor(vertices[:,:2].min(axis=0));hi=np.ceil(vertices[:,:2].max(axis=0))
    size=np.ceil((hi-lo)/step).astype(int)
    start=np.floor((boxes[:,0]-lo)/step).astype(int)
    stop=np.floor((boxes[:,1]-lo)/step).astype(int)
    start=np.maximum(start,0);stop=np.minimum(stop,size-1)
    valid=np.all(stop>=start,axis=1);start=start[valid];stop=stop[valid]
    difference=np.zeros(tuple(size+1),dtype=np.int64)
    np.add.at(difference,(start[:,0],start[:,1]),1)
    np.add.at(difference,(stop[:,0]+1,start[:,1]),-1)
    np.add.at(difference,(start[:,0],stop[:,1]+1),-1)
    np.add.at(difference,(stop[:,0]+1,stop[:,1]+1),1)
    blocked=difference.cumsum(axis=0).cumsum(axis=1)[:-1,:-1]>0
    blocked[[0,-1],:]=True;blocked[:,[0,-1]]=True
    return blocked,boxes,lo,step


def grid_path(blocked, source, target):
    queue=[(0.,0.,source)];cost={source:0};parent={}
    while queue:
        _,g,p=heapq.heappop(queue)
        if g!=cost[p]:continue
        if p==target:
            path=[p]
            while p in parent:p=parent[p];path.append(p)
            return path[::-1]
        for d in [(1,0),(-1,0),(0,1),(0,-1)]:
            q=(p[0]+d[0],p[1]+d[1])
            if not (0<=q[0]<blocked.shape[0] and 0<=q[1]<blocked.shape[1]) or blocked[q]:continue
            new=g+1
            if new<cost.get(q,math.inf):
                cost[q]=new;parent[q]=p
                h=abs(q[0]-target[0])+abs(q[1]-target[1])
                heapq.heappush(queue,(new+h,new,q))
    return None


def intersects_boxes(a,b,boxes):
    """Continuous segment / inflated XY AABB intersection, no point sampling."""
    a=np.asarray(a[:2]);b=np.asarray(b[:2]);d=b-a
    low=np.zeros(len(boxes));high=np.ones(len(boxes))
    for axis in range(2):
        if abs(d[axis])<1e-14:
            valid=(a[axis]>=boxes[:,0,axis])&(a[axis]<=boxes[:,1,axis])
            high[~valid]=-1.
        else:
            t0=(boxes[:,0,axis]-a[axis])/d[axis];t1=(boxes[:,1,axis]-a[axis])/d[axis]
            low=np.maximum(low,np.minimum(t0,t1));high=np.minimum(high,np.maximum(t0,t1))
    return bool(np.any(low<=high))


def corridor_mesh(cells, origin, step, altitude):
    vertices=[];faces=[];index={}
    def vertex(x,y):
        key=(x,y)
        if key not in index:
            index[key]=len(vertices);vertices.append(Point(origin[0]+x*step,origin[1]+y*step,altitude))
        return index[key]
    for x,y in cells:
        a,b,c,d=vertex(x,y),vertex(x+1,y),vertex(x,y+1),vertex(x+1,y+1)
        faces.extend([(a,b,c),(b,d,c)])
    # Put endpoints inside actual triangles instead of snapping to a mesh corner.
    endpoints=[]
    for fid in [0,len(faces)-1]:
        a,b,c=faces[fid]
        points=[vertices[i] for i in (a,b,c)]
        v=len(vertices);vertices.append(Point(sum(p.x for p in points)/3,sum(p.y for p in points)/3,altitude))
        faces[fid]=(a,b,v);faces.extend([(b,c,v),(c,a,v)]);endpoints.append(v)
    return Mesh(vertices,faces),endpoints


def plan_urban(vertices,faces,altitude=9.,clearance=3.5,step=1.):
    if altitude<=clearance:raise ValueError('Altitude must exceed clearance.')
    started=time.monotonic()
    blocked,boxes,origin,step=obstacle_grid(vertices,faces,altitude,clearance,step)
    free=np.argwhere(~blocked)
    rng=np.random.default_rng(2026)
    # Find a reproducible local mission that needs a detour, not just an open river flight.
    for attempt in range(160):
        a,b=free[rng.integers(len(free),size=2)]
        distance=float(np.linalg.norm(a-b)*step)
        if not 25<=distance<=65:continue
        point_a=origin+(a+.5)*step;point_b=origin+(b+.5)*step
        if not intersects_boxes(point_a,point_b,boxes):continue
        cells=grid_path(blocked,tuple(a),tuple(b))
        if cells is None or len(cells)>130:continue
        mesh,(source,target)=corridor_mesh(cells,origin,step,altitude)
        try:
            paths,stats=solve(mesh,source,timeout=8.,max_nodes=100000)
            path=paths[target]
        except (ValueError,RuntimeError,TimeoutError):continue
        original_count=len(path)
        compact=[]
        for p in path:
            if compact and math.dist(compact[-1],p)<1e-9:continue
            while len(compact)>=2:
                a=np.array(compact[-1])-np.array(compact[-2]);b=np.array(p)-np.array(compact[-1])
                if np.linalg.norm(np.cross(a,b))<=1e-8*max(1.,np.linalg.norm(a)*np.linalg.norm(b)) and np.dot(a,b)>0:
                    compact.pop()
                else:break
            compact.append(p)
        path=compact
        if not intersects_boxes(path[0],path[-1],boxes):continue
        if any(intersects_boxes(p,q,boxes) for p,q in zip(path,path[1:])):continue
        # All segments must remain on the selected mesh, independently of planner output.
        from verification import segment_on_mesh
        points=[(p.x,p.y,p.z) for p in mesh.points]
        if not all(segment_on_mesh(p,q,points,mesh.faces,1e-7) for p,q in zip(path,path[1:])):continue
        length=sum(math.dist(p,q) for p,q in zip(path,path[1:]))
        report={'altitude':altitude,'clearance':clearance,'cell_size':step,'corridor_cells':len(cells),
                'corridor_faces':len(mesh.faces),'city_triangles':len(faces),'blocked_cells':int(blocked.sum()),
                'grid_shape':list(blocked.shape),'direct_route_blocked':True,'planned_segments_clear':True,
                'length':length,'direct_length':math.dist(path[0],path[-1]),'planning_seconds':time.monotonic()-started,
                'funnel_stats':stats,'optimality_scope':'experimental Funnel Tree within A*-selected corridor; not city-global optimality',
                'collision_scope':'conservative infinite XY obstacle columns, inflated triangle AABBs; normalized city geometry',
                'source':source,'target':target,'search_attempt':attempt}
        report.update({'raw_path_points':original_count,'waypoints':len(path)})
        return mesh,path,report,blocked,origin
    raise RuntimeError('No validated local detour found. No unsafe route was produced.')
