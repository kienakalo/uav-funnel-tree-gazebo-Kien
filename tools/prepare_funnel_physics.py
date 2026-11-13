"""Create a separate force-driven world from the validated Funnel preview."""
import hashlib
import argparse
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT))
from trajectory import Trajectory
from prepare import shape
import numpy as np

CITY_STL_RECORD = np.dtype([('normal', '<f4', (3,)), ('triangle', '<f4', (3, 3)), ('attr', '<u2')])
DELIVERY_PAD_SIZE = 1.0
DELIVERY_PAD_THICKNESS = 0.1


def add_surface_overlay(world, out):
    """Draw a translucent surface and batched, double-sided triangle edges."""
    from mesh import read_geom
    mesh = read_geom(out / 'surface.geom')
    triangles = []
    for a, b in sorted(mesh.edge_faces):
        pa, pb = mesh.points[a], mesh.points[b]
        start = np.array([pa.x, pa.y, pa.z + .04])
        end = np.array([pb.x, pb.y, pb.z + .04])
        delta = end - start
        side = np.cross(delta, [0., 0., 1.])
        if np.linalg.norm(side) < 1e-12:
            side = np.cross(delta, [1., 0., 0.])
        side *= .035 / np.linalg.norm(side)
        p, q, r, s = start-side, start+side, end+side, end-side
        for triangle in ((p, q, r), (p, r, s)):
            triangles.extend((triangle, triangle[::-1]))
    records = np.zeros(len(triangles), dtype=CITY_STL_RECORD)
    records['triangle'] = triangles
    normal = np.cross(records['triangle'][:, 1] - records['triangle'][:, 0],
                      records['triangle'][:, 2] - records['triangle'][:, 0])
    normal /= np.linalg.norm(normal, axis=1)[:, None]
    records['normal'] = normal
    edge_path = out / 'surface_edges.stl'
    with edge_path.open('wb') as stream:
        stream.write(b'Navigation mesh edges'.ljust(80, b'\0'))
        stream.write(len(records).to_bytes(4, 'little'))
        stream.write(records.tobytes())
    model = ET.SubElement(world, 'model', name='navigation_surface')
    ET.SubElement(model, 'static').text = 'true'
    link = ET.SubElement(model, 'link', name='surface')
    for name, path, color, transparency in (
        ('navigation_mesh', out/'surface.stl', '.05 .65 .8 1', '.75'),
        ('triangle_edges', edge_path, '.02 .25 .4 1', '0'),
    ):
        visual = ET.SubElement(link, 'visual', name=name)
        ET.SubElement(visual, 'cast_shadows').text = 'false'
        ET.SubElement(ET.SubElement(ET.SubElement(visual, 'geometry'), 'mesh'), 'uri').text = path.as_uri()
        material = ET.SubElement(visual, 'material')
        for field in ('ambient', 'diffuse', 'emissive'):
            ET.SubElement(material, field).text = color
        ET.SubElement(visual, 'transparency').text = transparency
    print(f'Save at: {edge_path}')


