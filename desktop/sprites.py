"""Layer-based 2D stand-in for a rigged Live2D model.

The handoff package ships both a flattened, seam-free picture of the confirmed
artwork (``neutral.png``) and the closed-eye / open-mouth pieces. Stacking the
29 separate parts produced a visible alpha seam at the waist and opened gaps
whenever a part moved, so the flattened image is the base and only the two
genuinely animated pieces are overlaid.

What this costs: the irises are baked into the base, so eye tracking is out of
scope here. Blink, mouth, breathing and a slight body tilt all remain.
"""
from pathlib import Path

from PIL import Image

BASE = 'base'
EYES = ('Eye_L_Closed', 'Eye_R_Closed')
MOUTH = 'Mouth_Open'


class Sprites:
    """A seam-free base picture plus the pieces that change per frame."""

    def __init__(self, layer_dir, canvas=(1536, 2048), scale=.34):
        self.layer_dir = Path(layer_dir)
        self.size = (round(canvas[0] * scale), round(canvas[1] * scale))
        self.base = self._load(BASE)
        self.eyes = [image for image in (self._load(name) for name in EYES) if image]
        self.mouth = self._load(MOUTH)

    def _load(self, name):
        path = self.layer_dir / f'{name}.png'
        if not path.is_file():
            return None
        return Image.open(path).convert('RGBA').resize(self.size, Image.LANCZOS)

    def build(self):
        if self.base is None:
            raise FileNotFoundError(f'missing base picture in {self.layer_dir}')
        return self

    def frame(self, eye_open=1.0, mouth=0.0, sway=0.0, breath=0.5):
        """Compose one frame.

        ``eye_open`` 1 = open, 0 = closed; ``mouth`` 0 = closed, 1 = open;
        ``sway`` tilts the finished picture in degrees; ``breath`` 0..1 scales
        it by about half a percent. Nothing inside the picture is ever moved on
        its own, which is what kept opening seams between drawn parts.
        """
        eye_open = max(0.0, min(1.0, float(eye_open)))
        mouth = max(0.0, min(1.0, float(mouth)))
        breath = max(0.0, min(1.0, float(breath)))

        canvas = self.base.copy()
        if eye_open < .999:
            fade = 1 - eye_open
            for layer in self.eyes:
                canvas.alpha_composite(self._faded(layer, fade))
        if mouth > .01 and self.mouth is not None:
            canvas.alpha_composite(self._faded(self.mouth, mouth))
        return self._pose(canvas, sway, breath)

    @staticmethod
    def _faded(layer, alpha):
        faded = layer.copy()
        faded.putalpha(faded.getchannel('A').point(lambda value: round(value * alpha)))
        return faded

    def _pose(self, canvas, sway, breath):
        """Tilt and scale the whole picture; a global transform cannot open seams."""
        if abs(sway) < .01 and abs(breath - .5) < .01:
            return canvas
        width, height = self.size
        pivot = (width / 2, height * .95)
        if abs(sway) >= .01:
            canvas = canvas.rotate(sway, resample=Image.BICUBIC, center=pivot)
        factor = 1 + (breath - .5) * .012        # +/-0.6 %
        if abs(factor - 1) >= .0005:
            scaled = canvas.resize((round(width * factor), round(height * factor)), Image.BILINEAR)
            canvas = Image.new('RGBA', self.size, (0, 0, 0, 0))
            canvas.alpha_composite(scaled, (round((width - scaled.width) / 2),
                                            round(pivot[1] - pivot[1] * factor)))
        return canvas
