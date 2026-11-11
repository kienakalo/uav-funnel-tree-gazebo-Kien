"""Experimental Funnel Tree: local cosine propagation + Procedure 2.

Reconstruction unfolds only the selected face strip, independently of propagation.
Resource limits are explicit. No fallback to edge-Dijkstra is used as a solution.
"""
from dataclasses import dataclass, field
import math
import time
import numpy as np

PI = math.pi


def angle_sides(a, b, opposite):
    if a*b <= 1e-28:
        return 0.0
    return math.acos(max(-1., min(1., (a*a+b*b-opposite*opposite)/(2*a*b))))


def cosine_side(a, b, angle):
    return math.sqrt(max(0., a*a+b*b-2*a*b*math.cos(angle)))


@dataclass(eq=False)
class Funnel:
    p: int
    q: int
    x: int
    sequence: tuple
    sp: float
    pq: float
    spq: float
    psw: float
    pqv: float = 0.
    deleted: bool = False
    children: list = field(default_factory=list)


def clip_children(length_a, angle_a, length_b, angle_b, tolerance=1e-10):
    """Procedure 2, returning (which funnel, which child), 0=left, 1=right.

    Lengths are linear lengths; angles are at v from the common p-side.
    Equality uses a relative numerical tolerance.
    """
    da = angle_a-angle_b
    dl = length_a-length_b
    leps = tolerance*max(1.,abs(length_a),abs(length_b))
    if abs(da) <= tolerance:
        return []
    if dl < -leps:
        return [('B', 1 if da > 0 else 0)]
    if dl > leps:
        return [('A', 0 if da > 0 else 1)]
    return [('A',0),('B',1)] if da > 0 else [('A',1),('B',0)]


def seeds(mesh, source):
    remaining = set(mesh.vertex_faces[source])
    result = []
    # Traverse incident triangles consistently; supports a single boundary fan too.
    boundary = [v for edge,faces in mesh.edge_faces.items() if source in edge and len(faces)==1 for v in edge if v != source]
    if boundary:
        p = boundary[0]
        face_id = mesh.edge_faces[tuple(sorted((source,p)))][0]
    else:
        face_id = min(remaining)
        p = next(v for v in mesh.faces[face_id] if v != source)
    while remaining:
        if face_id not in remaining:
            raise ValueError('Incident faces are not one manifold fan.')
        remaining.remove(face_id)
        q = mesh.third_vertex(face_id,source,p)
        result.append(Funnel(p,q,p,(face_id,),mesh.distance(source,p),mesh.distance(p,q),mesh.angle(source,p,q),mesh.angle(p,source,q)))
        next_face = mesh.other_face(source,q,face_id)
        if not remaining:
            break
        if next_face is None:
            raise ValueError('Disconnected incident fan.')
        p,face_id = q,next_face
    return result