def benchmark_route(case,preview_route):
    from run_funnel_benchmark import verify
    from mesh import read_geom
    from prepare_funnel_gazebo import simplify
    folder=ROOT/'generated/funnel_benchmark'
    report=json.loads((folder/'benchmark_results.json').read_text())
    # Reuse the exact recorded endpoints, including choices among tied nearest
    # triangles. NumPy versions can order equal-distance candidates differently.
    manifest=json.loads((folder/'cases.json').read_text())
    cases=manifest['cases']
    mesh=read_geom(ROOT/'generated/funnel_input_y2p00.geom')
    digest=hashlib.sha256()
    for path in (ROOT/'generated/funnel_input_y2p00.geom',ROOT/'generated/navigation_y2p00_grid.npz',
                 ROOT/'src/funnel_tree.py',ROOT/'src/mesh.py',ROOT/'tools/run_funnel_benchmark.py',
                 ROOT/'tools/run_funnel_route.py',ROOT/'src/verification.py'):
        digest.update(path.read_bytes())
    digest.update(json.dumps(cases,sort_keys=True).encode())
    if digest.hexdigest()!=report['signature'] or manifest['signature']!=report['signature']:
        raise ValueError('Benchmark inputs or code changed; run tools/run_funnel_benchmark.py again')
    row=next(row for row in report['cases'] if row['id']==case)
    if not report['complete'] or row['status']!='PASS' or not row['surface_membership_passed']:
        raise ValueError('The selected case has not passed planning validation')
    source=folder/row['route_file']
    candidate=json.loads(source.read_text())
    if candidate['signature']!=report['signature']:
        raise ValueError('Case route signature mismatch')
    points=simplify(candidate['points'])
    if not verify(mesh,[(p.x,p.y,p.z) for p in mesh.points],points):
        raise ValueError('Case route exits navigation mesh')
    if math.dist(points[0],row['start_xyz'])>1e-7 or math.dist(points[-1],row['goal_xyz'])>1e-7:
        raise ValueError('Case route endpoints do not match benchmark')
    scale=preview_route['transform']['scale']
    origin=np.array(preview_route['transform']['origin'])
    transformed=(np.array(points)[:,[0,2,1]]*[1,-1,1]-origin)*scale
    length=sum(math.dist(a,b) for a,b in zip(transformed,transformed[1:]))
    if abs(length-candidate['length']*scale)>1e-6:
        raise ValueError('Scaled case length mismatch')
    route=dict(preview_route)
    route.update(waypoints=transformed.tolist(),original_waypoints=points,length=length,
                 original_model_length=candidate['length'],altitude=float(transformed[0,2]),
                 source_route_file=source.relative_to(ROOT).as_posix(),
                 source_route_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),case=case)
    return route


def replace_route(world,points,show_descent=False):
    old=world.find("model[@name='funnel_route']")
    if old is not None:
        world.remove(old)
    model=ET.SubElement(world,'model',name='funnel_route')
    ET.SubElement(model,'static').text='true'
    link=ET.SubElement(model,'link',name='route')
    for i,(a,b) in enumerate(zip(points,points[1:])):
        d=[y-x for x,y in zip(a,b)]
        midpoint=[(x+y)/2 for x,y in zip(a,b)]
        pose=[*midpoint,0,math.atan2(math.hypot(d[0],d[1]),d[2]),math.atan2(d[1],d[0])]
        color='.05 .8 1 1' if show_descent and i==len(points)-2 else '1 .5 .03 1'
        shape(link,f'segment_{i}','cylinder',(.1,math.dist(a,b)),' '.join(map(str,pose)),color)
    for i,point in enumerate(points):
        color='.1 1 .2 1' if i==0 else '1 .05 .3 1' if i==len(points)-1 else '1 .65 .05 1'
        shape(link,f'point_{i}','sphere',.35,' '.join(map(str,[*point,0,0,0])),color)


def low_collision_route(city_stl, preview_route):
    """Aim a short approach through the first city surface on the START–GOAL line."""
    altitude = 3.6  # Gazebo Z, after the city has been scaled.
    approach_distance = 4.0
    start, goal = np.array([preview_route['waypoints'][i] for i in (0, -1)])
    start[2] = goal[2] = altitude
    heading = goal - start
    length = np.linalg.norm(heading)
    heading /= length

    # Intersect the centreline with the triangles in the actual collision mesh.
    triangles = np.fromfile(city_stl, dtype=CITY_STL_RECORD, offset=84)['triangle']
    heights = triangles[:, :, 2]
    crosses_altitude = (heights.min(axis=1) <= altitude) & (heights.max(axis=1) >= altitude)
    a, b, c = triangles[crosses_altitude].astype(float).transpose(1, 0, 2)
    edge1, edge2 = b - a, c - a
    p = np.cross(heading, edge2)
    det = np.sum(edge1 * p, axis=1)
    valid = abs(det) > 1e-9
    relative = start - a[valid]
    q = np.cross(relative, edge1[valid])
    u = np.sum(relative * p[valid], axis=1) / det[valid]
    v = (q @ heading) / det[valid]
    distances = np.sum(edge2[valid] * q, axis=1) / det[valid]
    hits = distances[(u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9)
                     & (distances > 0) & (distances < length)]
    if not len(hits) or hits.min() < approach_distance:
        raise ValueError('Could not find a city surface at the selected altitude with room for the approach')
    impact = start + hits.min() * heading
    approach = impact - approach_distance * heading
    target = impact + 1.0 * heading
    return dict(case='low_collision', waypoints=[approach.tolist(), target.tolist()],
                altitude=altitude, length=math.dist(approach, target), speed=2., start_delay=5.,
                expected_centreline_intersection=impact.tolist())


