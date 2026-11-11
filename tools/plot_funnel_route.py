#!/usr/bin/env python3
"""Plot the candidate route in the original X/Z navigation coordinates."""
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mesh import read_geom


def main():
    mesh = read_geom(ROOT / "generated/funnel_input_y2p00.geom")
    route = json.loads((ROOT / "generated/funnel_route_candidate_y2p00.json").read_text())
    vertices = np.array([(p.x, p.z) for p in mesh.points])
    triangles = vertices[np.array(mesh.faces)]
    path = np.array(route["points"])
    fig, ax = plt.subplots(figsize=(11, 10))
    ax.set_facecolor("#e3e5e8")
    ax.add_collection(PolyCollection(triangles, facecolors="#d6eddd", edgecolors="none"))
    ax.plot(path[:, 0], path[:, 2], color="#db660b", linewidth=2.3,
            label=f"Funnel candidate: {route['length']:.3f} model units", zorder=3)
    chain = vertices[route["source_chain"]]
    ax.scatter(chain[1:-1, 0], chain[1:-1, 1], s=30, color="#db660b", zorder=4,
               label="Intermediate secondary sources")
    for label, row, color in (("START", path[0], "#147a3a"), ("GOAL", path[-1], "#b22238")):
        ax.scatter(row[0], row[2], s=65, color=color, zorder=5)
        ax.annotate(label, (row[0], row[2]), xytext=(7, 7), textcoords="offset points", weight="bold")
    ax.autoscale()
    ax.set_aspect("equal")
    ax.set_xlabel("X (original model units)")
    ax.set_ylabel("Z (original model units)")
    ax.set_title("Candidate route on navigation surface (Y = 2)\nGreen: navigation mesh; gray: excluded/outside mesh")
    ax.legend(loc="lower left", fontsize=9)
    fig.text(.5, .015, "Candidate route; global shortest-path optimality is not certified.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .03, 1, 1))
    output = ROOT / "generated/funnel_route_candidate_y2p00.png"
    fig.savefig(output, dpi=160)
    plt.close(fig)
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
