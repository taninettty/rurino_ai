"""Reopen delivered PSDs and check gaze, clipping, color and hidden-layer states."""
import gc,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageSequence
from psd_tools import PSDImage

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'rebuild_v3_4/turn_redraw/eye_layers'
GAZES=[(-6,0),(0,0),(6,0),(0,-4),(0,4)]

def main():
    (OUT/'qa').mkdir(exist_ok=True)
    sources=json.loads((OUT/'source-crops.json').read_text());reports=[]
    overview=Image.new('RGB',(1536,810),(225,229,237))
    layersheet=Image.new('RGB',(1600,1000),(43,48,61))
    for row,(side,record) in enumerate(sources.items()):
        dest=OUT/side;box=record['crop_xyxy'];path=dest/f'Rurino_Turn_{side.title()}_Eye_Materials_v034.psd'
        psd=PSDImage.open(path);layers=list({id(l):l for l in psd.descendants() if l.kind=='pixel'}.values())
        assert len(layers)==10 and len({l.name for l in layers})==10
        irises=[l for l in layers if l.name.endswith('_Iris')]
        assert len(irises)==2 and all(l.clipping_layer for l in irises)
        offsets={l.name:l.offset for l in irises};checks=[]
        openings=[np.array(Image.open(dest/'masks'/f'{n}_Opening.png')) for n in ['Near','Far']]
        outside=np.maximum.reduce(openings)==0
        baseline=np.array(psd.composite(viewport=tuple(box),force=True))
        for i,(dx,dy) in enumerate(GAZES):
            for l in irises:
                x,y=offsets[l.name];l.offset=(x+dx,y+dy)
            actual=np.array(psd.composite(viewport=tuple(box),force=True))
            expected=np.array(Image.open(dest/'qa'/f'gaze-{i}.png').convert('RGBA'))
            error=np.abs(actual.astype('int16')-expected.astype('int16'))
            stable=bool(np.array_equal(actual[outside],baseline[outside]))
            # PSD clipping and the local preview differ at a few antialiased edge
            # texels. Bound those separately; opaque eye interiors must agree.
            opening=np.maximum.reduce(openings);edge_diff=error[:,:,:3].max(2)>2
            assert error[:,:,:3][opening==255].max()<=2
            assert error[:,:,:3].max()<=10 and edge_diff.sum()<=8 and error[:,:,3].max()<=1
            assert stable, 'iris appeared outside fixed eye-white aperture'
            checks.append({'shift':[dx,dy],'saved_psd_rgb_error_max':int(error[:,:,:3].max()),
                           'saved_psd_alpha_error_max':int(error[:,:,3].max()),'outside_apertures_unchanged':stable,
                           'antialiased_edge_pixels_over_2_levels':int(edge_diff.sum()),
                           'opaque_aperture_rgb_error_max':int(error[:,:,:3][opening==255].max())})
            Image.fromarray(actual).save(dest/'qa'/f'psd-gaze-{i}.png')
        for l in irises:l.offset=offsets[l.name]
        # The delivered animation uses the reopened PSD's clipping renderer.
        psd_frames=[]
        for t in range(24):
            dx=round(6*np.sin(t*2*np.pi/24));dy=round(3*np.sin(t*4*np.pi/24))
            for l in irises:
                x,y=offsets[l.name];l.offset=(x+dx,y+dy)
            psd_frames.append(psd.composite(viewport=tuple(box),force=True).convert('RGB'))
        psd_frames[0].save(dest/'qa/psd-gaze-material-check.png',save_all=True,append_images=psd_frames[1:],duration=85,loop=0,disposal=0,blend=0)
        for l in irises:l.offset=offsets[l.name]
        for kind in ['iris-hidden','eyes-hidden']:
            if kind=='iris-hidden':
                for l in irises:l.visible=False
            else:
                for g in psd:
                    if g.name.startswith('02_'):g.visible=False
            actual=np.array(psd.composite(viewport=tuple(box),force=True))
            expected=np.array(Image.open(dest/'qa'/f'{kind}.png').crop(box).convert('RGBA'))
            error=np.abs(actual.astype('int16')-expected.astype('int16'))
            assert error[:,:,:3].max()<=2 and error[:,:,3].max()<=1
            Image.fromarray(actual).save(dest/'qa'/f'psd-{kind}.png')
        # Validate no colored iris is baked into eye-white layers.
        colors=[]
        for n in ['Far','Near']:
            a=np.array(Image.open(dest/'layers'/f'{n}_White.png')).astype('int16')
            r,g,b=a[:,:,:3].transpose(2,0,1)
            residual=(a[:,:,3]>240)&(g-r>10)&(b-r>10)
            assert not residual.any()
            colors.append({'eye':n,'cyan_iris_residue_pixels_on_sclera':int(residual.sum())})
        source=np.array(Image.open(OUT.parent/record['source']).convert('RGBA'))
        neutral=np.array(Image.open(dest/'qa/neutral.png').convert('RGBA'))
        outside_band=np.ones(source.shape[:2],bool);x,y,r,b=box;outside_band[y:b,x:r]=False
        assert np.array_equal(source[outside_band],neutral[outside_band])
        for col,(label,image_path) in enumerate([('ORIGINAL',OUT/record['file']),('SAVED PSD',dest/'qa/psd-gaze-1.png')]):
            im=Image.open(image_path).convert('RGBA');overview.paste(im,(col*768,row*405+21),im)
            ImageDraw.Draw(overview).text((col*768+10,row*405+4),side.upper()+' / '+label,fill=(40,45,60))
        for j,name in enumerate([n+'_'+p for n in ['Far','Near'] for p in ['White','Iris','UpperLid','LowerLid']]):
            im=Image.open(dest/'layers'/f'{name}.png').convert('RGBA');bounds=im.getbbox();im=im.crop(bounds)
            factor=min(350/im.width,160/im.height);im=im.resize((round(im.width*factor),round(im.height*factor)),Image.Resampling.LANCZOS)
            col=j%4;tile_row=row*2+j//4;tx=col*400;ty=tile_row*250
            layersheet.paste(im,(tx+(400-im.width)//2,ty+55),im)
            ImageDraw.Draw(layersheet).text((tx+12,ty+14),side.upper()+' / '+name,fill='white')
        reports.append({'side':side,'psd_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pixel_layers':len(layers),'iris_clipping_layers':len(irises),
                        'gaze_checks':checks,'white_layer_checks':colors,'outside_eye_band_exact':True,
                        'source_alpha_note':'opaque eye-layer compositing can raise near-opaque source alpha by a few levels inside the eye band',
                        'limits':'small iris translation only; no side blink, head turn, physics, or Cubism runtime validation'})
        del psd;gc.collect()
    overview.save(OUT/'qa/side-eye-neutral-comparison.jpg',quality=96)
    layersheet.save(OUT/'qa/side-eye-layer-sheet.jpg',quality=96)
    left=Image.open(OUT/'left/qa/psd-gaze-material-check.png');right=Image.open(OUT/'right/qa/psd-gaze-material-check.png');frames=[]
    assert left.n_frames==right.n_frames==24
    for index in range(24):
        left.seek(index);right.seek(index);frame=Image.new('RGB',(768,816),(225,229,237));d=ImageDraw.Draw(frame)
        frame.paste(left.convert('RGB'),(0,24));frame.paste(right.convert('RGB'),(0,432))
        d.text((10,6),'LEFT VIEW / eye materials, fixed head',fill=(40,45,60));d.text((10,414),'RIGHT VIEW / eye materials, fixed head',fill=(40,45,60));frames.append(frame)
    frames[0].save(OUT/'qa/side-eye-gaze-check.png',save_all=True,append_images=frames[1:],duration=85,loop=0,disposal=0,blend=0)
    (OUT/'qa/saved-psd-verification.json').write_text(json.dumps(reports,indent=2)+'\n')
    print(json.dumps(reports,indent=2))

if __name__=='__main__':main()
