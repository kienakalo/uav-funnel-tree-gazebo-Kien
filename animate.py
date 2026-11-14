# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main libraries: Python stdlib (argparse, csv, json, math, pathlib, re, shutil, subprocess,
# sys, time).
"""Pose preview: send position commands, without physical flight control."""
import argparse,csv,json,math,re,shutil,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def send_pose(point, world, retries=4, timeout_ms=5000):
    """Retry the same idempotent pose request; never skip a failed frame."""
    request=f'name: "drone", position: {{x: {point[0]}, y: {point[1]}, z: {point[2]}}}, orientation: {{w: 1}}'
    command=['gz','service','-s',f'/world/{world}/set_pose','--reqtype','gz.msgs.Pose',
             '--reptype','gz.msgs.Boolean','--timeout',str(timeout_ms),'--req',request]
    detail = ''
    for attempt in range(retries+1):
        try:
            result=subprocess.run(command,capture_output=True,text=True,timeout=timeout_ms/1000+3)
            if result.returncode==0 and re.search(r'\bdata\s*:\s*true\b', result.stdout, re.I):
                return attempt+1
            detail=(result.stdout+'\n'+result.stderr).strip() or f'gz exited with code {result.returncode}'
        except subprocess.TimeoutExpired:
            detail='The gz service client exceeded its process timeout.'
        if attempt < retries:
            delay=min(2., .5*2**attempt)
            print(f'Pose request failed; retry {attempt+1}/{retries} in {delay:g}s: {detail}',
                  file=sys.stderr,flush=True)
            time.sleep(delay)
    raise RuntimeError(f'Set-pose failed after {retries+1} attempts for /world/{world}/set_pose. '
                       f'The simulator may have stopped or its transport may be unavailable. Last response: {detail}')


def main():
    p=argparse.ArgumentParser();p.add_argument('--speed',type=float,default=10.);p.add_argument('--dry-run',action='store_true')
    p.add_argument('--route',type=Path,default=ROOT/'generated/route.json')
    p.add_argument('--world',default='hcm_demo')
    p.add_argument('--log',type=Path,default=ROOT/'generated/pose_commands.csv')
    p.add_argument('--retries',type=int,default=4,help='Retries after the first failed request')
    p.add_argument('--request-timeout-ms',type=int,default=5000)
    p.add_argument('--start-frame',type=int,default=0,help='Resume at this zero-based frame in an already running world')
    args=p.parse_args()
    if not math.isfinite(args.speed) or args.speed<=0:p.error('Speed must be finite and positive.')
    if args.retries<0 or args.request_timeout_ms<1 or args.start_frame<0:p.error('Invalid retry, timeout or start frame.')
    route=json.loads(args.route.read_text())['waypoints']
    if len(route)<2 or any(len(point)!=3 or not all(math.isfinite(x) for x in point) for point in route):
        p.error('Route must contain at least two finite XYZ waypoints.')
    if not args.dry_run and not shutil.which('gz'):p.error('Gazebo not installed: run scripts/install_ubuntu.sh inside Ubuntu.')
    frames=[]
    for a,b in zip(route,route[1:]):
        count=max(1,math.ceil(math.dist(a,b)/args.speed*10))
        frames.extend([[x+(y-x)*i/count for x,y in zip(a,b)] for i in range(count)])
    frames.append(route[-1])
    if args.start_frame>=len(frames):p.error('Start frame is outside the route.')
    if args.dry_run:print('Dry run:',len(frames),'pose frames; no Gazebo request sent.');return
    with args.log.open('w',newline='') as log:
        writer=csv.writer(log);writer.writerow(['frame','x','y','z','service_accepted','attempts','error'])
        for i in range(args.start_frame,len(frames)):
            point=frames[i]
            try:
                attempts=send_pose(point,args.world,args.retries,args.request_timeout_ms)
            except RuntimeError as exc:
                writer.writerow([i,*point,False,args.retries+1,str(exc)]);log.flush()
                raise RuntimeError(f'Preview stopped at frame {i}/{len(frames)-1}. '
                                   f'Log: {args.log}. Resume with --start-frame {i} using the same route and speed. {exc}') from exc
            writer.writerow([i,*point,True,attempts,'']);log.flush()
            if i%20==0:print(f'Pose preview {i}/{len(frames)}',flush=True)
            time.sleep(.1)
    print('Completed. Log contains commanded positions, not measured flight telemetry.')


if __name__=='__main__':
    try:
        main()
    except RuntimeError as exc:
        print(str(exc),file=sys.stderr,flush=True)
        raise SystemExit(1)
