"""Run experimental Funnel Tree on the supplied geom meshes."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from mesh import read_geom
from funnel_tree import solve


def main():
    p=argparse.ArgumentParser();p.add_argument('mesh',nargs='?',default='cliff');p.add_argument('--source',type=int,default=1)
    p.add_argument('--timeout',type=float,default=20);p.add_argument('--no-clip',action='store_true');args=p.parse_args()
    mesh_path=Path(args.mesh)
    if not mesh_path.exists():mesh_path=ROOT/'data/input'/(args.mesh.removesuffix('.geom')+'.geom')
    paths,stats=solve(read_geom(mesh_path),args.source,timeout=args.timeout,clipping=not args.no_clip)
    out=ROOT/'generated';out.mkdir(exist_ok=True)
    stem=f'{mesh_path.stem}_s{args.source}'
    with (out/(stem+'.geom')).open('w') as f:
        for path in paths:
            f.write(str(len(path))+' '+' '.join('['+' '.join(f'{x:.17g}' for x in point)+']' for point in path)+'\n')
    (out/(stem+'_stats.json')).write_text(json.dumps(stats,indent=2)+'\n')
    print('Saved',out/(stem+'.geom'));print(json.dumps(stats,indent=2))


if __name__=='__main__':main()