def delivery_route(city_stl, preview_route, case='delivery', plan_folder=None):
    """Use a saved Funnel plan and check the final vertical delivery approach."""
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union

    filename = 'surface_plan.json' if case == 'surface_delivery' else 'horizontal_plan.json'
    plan_path = (Path(plan_folder) if plan_folder is not None else ROOT / f'generated/funnel_physics/{case}') / filename
    plan = json.loads(plan_path.read_text())
    for relative, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Delivery plan input changed: {relative}; rebuild the delivery plan')
    horizontal_points = np.array(plan['waypoints'])
    if math.dist(horizontal_points[0], preview_route['waypoints'][1]) > 1e-7:
        raise ValueError('The delivery plan must preserve the fixed START')
    goal = horizontal_points[-1]
    x, y, cruise_z = goal
    triangles = np.fromfile(city_stl, dtype=CITY_STL_RECORD, offset=84)['triangle']
    bounds_min, bounds_max = triangles.min(axis=1), triangles.max(axis=1)
    xy = goal[:2]
    half = DELIVERY_PAD_SIZE / 2
    near_pad = ((bounds_min[:, :2] <= xy + half) & (bounds_max[:, :2] >= xy - half)).all(axis=1)
    if not near_pad.any():
        raise ValueError('No city surface underneath the selected delivery spot')
    ground_z = float(bounds_max[near_pad, 2].max())
    flat = near_pad & (abs(triangles[:, :, 2] - ground_z) <= 1e-5).all(axis=1)
    floor = unary_union([Polygon(face[:, :2]) for face in triangles[flat]])
    footprint = box(x - half, y - half, x + half, y + half)
    if footprint.difference(floor).area > 1e-6:
        raise ValueError('The delivery pad footprint is not fully supported by a flat city surface')

    delivery_z = ground_z + DELIVERY_PAD_THICKNESS + 1.0
    if cruise_z <= delivery_z:
        raise ValueError('Cruise altitude must be above the delivery hover point')
    # The descent column extends beyond the arms and ends above the floor.
    half_clearance = 1.6
    lower = [x - half_clearance, y - half_clearance, ground_z + 1e-4]
    upper = [x + half_clearance, y + half_clearance, cruise_z + 0.5]
    overlaps = ((bounds_min <= upper) & (bounds_max >= lower)).all(axis=1)
    if overlaps.any():
        raise ValueError('The descent column overlaps city geometry above the floor')

    horizontal_length = sum(math.dist(a, b) for a, b in zip(horizontal_points, horizontal_points[1:]))
    expected_length = plan['flight_length'] if case == 'surface_delivery' else plan['horizontal_length']
    if abs(horizontal_length - expected_length) > 1e-6:
        raise ValueError('Delivery plan length mismatch')
    result = dict(preview_route, case=case,
                waypoints=[*plan['waypoints'], [x, y, delivery_z]],
                original_waypoints=plan['original_waypoints'],
                original_model_length=plan['original_model_length'],
                horizontal_length=horizontal_length, length=horizontal_length + cruise_z - delivery_z,
                altitude=cruise_z, speed=3., start_delay=4., descent_speed=1.0, delivery_ground_z=ground_z,
                source_route_file=plan_path.relative_to(ROOT).as_posix(),
                source_route_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                delivery_destination=plan['selection'],
                delivery_clearance_aabb={'min': lower, 'max': upper})
    if case == 'surface_delivery':
        result.update(speed=5., dwell=0.)
        result['surface_plan_sha256'] = hashlib.sha256(plan_path.read_bytes()).hexdigest()
        result['surface_following_length'] = horizontal_length
        result['horizontal_length'] = sum(math.dist(a[:2], b[:2]) for a, b in zip(horizontal_points, horizontal_points[1:]))
        result['surface_waypoints'] = plan['surface_waypoints']
    return result


