"""Paint concealed roots onto the existing L02/R02 raster locks.

This is local material editing, not a new LibTV generation or a motion rig.
The old visible tips remain in place. Root geometry is drawn separately for
each side; all colour samples come from that lock's own source pixels.
"""
from pathlib import Path
import json
import cv2
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import distance_transform_edt, gaussian_filter1d
from PIL import Image, ImageDraw, ImageFont
from psd_tools import PSDImage
from split_left_head_parts_v34 import ROOT, TURN, pixels, clone, add, sha
from build_hair_flow_redraw_v34 import full

OUT = TURN / 'hair_drop_refinement'
SOURCE = TURN / 'hair_flow_continued/Rurino_Left_Head_Hair_Joins_STATIC_v034.psd'
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
CONFIG = {
    'L02': {'source': 'L02_OuterDrop_EdgeCleanup_VISIBLE_ONLY',
            'y': [250, 320, 400, 480, 550, 610],
            'left': [535, 490, 450, 427, 395, 371],
            'right': [535, 510, 484, 456, 428, 415]},
    'R02': {'source': 'R02_OuterDrop',
            'y': [230, 320, 420, 500, 550, 610],
            'left': [1518, 1548, 1590, 1618, 1637, 1658],
            'right': [1518, 1585, 1650, 1694, 1711, 1729]},
}


def paint_root(source, cfg):
    yy, xx = np.indices(source.shape[:2], dtype='float32')
    left = PchipInterpolator(cfg['y'], cfg['left'], extrapolate=False)(yy[:, 0])
    right = PchipInterpolator(cfg['y'], cfg['right'], extrapolate=False)(yy[:, 0])
    active = np.isfinite(left) & np.isfinite(right)
    left = np.nan_to_num(left)[:, None]
    right = np.nan_to_num(right)[:, None]
    width = np.maximum(right - left, 1)
    u = np.clip((xx - left) / width, 0, 1)
    alpha = np.minimum(np.clip(xx - left + .5, 0, 1), np.clip(right - xx + .5, 0, 1)) * active[:, None]
    # Read the gold section as a transverse palette, not the whole character.
    profiles = []
    for y in range(510, 536):
        xs = np.where(source[y, :, 3] > 200)[0]
        if len(xs) < 12:
            continue
        positions = np.linspace(xs.min()+3, xs.max()-3, 128)
        profiles.append(np.stack([np.interp(positions, np.arange(2048), source[y, :, c]) for c in range(3)], axis=1))
    profile = gaussian_filter1d(np.median(profiles, axis=0), 3, axis=0)
    colour = np.stack([np.interp(u, np.linspace(0, 1, 128), profile[:, c]) for c in range(3)], axis=2)
    # Keep roots softly golden; shade follows the drawn cross-section.
    highlight = 5 * np.exp(-((u - .45) / .20) ** 2)
    colour = np.clip(colour + highlight[:, :, None], 0, 255)
    # Near the old cut, bridge only from the lock's opaque interior. Excluding
    # the contour prevents transferring a dark line into the new root paint.
    interior = cv2.distanceTransform((source[:, :, 3] > 200).astype('uint8'), cv2.DIST_L2, 5) > 4
    dist, nearest = distance_transform_edt(~interior, return_indices=True)
    nearby = source[nearest[0], nearest[1], :3].astype('float32')
    t = np.clip(dist / 24, 0, 1)
    blend = (1 - t*t*(3-2*t))[:, :, None]
    colour = colour*(1-blend) + nearby*blend
    # Fine root outline, tapering away inside the old opaque source.
    edge = np.minimum(xx-left, right-xx)
    line = np.clip(1.8-edge, 0, 1) * active[:, None]
    outline = np.array([125, 108, 119], dtype='float32')
    line *= np.clip((535-yy)/50, 0, 1)
    colour = colour*(1-line[:, :, None]) + outline*line[:, :, None]
    plate = np.dstack([np.rint(np.clip(colour, 0, 255)).astype('uint8'), np.rint(alpha*255).astype('uint8')])
    plate[plate[:, :, 3] == 0] = 0
    complete = np.array(Image.alpha_composite(Image.fromarray(plate), Image.fromarray(source)))
    complete[plate[:, :, 3] == 0] = source[plate[:, :, 3] == 0]
    return complete, plate