def propagate(mesh, source, deadline, max_nodes, clipping=True, target_vertices=None):
    # Optional diagnostic scope: propagation is unchanged, but reconstruct
    # candidates only for these destinations. Other distances remain unknown.
    if target_vertices is not None:
        target_vertices = set(target_vertices)
    roots = seeds(mesh,source)
    levels = [roots]
    occupied = {}
    candidates=[]
    stats = {'source':source,'nodes':len(roots),'clip_events':0,'deleted_children':0,'levels':0}
    while levels[-1]:
        if time.monotonic()>deadline:
            raise TimeoutError('Funnel propagation time limit exceeded.')
        if len(levels)>len(mesh.faces)+1:
            raise RuntimeError('Face-level limit exceeded; inspect topology or algorithm.')
        new = []
        for f in levels[-1]:
            if f.deleted:
                continue
            while True:
                if time.monotonic()>deadline:
                    raise TimeoutError('Funnel propagation time limit exceeded.')
                face = mesh.other_face(f.x,f.q,f.sequence[-1])
                if face is None or face in f.sequence:
                    break
                f.sequence += (face,)
                v = mesh.third_vertex(face,f.x,f.q)
                f.pqv += mesh.angle(f.x,f.q,v)
                vq = mesh.distance(v,f.q)
                pv = cosine_side(f.pq,vq,f.pqv)
                vpq = angle_sides(pv,f.pq,vq)
                if f.pqv>PI:
                    vpq = -vpq
                beta = f.spq+vpq
                if beta >= PI:
                    f.x = v
                    continue
                sv = cosine_side(f.sp,pv,beta)
                # Save a reached destination even when the following update only
                # changes q in-place (especially important at an open boundary).
                candidates.append(Funnel(v,f.q,v,f.sequence,sv,vq,0.,0.))
                psv = angle_sides(f.sp,sv,pv)
                f.pqv = mesh.angle(f.x,v,f.q)+vpq+f.pqv-PI
                if psv >= f.psw:
                    f.q,f.pq,f.spq = v,pv,beta
                    continue
                pvs = angle_sides(pv,sv,f.sp)
                svq = angle_sides(pv,vq,f.pq)-pvs
                left = Funnel(f.p,v,f.x,f.sequence,f.sp,pv,beta,psv,f.pqv)
                right = Funnel(v,f.q,v,f.sequence,sv,vq,svq,f.psw-psv)
                f.children = [left,right]
                # Same ordered edge/vertex at a fixed source: same occupied angle.
                key = (f.p,f.q,v)
                previous = occupied.get(key)
                if previous and clipping:
                    old,old_length,old_angle = previous
                    decisions = clip_children(sv,pvs,old_length,old_angle)
                    stats['clip_events'] += 1
                    for who,side in decisions:
                        child = (f if who=='A' else old).children[side]
                        if not child.deleted:
                            child.deleted = True
                            stats['deleted_children'] += 1
                if previous is None or sv < previous[1]:
                    occupied[key] = (f,sv,pvs)
                new.extend(f.children)
                stats['nodes'] += 2
                if stats['nodes']>max_nodes:
                    raise RuntimeError('Funnel node limit exceeded; no result certified.')
                break
        levels.append([f for f in new if not f.deleted])
    stats['levels'] = len(levels)-1
    best = [None]*len(mesh.points)
    distances = [math.inf]*len(mesh.points)
    distances[source] = 0.
    # Validate shortest candidates first; longer candidates for an already
    # validated destination cannot improve its distance.
    ordered = [f for level in levels for f in level if not f.deleted]+candidates
    ordered.sort(key=lambda f: f.sp)
    stats['reconstruction_attempts'] = 0
    stats['reconstruction_rejected'] = 0
    for f in ordered:
        if time.monotonic() > deadline:
            raise TimeoutError('Funnel reconstruction time limit exceeded.')
        if target_vertices is not None and f.p not in target_vertices:
            continue
        if f.sp < distances[f.p]:
            stats['reconstruction_attempts'] += 1
            try:
                path=reconstruct(mesh,source,f,deadline=deadline)
                length=sum(math.dist(a,b) for a,b in zip(path,path[1:]))
                if abs(length-f.sp)>1e-6*max(1.,f.sp):
                    stats['reconstruction_rejected'] += 1
                    continue
            except (ValueError,np.linalg.LinAlgError):
                stats['reconstruction_rejected'] += 1
                continue
            distances[f.p],best[f.p] = f.sp,f
    # An open fan has one terminal q that never becomes another root's p.
    # All adjacent vertices have a globally shortest straight edge from source.
    for face_id in mesh.vertex_faces[source]:
        for v in mesh.faces[face_id]:
            if v==source: continue
            if target_vertices is not None and v not in target_vertices:
                continue
            d=mesh.distance(source,v)
            if d <= distances[v]+1e-12:
                q=mesh.third_vertex(face_id,source,v)
                distances[v]=d
                best[v]=Funnel(v,q,v,(face_id,),d,mesh.distance(v,q),mesh.angle(source,v,q),mesh.angle(v,source,q))
    return distances,best,stats


