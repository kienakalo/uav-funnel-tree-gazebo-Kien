# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main libraries: Python stdlib (argparse, json, math, pathlib, sys, xml); local modules
# (city, funnel_tree, mesh).
"""Create offline Gazebo world, city STL, virtual flight mesh and route."""
import argparse
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from mesh import Mesh,Point
from funnel_tree import solve
from city import load_city,write_stl

ROOT=Path(__file__).resolve().parent


def material(visual,color):
    mat=ET.SubElement(visual,'material')
    ET.SubElement(mat,'ambient').text=color
    ET.SubElement(mat,'diffuse').text=color


def shape(link,name,kind,size,pose,color):
    v=ET.SubElement(link,'visual',name=name);ET.SubElement(v,'pose').text=pose
    geom=ET.SubElement(v,'geometry');elem=ET.SubElement(geom,kind)
    if kind=='sphere':ET.SubElement(elem,'radius').text=str(size)
    elif kind=='box':ET.SubElement(elem,'size').text=size
    elif kind=='cylinder':
        ET.SubElement(elem,'radius').text=str(size[0]);ET.SubElement(elem,'length').text=str(size[1])
    material(v,color)
    return v


def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['pose','physics'],default='pose');args=p.parse_args()
    out=ROOT/'generated';out.mkdir(exist_ok=True)
    vertices,faces,meta=load_city(ROOT/'assets/city.glb')
    write_stl(out/'city.stl',vertices,faces)
    z=float(vertices[:,2].max())+10.
    # Explicit virtual horizontal navigation surface ABOVE city, not a conversion
    # of disconnected building shells into a purported navigable manifold.
    mesh=Mesh([Point(-70,-55,z),Point(70,-55,z),Point(-70,55,z),Point(70,55,z)],[(0,1,2),(1,3,2)])
    missions=[(0,3),(3,1),(1,2),(2,0)]
    waypoints=[];all_stats=[]
    for source,target in missions:
        paths,stats=solve(mesh,source)
        path=paths[target]
        if waypoints:path=path[1:]
        waypoints.extend(path);all_stats.append(stats)
    route={'waypoints':waypoints,'speed':5.,'surface':'virtual plane above city maximum height',
           'altitude':z,'mission_vertex_pairs':missions,'planner':'Python local-cosine Funnel Tree + clipping (experimental)',
           'stats':all_stats,'length':sum(math.dist(a,b) for a,b in zip(waypoints,waypoints[1:]))}
    (out/'route.json').write_text(json.dumps(route,indent=2)+'\n')
    (out/'city_metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    with (out/'flight_surface.geom').open('w') as f:
        f.write('4 2 5\n')
        for point in mesh.points:f.write(f'{point.x} {point.y} {point.z}\n')
        for face in mesh.faces:f.write('3 '+' '.join(map(str,face))+'\n')
    sdf=ET.Element('sdf',version='1.9');world=ET.SubElement(sdf,'world',name='hcm_demo')
    ET.SubElement(world,'gravity').text='0 0 -9.8'
    physics=ET.SubElement(world,'physics',name='default',type='ignored')
    ET.SubElement(physics,'max_step_size').text='0.002';ET.SubElement(physics,'real_time_factor').text='1'
    for filename,name in [('physics','Physics'),('user-commands','UserCommands'),('scene-broadcaster','SceneBroadcaster')]:
        ET.SubElement(world,'plugin',filename=f'gz-sim-{filename}-system',name=f'gz::sim::systems::{name}')
    scene=ET.SubElement(world,'scene');ET.SubElement(scene,'ambient').text='.65 .65 .65 1';ET.SubElement(scene,'background').text='.08 .12 .18 1'
    light=ET.SubElement(world,'light',name='sun',type='directional');ET.SubElement(light,'pose').text='0 0 300 0 0 0'
    ET.SubElement(light,'diffuse').text='.9 .9 .9 1';ET.SubElement(light,'direction').text='-.3 -.5 -1'
    city=ET.SubElement(world,'model',name='HCM_city');ET.SubElement(city,'static').text='true'
    link=ET.SubElement(city,'link',name='geometry');v=ET.SubElement(link,'visual',name='city')
    geom=ET.SubElement(v,'geometry');mg=ET.SubElement(geom,'mesh');ET.SubElement(mg,'uri').text='city.stl'
    material(v,'.45 .65 .78 1')
    # Static city collision uses the same baked geometry; pose preview ignores contacts.
    collision=ET.SubElement(link,'collision',name='city_collision');cg=ET.SubElement(collision,'geometry');cm=ET.SubElement(cg,'mesh');ET.SubElement(cm,'uri').text='city.stl'
    # Mark route as thin static cylinders connecting consecutive waypoints.
    route_model=ET.SubElement(world,'model',name='planned_route');ET.SubElement(route_model,'static').text='true'
    rl=ET.SubElement(route_model,'link',name='route')
    for i,(a,b) in enumerate(zip(waypoints,waypoints[1:])):
        d=[y-x for x,y in zip(a,b)];length=math.dist(a,b)
        if length<1e-8:continue
        mid=[(x+y)/2 for x,y in zip(a,b)]
        yaw=math.atan2(d[1],d[0]);pitch=math.atan2(math.hypot(d[0],d[1]),d[2])
        shape(rl,f'segment_{i}','cylinder',(.12,length),' '.join(map(str,[*mid,0,pitch,yaw])),'1 .55 .05 1')
    for i,point in enumerate(mesh.points):
        shape(rl,f'waypoint_{i}','sphere',1.,f'{point.x} {point.y} {point.z} 0 0 0','.15 1 .4 1')
    drone=ET.SubElement(world,'model',name='drone');ET.SubElement(drone,'pose').text=' '.join(map(str,[*waypoints[0],0,0,0]))
    dl=ET.SubElement(drone,'link',name='body');ET.SubElement(dl,'gravity').text='true' if args.mode=='physics' else 'false'
    inertial=ET.SubElement(dl,'inertial');ET.SubElement(inertial,'mass').text='1'
    inertia=ET.SubElement(inertial,'inertia')
    for key in ['ixx','iyy','izz']:ET.SubElement(inertia,key).text='.4'
    shape(dl,'body','box','2 1.2 .45','0 0 0 0 0 0','1 .2 .05 1')
    shape(dl,'arm_x','box','4 .15 .15','0 0 0 0 0 0','.1 .1 .1 1')
    shape(dl,'arm_y','box','.15 4 .15','0 0 0 0 0 0','.1 .1 .1 1')
    for i,(x,y) in enumerate([(2,0),(-2,0),(0,2),(0,-2)]):
        shape(dl,f'rotor_{i}','cylinder',(.7,.08),f'{x} {y} .2 0 0 0','.1 .9 .9 1')
    if args.mode=='physics':
        col=ET.SubElement(dl,'collision',name='body');geom=ET.SubElement(col,'geometry');box=ET.SubElement(geom,'box');ET.SubElement(box,'size').text='2 1.2 .45'
        plugin=ET.SubElement(drone,'plugin',filename='gz-sim-python-system-loader-system',name='gz::sim::systems::PythonSystemLoader')
        ET.SubElement(plugin,'module_name').text='drone_system'
    gui=ET.SubElement(world,'gui',fullscreen='false')
    plugin=ET.SubElement(gui,'plugin',filename='MinimalScene',name='3D View')
    ET.SubElement(plugin,'engine').text='ogre2';ET.SubElement(plugin,'scene').text='scene'
    ET.SubElement(plugin,'camera_pose').text=f'180 -230 {z+170} 0 .65 2.2'
    ET.SubElement(gui,'plugin',filename='GzSceneManager',name='Scene Manager')
    ET.SubElement(gui,'plugin',filename='InteractiveViewControl',name='Interactive view control')
    ET.SubElement(gui,'plugin',filename='WorldControl',name='World control')
    ET.SubElement(gui,'plugin',filename='WorldStats',name='World stats')
    ET.indent(sdf)
    ET.ElementTree(sdf).write(out/'hcm_demo.sdf',encoding='utf-8',xml_declaration=True)
    print(f'Prepared {len(faces):,} city triangles; flight altitude {z:.2f}; mode {args.mode}.')
    print('World:',out/'hcm_demo.sdf')


if __name__=='__main__':main()
