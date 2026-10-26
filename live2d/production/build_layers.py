"""Build an editable, original-pixel PSD for Cubism preparation, not a .moc3.

All annotation coordinates are on the 768x1024 review image and scale by two.
L/R names mean the viewer's left/right, not anatomical left/right.
"""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer, Group

ROOT = Path(__file__).resolve().parents[1]
W, H = 1536, 2048
OUT = ROOT / 'layers'
OUT.mkdir(exist_ok=True)


def polygon(points):
    im = Image.new('L', (W, H))
    ImageDraw.Draw(im).polygon([(round(x*2), round(y*2)) for x, y in points], fill=255)
    return np.asarray(im) > 0


def rect(box):
    x, y, r, b = box
    return polygon([(x,y),(r,y),(r,b),(x,b)])


def ellipse(box):
    im = Image.new('L', (W,H))
    ImageDraw.Draw(im).ellipse(tuple(round(v*2) for v in box), fill=255)
    return np.asarray(im) > 0


def clean_alpha(im):
    a = np.array(im.convert('RGBA'))
    # Only remove disconnected generation specks; leave the character's pixels unchanged.
    strong = (a[:,:,3] > 32).astype('uint8')
    n, labels, stats, _ = cv2.connectedComponentsWithStats(strong)
    ids = [i for i in range(1,n) if stats[i,cv2.CC_STAT_AREA] > 200]
    keep = np.isin(labels,ids).astype('uint8')
    keep = cv2.dilate(keep,np.ones((3,3),np.uint8))
    a[:,:,3] *= keep
    return a


