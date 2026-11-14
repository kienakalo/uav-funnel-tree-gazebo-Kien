# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main libraries: Python stdlib (argparse, json, os, pathlib, signal, subprocess, time, xml).
"""Run accelerated headless force-feedback tracking and save real telemetry."""
import json
import argparse
import os
from pathlib import Path
import signal
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--activated-venv',action='store_true',help='Reproduce launching from an activated virtualenv')
    parser.add_argument('--case',choices=('original','cross_city','short_open','narrow_corridor'),default='original')
    args=parser.parse_args()
    out=ROOT/'generated/funnel_physics'
    world_name='funnel_physics'
    if args.case!='original':
        out=out/args.case
        world_name+='_'+args.case
    subprocess.run(['/usr/bin/python3',str(ROOT/'tools/prepare_funnel_physics.py'),'--case',args.case],check=True,cwd=ROOT)
    tree=ET.parse(out/'funnel_physics.sdf')
    tree.getroot().find('world/physics/real_time_factor').text='0'
    test_world=out/'headless_check.sdf'
    tree.write(test_world,encoding='utf-8',xml_declaration=True)
    env=dict(os.environ)
    env['GZ_PARTITION']=f'funnel_physics_check_{os.getpid()}'
    env['FUNNEL_RUN_ID']=f'headless_check_{os.getpid()}_{time.time_ns()}'
    env['FUNNEL_PHYSICS_CASE']=args.case
    if args.activated_venv:
        env['VIRTUAL_ENV']=str(ROOT/'.venv')
        env['PATH']=str(ROOT/'.venv/bin')+os.pathsep+env['PATH']
    env['PYTHONPATH']=str(ROOT/'src')+os.pathsep+env.get('PYTHONPATH','')
    env['GZ_SIM_SYSTEM_PLUGIN_PATH']=str(ROOT/'src')+os.pathsep+env.get('GZ_SIM_SYSTEM_PLUGIN_PATH','')
    telemetry=out/'physics_telemetry.csv'
    old_stamp=telemetry.stat().st_mtime_ns if telemetry.exists() else None
    with (out/'gazebo_headless.log').open('w') as log:
        server=subprocess.Popen(['bash',str(ROOT/'scripts/gazebo_system_python.sh'),'sim','-s','-v','3',str(test_world)],cwd=ROOT,env=env,
                                stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            init_deadline=time.monotonic()+30
            metadata_path=out/'telemetry_metadata.json'
            while True:
                if server.poll() is not None:
                    raise RuntimeError('Gazebo exited before controller initialization')
                if metadata_path.exists() and json.loads(metadata_path.read_text()).get('run_id')==env['FUNNEL_RUN_ID']:
                    break
                if time.monotonic()>init_deadline:
                    raise TimeoutError('Controller did not initialize while paused')
                time.sleep(.2)
            reply=subprocess.run(['gz','service','-s',f'/world/{world_name}/control','--reqtype','gz.msgs.WorldControl',
                                  '--reptype','gz.msgs.Boolean','--timeout','5000','--req','pause: false'],
                                 cwd=ROOT,env=env,capture_output=True,text=True,timeout=10,check=True)
            if 'data: true' not in reply.stdout:
                raise RuntimeError('Could not unpause initialized physics world')
            print('Controller initialized while paused; starting force-driven tracking.',flush=True)
            deadline=time.monotonic()+90
            while True:
                if server.poll() is not None:
                    raise RuntimeError('Gazebo exited; see generated/funnel_physics/gazebo_headless.log')
                if telemetry.exists() and telemetry.stat().st_mtime_ns!=old_stamp:
                    lines=telemetry.read_text().splitlines()
                    if len(lines)>1 and lines[-1].endswith(',complete'):
                        metadata=json.loads((out/'telemetry_metadata.json').read_text())
                        if metadata.get('run_id')!=env['FUNNEL_RUN_ID']:
                            raise ValueError('Telemetry belongs to a different simulation run')
                        print('Force-driven mission completed; stopping isolated test world.',flush=True)
                        break
                if time.monotonic()>deadline:
                    raise TimeoutError('No completed force-driven telemetry within 90 wall seconds; inspect gazebo_headless.log')
                time.sleep(.5)
        finally:
            if server.poll() is None:
                os.killpg(server.pid,signal.SIGTERM)
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(server.pid,signal.SIGKILL)
                    server.wait(timeout=5)
    subprocess.run(['/usr/bin/python3',str(ROOT/'tools/analyze_funnel_physics.py'),'--case',args.case],cwd=ROOT,check=True)


if __name__=='__main__':
    main()