def add_delivery_pad(world, delivery_point, ground_z, horizontal_points):
    x, y, z = delivery_point
    pad = ET.SubElement(world, 'model', name='delivery_pad')
    ET.SubElement(pad, 'static').text = 'true'
    ET.SubElement(pad, 'pose').text = f'{x} {y} {ground_z + DELIVERY_PAD_THICKNESS / 2} 0 0 0'
    link = ET.SubElement(pad, 'link', name='pad')
    size = f'{DELIVERY_PAD_SIZE} {DELIVERY_PAD_SIZE} {DELIVERY_PAD_THICKNESS}'
    shape(link, 'platform', 'box', size, '0 0 0 0 0 0', '.06 .65 .45 1')
    collision = ET.SubElement(link, 'collision', name='pad_collision')
    ET.SubElement(ET.SubElement(ET.SubElement(collision, 'geometry'), 'box'), 'size').text = size

    # Fit the full journey, including the fixed START and the distant destination.
    points = np.array(horizontal_points)
    low, high = points.min(axis=0), points.max(axis=0)
    centre = (low + high) / 2
    span = max(high[0] - low[0], high[1] - low[1], 20.)
    camera = centre + np.array([-.6 * span, -.6 * span, span])
    camera_pose = [*camera, 0., math.atan2(1., math.hypot(.6, .6)), math.pi / 4]
    world.find("gui/plugin[@filename='MinimalScene']/camera_pose").text = ' '.join(map(str, camera_pose))