def main():
    source = clean_alpha(Image.open(ROOT/'rurino_master.png'))
    labels = np.zeros((H,W),np.uint8)
    definitions = []

    def assign(name, group, mask):
        idx = len(definitions)+1
        labels[mask] = idx
        definitions.append((idx,name,group))

    assign('Body_Torso','02_Body',np.ones((H,W),bool))
    assign('Hair_Back_L','01_Back_Hair',rect((35,230,321,696)))
    assign('Hair_Back_R','01_Back_Hair',rect((447,230,730,696)))
    assign('Legs','02_Body',rect((180,940,590,1024)))
    assign('Skirt','02_Body',polygon([(277,680),(499,680),(527,761),(557,832),(615,944),
         (596,973),(529,986),(448,999),(333,999),(245,985),(178,970),(156,944),(214,821)]))
    # Torso side seams override back hair only in the visible garment area.
    assign('Body_Chest','02_Body',polygon([(262,352),(342,328),(428,329),(505,351),
         (500,445),(499,565),(498,646),(505,693),(280,695),(273,622),(280,510),(271,431)]))
    arm = [(260,351),(268,390),(278,443),(280,512),(269,614),(245,689),(213,787),
           (202,823),(183,859),(116,843),(115,781),(143,711),(173,626),(190,548),
           (207,456),(227,382)]
    assign('Arm_L','03_Arms',polygon(arm))
    assign('Arm_R','03_Arms',polygon([(768-x,y) for x,y in arm]))
    assign('Hair_Lock_R','07_Front_Hair',polygon([(489,231),(508,291),(518,350),
          (520,396),(531,435),(530,467),(552,488),(554,504),(534,519),(511,523),
          (502,518),(508,507),(535,497),(533,486),(518,470),(514,438),(507,397),
          (500,354),(492,307)]))
    hand = [(120,846),(181,862),(160,916),(154,946),(154,989),(120,985),
            (97,945),(93,902)]
    assign('Hand_L','03_Arms',polygon(hand))
    assign('Hand_R','03_Arms',polygon([(768-x,y) for x,y in hand]))
    assign('Neck','04_Neck',polygon([(352,303),(418,303),(421,333),(435,346),
          (429,382),(417,393),(385,379),(351,389),(341,356),(350,335)]))
    assign('Hair_Front_L','07_Front_Hair',rect((150,0,383,340)))
    assign('Hair_Front_R','07_Front_Hair',rect((383,0,615,340)))
    face = polygon([(378,76),(386,80),(400,109),(410,148),(421,183),(439,192),
          (465,197),(468,231),(458,259),(444,282),(419,303),(386,322),(357,310),
          (334,296),(316,278),(304,258),(299,229),(299,200),(305,175),(323,146),
          (344,116),(361,93)])
    assign('Face_Skin','05_Head',face)
    assign('Flower_L','08_Flowers',polygon([(232,85),(257,45),(286,20),(302,24),
           (307,58),(292,91),(277,116),(238,134),(225,126)]))
    assign('Flower_R','08_Flowers',polygon([(447,24),(472,20),(499,44),(526,75),
           (530,115),(510,133),(485,120),(469,91),(457,61)]))
    assign('Brow_L','06_Face_Features',polygon([(297,172),(312,165),(333,162),
           (346,165),(359,172),(341,169),(320,168),(303,176)]))
    assign('Brow_R','06_Face_Features',polygon([(401,171),(412,165),(435,162),
           (450,165),(465,172),(456,174),(437,168),(418,168),(404,174)]))
    eye_l = polygon([(294,188),(314,188),(336,190),(351,202),(359,224),
          (346,236),(319,239),(300,228),(291,207)])
    eye_r = polygon([(404,202),(416,191),(439,187),(459,187),(470,202),
          (464,226),(448,237),(424,238),(407,227)])
    assign('Eye_L_White_Lash','06_Face_Features',eye_l)
    assign('Eye_R_White_Lash','06_Face_Features',eye_r)
    assign('Eye_L_Iris','06_Face_Features',ellipse((313,199,347,233)))
    assign('Eye_R_Iris','06_Face_Features',ellipse((414,198,450,232)))
    mouth = ellipse((358,268,408,285))
    assign('Mouth_Closed','06_Face_Features',mouth)

    # Put thin remaining sleeve-edge pixels in their arm, not a stray torso layer.
    yy,xx=np.indices(labels.shape)
    ids={name:idx for idx,name,_ in definitions}
    leftover=(labels==ids['Body_Torso'])
    labels[leftover&(xx<W//2)] = ids['Arm_L']
    labels[leftover&(xx>=W//2)] = ids['Arm_R']

    layers = []
    for idx,name,group in definitions:
        pixels = source.copy()
        pixels[:,:,3] = np.where(labels==idx,source[:,:,3],0)
        pixels[pixels[:,:,3] == 0] = 0
        if pixels[:,:,3].max() == 0:
            continue
        im=Image.fromarray(pixels)
        im.save(OUT/f'{name}.png',compress_level=3)
        layers.append(dict(name=name,group=group,image=im,visible=True,kind='original_pixels'))

    # Record the exact neutral composite before adding optional underpaint.
    neutral=Image.new('RGBA',(W,H))
    for item in layers:
        neutral.alpha_composite(item['image'])
    neutral.save(ROOT/'neutral_reassembled.png')
    a=np.array(neutral); diff=np.abs(a.astype('int16')-source.astype('int16'))
    # RGB is irrelevant under zero alpha; visible original pixels must be exactly preserved.
    visible=source[:,:,3]>0
    report={'canvas':[W,H],'neutral_visible_max_error':int(diff[visible].max()),
            'neutral_alpha_max_error':int(diff[:,:,3].max()),'original_layer_count':len(layers)}
    assert report['neutral_visible_max_error']==0 and report['neutral_alpha_max_error']==0

    expression_file=ROOT/'expression_aligned.png'
    if expression_file.exists():
        expression=Image.open(expression_file).convert('RGBA')
        for name,box in [('Eye_L_Closed',(289,183,365,247)),
                         ('Eye_R_Closed',(398,183,474,247)),
                         ('Mouth_Open',(350,259,417,304))]:
            mask=Image.new('L',(W,H))
            ImageDraw.Draw(mask).ellipse(tuple(v*2 for v in box),fill=255)
            mask=mask.filter(ImageFilter.GaussianBlur(3))
            pixels=np.array(expression)
            pixels[:,:,3]=(pixels[:,:,3].astype('float32')*np.array(mask)/255).astype('uint8')
            pixels[pixels[:,:,3]==0]=0
            im=Image.fromarray(pixels)
            im.save(OUT/f'{name}.png',compress_level=3)
            layers.append(dict(name=name,group='06_Face_Features',image=im,
                               visible=False,kind='aligned_expression_patch'))

    for name,box,color in [('Eye_L_Sclera_Fill',(313,199,347,233),(243,243,242,255)),
                           ('Eye_R_Sclera_Fill',(414,198,450,232),(245,244,244,255))]:
        im=Image.new('RGBA',(W,H))
        ImageDraw.Draw(im).ellipse(tuple(v*2 for v in box),fill=color)
        im.save(OUT/f'{name}.png',compress_level=3)
        layers.append(dict(name=name,group='06_Face_Features',image=im,
                           visible=False,kind='sclera_extension_for_iris_movement'))

    # Supplemental whole-canvas assets remain hidden until alignment is checked in Cubism.
    for name,file in [('Underpaint_Body_Aligned','body_underpaint_aligned.png'),
                      ('Underpaint_Face_Aligned','face_underpaint_aligned.png'),
                      ('Underpaint_RearHair','hair_underpaint.png'),
                      ('Expression_Blink_Mouth_Aligned','expression_aligned.png')]:
        path=ROOT/file
        if path.exists():
            im=Image.open(path).convert('RGBA')
            if im.size != (W,H):
                raise ValueError(f'{file} must retain the source canvas size, got {im.size}')
            layers.append(dict(name=name,group='90_LibTV_Supplements',image=im,
                               visible=False,kind='libtv_supplement_for_binding_review'))
    layers.append(dict(name='Approved_Reference',group='99_Reference',
                       image=Image.fromarray(source),visible=False,kind='reference'))

    # RGBA is essential here: frompil converts to the PSD's PIL mode before writing.
    # RGB would silently drop layer alpha and produce opaque black rectangles.
    psd=PSDImage.new('RGBA',(W,H),color=0,depth=8)
    groups={}
    manifest=[]
    for group in sorted({x['group'] for x in layers}):
        groups[group]=Group.new(group,parent=psd)
    for item in layers:
        bbox=item['image'].getbbox()
        if not bbox:
            continue
        cropped=item['image'].crop(bbox)
        layer=PixelLayer.frompil(cropped,psd_file=psd,layer_name=item['name'],
                                 top=bbox[1],left=bbox[0])
        groups[item['group']].append(layer)
        layer.visible=item['visible']
        manifest.append({k:v for k,v in item.items() if k!='image'}|{'bbox':bbox})
    for group in ('90_LibTV_Supplements','99_Reference'):
        if group in groups:
            groups[group].visible=False
    psd.save(ROOT/'Rurino_Live2D_Layers.psd')
    (ROOT/'layer_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    (ROOT/'validation.json').write_text(json.dumps(report,indent=2))

    # Re-open from disk: verify data, names and canvas survive PSD serialization.
    loaded=PSDImage.open(ROOT/'Rurino_Live2D_Layers.psd')
    assert loaded.size==(W,H)
    actual=[x for x in loaded.descendants() if not x.is_group()]
    assert len(actual)==len(manifest)
    rendered=loaded.composite(force=True)
    rendered.save(ROOT/'psd_composite.png')
    composite=np.array(rendered.convert('RGBA'))
    report['psd_composite_alpha_error']=int(np.abs(composite[:,:,3].astype(int)-source[:,:,3]).max())
    report['psd_composite_rgb_error']=int(np.abs(composite[:,:,:3].astype(int)-source[:,:,:3])[visible].max())
    assert report['psd_composite_alpha_error'] <= 1
    assert report['psd_composite_rgb_error'] <= 1
    (ROOT/'validation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)
    print(f'PSD saved with {len(actual)} layers',flush=True)


if __name__=='__main__':main()
