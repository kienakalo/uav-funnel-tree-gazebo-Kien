# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, uav-funnel-tree-gazebo contributors
# Main libraries: NumPy; Python stdlib (argparse, csv, hashlib, json, pathlib, struct).
"""Inspect original GLB scene Y levels. No Gazebo axis conversion or rescaling.

Only numpy is required. This reader supports this asset's uncompressed GLB2
triangle primitives; unsupported encodings fail explicitly.
"""
import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path
import numpy as np


def transformed_objects(filename):
    blob=filename.read_bytes()
    magic,version,total=struct.unpack_from('<4sII',blob)
    if magic!=b'glTF' or version!=2 or total!=len(blob):raise ValueError('Invalid GLB2.')
    chunks={};offset=12
    while offset<len(blob):
        size,kind=struct.unpack_from('<II',blob,offset)
        chunks[kind]=blob[offset+8:offset+8+size];offset+=8+size
    doc=json.loads(chunks[0x4e4f534a]);binary=chunks[0x004e4942]
    def accessor(i):
        a=doc['accessors'][i]
        if 'sparse' in a:raise ValueError('Sparse accessor not supported.')
        view=doc['bufferViews'][a['bufferView']]
        if view.get('buffer',0)!=0:raise ValueError('External buffer not supported.')
        dtype=np.dtype({5121:'u1',5123:'<u2',5125:'<u4',5126:'<f4'}[a['componentType']])
        width={'SCALAR':1,'VEC3':3}[a['type']]
        return np.ndarray((a['count'],width),dtype=dtype,buffer=binary,
            offset=view.get('byteOffset',0)+a.get('byteOffset',0),
            strides=(view.get('byteStride',width*dtype.itemsize),dtype.itemsize)).copy()
    def local_matrix(node):
        if 'matrix' in node:return np.array(node['matrix']).reshape(4,4,order='F')
        x,y,z,w=node.get('rotation',[0,0,0,1])
        rotation=np.array([[1-2*y*y-2*z*z,2*x*y-2*z*w,2*x*z+2*y*w],
            [2*x*y+2*z*w,1-2*x*x-2*z*z,2*y*z-2*x*w],
            [2*x*z-2*y*w,2*y*z+2*x*w,1-2*x*x-2*y*y]])
        matrix=np.eye(4);matrix[:3,:3]=rotation@np.diag(node.get('scale',[1,1,1]))
        matrix[:3,3]=node.get('translation',[0,0,0]);return matrix
    def walk(i,parent):
        node=doc['nodes'][i];matrix=parent@local_matrix(node)
        if 'mesh' in node:
            pieces=[]
            for primitive in doc['meshes'][node['mesh']]['primitives']:
                if primitive.get('mode',4)!=4 or primitive.get('extensions',{}).get('KHR_draco_mesh_compression'):
                    raise ValueError('Only uncompressed triangle primitives supported.')
                p=accessor(primitive['attributes']['POSITION']).astype(float)
                p=(np.c_[p,np.ones(len(p))]@matrix.T)[:,:3]
                indices=accessor(primitive['indices']).ravel() if 'indices' in primitive else np.arange(len(p))
                pieces.append(p[indices.reshape(-1,3)])
            yield node.get('name',str(i)),np.concatenate(pieces)
        for child in node.get('children',[]):yield from walk(child,matrix)
    for i in doc['scenes'][doc.get('scene',0)]['nodes']:yield from walk(i,np.eye(4))


def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--city',type=Path)
    parser.add_argument('--out',type=Path,default=root/'generated')
    args=parser.parse_args()
    city=args.city or next((p for p in [root/'data/input/city.glb',root/'assets/city.glb'] if p.is_file()),None)
    if city is None or not city.is_file():parser.error('Use --city path/to/city.glb')
    heights=np.arange(.5,5.51,.5);eps=1e-6
    rows=[dict(flight_height=float(h),intersect_objects=0,crossing_faces=0,coplanar_faces=0) for h in heights]
    objects=[]
    for name,triangles in transformed_objects(city):
        if not np.isfinite(triangles).all():raise ValueError('Nonfinite geometry.')
        lo=triangles.min(axis=(0,1));hi=triangles.max(axis=(0,1))
        low=triangles[:,:,1].min(axis=1);high=triangles[:,:,1].max(axis=1)
        objects.append(dict(object=name,faces=len(triangles),y_min=float(lo[1]),y_max=float(hi[1]),
            x_min=float(lo[0]),x_max=float(hi[0]),z_min=float(lo[2]),z_max=float(hi[2])))
        for h,row in zip(heights,rows):
            # Bounds and triangles are BOTH in transformed scene coordinates.
            if not lo[1]-eps<=h<=hi[1]+eps:continue
            crossing=int(((low<=h+eps)&(high>=h-eps)&((high-low)>eps)).sum())
            coplanar=int((np.abs(triangles[:,:,1]-h)<eps).all(axis=1).sum())
            row['intersect_objects']+=int(crossing>0 or coplanar>0)
            row['crossing_faces']+=crossing;row['coplanar_faces']+=coplanar
    args.out.mkdir(parents=True,exist_ok=True)
    write_csv(args.out/'flight_level_candidates_fixed.csv',rows)
    write_csv(args.out/'city_object_height_bounds_fixed.csv',objects)
    metadata={'city_file':str(city.resolve()),'sha256':hashlib.sha256(city.read_bytes()).hexdigest(),
              'coordinates':'original transformed GLB scene, Y-up; no Gazebo normalization',
              'units':'model units; physical scale not verified','epsilon':eps,'objects':len(objects),
              'faces':sum(o['faces'] for o in objects),'levels':rows}
    (args.out/'flight_levels_fixed_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('ORIGINAL GLB SCENE: Y-up; model units, NOT verified metres.')
    print('Objects:',len(objects),'Faces:',metadata['faces'])
    for row in rows:
        print(f'Y={row["flight_height"]:.2f} | objects={row["intersect_objects"]} | crossing_faces={row["crossing_faces"]} | coplanar_faces={row["coplanar_faces"]}')
    print('Saved fixed CSV files and metadata in',args.out)


if __name__=='__main__':main()