def configure_surface_gui(world):
    """Keep standard Gazebo helper plugins from consuming the scene viewport."""
    ET.SubElement(world.find('gui'), 'plugin', filename='CameraTracking', name='Camera Tracking')
    for plugin in world.findall('gui/plugin'):
        name = plugin.get('filename')
        panel = ET.SubElement(plugin, 'gz-gui')
        ET.SubElement(panel, 'property', type='bool', key='showTitleBar').text = 'false'
        ET.SubElement(panel, 'property', type='string', key='state').text = 'docked' if name == 'MinimalScene' else 'floating'
        if name == 'MinimalScene':
            ET.SubElement(panel, 'title').text = '3D View'
            continue
        ET.SubElement(panel, 'property', type='bool', key='resizable').text = 'false'
        if name in ('GzSceneManager', 'InteractiveViewControl', 'CameraTracking'):
            width, height = 5, 5
        else:
            width, height = (200, 72) if name == 'WorldControl' else (230, 90)
            ET.SubElement(panel, 'property', type='double', key='z').text = '1'
            anchors = ET.SubElement(panel, 'anchors', target='3D View')
            side = 'left' if name == 'WorldControl' else 'right'
            ET.SubElement(anchors, 'line', own=side, target=side)
            ET.SubElement(anchors, 'line', own='bottom', target='bottom')
        ET.SubElement(panel, 'property', type='double', key='width').text = str(width)
        ET.SubElement(panel, 'property', type='double', key='height').text = str(height)
        if name == 'WorldControl':
            for tag in ('play_pause', 'step', 'start_paused', 'use_event'):
                ET.SubElement(plugin, tag).text = 'true'
        elif name == 'WorldStats':
            ET.SubElement(plugin, 'sim_time').text = 'true'
            ET.SubElement(plugin, 'real_time_factor').text = 'true'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('original','cross_city','short_open','narrow_corridor','low_collision','delivery','surface_delivery'),default='original')
    parser.add_argument('--show-surface',action='store_true',help='Show the 3D navigation surface and triangle edges')
    parser.add_argument('--destination',choices=('g1','g2','g3'),help='Select a saved fixed-START city experiment')
    args=parser.parse_args()
    if args.destination and args.case!='surface_delivery':
        parser.error('--destination requires --case surface_delivery')
    generated=ROOT/'generated'
    preview=generated/'funnel_preview'
    out=generated/'funnel_physics'
    validation=json.loads((generated/'funnel_route_candidate_validation_y2p00.json').read_text())
    route=json.loads((preview/'route.json').read_text())
    for key,path in (('route_sha256',generated/'funnel_route_candidate_y2p00.json'),
                     ('mesh_sha256',generated/'funnel_input_y2p00.geom')):
        if validation[key]!=hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError('Candidate or mesh changed; repeat candidate validation and preview export')
    if not validation['surface_membership_passed'] or route['source_route_sha256']!=validation['route_sha256']:
        raise ValueError('Preview route is not the validated candidate')
    world_name='funnel_physics'
    if args.case!='original':
        if args.case=='low_collision':
            route=low_collision_route(preview/'city.stl',route)
        elif args.case in ('delivery','surface_delivery'):
            mission_folder=ROOT/'generated/city_three_goals'/args.destination if args.destination else None
            route=delivery_route(preview/'city.stl',route,args.case,mission_folder)
        else:
            route=benchmark_route(args.case,route)
        out=out/args.case
        world_name+='_'+args.case
    if args.destination:
        out=ROOT/'generated/city_three_goals'/args.destination
        world_name+='_'+args.destination
    out.mkdir(exist_ok=True,parents=True)
    if args.case not in ('low_collision','delivery','surface_delivery'):
        route['speed']=5.
    route.update(max_acceleration=3.,mode='force_feedback_point_mass',world=world_name)
    if args.case in ('short_open','narrow_corridor'):
        route.update(speed=2.,start_delay=8.)
    tree=ET.parse(preview/'funnel_demo.sdf')
    world=tree.getroot().find('world')
    world.set('name',world_name)
    if args.case!='original':
        replace_route(world,route['waypoints'],show_descent=args.case in ('delivery','surface_delivery'))
    if args.case in ('delivery','surface_delivery'):
        add_delivery_pad(world,route['waypoints'][-1],route['delivery_ground_z'],route['waypoints'][:-1])
    if args.case=='surface_delivery':
        configure_surface_gui(world)
    if args.case=='surface_delivery' and args.show_surface:
        add_surface_overlay(world, out)
    if args.case in ('short_open','narrow_corridor'):
        centre=np.mean([route['waypoints'][0],route['waypoints'][-1]],axis=0)
        camera=centre+np.array([12.,-16.,12.])
        camera_pose=[*camera,0.,math.atan2(12.,20.),math.atan2(16.,-12.)]
        world.find("gui/plugin[@filename='MinimalScene']/camera_pose").text=' '.join(map(str,camera_pose))
    if args.case=='low_collision':
        centre=np.array(route['expected_centreline_intersection'])
        heading=centre-route['waypoints'][0]
        heading/=np.linalg.norm(heading)
        camera=centre-10.*heading+9.*np.array([-heading[1],heading[0],0.])+[0.,0.,7.]
        direction=centre-camera
        camera_pose=[*camera,0.,math.atan2(-direction[2],math.hypot(*direction[:2])),
                     math.atan2(direction[1],direction[0])]
        world.find("gui/plugin[@filename='MinimalScene']/camera_pose").text=' '.join(map(str,camera_pose))
    city=world.find("model[@name='HCM_city']/link")
    uri=(preview/'city.stl').as_uri()
    city.find('visual/geometry/mesh/uri').text=uri
    if args.case=='surface_delivery':
        from prepare_city_visual import prepare_visuals, OUT as visual_folder
        colours=prepare_visuals()
        city.remove(city.find('visual'))
        for group in colours['groups']:
            visual=ET.SubElement(city,'visual',name=group['name'])
            ET.SubElement(ET.SubElement(ET.SubElement(visual,'geometry'),'mesh'),'uri').text=(visual_folder/group['file']).as_uri()
            material=ET.SubElement(visual,'material')
            rgba=' '.join(map(str,group['rgba']))
            ET.SubElement(material,'ambient').text=rgba
            ET.SubElement(material,'diffuse').text=rgba
            ET.SubElement(material,'specular').text='.08 .08 .08 1'
        scene=world.find('scene')
        scene.find('ambient').text='.65 .65 .65 1'
        scene.find('background').text='.72 .81 .9 1'
        ET.SubElement(scene,'shadows').text='true'
    collision=ET.SubElement(city,'collision',name='city_collision')
    ET.SubElement(ET.SubElement(ET.SubElement(collision,'geometry'),'mesh'),'uri').text=uri
    drone=world.find("model[@name='drone']")
    drone.find('pose').text=' '.join(map(str,[*route['waypoints'][0],0,0,0]))
    body=drone.find("link[@name='body']")
    body.find('gravity').text='true'
    # A visual-only locator makes the small vehicle visible in the city-wide view.
    shape(body,'locator_stem','cylinder',(.06,1.8),'0 0 1.2 0 0 0','1 .05 .8 1')
    locator=shape(body,'locator','sphere',.5,'0 0 2.1 0 0 0','1 .05 .8 1')
    ET.SubElement(locator.find('material'),'emissive').text='.8 .02 .6 1'
    collision=ET.SubElement(body,'collision',name='body_collision')
    ET.SubElement(ET.SubElement(ET.SubElement(collision,'geometry'),'box'),'size').text='.9 .6 .25'
    if args.case=='low_collision':
        ET.SubElement(world,'plugin',filename='gz-sim-contact-system',name='gz::sim::systems::Contact')
        sensor=ET.SubElement(body,'sensor',name='drone_contact',type='contact')
        ET.SubElement(ET.SubElement(sensor,'contact'),'collision').text='body_collision'
    plugin=ET.SubElement(drone,'plugin',filename='gz-sim-python-system-loader-system',name='gz::sim::systems::PythonSystemLoader')
    ET.SubElement(plugin,'module_name').text='funnel_drone_system'
    ET.indent(tree.getroot())
    tree.write(out/'funnel_physics.sdf',encoding='utf-8',xml_declaration=True)
    (out/'route.json').write_text(json.dumps(route,indent=2)+'\n')
    trajectory=Trajectory(route['waypoints'],route['speed'],dwell=route.get('dwell',1.5),max_acceleration=route['max_acceleration'],
                          descent_speed=route.get('descent_speed'))
    duration=trajectory.duration+route.get('start_delay',2.)
    print(f'Prepared: {out / "funnel_physics.sdf"}')
    print(f'Force feedback tracking; speed limit {route["speed"]:g}; waypoint dwell {trajectory.dwell:g}s; duration about {duration:.1f} simulated seconds.')
    print(f'Telemetry: {out / "physics_telemetry.csv"}')
    if args.case=='low_collision':
        print(f'Collision experiment: Gazebo Z={route["altitude"]:g}; aim through the city mesh.')
        print(f'Contacts: /world/{world_name}/model/drone/link/body/sensor/drone_contact/contact')
    if args.case in ('delivery','surface_delivery'):
        print(f'Delivery descent: Z={route["altitude"]:.2f} to Z={route["waypoints"][-1][2]:.2f}; final hover above the pad.')
    print('Model: 1 kg point mass, gravity compensation and PD feedback; not a rotor or autopilot simulation.')
    for filename in ('funnel_physics.sdf','route.json'):
        print(f'Save at: {out / filename}')


if __name__=='__main__':
    main()
