"""Re-export existing facial materials with stable colours; no PSD edits.

The APNG is lossless. GIF uses one shared palette and no error diffusion,
so changes in the iris cannot recolour otherwise stationary pixels.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'rebuild_v3_4/face_features'
CROP = (380, 180, 1660, 1400)
BASE = ['BackHair_Concealed_Support', 'Skin_Concealed_Support',
        'Ponytail_L', 'Ponytail_R', 'Body_Reference', 'Neck_Reference',
        'Face_Reference', 'Ear_L', 'Ear_R']


def export_frames(frames, directory):
    directory = Path(directory)
    # Give the small eye regions adequate palette coverage alongside the head.
    samples = Image.new('RGB', (640, 320 * len(frames)))
    for k, frame in enumerate(frames):
        samples.paste(frame.resize((320, 320)), (0, 320*k))
        samples.paste(frame.crop((130, 270, 520, 400)).resize((320, 320)), (320, 320*k))
    palette = samples.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    indexed = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    indexed[0].save(directory/'gaze-material-check.gif', save_all=True,
                    append_images=indexed[1:], duration=90, loop=0,
                    disposal=2, optimize=False)
    frames[0].save(directory/'gaze-material-check.png', save_all=True,
                   append_images=frames[1:], duration=90, loop=0,
                   disposal=0, blend=0)


def decode(path):
    with Image.open(path) as im:
        frames = []
        for k in range(im.n_frames):
            im.seek(k)
            frames.append(np.array(im.convert('RGB')))
    return np.stack(frames)


def encoding_metrics(actual, reference):
    assert actual.shape == reference.shape
    stationary = np.all(reference == reference[0], axis=(0, 3))
    changed = np.any(actual != actual[0], axis=(0, 3))
    error = np.abs(actual.astype('int16') - reference.astype('int16'))
    eyes = error[:, 300:390, 145:510]
    return {'stationary_pixels': int(stationary.sum()),
            'stationary_pixels_recoloured': int((stationary & changed).sum()),
            'max_rgb_error': int(error.max()),
            'eye_crop_mean_absolute_rgb_error': float(eyes.mean()),
            'eye_crop_p95_absolute_rgb_error': float(np.percentile(eyes, 95))}


def main(baseline=None):
    qa = OUT/'qa'
    # An explicit baseline prevents a subsequent run labelling the fixed GIF
    # as the faulty original. Read before overwriting the current preview.
    old = decode(baseline) if baseline is not None else None
    manifest = json.loads((OUT/'manifest.json').read_text())
    parts = {l['name']: Image.open(OUT/l['file']).convert('RGBA').crop(CROP)
             for l in manifest['layers']}
    size = parts[BASE[0]].size
    base = Image.new('RGBA', size)
    for n in BASE:
        base.alpha_composite(parts[n])
    front = Image.new('RGBA', size)
    front_names = [n for n in parts if n not in BASE and not n.startswith(('Eye_', 'Mouth_', 'Brow_'))]
    front_names += ['Brow_L', 'Brow_R']
    for n in front_names:
        front.alpha_composite(parts[n])
    gazes = [(round(12*np.sin(k*2*np.pi/36)), round(5*np.sin(k*4*np.pi/36)))
             for k in range(36)]
    # Follow the SAME fully opaque iris texels, excluding any lid/hair clipping.
    tracks = {}
    for side in ['L', 'R']:
        iris = np.array(parts[f'Eye_{side}_Iris'])
        white = np.array(parts[f'Eye_{side}_White'])
        occlusion = front.copy()
        for suffix in ['UpperLid', 'LowerLid']:
            occlusion.alpha_composite(parts[f'Eye_{side}_{suffix}'])
        visible = (white[:, :, 3] == 255) & (np.array(occlusion)[:, :, 3] == 0)
        ys, xs = np.nonzero(iris[:, :, 3] == 255)
        safe = np.ones(len(xs), bool)
        for dx, dy in gazes:
            safe &= visible[ys+dy, xs+dx]
        ys, xs = ys[safe], xs[safe]
        assert len(xs) > 100
        tracks[side] = (ys, xs, iris[ys, xs, :3])
    tracking_error = {'L': 0, 'R': 0}
    frames = []
    for dx, dy in gazes:
        result = base.copy()
        for side in ['L', 'R']:
            moving = Image.new('RGBA', size)
            moving.alpha_composite(parts[f'Eye_{side}_Iris'], (dx, dy))
            arr = np.array(moving)
            eye = np.array(parts[f'Eye_{side}_White'])
            alpha = arr[:, :, 3:4].astype('float32')/255
            eye[:, :, :3] = np.rint(arr[:, :, :3]*alpha + eye[:, :, :3]*(1-alpha)).astype('uint8')
            result.alpha_composite(Image.fromarray(eye))
            for suffix in ['UpperLid', 'LowerLid']:
                result.alpha_composite(parts[f'Eye_{side}_{suffix}'])
        result.alpha_composite(parts['Mouth_Neutral'])
        for n in front_names:
            result.alpha_composite(parts[n])
        a = np.array(result)
        for side, (ys, xs, expected) in tracks.items():
            error = np.abs(a[ys+dy, xs+dx, :3].astype('int16') - expected.astype('int16'))
            tracking_error[side] = max(tracking_error[side], int(error.max()))
        if (dx, dy) == (0, 0):
            expected = np.array(Image.open(qa/'neutral.png').crop(CROP))
            assert np.array_equal(a, expected), 'Export renderer changed neutral material'
        result.thumbnail((640, 640))
        tile = Image.new('RGB', (640, 640), (225, 229, 237))
        tile.paste(result, ((640-result.width)//2, (640-result.height)//2), result)
        ImageDraw.Draw(tile).text((12, 10), 'IRIS CLIPPING CHECK / MATERIALS ONLY', fill=(40,45,60))
        frames.append(tile)
    assert tracking_error == {'L': 0, 'R': 0}
    reference = np.stack([np.array(f) for f in frames])
    before = encoding_metrics(old, reference) if old is not None else None
    export_frames(frames, qa)
    gif = encoding_metrics(decode(qa/'gaze-material-check.gif'), reference)
    apng = encoding_metrics(decode(qa/'gaze-material-check.png'), reference)
    assert gif['stationary_pixels_recoloured'] == 0
    assert apng['max_rgb_error'] == 0
    assert apng['stationary_pixels_recoloured'] == 0
    report = {'scope': 'preview encoding, unchanged PSD and material textures',
              'frames': len(frames), 'old_gif': before, 'shared_palette_gif': gif,
              'lossless_apng': apng,
              'tracked_iris_texels': {s: len(v[0]) for s,v in tracks.items()},
              'tracked_iris_rgb_error_max': tracking_error,
              'limitation': 'GIF remains limited to 256 colours; use APNG for colour review'}
    (qa/'gaze-colour-checks.json').write_text(json.dumps(report, indent=2)+'\n')
    if old is None:
        print(json.dumps(report, indent=2))
        return
    sheet = Image.new('RGB', (1260, 560), 'white')
    draw = ImageDraw.Draw(sheet)
    for row, k in enumerate([9, 27]):
        for col, (label, a) in enumerate([('OLD GIF', old[k]), ('LOSSLESS', reference[k])]):
            tile = Image.fromarray(a).crop((165, 295, 480, 405)).resize((630,220))
            sheet.paste(tile, (col*630, row*280+30))
            draw.text((col*630+10, row*280+10), f'{label} / Frame {k}', fill='black')
    sheet.save(qa/'gaze-colour-comparison.png')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, help='Optional original GIF to diagnose')
    main(parser.parse_args().baseline)
