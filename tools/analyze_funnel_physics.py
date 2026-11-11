"""Check measured Funnel tracking and segment intersections with conservative columns."""
import csv
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from urban_navigation import intersects_boxes
from inspect_flight_levels_fixed import transformed_objects


def main(case=None):
    if case is None:
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--case',choices=('original','cross_city','short_open','narrow_corridor'),default='original')
        case=parser.parse_args().case
    out=ROOT/'generated/funnel_physics'
    if case!='original':
        out=out/case
    route_path=out/'route.json'
    route=json.loads(route_path.read_text())
    metadata=json.loads((out/'telemetry_metadata.json').read_text())
    if metadata['route_sha256']!=hashlib.sha256(route_path.read_bytes()).hexdigest():
        raise ValueError('Telemetry does not match the current physics route')
    source=ROOT/route.get('source_route_file','generated/funnel_route_candidate_y2p00.json')
    if route['source_route_sha256']!=hashlib.sha256(source.read_bytes()).hexdigest():
        raise ValueError('Physics route does not match the current candidate')
    with (out/'physics_telemetry.csv').open(newline='') as stream:
        rows=list(csv.DictReader(stream))
    if not rows:
        raise ValueError('No physics telemetry yet')
    columns=('sim_time','x','y','z','target_x','target_y','target_z','error','vx','vy','vz')
    values=np.array([[float(row[k]) for k in columns] for row in rows])
    if not np.all(np.isfinite(values)) or np.any(np.diff(values[:,0])<=0):
        raise ValueError('Nonfinite or nonmonotonic telemetry')
    errors=np.linalg.norm(values[:,1:4]-values[:,4:7],axis=1)
    if not np.allclose(errors,values[:,7],atol=1e-8,rtol=0):
        raise ValueError('Recorded errors disagree with measured positions')
    scale=route['transform']['scale']
    reverted=values[:,1:4]/scale+np.array(route['transform']['origin'])
    xz=reverted[:,:2]*[1,-1]
    navigation=json.loads((ROOT/'generated/navigation_y2p00_report.json').read_text())
    asset=next((p for p in (ROOT/'data/input/city.glb',ROOT/'assets/city.glb')
                if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==navigation['sha256']),None)
    if asset is None:
        raise ValueError('No matching city asset')
    parts=[]
    cutoff=min(navigation['height'],float(reverted[:,2].min()))-navigation['vertical_clearance']
    for _,triangles in transformed_objects(asset):
        upper=triangles[triangles[:,:,1].max(axis=1)>=cutoff]
        if len(upper):
            projected=upper[:,:,[0,2]]
            margin=navigation['horizontal_clearance']
            parts.append(np.stack([projected.min(axis=1)-margin,projected.max(axis=1)+margin],axis=1))
    if not parts:
        raise ValueError('Obstacle model unexpectedly empty')
    boxes=np.concatenate(parts)
    hits=[i for i,(a,b) in enumerate(zip(xz,xz[1:])) if intersects_boxes(a,b,boxes)]
    final_error=math.dist(values[-1,1:4],route['waypoints'][-1])
    altitude_error=float(np.max(np.abs(values[:,3]-route['altitude'])))
    moving=errors[[row['phase']=='moving' for row in rows]]
    expected_segments=set(range(len(route['waypoints'])-1))
    observed={int(row['segment']) for row in rows if row['phase']=='dwell'}
    passed=bool(rows[-1]['phase']=='complete' and not hits and float(errors.max())<.1
                and final_error<.1 and altitude_error<.05 and expected_segments<=observed)
    result={'case':case,'checks_passed':passed,'last_phase':rows[-1]['phase'],'samples':len(rows),
            'telemetry_sha256':hashlib.sha256((out/'physics_telemetry.csv').read_bytes()).hexdigest(),
            'max_tracking_error':float(errors.max()),'moving_rmse':float(np.sqrt(np.mean(moving**2))) if len(moving) else None,
            'final_goal_error':final_error,'max_altitude_deviation':altitude_error,
            'max_measured_speed':float(np.linalg.norm(values[:,8:11],axis=1).max()),
            'dwell_segments_observed':sorted(observed),'obstacle_intersecting_sample_segments':hits,
            'route_sha256':metadata['route_sha256'],
            'scope':'measured centreline and straight segments between CSV samples vs inflated obstacle columns; not a continuous-time contact proof',
            'rotor_or_autopilot_simulation':False}
    (out/'physics_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)
    print(f'Save at: {out / "physics_validation.json"}',flush=True)
    if not passed:
        raise SystemExit('Not passed: if last_phase is not complete, keep the simulation running and check later.')


if __name__=='__main__':
    main()
