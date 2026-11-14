# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Matplotlib, NumPy; Python stdlib (argparse, collections, hashlib, json,
# pathlib); local modules (inspect_flight_levels_fixed).
"""Build a conservative grid navigation surface in original GLB scene units.

Uses all upper triangle projections, not guessed closures of broken contours.
This creates a surface; it does not run Funnel Tree or claim a shortest route.
"""
import argparse,json,hashlib
from collections import deque,Counter
from pathlib import Path
import numpy as np
from inspect_flight_levels_fixed import transformed_objects


def rasterize(boxes,origin,step,shape):
    size=np.array(shape,dtype=int)
    start=np.floor((boxes[:,0]-origin)/step).astype(int)
    stop=np.floor((boxes[:,1]-origin)/step).astype(int)
    # Also block a cell touching the lower box edge exactly.
    exact=np.isclose((boxes[:,0]-origin)/step,start,rtol=0,atol=1e-10)
    start-=exact.astype(int)
    start=np.maximum(start,0);stop=np.minimum(stop,size-1)
    valid=np.all(stop>=start,axis=1);start=start[valid];stop=stop[valid]
    delta=np.zeros(tuple(size+1),dtype=np.int64)
    np.add.at(delta,(start[:,0],start[:,1]),1)
    np.add.at(delta,(stop[:,0]+1,start[:,1]),-1)
    np.add.at(delta,(start[:,0],stop[:,1]+1),-1)
    np.add.at(delta,(stop[:,0]+1,stop[:,1]+1),1)
    return delta.cumsum(0).cumsum(1)[:-1,:-1]>0


def eliminate_point_contacts(free):
    free=free.copy();removed=0
    while True:
        found=False
        for x in range(free.shape[0]-1):
            for z in range(free.shape[1]-1):
                a,b,c,d=bool(free[x,z]),bool(free[x+1,z]),bool(free[x,z+1]),bool(free[x+1,z+1])
                if a and d and not b and not c:free[x+1,z+1]=False;removed+=1;found=True
                elif b and c and not a and not d:free[x+1,z]=False;removed+=1;found=True
        if not found:return free,removed


def components(free):
    labels=np.full(free.shape,-1,dtype=np.int32);parts=[]
    for i,j in zip(*np.where(free)):
        if labels[i,j]>=0:continue
        label=len(parts);queue=deque([(int(i),int(j))]);labels[i,j]=label;cells=[]
        while queue:
            x,z=queue.popleft();cells.append((x,z))
            for a,b in [(x-1,z),(x+1,z),(x,z-1),(x,z+1)]:
                if 0<=a<free.shape[0] and 0<=b<free.shape[1] and free[a,b] and labels[a,b]<0:
                    labels[a,b]=label;queue.append((a,b))
        parts.append(cells)
    return labels,parts


def make_mesh(cells,origin,step,height):
    points=[];faces=[];indices={}
    def point(x,z):
        key=(x,z)
        if key not in indices:
            indices[key]=len(points);points.append((float(origin[0]+x*step),height,float(origin[1]+z*step)))
        return indices[key]
    for x,z in cells:
        a,b,c,d=point(x,z),point(x+1,z),point(x,z+1),point(x+1,z+1)
        # Winding is +Y in original X/Y/Z scene coordinates.
        faces.extend([(a,c,b),(b,c,d)])
    return np.array(points),np.array(faces,dtype=np.int64)


