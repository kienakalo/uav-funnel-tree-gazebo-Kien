# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (json, math, pathlib, subprocess, sys, xml); local modules
# (city, prepare, urban_navigation).
"""Prepare a lower-altitude, obstacle-aware mission using existing city assets."""
import json,math,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from city import load_city
from urban_navigation import plan_urban
from prepare import shape


def main():
    baseline=subprocess.run([sys.executable,str(ROOT/'prepare.py'),'--mode','physics'],cwd=ROOT,capture_output=True,text=True)
    if baseline.returncode:raise RuntimeError(baseline.stdout+baseline.stderr)
    vertices,faces,_=load_city(ROOT/'data/source/city.glb')
    mesh,path,report,blocked,origin=plan_urban(vertices,faces)
    out=ROOT/'generated'
    route={'waypoints':path,'speed':3.,'surface':'open triangulated obstacle-free grid corridor at constant altitude',
           'altitude':report['altitude'],'planner':report['optimality_scope'],'length':report['length'],'urban_report':'urban_report.json'}
    (out/'route.json').write_text(json.dumps(route,indent=2)+'\n')
    (out/'urban_report.json').write_text(json.dumps(report,indent=2)+'\n')
    with (out/'flight_surface.geom').open('w') as f:
        f.write(f'{len(mesh.points)} {len(mesh.faces)} {len(mesh.edge_faces)}\n')
        for p in mesh.points:f.write(f'{p.x} {p.y} {p.z}\n')
        for face in mesh.faces:f.write('3 '+' '.join(map(str,face))+'\n')
    tree=ET.parse(out/'hcm_demo.sdf');world=tree.getroot().find('world')
    world.remove(world.find("model[@name='planned_route']"))
    model=ET.SubElement(world,'model',name='planned_route');ET.SubElement(model,'static').text='true'
    link=ET.SubElement(model,'link',name='route')
    for i,(a,b) in enumerate(zip(path,path[1:])):
        d=[y-x for x,y in zip(a,b)];length=math.dist(a,b);mid=[(x+y)/2 for x,y in zip(a,b)]
        pose=[*mid,0,math.atan2(math.hypot(d[0],d[1]),d[2]),math.atan2(d[1],d[0])]
        shape(link,f'path_{i}','cylinder',(.12,length),' '.join(map(str,pose)),'1 .55 .05 1')
    for i,p in enumerate(path):
        color='.1 1 .2 1' if i==0 else '1 .1 .8 1' if i==len(path)-1 else '.2 .8 1 1'
        shape(link,f'point_{i}','sphere',.45,' '.join(map(str,[*p,0,0,0])),color)
    # Red direct line shows why flying straight is inadmissible in the column model.
    a,b=path[0],path[-1];mid=[(x+y)/2 for x,y in zip(a,b)]
    shape(link,'blocked_direct','cylinder',(.07,math.dist(a,b)),
          ' '.join(map(str,[*mid,0,math.pi/2,math.atan2(b[1]-a[1],b[0]-a[0])])),'.85 .1 .1 1')
    world.find("model[@name='drone']/pose").text=' '.join(map(str,[*path[0],0,0,0]))
    mid=[(a+b)/2 for a,b in zip(path[0],path[-1])]
    world.find("gui/plugin[@filename='MinimalScene']/camera_pose").text=f'{mid[0]+65} {mid[1]-80} 75 0 .55 2.25'
    ET.indent(tree.getroot());tree.write(out/'hcm_demo.sdf',encoding='utf-8',xml_declaration=True)
    print(f'[Urban V3] Altitude {report["altitude"]}, clearance {report["clearance"]}, corridor {len(mesh.faces)} triangles.')
    print(f'[Urban V3] Direct line BLOCKED; planned route checked CLEAR. Length {report["length"]:.2f}, waypoints {len(path)}.')
    print('[Urban V3] A* chooses corridor; experimental Funnel Tree computes path inside corridor. No city-global optimum claimed.')


if __name__=='__main__':main()
