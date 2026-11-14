#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main libraries: Matplotlib, NumPy; Python stdlib (argparse, csv, hashlib, io, json, pathlib,
# sys); local modules (analyze_funnel_physics, mesh).
"""Validate recorded physics telemetry and export route/tracking figures and summary."""
import csv
import argparse
import hashlib
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from mesh import read_geom
from analyze_funnel_physics import main as validate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('original','cross_city','short_open','narrow_corridor'),default='original')
    args=parser.parse_args()
    # Revalidate so plots cannot silently reuse a report from an earlier flight.
    validate(case=args.case)
    out=ROOT/'generated/funnel_physics'
    if args.case!='original':
        out=out/args.case
    report=json.loads((out/'physics_validation.json').read_text())
    route=json.loads((out/'route.json').read_text())
    csv_path=out/'physics_telemetry.csv'
    csv_bytes=csv_path.read_bytes()
    if hashlib.sha256(csv_bytes).hexdigest()!=report['telemetry_sha256']:
        raise ValueError('Telemetry changed during validation; close Gazebo and export again')
    import io
    rows=list(csv.DictReader(io.StringIO(csv_bytes.decode('utf-8'))))
    columns=('sim_time','x','y','z','target_x','target_y','target_z','vx','vy','vz')
    values=np.array([[float(row[key]) for key in columns] for row in rows])
    times=values[:,0]-values[0,0]
    measured=values[:,1:4]
    targets=values[:,4:7]
    errors=np.linalg.norm(measured-targets,axis=1)
    speeds=np.linalg.norm(values[:,7:10],axis=1)
    reverted=measured/route['transform']['scale']+np.array(route['transform']['origin'])
    measured_xz=reverted[:,:2]*[1,-1]
    mesh=read_geom(ROOT/'generated/funnel_input_y2p00.geom')
    vertices=np.array([(p.x,p.z) for p in mesh.points])
    planned=np.array(route['original_waypoints'])[:,[0,2]]
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(10,9))
    ax.set_facecolor('#e4e7eb')
    ax.add_collection(PolyCollection(vertices[np.array(mesh.faces)],facecolors='#d7eadc',edgecolors='none'))
    ax.plot(planned[:,0],planned[:,1],color='#e68019',linewidth=3,label='Planned route')
    ax.plot(measured_xz[:,0],measured_xz[:,1],color='#135fbe',linewidth=1.4,linestyle='--',label='Measured trajectory')
    for label,point,color in (('START',planned[0],'#127c43'),('GOAL',planned[-1],'#b71e42')):
        ax.scatter(*point,s=50,color=color,zorder=4)
        ax.annotate(label,point,xytext=(6,7),textcoords='offset points',weight='bold')
    ax.autoscale()
    ax.set_aspect('equal')
    ax.set(xlabel='X (original model units)',ylabel='Z (original model units)',
           title='Funnel route and measured force-driven trajectory\nCurves overlap at this map scale')
    ax.legend(loc='lower left')
    fig.tight_layout()
    path=out/'physics_route_tracking.png'
    fig.savefig(path,dpi=180)
    plt.close(fig)
    print(f'Save at: {path}',flush=True)

    fig,axes=plt.subplots(3,1,figsize=(11,9),sharex=True)
    axes[0].plot(times,errors,color='#135fbe',linewidth=1.3)
    peak=int(np.argmax(errors))
    axes[0].scatter(times[peak],errors[peak],color='#b71e42',s=25,zorder=3)
    axes[0].set(ylabel='Position error (sim. units)',
                title=f'Force-feedback tracking | max error {errors[peak]:.6f} | moving RMSE {report["moving_rmse"]:.6f}')
    for i,axis in enumerate(('X','Y','Z')):
        axes[1].plot(times,measured[:,i]-targets[:,i],label=axis,linewidth=1.1)
    axes[1].set_ylabel('Signed error (sim. units)')
    axes[1].legend(ncol=3,loc='upper right')
    axes[2].plot(times,speeds,color='#127c43',label='Measured speed')
    axes[2].axhline(route['speed'],linestyle='--',color='#b71e42',linewidth=1,label='Reference speed limit')
    axes[2].set(xlabel='Elapsed simulation time (s)',ylabel='Speed (sim. units/s)')
    axes[2].legend(loc='upper right')
    complete=next((times[i] for i,row in enumerate(rows) if row['phase']=='complete'),None)
    for ax in axes:
        ax.grid(alpha=.2)
        if complete is not None:
            ax.axvline(complete,linestyle=':',color='#666666',linewidth=1)
    fig.text(.5,.012,'Dotted vertical line: route complete. Model: 1 kg point mass; decorative rotors.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.03,1,1))
    path=out/'physics_tracking_metrics.png'
    fig.savefig(path,dpi=180)
    plt.close(fig)
    print(f'Save at: {path}',flush=True)
    summary=(
        'KET QUA MO PHONG BAM TUYEN FUNNEL\n\n'
        f'Kiem tra: {report["checks_passed"]}\nTrang thai cuoi: {report["last_phase"]}\n'
        f'So mau do: {report["samples"]}\nDo dai tuyen (don vi mo hinh goc): {route["original_model_length"]:.9f}\n'
        f'Do dai tuyen (don vi mo phong): {route["length"]:.9f}\n'
        f'Sai lech bam tuyen lon nhat: {report["max_tracking_error"]:.9f}\n'
        f'RMSE khi di chuyen: {report["moving_rmse"]:.9f}\n'
        f'Sai lech cuoi toi GOAL: {report["final_goal_error"]:.12f}\n'
        f'Sai lech do cao lon nhat: {report["max_altitude_deviation"]:.9f}\n'
        f'Toc do do duoc lon nhat: {report["max_measured_speed"]:.9f}\n'
        f'Cac doan co dung cho: {report["dwell_segments_observed"]}\n'
        f'So doan noi mau giao cot vat can mo rong: {len(report["obstacle_intersecting_sample_segments"])}\n\n'
        'PHAM VI\n'
        'Mo hinh khoi diem 1 kg co bu trong luc va dieu khien PD; chua mo phong luc day tung rotor/autopilot.\n'
        'Kiem tra hinh hoc ap dung cho tam drone va doan thang noi cac mau CSV; khong phai chung minh lien tuc theo thoi gian.\n'
        'Don vi mo phong duoc chuan hoa tu asset, chua phai du lieu dia ly do dac.\n'
        'Chua chung nhan tuyen ngan nhat toan cuc.\n\n'
        f'Route SHA256: {report["route_sha256"]}\nTelemetry SHA256: {report["telemetry_sha256"]}\n')
    path=out/'physics_summary.txt'
    path.write_text(summary,encoding='utf-8')
    print(f'Save at: {path}',flush=True)


if __name__=='__main__':
    main()