def inspect_mesh(points,faces):
    edge_faces={};vertex_faces=[[] for _ in points]
    for fid,face in enumerate(faces):
        for v in face:vertex_faces[v].append(fid)
        for a,b in zip(face,np.roll(face,-1)):edge_faces.setdefault(tuple(sorted((int(a),int(b)))),[]).append(fid)
    boundary_degree=Counter();bad_edges=0
    for (a,b),adj in edge_faces.items():
        if len(adj)==1:boundary_degree[a]+=1;boundary_degree[b]+=1
        if len(adj)>2:bad_edges+=1
    bad_fans=0
    for v,incident in enumerate(vertex_faces):
        adjacency={f:set() for f in incident}
        for f in incident:
            for w in faces[f]:
                if w==v:continue
                fs=edge_faces[tuple(sorted((int(v),int(w))))]
                for g in fs:
                    if g!=f:adjacency[f].add(g)
        if not incident:bad_fans+=1;continue
        reached={incident[0]};stack=[incident[0]]
        while stack:
            for g in adjacency[stack.pop()]:
                if g not in reached:reached.add(g);stack.append(g)
        if len(reached)!=len(incident):bad_fans+=1
    areas=np.linalg.norm(np.cross(points[faces[:,1]]-points[faces[:,0]],points[faces[:,2]]-points[faces[:,0]]),axis=1)/2
    return {'vertices':len(points),'triangles':len(faces),'edges':len(edge_faces),
        'boundary_edges':sum(len(a)==1 for a in edge_faces.values()),'nonmanifold_edges':bad_edges,
        'bad_boundary_vertices':sum(d!=2 for d in boundary_degree.values()),'disconnected_vertex_fans':bad_fans,
        'degenerate_triangles':int((areas<=1e-12).sum()),'area':float(areas.sum())}


def write_geom(path,points,faces,edges):
    with path.open('w') as f:
        f.write(f'{len(points)} {len(faces)} {edges}\n')
        for p in points:f.write(' '.join(f'{x:.17g}' for x in p)+'\n')
        for face in faces:f.write('3 '+' '.join(map(str,face))+'\n')


