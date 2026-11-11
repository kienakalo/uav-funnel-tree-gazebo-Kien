#!/usr/bin/env python3
"""Export the validated candidate and matching city into a separate pose-preview world."""
import hashlib
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from city import load_city, write_stl
from prepare import shape, material
from verification import segment_on_mesh
from mesh import read_geom


def simplify(points):
    """Remove only forward collinear face crossings, retaining route corners."""
    result = []
    for point in points:
        if result and math.dist(result[-1], point) < 1e-12:
            continue
        while len(result) >= 2:
            a, b, c = np.array(result[-2]), np.array(result[-1]), np.array(point)
            delta = c-a
            length = float(np.linalg.norm(delta))
            if length <= 1e-12:
                break
            t = float(np.dot(b-a, delta) / (length*length))
            deviation = float(np.linalg.norm(b-(a+t*delta)))
            if not 0 <= t <= 1 or deviation > 1e-10:
                break
            result.pop()
        result.append(point)
    return result


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    generated = ROOT / "generated"
    candidate_path = generated / "funnel_route_candidate_y2p00.json"
    mesh_path = generated / "funnel_input_y2p00.geom"
    validation = json.loads((generated / "funnel_route_candidate_validation_y2p00.json").read_text())
    if not validation.get("surface_membership_passed"):
        raise ValueError("Run tools/check_funnel_candidate.py successfully first")
    if validation["mesh_sha256"] != sha(mesh_path) or validation["route_sha256"] != sha(candidate_path):
        raise ValueError("Mesh or candidate changed since validation; validate again")
    candidate = json.loads(candidate_path.read_text())
    navigation = json.loads((generated / "navigation_y2p00_report.json").read_text())
    city_path = next((p for p in (ROOT / "data/input/city.glb", ROOT / "assets/city.glb")
                      if p.exists() and sha(p) == navigation["sha256"]), None)
    if city_path is None:
        raise ValueError("No city asset matches the navigation surface asset hash")
    model_path = simplify(candidate["points"])
    mesh = read_geom(mesh_path)
    coords = [(p.x, p.y, p.z) for p in mesh.points]
    for a, b in zip(model_path, model_path[1:]):
        if not segment_on_mesh(a, b, coords, mesh.faces, 1e-7):
            raise ValueError("Simplified segment exits navigation mesh")
    vertices, faces, metadata = load_city(city_path)
    scale = metadata["scale"]
    origin = np.array(metadata["origin"])
    original = np.array(model_path)
    transformed = (original[:, [0, 2, 1]] * [1, -1, 1] - origin) * scale
    # Round trip catches axis sign/order or offset mistakes before SDF export.
    restored = transformed/scale + origin
    restored = restored[:, [0, 2, 1]] * [1, 1, -1]
    if not np.allclose(restored, original, atol=1e-10, rtol=0):
        raise ValueError("Coordinate transform round trip failed")
    out = generated / "funnel_preview"
    out.mkdir(exist_ok=True)
    write_stl(out / "city.stl", vertices, faces)
    waypoints = transformed.tolist()
    length = sum(math.dist(a, b) for a, b in zip(waypoints, waypoints[1:]))
    if abs(length-candidate["length"]*scale) > 1e-6:
        raise ValueError("Scaled route length mismatch")
    route = {"waypoints": waypoints, "speed": 10., "length": length,
             "world": "funnel_demo", "mode": "pose_preview", "source_route_sha256": sha(candidate_path),
             "original_model_length": candidate["length"], "original_waypoints": model_path,
             "transform": {"formula": "([X, -Z, Y] - origin) * scale", "origin": origin.tolist(), "scale": scale},
             "altitude": waypoints[0][2], "optimality_certified": False,
             "units": "normalized simulation units treated as metres; not surveyed coordinates"}
    (out / "route.json").write_text(json.dumps(route, indent=2)+"\n")
    (out / "city_metadata.json").write_text(json.dumps(metadata, indent=2)+"\n")
    sdf = ET.Element("sdf", version="1.9")
    world = ET.SubElement(sdf, "world", name="funnel_demo")
    ET.SubElement(world, "gravity").text = "0 0 -9.8"
    physics = ET.SubElement(world, "physics", name="default", type="ignored")
    ET.SubElement(physics, "max_step_size").text = "0.002"
    ET.SubElement(physics, "real_time_factor").text = "1"
    for filename, name in (("physics", "Physics"), ("user-commands", "UserCommands"), ("scene-broadcaster", "SceneBroadcaster")):
        ET.SubElement(world, "plugin", filename=f"gz-sim-{filename}-system", name=f"gz::sim::systems::{name}")
    scene = ET.SubElement(world, "scene")
    ET.SubElement(scene, "ambient").text = ".7 .7 .7 1"
    ET.SubElement(scene, "background").text = ".08 .12 .18 1"
    light = ET.SubElement(world, "light", name="sun", type="directional")
    ET.SubElement(light, "pose").text = "0 0 300 0 0 0"
    ET.SubElement(light, "diffuse").text = ".9 .9 .9 1"
    ET.SubElement(light, "direction").text = "-.3 -.5 -1"
    city = ET.SubElement(world, "model", name="HCM_city")
    ET.SubElement(city, "static").text = "true"
    link = ET.SubElement(city, "link", name="geometry")
    visual = ET.SubElement(link, "visual", name="city")
    geometry = ET.SubElement(visual, "geometry")
    city_mesh = ET.SubElement(geometry, "mesh")
    ET.SubElement(city_mesh, "uri").text = "city.stl"
    material(visual, ".45 .65 .78 1")
    model = ET.SubElement(world, "model", name="funnel_route")
    ET.SubElement(model, "static").text = "true"
    route_link = ET.SubElement(model, "link", name="route")
    for i, (a, b) in enumerate(zip(waypoints, waypoints[1:])):
        d = [y-x for x, y in zip(a, b)]
        midpoint = [(x+y)/2 for x, y in zip(a, b)]
        pose = [*midpoint, 0, math.atan2(math.hypot(d[0], d[1]), d[2]), math.atan2(d[1], d[0])]
        shape(route_link, f"segment_{i}", "cylinder", (.1, math.dist(a, b)), " ".join(map(str, pose)), "1 .5 .03 1")
    for i, point in enumerate(waypoints):
        color = ".1 1 .2 1" if i == 0 else "1 .05 .3 1" if i == len(waypoints)-1 else "1 .65 .05 1"
        shape(route_link, f"point_{i}", "sphere", .35, " ".join(map(str, [*point, 0, 0, 0])), color)
    drone = ET.SubElement(world, "model", name="drone")
    ET.SubElement(drone, "pose").text = " ".join(map(str, [*waypoints[0], 0, 0, 0]))
    body = ET.SubElement(drone, "link", name="body")
    ET.SubElement(body, "gravity").text = "false"
    inertial = ET.SubElement(body, "inertial")
    ET.SubElement(inertial, "mass").text = "1"
    inertia = ET.SubElement(inertial, "inertia")
    for axis in ("ixx", "iyy", "izz"):
        ET.SubElement(inertia, axis).text = ".1"
    shape(body, "body", "box", ".9 .6 .25", "0 0 0 0 0 0", "1 .2 .05 1")
    shape(body, "arm_x", "box", "1.8 .09 .09", "0 0 0 0 0 0", ".1 .1 .1 1")
    shape(body, "arm_y", "box", ".09 1.8 .09", "0 0 0 0 0 0", ".1 .1 .1 1")
    for i, (x, y) in enumerate(((.9, 0), (-.9, 0), (0, .9), (0, -.9))):
        shape(body, f"rotor_{i}", "cylinder", (.3, .05), f"{x} {y} .1 0 0 0", ".1 .9 .9 1")
    gui = ET.SubElement(world, "gui", fullscreen="false")
    plugin = ET.SubElement(gui, "plugin", filename="MinimalScene", name="3D View")
    ET.SubElement(plugin, "engine").text = "ogre2"
    ET.SubElement(plugin, "scene").text = "scene"
    ET.SubElement(plugin, "camera_pose").text = "170 -210 160 0 .6 2.2"
    for filename, name in (("GzSceneManager", "Scene Manager"), ("InteractiveViewControl", "Interactive view control"),
                           ("WorldControl", "World control"), ("WorldStats", "World stats")):
        ET.SubElement(gui, "plugin", filename=filename, name=name)
    ET.indent(sdf)
    ET.ElementTree(sdf).write(out / "funnel_demo.sdf", encoding="utf-8", xml_declaration=True)
    print(f"Prepared: {out / 'funnel_demo.sdf'}")
    print(f"Route: {len(candidate['points'])} face crossings -> {len(waypoints)} corner waypoints")
    print(f"Scale: {scale:.9f}; altitude: {route['altitude']:.6f}; route length: {length:.6f}")
    print("Original and simplified routes verified on mesh; axis transform round trip PASS.")
    print("Mode: pose preview, without force or rotor flight simulation.")


if __name__ == "__main__":
    main()
