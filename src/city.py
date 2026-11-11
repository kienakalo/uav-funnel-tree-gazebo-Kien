"""Load this GLB's uncompressed triangle primitives and bake scene transforms."""
import json
import struct
from pathlib import Path
import numpy as np


def load_city(filename, width=200.):
    blob = Path(filename).read_bytes()
    magic,version,total = struct.unpack_from('<4sII',blob)
    if magic!=b'glTF' or version!=2 or total!=len(blob):
        raise ValueError('Invalid GLB 2 file.')
    chunks = {}; offset = 12
    while offset<len(blob):
        size,kind = struct.unpack_from('<II',blob,offset)
        chunks[kind] = blob[offset+8:offset+8+size]; offset += 8+size
    doc = json.loads(chunks[0x4e4f534a]); binary = chunks[0x004e4942]
    types = {5121:'u1',5123:'<u2',5125:'<u4',5126:'<f4'}
    widths = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}
    def accessor(i):
        a = doc['accessors'][i]
        if 'sparse' in a: raise ValueError('Sparse accessor unsupported.')
        view = doc['bufferViews'][a['bufferView']]
        dt = np.dtype(types[a['componentType']]); w = widths[a['type']]
        return np.ndarray((a['count'],w),dtype=dt,buffer=binary,
            offset=view.get('byteOffset',0)+a.get('byteOffset',0),
            strides=(view.get('byteStride',w*dt.itemsize),dt.itemsize)).copy()
    def transform(node):
        if 'matrix' in node: return np.array(node['matrix']).reshape(4,4,order='F')
        x,y,z,w = node.get('rotation',[0,0,0,1])
        R=np.array([[1-2*y*y-2*z*z,2*x*y-2*z*w,2*x*z+2*y*w],
                    [2*x*y+2*z*w,1-2*x*x-2*z*z,2*y*z-2*x*w],
                    [2*x*z-2*y*w,2*y*z+2*x*w,1-2*x*x-2*y*y]])
        T=np.eye(4);T[:3,:3]=R@np.diag(node.get('scale',[1,1,1]));T[:3,3]=node.get('translation',[0,0,0])
        return T
    vertices=[]; faces=[]; offset=0
    def walk(i,parent):
        nonlocal offset
        node=doc['nodes'][i];M=parent@transform(node)
        if 'mesh' in node:
            for primitive in doc['meshes'][node['mesh']]['primitives']:
                if primitive.get('mode',4)!=4: raise ValueError('Only triangle primitives supported.')
                p=accessor(primitive['attributes']['POSITION']).astype(float)
                p=(np.c_[p,np.ones(len(p))]@M.T)[:,:3]
                # glTF scene Y-up -> Gazebo Z-up after all nested transforms.
                p=p[:,[0,2,1]]*np.array([1,-1,1])
                ind=accessor(primitive['indices']).ravel() if 'indices' in primitive else np.arange(len(p))
                faces.append(ind.reshape(-1,3)+offset);vertices.append(p);offset+=len(p)
        for child in node.get('children',[]):walk(child,M)
    for root in doc['scenes'][doc.get('scene',0)]['nodes']:walk(root,np.eye(4))
    vertices=np.vstack(vertices);faces=np.vstack(faces).astype(np.int64)
    lo,hi=vertices.min(axis=0),vertices.max(axis=0)
    scale=width/max(hi[0]-lo[0],hi[1]-lo[1])
    origin=np.array([(lo[0]+hi[0])/2,(lo[1]+hi[1])/2,lo[2]])
    vertices=(vertices-origin)*scale
    meta={'source_asset':doc.get('asset'), 'triangles':len(faces),'vertices':len(vertices),
          'source_bounds':[lo.tolist(),hi.tolist()], 'scale':scale,'origin':origin.tolist(),
          'bounds':[vertices.min(axis=0).tolist(),vertices.max(axis=0).tolist()],
          'units':'illustrative normalized units treated as metres in simulation; not surveyed georeferencing',
          'textures':'omitted in STL export; geometry preserved'}
    return vertices,faces,meta


def write_stl(filename,vertices,faces):
    triangles=vertices[faces]
    normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    length=np.linalg.norm(normals,axis=1);normals/=np.maximum(length[:,None],1e-30)
    records=np.zeros(len(faces),dtype=[('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attribute','<u2')])
    records['normal']=normals;records['vertices']=triangles
    with Path(filename).open('wb') as f:
        f.write(b'HCM normalized preview; attribution in ATTRIBUTION.md'.ljust(80,b' '))
        f.write(struct.pack('<I',len(faces)));f.write(records.tobytes())
