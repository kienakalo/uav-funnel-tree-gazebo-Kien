"""Check measured centreline against the same conservative obstacle columns."""
import csv,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from city import load_city
from urban_navigation import obstacle_grid,intersects_boxes
from trajectory import Trajectory
data=json.loads((ROOT/'generated/urban_report.json').read_text())
route=json.loads((ROOT/'generated/route.json').read_text())
v,f,_=load_city(ROOT/'assets/city.glb')
_,boxes,_,_=obstacle_grid(v,f,data['altitude'],data['clearance'],data['cell_size'])
with (ROOT/'generated/physics_telemetry.csv').open() as stream:rows=list(csv.DictReader(stream))
if not rows:raise SystemExit('No physics telemetry yet.')
points=[tuple(float(r[k]) for k in ('x','y','z')) for r in rows]
height_error=max(abs(p[2]-data['altitude']) for p in points)
hits=sum(intersects_boxes(a,b,boxes) for a,b in zip(points,points[1:]))
print('Last phase:',rows[-1].get('phase','unknown'))
print('Max tracking error:',max(float(r['error']) for r in rows))
print('Max altitude deviation:',height_error)
print('Sample-to-sample segment intersections with inflated obstacle columns:',hits)
print('Planned route blocked:',not data['planned_segments_clear'])
print('Expected movement segments:',len(Trajectory(route['waypoints'],route['speed']).segments))
print('Dwell IDs observed:',sorted({int(r['segment']) for r in rows if r.get('phase')=='dwell'}))
print('CSV segments approximate actual motion between samples; this is not Gazebo contact-sensor evidence.')
if hits or height_error>.05:raise SystemExit('CHECK FAILED: preserve logs and stop this demo.')
if rows[-1].get('phase')!='complete':raise SystemExit('Mission is not complete yet. Keep Gazebo running and check again later.')
