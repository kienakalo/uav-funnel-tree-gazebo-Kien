"""Bước 1: dữ liệu bề mặt và các phép tính hình học; chưa tính đường đi."""
from dataclasses import dataclass, field
from pathlib import Path
import math


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float

    def distance(self, other):
        return math.sqrt((self.x-other.x)**2 + (self.y-other.y)**2 + (self.z-other.z)**2)


@dataclass
class Mesh:
    points: list[Point]
    faces: list[tuple[int, int, int]]
    vertex_faces: list[list[int]] = field(init=False)
    edge_faces: dict[tuple[int, int], list[int]] = field(init=False)

    def __post_init__(self):
        self.vertex_faces = [[] for _ in self.points]
        self.edge_faces = {}
        seen_faces = set()
        coords = [(p.x,p.y,p.z) for p in self.points]
        if any(not all(math.isfinite(x) for x in c) for c in coords):
            raise ValueError('Tọa độ không hữu hạn.')
        if len(set(coords)) != len(coords):
            raise ValueError('Có đỉnh trùng tọa độ.')
        for face_id, face in enumerate(self.faces):
            if len(set(face)) != 3 or any(v < 0 or v >= len(self.points) for v in face):
                raise ValueError(f'Mặt {face_id} có chỉ số đỉnh không hợp lệ.')
            key = tuple(sorted(face))
            if key in seen_faces:
                raise ValueError(f'Mặt {face_id} bị trùng.')
            seen_faces.add(key)
            a,b,c = [self.points[v] for v in face]
            u = (b.x-a.x,b.y-a.y,b.z-a.z)
            w = (c.x-a.x,c.y-a.y,c.z-a.z)
            cross = (u[1]*w[2]-u[2]*w[1],u[2]*w[0]-u[0]*w[2],u[0]*w[1]-u[1]*w[0])
            if sum(x*x for x in cross) == 0:
                raise ValueError(f'Mặt {face_id} suy biến.')
            for v in face:
                self.vertex_faces[v].append(face_id)
            a,b,c = face
            for v,w in [(a,b),(b,c),(c,a)]:
                edge = tuple(sorted((v,w)))
                self.edge_faces.setdefault(edge,[]).append(face_id)
                if len(self.edge_faces[edge]) > 2:
                    raise ValueError(f'Cạnh {edge} kề hơn hai mặt.')
        if any(not faces for faces in self.vertex_faces):
            raise ValueError('Có đỉnh không thuộc mặt nào.')

    def distance(self, a, b):
        return self.points[a].distance(self.points[b])

    def angle(self, a, b, c):
        """Góc ABC (đỉnh góc tại B), đơn vị radian, dùng định luật cos."""
        ab,bc,ac = self.distance(a,b),self.distance(b,c),self.distance(a,c)
        if ab == 0 or bc == 0:
            raise ValueError('Góc không xác định do cạnh có độ dài 0.')
        cosine = (ab*ab + bc*bc - ac*ac)/(2*ab*bc)
        return math.acos(max(-1.0,min(1.0,cosine)))

    def other_face(self, a, b, current_face):
        """Mặt bên kia cạnh AB; trả None nếu AB là cạnh biên."""
        adjacent = self.edge_faces[tuple(sorted((a,b)))]
        if current_face not in adjacent:
            raise ValueError('Mặt hiện tại không chứa cạnh được hỏi.')
        return next((f for f in adjacent if f != current_face),None)

    def third_vertex(self, face_id, a, b):
        face = self.faces[face_id]
        if a == b or a not in face or b not in face:
            raise ValueError('Hai đỉnh phải xác định một cạnh của mặt.')
        return next(v for v in face if v != a and v != b)


def read_geom(filename):
    """Header: V F E; tiếp V dòng x y z; tiếp F dòng 3 a b c."""
    lines = [s.strip() for s in Path(filename).read_text(encoding='utf-8').splitlines() if s.strip()]
    nv,nf,declared_edges = map(int,lines[0].split())
    if nv < 3 or nf < 1 or len(lines) != 1+nv+nf:
        raise ValueError('Header và số dòng không khớp hoặc mesh rỗng.')
    points = [Point(*map(float,line.split())) for line in lines[1:1+nv]]
    faces = []
    for line in lines[1+nv:]:
        count,*face = map(int,line.split())
        if count != 3 or len(face) != 3:
            raise ValueError('Chỉ nhận mặt tam giác.')
        faces.append(tuple(face))
    # Số cạnh thực được suy ra từ mặt, vì E trong vài file mẫu chưa chính xác.
    return Mesh(points,faces)
