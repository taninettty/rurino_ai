"""Fill the hidden V-shaped neckline so head translation cannot expose a gap.

Keep layer identity, bounds, lower neck, and collar unchanged. The top is already
inside the existing ArtMesh; no mesh stretching or extra drawable is needed.
"""
from pathlib import Path
import numpy as np
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer

root = Path(__file__).resolve().parents[1] / 'rebuild_v3_3'
psd = PSDImage.open(root / 'Rurino_Coordinated_Face_t051.psd')
for old in list(psd.descendants()):
    if old.is_group() or old.name != 'D_NECK_00':
        continue
    data = np.array(old.topil().convert('RGBA'))
    # Global x=710..843 lies between the two existing top corners.
    for x in range(710 - old.left, 844 - old.left):
        ys = np.flatnonzero(data[:, x, 3] > 240)
        if not len(ys):
            continue
        first = int(ys[0])
        sample_y = min(first + 8, data.shape[0] - 1)
        # Extend local skin color, removing the old cut-edge outline as well.
        data[:sample_y, x] = data[sample_y, x]
    im = Image.fromarray(data)
    new = PixelLayer.frompil(im, psd_file=psd, layer_name=old.name,
                             top=old.top, left=old.left)
    new._record.tagged_blocks = old._record.tagged_blocks
    parent = old.parent
    index = parent.index(old)
    parent.remove(old)
    parent.insert(index, new)
    im.save(root / 'Neck_extended.png')
psd.save(root / 'Rurino_Coordinated_Face_t052.psd')
print('Saved t052: hidden neckline filled; original mesh and collar retained')
