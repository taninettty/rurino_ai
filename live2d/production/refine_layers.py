"""Repair occluded areas using the existing LibTV underpainting.

Only add hidden pixels under higher, opaque original parts. This makes the
neutral reconstruction independently checkable instead of silently repainting it.
"""
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer, Group

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'refined'
W,H=1536,2048


def mask_poly(points):
    im=Image.new('L',(W,H))
    ImageDraw.Draw(im).polygon([(int(x*2),int(y*2)) for x,y in points],fill=255)
    return np.array(im)>0


def load(name):
    return np.array(Image.open(ROOT/name).convert('RGBA'))


def opaque(a):
    a=a.copy();a[:,:,3][a[:,:,3]>224]=255
    return a


def largest(mask):
    n,lab,stats,_=cv2.connectedComponentsWithStats(mask.astype('uint8'))
    if n<2:return mask
    return lab==(1+np.argmax(stats[1:,cv2.CC_STAT_AREA]))


def nearest_extend(pixels, target):
    """Extend existing boundary colors only into an explicitly allowed overlap."""
    valid=pixels[:,:,3]>224
    _,indices=cv2.distanceTransformWithLabels((~valid).astype('uint8'),cv2.DIST_L2,
                         5,labelType=cv2.DIST_LABEL_PIXEL)
    colors=pixels[valid]
    out=np.zeros_like(pixels)
    out[target]=colors[np.maximum(0,indices[target]-1)]
    out[:,:,3][target]=255
    return out


