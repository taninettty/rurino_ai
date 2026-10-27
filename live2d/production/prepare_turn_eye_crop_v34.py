"""Reproduce the unscaled crop sent to LibTV for the left far-eye edit."""
import hashlib,json
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
TURN=ROOT/'rebuild_v3_4/turn_redraw'
OUT=TURN/'eye_calibration/sources'

def main():
    src=TURN/'sources/turn-left-v2-source.png'
    box=[434,574,946,1086]
    im=Image.open(src).convert('RGBA').crop(box)
    path=OUT/'left-eye-crop-input.png';im.save(path)
    record={'source':str(src.relative_to(TURN)),
            'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
            'crop_xyxy':box,'input_dimensions':list(im.size),
            'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'purpose':'focused local eye redraw; native crop, no geometric transformation'}
    (OUT/'left-eye-crop-input.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))

if __name__=='__main__':main()
