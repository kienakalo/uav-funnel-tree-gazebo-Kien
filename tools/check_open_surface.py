"""Independent analytic shortest-path check on an L-shaped open mesh."""
import math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from mesh import Mesh,Point
from funnel_tree import solve
points=[Point(0,0,0),Point(2,0,0),Point(2,2,0),Point(1,2,0),Point(1,1,0),Point(0,1,0),Point(.2,.8,0),Point(1.2,1.8,0)]
faces=[(0,1,4),(0,4,6),(4,5,6),(5,0,6),(1,2,4),(2,3,7),(3,4,7),(4,2,7)]
paths,_=solve(Mesh(points,faces),6)
length=sum(math.dist(a,b) for a,b in zip(paths[7],paths[7][1:]))
expected=2*math.sqrt(.68)
assert abs(length-expected)<1e-7,(length,expected)
print('L-shaped open surface PASS; length:',length,'analytic:',expected)