def main():
    (OUT/'layers').mkdir(parents=True,exist_ok=True)
    source=opaque(load('neutral_reassembled.png'))
    original=json.loads((ROOT/'layer_manifest.json').read_text())
    names=[x['name'] for x in original if x['kind']=='original_pixels']
    ownership=np.full((H,W),-1,np.int16)
    for i,name in enumerate(names):
        ownership[load('layers/'+name+'.png')[:,:,3]>0]=i

    # The first split assigned the upper tail sections to the front-hair rectangle.
    # Move only existing hair pixels; do not take the sleeve or face with them.
    left_tail=mask_poly([(244,253),(281,269),(296,302),(323,339),(304,410),
         (299,604),(282,685),(65,685),(57,513),(82,451),(141,395),(190,340),(216,287)])
    right_tail=np.fliplr(left_tail)
    for side,m in [('L',left_tail),('R',right_tail)]:
        front=names.index('Hair_Front_'+side);back=names.index('Hair_Back_'+side)
        ownership[m&(ownership==front)] = back

    # Cuff fragments outside the main hand go back to the sleeve.
    for side in ['L','R']:
        hand=names.index('Hand_'+side);arm=names.index('Arm_'+side)
        selected=(ownership==hand)&(source[:,:,3]>32)
        ownership[selected&~largest(selected)] = arm
        # The pale curl is hair, not fabric, and must not move with the arm.
        yy,xx=np.indices((H,W))
        light=(source[:,:,1]>105)&(source[:,:,2]>105)
        hairbit=(ownership==arm)&light&(yy<1360)&(yy>540)
        if side=='L':hairbit &= xx<520
        else:hairbit &= xx>1010
        ownership[hairbit] = names.index('Hair_Back_'+side)
        sleeve=(ownership==arm)&(source[:,:,3]>32)
        fragments=sleeve&~largest(sleeve)
        ownership[fragments&(yy>=1360)] = names.index('Skirt')
        ownership[fragments&(yy<1360)] = names.index('Body_Chest')

    # Include the entire eye boundary in its movable patch so skin underneath
    # does not retain an old eyelash when the open-eye pieces are hidden.
    for side,points in [('L',[(288,183),(320,179),(351,190),(365,225),(351,247),(304,246),(285,217)]),
                        ('R',[(399,190),(432,178),(465,181),(477,218),(459,246),(413,246),(398,225)])]:
        m=mask_poly(points)&(ownership==names.index('Face_Skin'))
        ownership[m]=names.index('Eye_'+side+'_White_Lash')

    order=[('Hair_Back_L','01_Back_Hair'),('Hair_Back_R','01_Back_Hair'),
       ('Legs','02_Legs'),('Arm_L','03_Arms'),('Arm_R','03_Arms'),
       ('Skirt','04_Body'),('Body_Chest','04_Body'),
       ('Hand_L','05_Hands'),('Hand_R','05_Hands'),('Neck','06_Neck'),
       ('Face_Skin','07_Head'),('Brow_L','08_Face'),('Brow_R','08_Face'),
       ('Eye_L_White_Lash','08_Face'),('Eye_R_White_Lash','08_Face'),
       ('Eye_L_Iris','08_Face'),('Eye_R_Iris','08_Face'),('Mouth_Closed','08_Face'),
       ('Hair_Front_L','09_Front_Hair'),('Hair_Front_R','09_Front_Hair'),
       ('Hair_Lock_R','09_Front_Hair'),('Flower_L','10_Flowers'),('Flower_R','10_Flowers')]
    z={name:i for i,(name,_) in enumerate(order)}
    owner_z=np.full((H,W),-1,np.int16)
    for name,i in z.items():owner_z[ownership==names.index(name)]=i
    parts={}
    for name,_ in order:
        a=source.copy();a[:,:,3][ownership!=names.index(name)]=0;a[a[:,:,3]==0]=0
        parts[name]=a
    records={}

    def add_hidden(name,paint,shape,method):
        permitted=shape&(source[:,:,3]==255)&(owner_z>z[name])&(paint[:,:,3]>32)
        current=parts[name]
        permitted &= current[:,:,3]==0
        current[permitted]=paint[permitted]
        current[:,:,3][permitted]=255
        records.setdefault(name,[]).append({'method':method,'added_pixels':int(permitted.sum())})

    body=opaque(load('body_underpaint_aligned.png'))
    face=opaque(load('face_underpaint_aligned.png'))
    add_hidden('Face_Skin',face,mask_poly([(276,50),(487,50),(503,220),(460,285),
          (416,320),(384,324),(335,305),(291,263),(267,177)]),'LibTV face, nose/chin registration')
    add_hidden('Body_Chest',body,mask_poly([(244,354),(343,322),(425,322),(523,352),
          (531,470),(513,610),(511,695),(272,695),(252,608),(241,460)]),'LibTV clothing under hair and shoulders')
    add_hidden('Neck',body,mask_poly([(346,286),(422,286),(439,363),(419,394),
          (349,395),(330,350)]),'LibTV neck under jaw and collar')

    # Explicit visual landmarks, not the earlier low-confidence automatic fit.
    hair=opaque(load('hair_underpaint.png'))
    src=np.float32([(240,280),(50,600),(120,810)])*2
    dst=np.float32([(270,250),(95,500),(135,653)])*2
    hair_shapes={}
    for side in ['L','R']:
        p=src.copy();q=dst.copy()
        if side=='R':p[:,0]=W-p[:,0];q[:,0]=W-q[:,0]
        matrix=cv2.getAffineTransform(p,q)
        warped=cv2.warpAffine(hair,matrix,(W,H),flags=cv2.INTER_CUBIC)
        shape=mask_poly([(229,67),(288,83),(301,246),(326,335),(310,446),
             (300,573),(280,675),(116,682),(66,626),(66,484),(128,413),
             (188,339),(215,256),(209,152)])
        if side=='R':shape=np.fliplr(shape)
        hair_shapes[side]=shape
        add_hidden('Hair_Back_'+side,warped,shape,'LibTV tail; manual 3-point hidden-region alignment')
        records['Hair_Back_'+side][-1]['matrix']=matrix.tolist()

    # Give sleeves and wrists an overlap that stays behind their visible partner.
    for side in ['L','R']:
        arm='Arm_'+side; hand='Hand_'+side
        region=cv2.dilate((parts[arm][:,:,3]>224).astype('uint8'),np.ones((25,25),np.uint8))>0
        add_hidden(arm,body,region,'LibTV sleeve overlap under torso/cuff')
        hand_region=cv2.dilate((parts[hand][:,:,3]>224).astype('uint8'),np.ones((21,21),np.uint8))>0
        # Hands are above sleeves, so extend them under the sleeve via a separate
        # support drawn immediately below the sleeves, rather than covering a cuff.
        support=nearest_extend(parts[hand],hand_region)
        permitted=hand_region&(ownership==names.index(arm))&(source[:,:,3]==255)
        support[:,:,3][~permitted]=0;support[support[:,:,3]==0]=0
        parts['Wrist_Overlap_'+side]=support
        records['Wrist_Overlap_'+side]=[{'method':'boundary skin extension under cuff',
                                     'added_pixels':int(permitted.sum())}]

    # Eye whites must remain continuous when the iris moves.
    for side,color in [('L',(243,243,242,255)),('R',(245,244,244,255))]:
        iris=(ownership==names.index('Eye_'+side+'_Iris'))
        fill=np.zeros_like(source);fill[iris]=color
        add_hidden('Eye_'+side+'_White_Lash',fill,iris,'sclera continuation under iris')

    # Extend front hair underneath the two flower attachments using nearby hair.
    for side in ['L','R']:
        name='Hair_Front_'+side
        flower=(ownership==names.index('Flower_'+side))
        add_hidden(name,nearest_extend(parts[name],flower),flower,'hair under flower attachment')

    order=[('Wrist_Overlap_L','00_Joint_Overlaps'),('Wrist_Overlap_R','00_Joint_Overlaps')]+order
    for name,group in order:
        Image.fromarray(parts[name]).save(OUT/'layers'/f'{name}.png',compress_level=3)

    # Alternate facial states are never layered over open-state pixels in the test.
    alternatives={}
    for name in ['Eye_L_Closed','Eye_R_Closed','Mouth_Open']:
        a=opaque(load('layers/'+name+'.png'))
        alternatives[name]=a
        Image.fromarray(a).save(OUT/'layers'/f'{name}.png',compress_level=3)

    neutral=Image.new('RGBA',(W,H))
    for name,_ in order:neutral.alpha_composite(Image.fromarray(parts[name]))
    neutral.save(OUT/'neutral.png')
    result=np.array(neutral)
    rgb=np.abs(result[:,:,:3].astype(int)-source[:,:,:3].astype(int))
    visible=source[:,:,3]>0
    report={'visible_parts':len(order),'hidden_expression_parts':len(alternatives),
       'canvas':[W,H],'neutral_alpha_max_error':int(np.abs(result[:,:,3].astype(int)-source[:,:,3]).max()),
       'neutral_rgb_max_error':int(rgb[visible].max()),
       'opaque_body_alpha_normalization':'source alpha >224 raised to255 for solid overlapping parts',
       'repairs':records,'cubism_bound':False}
    assert report['neutral_alpha_max_error']==0,report
    assert report['neutral_rgb_max_error']<=1,report

    psd=PSDImage.new('RGBA',(W,H),color=0,depth=8)
    groups={}
    manifest=[]
    def insert(name,group,a,visible=True):
        if group not in groups:groups[group]=Group.new(group,parent=psd)
        im=Image.fromarray(a);box=im.getbbox()
        layer=PixelLayer.frompil(im.crop(box),psd_file=psd,layer_name=name,top=box[1],left=box[0])
        groups[group].append(layer);layer.visible=visible
        manifest.append({'name':name,'group':group,'visible':visible,'bbox':box})
    for name,group in order:insert(name,group,parts[name])
    for name,a in alternatives.items():insert(name,'08_Face',a,False)
    insert('Approved_Reference','99_Reference',source,False)
    groups['99_Reference'].visible=False
    psd.save(OUT/'Rurino_Repaired_Layers.psd')
    reread=PSDImage.open(OUT/'Rurino_Repaired_Layers.psd')
    re=np.array(reread.composite(force=True).convert('RGBA'))
    report['psd_roundtrip_alpha_error']=int(np.abs(re[:,:,3].astype(int)-result[:,:,3]).max())
    report['psd_roundtrip_rgb_error']=int(np.abs(re[:,:,:3].astype(int)-result[:,:,:3])[visible].max())
    assert report['psd_roundtrip_alpha_error']<=1 and report['psd_roundtrip_rgb_error']<=1
    Image.fromarray(re).save(OUT/'psd_render.png')
    (OUT/'layers.json').write_text(json.dumps(manifest,indent=2))
    (OUT/'repair_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='repairs'}),flush=True)


if __name__=='__main__':main()