def main():
    for folder in ['layers', 'qa']:
        (OUT/folder).mkdir(parents=True, exist_ok=True)
    source = PSDImage.open(SOURCE)
    lookup = {l.name:l for l in pixels(source)}
    locks, roots, records = {}, {}, []
    for name, cfg in CONFIG.items():
        old = full(lookup[cfg['source']])
        complete, root = paint_root(old, cfg)
        Image.fromarray(complete).save(OUT/'layers'/f'{name}_RootExtended.png')
        Image.fromarray(root).save(OUT/'layers'/f'{name}_PaintedHiddenRoot.png')
        # Paint extension only; the old lower shaft and tip are not resampled.
        assert np.array_equal(complete[611:], old[611:])
        opaque = old[:, :, 3] == 255
        assert np.array_equal(complete[opaque], old[opaque])
        locks[name] = complete
        roots[name] = root
        records.append({'name':name, 'source_layer':cfg['source'], 'root_control_points':cfg,
                        'old_opaque_pixels_exact':True, 'rows_611_down_rgba_exact':True,
                        'added_alpha_pixels':int(((complete[:,:,3]>0)&(old[:,:,3]==0)).sum())})
    # Inspect alpha in full, independently of a head composite crop.
    sheet = Image.new('RGB',(1440,1080),'#edf1f6')
    d = ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,22)
    for row,name in enumerate(['L02','R02']):
        old=full(lookup[CONFIG[name]['source']]);new=locks[name]
        box=Image.fromarray(new).getbbox()
        for col,(label,arr) in enumerate([('原可见段 · 顶部未补齐',old),('沿发流补画隐藏根部',new)]):
            x=col*720;y=row*520
            d.text((x+20,y+12),name+' · '+label,font=font,fill='#29394e')
            for cy in range(y+60,y+500,20):
                for cx in range(x+20,x+700,20):
                    c='#d3dbe5' if ((cx-x-20)//20+(cy-y-60)//20)%2 else '#e7ecf2'
                    d.rectangle((cx,cy,cx+19,cy+19),fill=c)
            tile=Image.fromarray(arr).crop(box)
            tile.thumbnail((640,410))
            sheet.paste(tile,(x+(720-tile.width)//2,y+70),tile)
    d.text((20,1045),'同一缕前后使用相同视口与比例；仅补根素材，运动遮挡尚未验证。',font=ImageFont.truetype(FONT,18),fill='#53637c')
    sheet.save(OUT/'qa/drop-root-alpha-comparison.jpg',quality=96)
    (OUT/'root-paint-records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')

    baseline = np.array(source.composite(force=True))
    psd = PSDImage.new('RGBA', (2048,2048), color=0)
    clone(source, psd, psd, [])
    dest = {l.name:l for l in pixels(psd)}
    hidden=[]
    for name,cfg in CONFIG.items():
        old=dest[cfg['source']];parent=old.parent;index=list(parent).index(old)
        new=add(psd,parent,Image.fromarray(locks[name]),name+'_RootExtended_LOCAL_PAINT')
        parent.remove(new);parent.insert(index,new)
        old.visible=False;hidden.append(old.name)
    path=OUT/'Rurino_Left_Head_Drop_Roots_v034.psd'
    psd.save(path)
    saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
    assert len(after)==51 and sum(l.clipping_layer for l in after.values())==4
    for name,old in lookup.items():
        new=after[name]
        assert new.offset==old.offset and np.array_equal(np.array(new.topil()),np.array(old.topil())),name
        assert (new.opacity,new.blend_mode,new.clipping_layer)==(old.opacity,old.blend_mode,old.clipping_layer),name
        assert new.visible==(False if name in hidden else old.visible),name
    neutral=np.array(saved.composite(force=True))
    support=np.logical_or.reduce([r[:,:,3]>0 for r in roots.values()])
    changed=np.any(neutral!=baseline,axis=2)
    assert not changed[~support].any()
    exterior=(baseline[:,:,3]==0)&(neutral[:,:,3]>0)
    assert not exterior.any(), 'painted root protrudes outside the head silhouette'
    Image.fromarray(neutral).save(OUT/'qa/saved-psd-open.png')
    states=[]
    for state in ['Open','Half','Closed']:
        for doc in [source,saved]:
            for g in doc:
                if g.name.startswith('02_'):g.visible=g.name=='02_'+state
        old=np.array(source.composite(force=True));new=np.array(saved.composite(force=True))
        face=np.zeros((2048,2048),bool);face[400:1230,620:1250]=True;face&=old[:,:,3]==255
        delta=np.abs(new.astype('int16')-old.astype('int16'))
        assert not delta[face].any()
        states.append({'state':state,'central_opaque_face_max_difference':int(delta[face].max()),'roi_xyxy':[620,400,1250,1230]})
    sheet=Image.new('RGB',(1400,800),'#e6edf4');d=ImageDraw.Draw(sheet)
    for col,(title,a) in enumerate([('补根前',baseline),('两缕补根放回头部',neutral)]):
        im=Image.fromarray(a).crop((120,0,1960,1800));im.thumbnail((690,740))
        sheet.paste(im,(col*700+(700-im.width)//2,50),im)
        d.text((col*700+16,12),title,font=font,fill='#29394e')
    sheet.save(OUT/'qa/drop-root-head-comparison.jpg',quality=95)
    report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':51,
            'source_49_layer_pixels_offsets_opacity_blend_clipping_retained':True,
            'newly_hidden_source_layers':hidden,'locks':records,
            'neutral_composite_changed_pixels':int(changed.sum()),
            'changed_pixels_outside_root_support':0,'new_pixels_outside_previous_head_silhouette':0,
            'saved_psd_state_checks':states,'method':'local concealed-root raster painting on existing visible locks; not a new LibTV image',
            'limitations':['R02 inner edge and neighbouring strand ownership still require refinement',
                           'root anchor positions and overlap not validated under movement',
                           'no new Cubism rig or body motion'],
            'libtv':{'node_id':'i-UcpjWnGYq3','status':'generation_rejected','code':'COMMERCIAL_BLOCKED','task_id':None}}
    (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