def reconstruct(mesh, source, funnel, deadline=None):
    """Unfold selected strip for path extraction; propagation itself stays intrinsic."""
    if deadline is not None and time.monotonic() > deadline:
        raise TimeoutError('Funnel reconstruction time limit exceeded.')
    target = funnel.p
    if source==target:
        p = mesh.points[source]
        return [(p.x,p.y,p.z)]*2
    first = mesh.faces[funnel.sequence[0]]
    a,b,c = first
    coords = {a:(0.,0.),b:(mesh.distance(a,b),0.)}
    ac,bc,ab = mesh.distance(a,c),mesh.distance(b,c),mesh.distance(a,b)
    cx = (ac*ac+ab*ab-bc*bc)/(2*ab)
    coords[c] = (cx,math.sqrt(max(0.,ac*ac-cx*cx)))
    start = coords[source]
    shared_edges = []
    current = first
    end = coords.get(target)
    for face_id in funnel.sequence[1:]:
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError('Funnel reconstruction time limit exceeded.')
        if end is not None:
            break
        nxt = mesh.faces[face_id]
        edge = sorted(set(current)&set(nxt))
        if len(edge)!=2:
            raise ValueError('Non-adjacent faces in trace.')
        u,v = edge
        old = next(x for x in current if x not in edge)
        new = next(x for x in nxt if x not in edge)
        U,V = coords[u],coords[v]
        dx,dy = V[0]-U[0],V[1]-U[1]
        length = math.hypot(dx,dy)
        if length == 0:
            raise ValueError('Collapsed edge in unfolded face strip.')
        ax,ay = dx/length,dy/length
        nx,ny = -ay,ax
        du,dv = mesh.distance(u,new),mesh.distance(v,new)
        along = (du*du+length*length-dv*dv)/(2*length)
        height = math.sqrt(max(0.,du*du-along*along))
        old_x,old_y = coords[old]
        sign = 1 if (old_x-U[0])*nx+(old_y-U[1])*ny>0 else -1
        shared_edges.append((u,v,U,V))
        coords[new] = (U[0]+along*ax-sign*height*nx,
                       U[1]+along*ay-sign*height*ny)
        current = nxt
        if target in nxt:
            end = coords[target]
    if end is None:
        raise ValueError('Target absent from face strip.')
    to3 = lambda p: (p.x,p.y,p.z)
    points = [to3(mesh.points[source])]
    dx,dy = end[0]-start[0],end[1]-start[1]
    prev_t = -1e-7
    for u,v,U,V in shared_edges:
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError('Funnel reconstruction time limit exceeded.')
        # Solve [direction, -(V-U)] * (t,r) = U-start directly.
        ex,ey = V[0]-U[0],V[1]-U[1]
        det = dy*ex-dx*ey
        if abs(det)<1e-12:
            continue
        bx,by = U[0]-start[0],U[1]-start[1]
        t = (ex*by-ey*bx)/det
        r = (dx*by-dy*bx)/det
        if t < prev_t-1e-6 or not -1e-6<=t<=1+1e-6 or not -1e-6<=r<=1+1e-6:
            raise ValueError('Selected geodesic exits its face strip.')
        prev_t = t
        point = tuple((1-r)*a+r*b for a,b in zip(to3(mesh.points[u]),to3(mesh.points[v])))
        if math.dist(point,points[-1])>1e-8:
            points.append(point)
    target3 = to3(mesh.points[target])
    if math.dist(target3,points[-1])>1e-8:
        points.append(target3)
    return [tuple(map(float,p)) for p in points]


def solve(mesh, source, timeout=20., max_nodes=200000, clipping=True):
    if not 0<=source<len(mesh.points):
        raise ValueError('Source out of range.')
    deadline = time.monotonic()+timeout
    sources = [source]
    boundary_vertices={v for edge,adjacent in mesh.edge_faces.items() if len(adjacent)==1 for v in edge}
    # Nonconvex surface: concatenate paths via negative-curvature vertices.
    for v in range(len(mesh.points)):
        if v==source:
            continue
        total = 0.
        for f in mesh.vertex_faces[v]:
            a,b = [i for i in mesh.faces[f] if i!=v]
            total += mesh.angle(a,v,b)
        threshold=PI if v in boundary_vertices else 2*PI
        if total>threshold+1e-5:
            sources.append(v)
    runs = [propagate(mesh,s,deadline,max_nodes,clipping) for s in sources]
    dist,best,_ = runs[0]
    dist = dist.copy()
    routes = [(0,v) for v in range(len(dist))]
    prefix = [None]*len(dist)
    for _ in range(len(sources)):
        changed = False
        for k,s in enumerate(sources[1:],1):
            for v,d in enumerate(runs[k][0]):
                candidate = dist[s]+d
                if candidate < dist[v]-1e-10:
                    dist[v],routes[v],prefix[v] = candidate,(k,v),s
                    changed = True
        if not changed:
            break
    cache = {}
    def trace(v, active):
        if v in active:
            raise ValueError('Cycle in path reconstruction.')
        if v in cache:
            return cache[v]
        if v==source:
            p=mesh.points[v]; return [(p.x,p.y,p.z)]*2
        k,_ = routes[v]
        f = runs[k][1][v]
        if f is None:
            raise ValueError(f'No funnel reached vertex {v}.')
        if time.monotonic() > deadline:
            raise TimeoutError('Funnel reconstruction time limit exceeded.')
        path = reconstruct(mesh,sources[k],f,deadline=deadline)
        if prefix[v] is not None:
            path = trace(prefix[v],active|{v})[:-1]+path
        cache[v] = path
        return path
    paths = [trace(v,set()) for v in range(len(dist))]
    for v,path in enumerate(paths):
        length = sum(math.dist(a,b) for a,b in zip(path,path[1:]))
        if abs(length-dist[v])>1e-6*max(1.,dist[v]):
            raise ValueError(f'Intrinsic / reconstructed length mismatch at {v}.')
    return paths,{'runs':[r[2] for r in runs],'clipping':clipping,'implementation_status':'experimental; validate per mesh'}
