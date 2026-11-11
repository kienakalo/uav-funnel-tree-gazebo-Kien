"""Colour the existing city geometry by height and face orientation."""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'generated/city_visual'
STL_RECORD = np.dtype([('normal', '<f4', (3,)), ('triangle', '<f4', (3, 3)), ('attr', '<u2')])
PALETTE = {
    'lower_surfaces': (.18, .34, .42, 1.),
    'street_level': (.32, .36, .39, 1.),
    'low_facades': (.86, .79, .65, 1.),
    'tall_facades': (.40, .61, .71, 1.),
    'low_roofs': (.66, .30, .20, 1.),
    'high_roofs': (.44, .52, .56, 1.),
    'sloped_surfaces': (.56, .60, .48, 1.),
}


def prepare_visuals():
    source = ROOT / 'generated/funnel_preview/city.stl'
    source_bytes = source.read_bytes()
    signature = hashlib.sha256(source_bytes + Path(__file__).read_bytes()).hexdigest()
    manifest_path = OUT / 'manifest.json'
    if manifest_path.exists():
        saved = json.loads(manifest_path.read_text())
        if saved.get('signature') == signature and all((OUT / group['file']).exists() for group in saved['groups']):
            return saved

    records = np.frombuffer(source_bytes, dtype=STL_RECORD, offset=84)
    triangles = records['triangle']
    top = triangles[:, :, 2].max(axis=1)
    middle = triangles[:, :, 2].mean(axis=1)
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    vertical = abs(normals[:, 2]) / np.maximum(np.linalg.norm(normals, axis=1), 1e-30)
    horizontal = vertical > .85
    walls = vertical < .35
    labels = np.full(len(records), 'sloped_surfaces', dtype='<U20')
    labels[walls & (top < 10.)] = 'low_facades'
    labels[walls & (top >= 10.)] = 'tall_facades'
    labels[horizontal & (middle < .6)] = 'lower_surfaces'
    labels[horizontal & (middle >= .6) & (middle <= 3.1)] = 'street_level'
    labels[horizontal & (middle > 3.1) & (top < 10.)] = 'low_roofs'
    labels[horizontal & (top >= 10.)] = 'high_roofs'
    OUT.mkdir(exist_ok=True, parents=True)
    groups = []
    for label, colour in PALETTE.items():
        selected = records[labels == label]
        if not len(selected):
            continue
        name = label + '.stl'
        with (OUT / name).open('wb') as stream:
            stream.write(f'City visual group: {label}; see ATTRIBUTION.md'.encode().ljust(80, b' '))
            stream.write(np.array([len(selected)], dtype='<u4').tobytes())
            stream.write(selected.tobytes())
        groups.append(dict(name=label, file=name, rgba=colour, triangles=len(selected)))
    if sum(group['triangles'] for group in groups) != len(records):
        raise ValueError('Coloured city export lost triangles')
    manifest = dict(signature=signature, source_sha256=hashlib.sha256(source_bytes).hexdigest(),
                    triangles=len(records), groups=groups,
                    classification='face orientation and height; illustrative colours, not surveyed semantic labels')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    report = prepare_visuals()
    print(json.dumps(report, indent=2))
    print(f'Save at: {OUT / "manifest.json"}')
