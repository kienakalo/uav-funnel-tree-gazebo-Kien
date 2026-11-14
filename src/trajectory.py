# Main libraries: math (Python standard library).
# Quintic time parameterization and feedforward + PD are implemented locally.
"""Time parameterization on the existing polyline; does not change path planning."""
import math


class Trajectory:
    def __init__(self, points, max_speed=5., dwell=1.5, max_acceleration=None, descent_speed=None):
        if max_speed<=0 or dwell<0 or not points:
            raise ValueError('Invalid trajectory settings.')
        if max_acceleration is not None and (not math.isfinite(max_acceleration) or max_acceleration<=0):
            raise ValueError('Invalid trajectory acceleration limit.')
        self.points=[tuple(map(float,p)) for p in points]
        self.descent_index=None
        if descent_speed is not None:
            if not math.isfinite(descent_speed) or descent_speed<=0:
                raise ValueError('Invalid descent speed limit.')
            if len(self.points)<2 or self.points[-2][:2]!=self.points[-1][:2] or self.points[-2][2]<=self.points[-1][2]:
                raise ValueError('The last waypoint must be directly below the preceding waypoint.')
            self.descent_index=len(self.points)-2
        self.segments=[]
        elapsed=0.
        for index,(a,b) in enumerate(zip(self.points,self.points[1:])):
            distance=math.dist(a,b)
            if distance<1e-9:
                continue
            # Quintic smoothstep peak derivative is 1.875.
            speed_limit=descent_speed if index==self.descent_index else max_speed
            duration=max(1.,1.875*distance/speed_limit)
            if max_acceleration is not None:
                # Peak second derivative of quintic smoothstep is 10/sqrt(3).
                duration=max(duration,math.sqrt((10/math.sqrt(3))*distance/max_acceleration))
            self.segments.append((elapsed,duration,a,b,index))
            elapsed+=duration+dwell
        self.duration=elapsed
        self.dwell=dwell

    def state(self,t):
        zero=(0.,0.,0.)
        if t<0:
            return self.points[0],zero,zero,-1,'waiting'
        for start,duration,a,b,index in self.segments:
            if t<start+duration:
                u=max(0.,(t-start)/duration)
                s=10*u**3-15*u**4+6*u**5
                ds=(30*u**2-60*u**3+30*u**4)/duration
                dds=(60*u-180*u**2+120*u**3)/(duration*duration)
                delta=[y-x for x,y in zip(a,b)]
                position=tuple(x+s*d for x,d in zip(a,delta))
                velocity=tuple(ds*d for d in delta)
                acceleration=tuple(dds*d for d in delta)
                phase='descending' if index==self.descent_index else 'moving'
                return position,velocity,acceleration,index,phase
            if t<start+duration+self.dwell:
                return b,zero,zero,index,'dwell'
        return self.points[-1],zero,zero,len(self.segments),'complete'


def control_acceleration(position,velocity,goal,goal_velocity,goal_acceleration):
    """Mass-normalized feedforward + PD tracking; gravity is added by the plugin."""
    return tuple(max(-6.,min(6.,a+2.5*(r-x)+3.2*(vr-v)))
                 for x,v,r,vr,a in zip(position,velocity,goal,goal_velocity,goal_acceleration))