def main():
    root=Path(__file__).resolve().parents[1]
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--city',type=Path);p.add_argument('--height',type=float,default=2.)
    p.add_argument('--clearance',type=float,default=1.);p.add_argument('--vertical-clearance',type=float,default=.2)
    p.add_argument('--cell',type=float,default=.5);p.add_argument('--out',type=Path,default=root/'generated')
    args=p.parse_args()
    if args.cell<=0 or args.clearance<0 or args.vertical_clearance<0:p.error('Invalid spacing or clearance')
    city=args.city or root/'data/source/city.glb'
    if not city.is_file():p.error('Use --city PATH')
    box_parts=[];low_parts=[];high_parts=[];upper=0
    for _,triangles in transformed_objects(city):
        low_parts.append(triangles.min(axis=(0,1)));high_parts.append(triangles.max(axis=(0,1)))
        # Infinite columns also reserve interiors below roofs. No shell watertightness needed.
        selected=triangles[triangles[:,:,1].max(axis=1)>=args.height-args.vertical_clearance]
        if len(selected):
            xz=selected[:,:,[0,2]];upper+=len(selected)
            box_parts.append(np.stack([xz.min(axis=1)-args.clearance,xz.max(axis=1)+args.clearance],axis=1))
    if not box_parts:raise SystemExit('No upper geometry: choose a meaningful height before continuing.')
    boxes=np.concatenate(box_parts);lo=np.min(low_parts,axis=0);hi=np.max(high_parts,axis=0)
    origin=np.floor(lo[[0,2]]/args.cell)*args.cell
    shape=np.ceil((hi[[0,2]]-origin)/args.cell).astype(int)
    blocked=rasterize(boxes,origin,args.cell,shape)
    # Keep a conservative margin from the asset's outer rectangular limits.
    centres_x=origin[0]+(np.arange(shape[0])+.5)*args.cell
    centres_z=origin[1]+(np.arange(shape[1])+.5)*args.cell
    edge_margin=args.clearance+args.cell/2
    outside=(centres_x[:,None]<lo[0]+edge_margin)|(centres_x[:,None]>hi[0]-edge_margin)|\
            (centres_z[None,:]<lo[2]+edge_margin)|(centres_z[None,:]>hi[2]-edge_margin)
    free,removed=eliminate_point_contacts(~(blocked|outside))
    labels,parts=components(free)
    if not parts:raise SystemExit('No free component remains. No mesh was exported.')
    best=max(range(len(parts)),key=lambda i:len(parts[i]));cells=parts[best]
    points,faces=make_mesh(cells,origin,args.cell,args.height);stats=inspect_mesh(points,faces)
    for key in ['nonmanifold_edges','bad_boundary_vertices','disconnected_vertex_fans','degenerate_triangles']:
        if stats[key]:raise RuntimeError(f'Mesh validation failed: {key}={stats[key]}')
    # Independent geometric test: no retained whole cell may touch any inflated AABB.
    for x,z in cells:
        low=origin+np.array([x,z])*args.cell;high=low+args.cell
        if np.any(np.all(boxes[:,1]>=low-1e-10,axis=1)&np.all(boxes[:,0]<=high+1e-10,axis=1)):
            raise RuntimeError('A retained cell intersects an inflated obstacle box.')
    tag=f'{args.height:.2f}'.replace('.','p');prefix=f'navigation_y{tag}';args.out.mkdir(exist_ok=True,parents=True)
    report={'height':args.height,'horizontal_clearance':args.clearance,'vertical_clearance':args.vertical_clearance,
        'cell_size':args.cell,'grid_shape':shape.tolist(),'upper_triangles':upper,'free_components':len(parts),
        'component_cell_counts':sorted([len(c) for c in parts],reverse=True),'largest_component_cells':len(cells),
        'conservatively_removed_point_contact_cells':removed,'all_retained_cells_clear_of_inflated_boxes':True,
        'mesh':stats,'coordinates':'original GLB scene: X/Y/Z with Y up; unverified model units',
        'original_scene_bounds':[lo.tolist(),hi.tolist()],'grid_origin_xz':origin.tolist(),
        'sha256':hashlib.sha256(city.read_bytes()).hexdigest(),
        'method':'upper-triangle X/Z AABB columns expanded in X/Z; raster free whole cells; largest edge-connected component',
        'status':'static conservative surface only; no route or city-global optimum certified'}
    write_geom(args.out/(prefix+'.geom'),points,faces,stats['edges'])
    (args.out/(prefix+'_report.json')).write_text(json.dumps(report,indent=2)+'\n')
    np.savez_compressed(args.out/(prefix+'_grid.npz'),blocked=blocked,free=free,labels=labels,origin=origin,cell=args.cell,component=best)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.collections import PolyCollection
    image=np.zeros(free.shape,dtype=int);image[blocked]=1;image[free]=2;image[labels==best]=3
    fig,ax=plt.subplots(figsize=(12,10))
    ax.imshow(image.T,origin='lower',extent=[origin[0],origin[0]+shape[0]*args.cell,origin[1],origin[1]+shape[1]*args.cell],
        cmap=ListedColormap(['#ebedf0','#e5a487','#c0d8dc','#d9f0df']),vmin=0,vmax=3,interpolation='nearest')
    ax.add_collection(PolyCollection(points[faces][:,:,[0,2]],facecolors='none',edgecolors='#438b67',linewidths=.15))
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color='#e5a487',label='Inflated obstacle columns'),Patch(color='#d9f0df',label='Selected component + mesh'),Patch(color='#c0d8dc',label='Other free components'),Patch(color='#ebedf0',label='Excluded margin or point contacts')],loc='upper right',fontsize=8)
    ax.set(xlabel='X (original model units)',ylabel='Z (original model units)',title=f'Navigation surface Y={args.height:g} | {stats["triangles"]} triangles\nConservative clearance: horizontal {args.clearance:g}, vertical {args.vertical_clearance:g}')
    ax.set_aspect('equal');fig.tight_layout();fig.savefig(args.out/(prefix+'.png'),dpi=150);plt.close(fig)
    print('=== NAVIGATION SURFACE: original GLB units, Y up ===')
    for key in ['height','horizontal_clearance','vertical_clearance','cell_size','upper_triangles','free_components','largest_component_cells','conservatively_removed_point_contact_cells','all_retained_cells_clear_of_inflated_boxes']:
        print(key+':',report[key])
    for key,value in stats.items():print(key+':',value)
    print('Saved:',args.out/(prefix+'.geom'));print('Saved:',args.out/(prefix+'.png'))
    print('No Funnel Tree run or Gazebo route change performed.')


if __name__=='__main__':main()
