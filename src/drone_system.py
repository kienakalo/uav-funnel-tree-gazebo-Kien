# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main libraries: Gazebo Harmonic Python bindings (gz.sim8, gz.math7);
# csv, json, math, pathlib (Python stdlib); trajectory (local project module).
"""V2: smooth reference, velocity/acceleration feedforward and position feedback.

Point-mass model with world force at COM; not a rotor/autopilot simulation.
"""
import csv
import json
import math
from pathlib import Path
from gz.math7 import Vector3d
from gz.sim8 import Model, Link
from trajectory import Trajectory, control_acceleration


class DroneSystem:
    route_relative_path='generated/route.json'
    telemetry_relative_path='generated/physics_telemetry.csv'
    label='Drone V2'
    progress_interval=None

    def configure(self,entity,sdf,ecm,event_mgr):
        self.link=Link(Model(entity).canonical_link(ecm))
        self.link.enable_velocity_checks(ecm,True)
        root=Path(__file__).resolve().parents[1]
        data=json.loads((root/self.route_relative_path).read_text())
        self.start_delay=float(data.get('start_delay',2.))
        if not math.isfinite(self.start_delay) or self.start_delay<0:
            raise ValueError('Invalid trajectory start delay')
        self.trajectory=Trajectory(data['waypoints'],max_speed=data.get('speed',5.),dwell=data.get('dwell',1.5),
                                   max_acceleration=data.get('max_acceleration'),
                                   descent_speed=data.get('descent_speed'))
        self.log=(root/self.telemetry_relative_path).open('w',newline='')
        self.writer=csv.writer(self.log)
        self.writer.writerow(['sim_time','x','y','z','target_x','target_y','target_z','error',
                              'vx','vy','vz','target_vx','target_vy','target_vz','segment','phase'])
        self.last_log=-1.
        self.start_time=None
        self.completed=False
        self.last_progress=-math.inf
        print(f'[{self.label}] Feedforward PD configured; route duration about {self.trajectory.duration+self.start_delay:.1f} simulated seconds.',flush=True)

    def pre_update(self,info,ecm):
        if info.paused:return
        pose=self.link.world_pose(ecm)
        velocity=self.link.world_linear_velocity(ecm)
        if pose is None or velocity is None:return
        t=info.sim_time.total_seconds()
        if self.start_time is None:self.start_time=t
        goal,goal_v,goal_a,segment,phase=self.trajectory.state(t-self.start_time-self.start_delay)
        p=pose.pos();position=(p.x(),p.y(),p.z())
        v=(velocity.x(),velocity.y(),velocity.z())
        a=control_acceleration(position,v,goal,goal_v,goal_a)
        self.link.add_world_force(ecm,Vector3d(a[0],a[1],a[2]+9.8))
        if t-self.last_log>=.1:
            error=math.dist(position,goal)
            self.writer.writerow([t,*position,*goal,error,*v,*goal_v,segment,phase])
            self.log.flush();self.last_log=t
        if phase=='complete' and not self.completed:
            print(f'[{self.label}] Route complete; holding final position.',flush=True)
            self.completed=True
        if self.progress_interval is not None and not self.completed and t-self.last_progress>=self.progress_interval:
            print(f'[{self.label}] t={t-self.start_time:.1f}s; segment={segment}; phase={phase}; error={math.dist(position,goal):.6f}',flush=True)
            self.last_progress=t


def get_system():return DroneSystem()
