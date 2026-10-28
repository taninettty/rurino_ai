"""Refine the two LibTV locks' static joins without changing the head drawing.

New hair geometry receives a small horizontal bend at the upper silhouette.
Original upper hair paint blends into the generated lower shading. Obsolete
outline fragments are removed from working copies; all 44 source layers remain
in the saved PSD, with five superseded layers hidden for recovery.
"""
import json
import cv2
import numpy as np
from scipy.ndimage import gaussian_filter, distance_transform_edt
from PIL import Image, ImageDraw, ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group
from build_hair_flow_redraw_v34 import SOURCE, OUT as PREVIOUS, full
from split_left_head_parts_v34 import ROOT, TURN, pixels, clone, add, sha

OUT = TURN / 'hair_flow_continued'
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def main():
    for folder in ['layers', 'masks', 'qa']:
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    source = PSDImage.open(SOURCE)
    lookup = {l.name: l for l in pixels(source)}
    baseline = np.array(source.composite(force=True))
    yy, xx = np.indices((2048, 2048), dtype='float32')

    def smooth(start, end):
        t = np.clip((yy - start) / (end - start), 0, 1)
        return t * t * (3 - 2 * t)

    # Nearest foreground colour is used only to extend the original upper
    # hair paint over the new lock's antialias; lower hair retains generated RGB.
    _, nearest = distance_transform_edt(baseline[:, :, 3] < 200, return_indices=True)
    reference = baseline[nearest[0], nearest[1], :3].astype('float32')
    replacements, locks, records, hidden = {}, {}, [], set()
    for name, side, start, radius in [('L01', 'Left', 495, 18), ('R01', 'Right', 490, 12)]:
        old_name = name + '_OuterFlick'
        pending_name = f'ShortRearHair_Image{side}_RootBoundary_PENDING'
        original, pending = full(lookup[old_name]), full(lookup[pending_name])
        input_path = PREVIOUS / 'layers' / f'{name}_Complete_Redraw_Placed.png'
        new = np.array(Image.open(input_path).convert('RGBA'))
        distance = cv2.distanceTransform((original[:, :, 3] == 0).astype('uint8'), cv2.DIST_L2, 5)
        cut = (pending[:, :, 3] > 0) & (distance < radius) & (yy > start) & (yy < 800)
        revised_pending = pending.copy()
        revised_pending[cut] = 0
        Image.fromarray((cut * 255).astype('uint8')).save(OUT / 'masks' / f'{name}_OldOutlineRemoval.png')

        # Fit only the top of each new hair lock to the established silhouette.
        # Each row translates; it is not widened, and the lower tip is untouched.
        edge_delta = np.zeros(2048, dtype='float32')
        for row in range(360, 700):
            ox = np.where(baseline[row, :, 3] > 128)[0]
            nx = np.where(new[row, :, 3] > 128)[0]
            if len(ox) and len(nx):
                edge_delta[row] = float(ox.min() - nx.min() if name == 'L01' else ox.max() - nx.max())
        edge_delta = gaussian_filter(edge_delta, 5)
        shift = edge_delta[:, None] * smooth(360, 435) * (1 - smooth(610, 700))
        premult = new.astype('float32') / 255
        premult[:, :, :3] *= premult[:, :, 3, None]
        warped = cv2.remap(premult, xx - shift, yy, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
        alpha = np.clip(warped[:, :, 3], 0, 1)
        new[:, :, :3] = np.rint(np.clip(warped[:, :, :3] / np.maximum(alpha[:, :, None], 1e-6), 0, 1) * 255).astype('uint8')
        new[:, :, 3] = np.rint(alpha * 255).astype('uint8')
        weight = (1 - smooth(500, 660))[:, :, None]
        new[:, :, :3] = np.clip(np.rint(new[:, :, :3] * (1 - weight) + reference * weight), 0, 255).astype('uint8')
        new[new[:, :, 3] == 0] = 0
        locks[name] = new
        replacements[pending_name] = (name + '_RootBoundary_Cleaned', revised_pending)
        hidden.update([old_name, pending_name])
        for label, arr in [(f'{name}_Complete_Joined', new), (f'{name}_RootBoundary_Cleaned', revised_pending)]:
            Image.fromarray(arr).save(OUT / 'layers' / (label + '.png'))
        records.append({'name': name, 'input_sha256': sha(input_path), 'removed_pending_outline_pixels': int(cut.sum()), 'max_upper_row_translation_pixels': float(np.abs(shift).max()), 'geometry_affected_rows': [360, 699], 'paint_transition_rows': [500, 659], 'method': 'upper lock horizontal bend and original upper hair paint blended into generated lower hair; head never transformed'})

    # A 2–3px spur of the obsolete outer flick was assigned to the adjacent L02.
    # Fit its uninterrupted outer edge above/below that spur and trim only alpha.
    original = full(lookup['L02_OuterDrop'])
    revised = original.copy()
    rows = np.array(list(range(710, 726)) + list(range(738, 755)))
    edges = np.array([np.where(original[y, :, 3] > 128)[0].min() for y in rows])
    fit = np.polyfit(rows - 730, edges, 2)
    for y in range(726, 738):
        edge = float(np.polyval(fit, y - 730))
        cap = np.clip(np.arange(2048) - edge + 1, 0, 1)
        revised[y, :, 3] = np.minimum(revised[y, :, 3], np.rint(cap * 255).astype('uint8'))
    changed_alpha = revised[:, :, 3] != original[:, :, 3]
    revised[changed_alpha & (revised[:, :, 3] == 0)] = 0
    spur_mask = np.any(revised != original, axis=2)
    assert not spur_mask[:726].any() and not spur_mask[738:].any()
    replacements['L02_OuterDrop'] = ('L02_OuterDrop_EdgeCleanup_VISIBLE_ONLY', revised)
    hidden.add('L02_OuterDrop')
    Image.fromarray(revised).save(OUT / 'layers/L02_OuterDrop_EdgeCleanup_VISIBLE_ONLY.png')
    Image.fromarray((spur_mask * 255).astype('uint8')).save(OUT / 'masks/L02_OldSpurRemoval.png')

    psd = PSDImage.new('RGBA', (2048, 2048), color=0)
    group = Group.new('00_Complete_Hair_Joined_STATIC_REVIEW', parent=psd)
    for name in ['R01', 'L01']:
        add(psd, group, Image.fromarray(locks[name]), name + '_Complete_Joined')
    clone(source, psd, psd, [])
    dest = {l.name: l for l in pixels(psd)}
    for name in hidden:
        dest[name].visible = False
    for old_name, (new_name, arr) in replacements.items():
        add(psd, dest[old_name].parent, Image.fromarray(arr), new_name)
    path = OUT / 'Rurino_Left_Head_Hair_Joins_STATIC_v034.psd'
    psd.save(path)
    saved = PSDImage.open(path)
    after = {l.name: l for l in pixels(saved)}
    assert len(after) == 49 and sum(l.clipping_layer for l in after.values()) == 4
    for name, layer in lookup.items():
        other = after[name]
        assert other.offset == layer.offset and np.array_equal(np.array(other.topil()), np.array(layer.topil())), name
        assert (other.opacity, other.blend_mode, other.clipping_layer) == (layer.opacity, layer.blend_mode, layer.clipping_layer), name
        assert other.visible == (False if name in hidden else layer.visible), name
    root_checks, states = [], []
    neutral = np.array(saved.composite(force=True))
    Image.fromarray(neutral).save(OUT / 'qa/saved-psd-open.png')
    interior = cv2.distanceTransform((baseline[:, :, 3] > 250).astype('uint8'), cv2.DIST_L2, 5)
    for name, box in [('L01', (350, 400, 520, 620)), ('R01', (1550, 380, 1760, 620))]:
        x0, y0, x1, y1 = box
        missing = (interior[y0:y1, x0:x1] > 3) & (neutral[y0:y1, x0:x1, 3] < 200)
        assert not missing.any(), name
        root_checks.append({'name': name, 'roi_xyxy': box, 'new_transparent_pixels_inside_original_root': int(missing.sum()), 'boundary_exclusion_pixels': 3, 'alpha_threshold': 200})
    for state in ['Open', 'Half', 'Closed']:
        for doc in [source, saved]:
            for g in doc:
                if g.name.startswith('02_'):
                    g.visible = g.name == '02_' + state
        old, new = np.array(source.composite(force=True)), np.array(saved.composite(force=True))
        face = np.zeros((2048, 2048), bool)
        face[400:1230, 620:1250] = True
        face &= old[:, :, 3] == 255
        difference = np.abs(old.astype('int16') - new.astype('int16'))
        assert not difference[face].any()
        states.append({'state': state, 'central_opaque_face_max_difference': int(difference[face].max()), 'roi_xyxy': [620, 400, 1250, 1230]})

    before = Image.open(PREVIOUS / 'qa/two-locks-head-trial.png').convert('RGBA')
    # Same crops and scale in each column; no magnification mismatch.
    sheet = Image.new('RGB', (1440, 1100), '#e6edf4')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(FONT, 23)
    boxes = [(185, 280, 545, 840), (1480, 260, 1930, 820)]
    for col, (title, im) in enumerate([('修整前', before), ('发根衔接、旧描边清理后', Image.fromarray(neutral))]):
        draw.text((col * 720 + 20, 12), title, font=font, fill='#29394e')
        for row, box in enumerate(boxes):
            tile = im.crop(box)
            tile.thumbnail((680, 480))
            sheet.paste(tile, (col * 720 + (720 - tile.width) // 2, row * 510 + 55), tile)
    draw.text((20, 1060), '静态接缝检查；身体动作与头发物理尚未绑定', font=ImageFont.truetype(FONT, 20), fill='#53637c')
    sheet.save(OUT / 'qa/hair-join-before-after.jpg', quality=96)
    sheet = Image.new('RGB', (1400, 800), '#e6edf4')
    draw = ImageDraw.Draw(sheet)
    for col, (title, im) in enumerate([('上一轮试装', before), ('本轮静态接缝修整', Image.fromarray(neutral))]):
        tile = im.crop((120, 0, 1960, 1800))
        tile.thumbnail((690, 740))
        sheet.paste(tile, (col * 700 + (700 - tile.width) // 2, 50), tile)
        draw.text((col * 700 + 16, 12), title, font=font, fill='#29394e')
    sheet.save(OUT / 'qa/head-join-comparison.jpg', quality=95)
    report = {'input_psd_sha256': sha(SOURCE), 'previous_trial_psd_sha256': sha(PREVIOUS / 'Rurino_Left_Head_Two_Redrawn_Locks_TRIAL_v034.psd'), 'saved_psd_sha256': sha(path), 'pixel_layers': 49, 'source_44_layers_rgba_offsets_and_render_flags_retained': True, 'source_layers_hidden': sorted(hidden), 'locks': records, 'L02_edge_cleanup_changed_pixels': int(spur_mask.sum()), 'root_roi_checks': root_checks, 'saved_psd_state_checks': states, 'new_generated_locks': 0, 'R02_generation': {'status': 'rejected', 'code': 'COMMERCIAL_BLOCKED', 'task_id': None, 'node_id': 'i-UcpjWnGYq3'}, 'scope': 'static joins of two existing redraws; L02 alpha cleanup only; no Cubism physics or body motion validation'}
    dump(OUT / 'verification.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
