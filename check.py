"""Regression and geometric checks; does not certify arbitrary-mesh optimality."""
import json,math,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from mesh import read_geom,Mesh,Point
from funnel_tree import solve,clip_children
from verification import read_paths,path_length,edge_distances,segment_on_mesh


def main():
    rows=[]
    for name,source in [('cliff',1),('J17',1),('L',1),('demo_mesh',1),('star',0),('star',1)]:
        m=read_geom(ROOT/f'data/input/{name}.geom');t=time.monotonic();paths,stats=solve(m,source)
        points=[(p.x,p.y,p.z) for p in m.points];upper=edge_distances(points,m.faces,source)
        for v,path in enumerate(paths):
            assert math.dist(path[0],points[source])<1e-7 and math.dist(path[-1],points[v])<1e-7
            length=path_length(path)
            assert math.dist(points[source],points[v])-1e-7<=length<=upper[v]+1e-7
            assert all(segment_on_mesh(a,b,points,m.faces,1e-7) for a,b in zip(path,path[1:])),(name,v)
        row={'mesh':name,'source':source,'seconds':time.monotonic()-t,'geometric_checks':True,'stats':stats}
        if (name,source)!=('star',1):
            expected=read_paths(ROOT/f'data/expected/{name}.geom')
            differences=[abs(path_length(a)-path_length(b)) for a,b in zip(paths,expected)]
            # Four-decimal coordinate rounding accumulates with the number of segments.
            for got,ref,diff in zip(paths,expected,differences):
                assert diff<=2*math.sqrt(3)*5e-5*max(len(ref)-1,1)+1e-8
            row['max_reference_length_difference']=max(differences)
        rows.append(row);print(name,source,'PASS',row.get('max_reference_length_difference','no supplied reference for source 1'))
    # Analytic planar case: all source/target pairs must equal straight Euclidean distance.
    m=Mesh([Point(0,0,0),Point(2,0,0),Point(0,2,0),Point(2,2,0)],[(0,1,2),(1,3,2)])
    for s in range(4):
        paths,_=solve(m,s)
        for v,path in enumerate(paths):assert abs(path_length(path)-m.distance(s,v))<1e-8
    assert clip_children(1,.8,2,.2)==[('B',1)]
    assert clip_children(2,.8,1,.2)==[('A',0)]
    assert clip_children(1,.8,1,.2)==[('A',0),('B',1)]
    assert clip_children(1,.2,2,.8)==[('B',0)]
    assert clip_children(2,.2,1,.8)==[('A',1)]
    assert clip_children(1,.2,1,.8)==[('A',1),('B',0)]
    result={'checks_passed':True,'rows':rows,'planar_all_pairs':True,'clip_rule_cases':True,
            'gazebo_runtime_tested':False,'arbitrary_mesh_optimality_certified':False}
    out=ROOT/'generated';out.mkdir(exist_ok=True);(out/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Planar all-pairs and clipping-rule checks: PASS. Gazebo runtime not available in this build environment.')


if __name__=='__main__':main()
