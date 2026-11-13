"""Force-driven Funnel route tracking using the existing 1 kg point-mass PD model."""
import hashlib
import json
import os
from pathlib import Path
from drone_system import DroneSystem


class FunnelDroneSystem(DroneSystem):
    route_relative_path='generated/funnel_physics/route.json'
    telemetry_relative_path='generated/funnel_physics/physics_telemetry.csv'
    label='Funnel Physics'
    progress_interval=10.

    def configure(self,entity,sdf,ecm,event_mgr):
        case=os.environ.get('FUNNEL_PHYSICS_CASE','original')
        if case not in ('original','cross_city','short_open','narrow_corridor','low_collision','delivery','surface_delivery'):
            raise ValueError('Unknown Funnel physics case')
        folder='generated/funnel_physics'+('' if case=='original' else '/'+case)
        folder=os.environ.get('FUNNEL_OUTPUT_DIR',folder)
        self.route_relative_path=folder+'/route.json'
        self.telemetry_relative_path=folder+'/physics_telemetry.csv'
        if case!='original':
            self.label='Funnel Physics '+case
        super().configure(entity,sdf,ecm,event_mgr)
        root=Path(__file__).resolve().parents[1]
        route=root/self.route_relative_path
        metadata={'route_sha256':hashlib.sha256(route.read_bytes()).hexdigest(),
                  'model':'1 kg point mass with force feedback; box body collision; decorative rotors',
                  'nominal_duration':self.trajectory.duration+self.start_delay,'case':case,
                  'world':json.loads(route.read_text())['world'],
                  'run_id':os.environ.get('FUNNEL_RUN_ID')}
        (route.parent/'telemetry_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')


def get_system():
    return FunnelDroneSystem()
