"""Layer-based 2D stand-in for a rigged Live2D model.

The handoff package ships the confirmed artwork as separate layers, so a pet
that blinks, breathes and speaks is possible without Cubism: composite the
layers once at load, then blend a few pre-rendered variants per frame. It is
not Live2D -- there is no mesh deformation or head perspective -- and the UI
must say so.

Draw order follows ``refined/layers.json``; every layer shares the 1536x2048
canvas, so they are composited at the origin.
"""
from pathlib import Path

from PIL import Image


class Sprites:
    """Pre-composited character states plus the numbers a frame needs."""

    def __init__(self, layer_dir, order, canvas=(1536, 2048), scale=.34):
        self.layer_dir = Path(layer_dir)
        self.size = (round(canvas[0] * scale), round(canvas[1] * scale))
        self.order = [name for name in order if name != 'Approved_Reference']
        self.cache = {}
        self._load_layers(scale)

    def _path(self, name):
        return self.layer_dir / f'{name}.png'

    def _load(self, name, scale):
        image = Image.open(self._path(name)).convert('RGBA')
        if scale != 1:
            image = image.resize(self.size, Image.LANCZOS)
        return image

    def _load_layers(self, scale):
        present = {path.stem for path in self.layer_dir.glob('*.png')}
        self.available = [name for name in self.order if name in present]
        self.layers = {name: self._load(name, scale) for name in self.available}

    def _composite(self, names):
        base = Image.new('RGBA', self.size, (0, 0, 0, 0))
        for name in self.available:
            if name in names:
                base.alpha_composite(self.layers[name])
        return base

    def build(self):
        """Pre-render the four head variants and the two body states."""
        head_names = {'Face_Skin', 'Brow_L', 'Brow_R', 'Eye_L_White_Lash', 'Eye_R_White_Lash',
                      'Eye_L_Iris', 'Eye_R_Iris', 'Mouth_Closed', 'Mouth_Open',
                      'Eye_L_Closed', 'Eye_R_Closed', 'Hair_Front_L', 'Hair_Front_R',
                      'Hair_Lock_R', 'Flower_L', 'Flower_R'}
        body_names = {'Hair_Back_L', 'Hair_Back_R', 'Legs', 'Arm_L', 'Arm_R', 'Skirt',
                      'Body_Chest', 'Hand_L', 'Hand_R', 'Neck', 'Wrist_Overlap_L', 'Wrist_Overlap_R'}
        eyes_closed = {'Eye_L_Closed', 'Eye_R_Closed'}
        mouth_open = {'Mouth_Open'}

        self.body = self._composite(body_names)
        self.head = {}
        for open_eyes in (True, False):
            for open_mouth in (True, False):
                names = set(head_names)
                if not open_eyes:
                    names -= {'Eye_L_White_Lash', 'Eye_R_White_Lash', 'Eye_L_Iris', 'Eye_R_Iris'}
                    names |= eyes_closed
                else:
                    names -= eyes_closed
                if not open_mouth:
                    names -= mouth_open
                self.head[(open_eyes, open_mouth)] = self._composite(names)
        return self

    def frame(self, eye_open=1.0, mouth=0.0, head_x=0.0, head_y=0.0, breath=0.0, iris=(0.0, 0.0)):
        """Compose one frame.

        ``eye_open`` 1 = open, 0 = closed; ``mouth`` 0 = closed, 1 = open;
        ``head_x``/``head_y`` are pixels for the head group; ``breath`` moves
        the body by a couple of pixels; ``iris`` shifts the irises only.
        """
        eye_open = max(0.0, min(1.0, eye_open))
        mouth = max(0.0, min(1.0, mouth))
        canvas = Image.new('RGBA', self.size, (0, 0, 0, 0))

        canvas.alpha_composite(self.body, (0, round(breath * 2)))

        opened = self.head[(True, mouth > .5)]
        closed = self.head[(False, mouth > .5)]
        blend = closed if eye_open < .5 else opened
        if eye_open not in (0.0, 1.0):
            blend = Image.blend(closed, opened, eye_open)
        canvas.alpha_composite(blend, (round(head_x), round(head_y)))
        return canvas
