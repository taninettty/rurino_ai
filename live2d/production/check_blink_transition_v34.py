"""Inspect 101 material states per eye for clipping and major contour breaks."""
import json

import cv2
import numpy as np
from PIL import Image

import build_blink_materials_v34 as blink


def main():
    parts = {
        f'Eye_{side}_{name}': Image.open(
            blink.SRC/'layers'/f'Eye_{side}_{name}.png').convert('RGBA')
        for side in 'LR' for name in ['White', 'Iris', 'UpperLid', 'LowerLid']
    }
    closed = Image.open(blink.OUT/'sources/closed-eyes-source.png').convert('RGBA')
    blank = Image.open(blink.SRC/'sources/featureless-skin.png').convert('RGBA')
    report = {}
    for side in 'LR':
        eye = blink.prepare_eye(side, parts, closed, blank)
        areas = []; components = []
        for p in np.linspace(0, 1, 101):
            pose = blink.keyform(eye, float(p))
            aperture = pose['White'][:, :, 3]
            assert np.array_equal(pose['Iris'], eye['parts']['Iris'])
            assert np.all(aperture <= eye['parts']['White'][:, :, 3])
            areas.append(int(aperture.sum()))
            _, _, stats, _ = cv2.connectedComponentsWithStats(
                (pose['UpperLid'][:, :, 3] > 127).astype('uint8'))
            # The lash and its separate crease are the two main components.
            components.append(int(np.count_nonzero(stats[1:, 4] > 8)))
        assert areas[0] == 0 and all(a <= b for a, b in zip(areas, areas[1:]))
        assert set(components) == {2}, (side, components)
        report[side] = {
            'samples': 101, 'opening_area_monotonic': True,
            'iris_texture_exact': True, 'aperture_inside_original': True,
            'major_upper_lid_component_counts': sorted(set(components)),
            'max_upper_lid_components': max(components),
            'component_min_area_px_exclusive': 8,
            'scope': 'raster material topology; not Cubism mesh verification',
        }
    (blink.OUT/'qa/dense-transition-checks.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
