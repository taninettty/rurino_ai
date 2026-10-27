"""Side-view eye materials. Fixed-aperture gaze checks, not a head/blink rig.

Original iris/lash pixels are retained. LibTV plates supply concealed sclera
and skin. Small hidden iris margins use nearest visible texels, never scaling.
"""
import gc,hashlib,json
from pathlib import Path
import cv2,numpy as np
from scipy.ndimage import binary_fill_holes,distance_transform_edt
from PIL import Image,ImageDraw,ImageFilter
from psd_tools import PSDImage
from psd_tools.api.layers import Group,PixelLayer

ROOT=Path(__file__).resolve().parents[1]
TURN=ROOT/'rebuild_v3_4/turn_redraw'
OUT=TURN/'eye_layers'
CONFIG={
 'left':[
  {'name':'Far','roi':[575,700,805,915],'ellipse':[684,824,56,73,8],'split_y':874,
   'hair_boxes':[[575,700,640,778],[575,770,625,900]],
   'polygon':[[580,708],[689,706],[757,738],[795,815],[780,889],[650,910],[601,873],[578,811]]},
  {'name':'Near','roi':[900,695,1220,910],'ellipse':[1041,818,78,77,6],'split_y':874,
   'hair_boxes':[[900,695,955,792],[1090,695,1140,770],[1140,695,1205,822]],
   'polygon':[[915,724],[1040,695],[1167,704],[1218,769],[1204,836],[1145,890],[975,905],[908,832]]}],
 'right':[
  {'name':'Near','roi':[845,690,1145,910],'ellipse':[1006,814,79,77,8],'split_y':870,
   'hair_boxes':[[845,690,955,785],[845,780,900,899]],
   'polygon':[[848,739],[949,690],[1080,706],[1138,761],[1123,849],[1059,897],[928,895],[847,836]]},
  {'name':'Far','roi':[1235,705,1485,918],'ellipse':[1361,825,64,76,8],'split_y':880,
   'hair_boxes':[[1262,705,1305,785],[1390,705,1480,809]],
   'polygon':[[1240,797],[1281,750],[1360,705],[1446,728],[1481,791],[1452,860],[1400,913],[1298,910]]}],
}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def largest(a):
    n,l,s,c=cv2.connectedComponentsWithStats(a.astype('uint8'))
    assert n>1
    return l==1+np.argmax(s[1:,4])
def soften(a,r=.4):return np.array(Image.fromarray(a.astype('uint8')*255).filter(ImageFilter.GaussianBlur(r)))
def required_alpha(target,background):
    t=target.astype('float32');b=background.astype('float32')
    needed=np.where(t<b,(b-t)/np.maximum(b,1),(t-b)/np.maximum(255-b,1))
    return np.ceil(np.clip(needed.max(2),0,1)*255)/255
def rgba(rgb,alpha):
    a=np.zeros((*alpha.shape,4),np.uint8);a[:,:,:3]=rgb[:,:,:3];a[:,:,3]=alpha;a[alpha==0]=0
    return Image.fromarray(a)
def over(base,top):
    result=base.copy();result.alpha_composite(top);return result
def rectmask(size,boxes,origin):
    m=np.zeros(size,bool);ox,oy=origin
    for x,y,r,b in boxes:m[max(0,y-oy):b-oy,max(0,x-ox):r-ox]=True
    return m
def put_layer(psd,parent,name,im,origin=(0,0),clip=False):
    box=im.getbbox()
    if not box:return
    layer=PixelLayer.frompil(im.crop(box),psd_file=psd,layer_name=name,top=box[1]+origin[1],left=box[0]+origin[0])
    parent.append(layer);layer.clipping_layer=clip

def make_side(side,record):
    dest=OUT/side
    for d in ['layers','masks','qa']:(dest/d).mkdir(parents=True,exist_ok=True)
    source=TURN/record['source'];assert sha(source)==record['source_sha256']
    original=Image.open(source).convert('RGBA');box=record['crop_xyxy'];ox,oy,x1,y1=box;size=(x1-ox,y1-oy)
    a=np.array(original.crop(box));rgb=a[:,:,:3];shape=a.shape[:2]
    plate_records={};plates={}
    for kind in ['white','skin']:
        path=OUT/'sources'/f'{side}-{kind}-generated.png';im=Image.open(path).convert('RGBA')
        assert im.width*size[1]==im.height*size[0]
        plates[kind]=np.array(im.resize(size,Image.Resampling.LANCZOS))[:,:,:3]
        plate_records[kind]={'file':str(path.relative_to(OUT)),'sha256':sha(path),'source_dimensions':list(im.size),'destination_crop':box}
    white,skin=plates['white'],plates['skin']
    # The right skin plate retained eyelid creases. Remove just those dark lines.
    cleanup=np.zeros(shape,bool)
    if side=='right':
        zones=rectmask(shape,[[978,698,1140,761],[1320,705,1397,745]],(ox,oy))
        cleanup=zones&(skin.min(2)<220)
        cleanup=cv2.dilate(cleanup.astype('uint8'),np.ones((5,5),np.uint8))>0
        skin=cv2.inpaint(skin,cleanup.astype('uint8')*255,5,cv2.INPAINT_TELEA)
    Image.fromarray(cleanup.astype('uint8')*255).save(dest/'masks/skin-cleanup.png')
    Image.fromarray(skin).save(dest/'qa/skin-plate-clean.png')
    features={};openings={};iris_masks={};supports={};feature_union=np.zeros(shape,np.uint8);hair_union=np.zeros(shape,bool);eye_records=[]
    yy=np.arange(shape[0])[:,None]+oy
    for cfg in CONFIG[side]:
        name=cfg['name'];x,y,r,b=cfg['roi'];roi=rectmask(shape,[cfg['roi']],(ox,oy))
        region=roi.copy()
        # Foreground pink/blond strands at the known overlaps, not skin or teal iris.
        signed=rgb.astype('int16');red,green,blue=signed.transpose(2,0,1)
        warm=(red>145)&(rgb.min(2)>105)&(((blue-green>3)&(red-green>8))|((green-blue>24)&(red-green<30)))
        hair=warm&rectmask(shape,cfg['hair_boxes'],(ox,oy))
        hair=cv2.dilate(hair.astype('uint8'),np.ones((5,5),np.uint8))>0
        # Explicitly retain narrow outlined bangs that skin completion can mistake
        # for an eyelid crease, plus the outside cheek-lock edge.
        paths={('right','Near'):[[(845,680),(970,680),(954,714),(933,755),(913,737),(894,724),(878,708),(845,690)]],
               ('right','Far'):[[(1305,680),(1336,680),(1326,710),(1318,733),(1306,753),(1288,771),(1273,783),(1285,760),(1298,739),(1303,710)]],
               ('left','Near'):[[(1220,770),(1220,910),(1177,910),(1196,881),(1208,847),(1216,807)]],
               ('left','Far'):[]}
        for points in paths[(side,name)]:
            m=Image.new('L',size);ImageDraw.Draw(m).polygon([(u-ox,v-oy) for u,v in points],fill=255)
            hair|=np.array(m)>0
        # Tiny isolated warm eyelash specks are not foreground hair strands.
        count,labels,stats,_=cv2.connectedComponentsWithStats(hair.astype('uint8'))
        keep=[j for j in range(1,count) if stats[j,cv2.CC_STAT_AREA]>=40]
        hair=np.isin(labels,keep)
        hair_union|=hair
        # Aperture comes from the blank-sclera drawing; constrain it locally.
        aperture_bounds={
            ('left','Far'):[(618,815),(625,785),(650,759),(684,751),(716,764),(744,788),(763,819),(767,850),(740,878),(714,890),(651,889),(625,869)],
            ('left','Near'):[(949,810),(965,780),(998,755),(1045,740),(1096,746),(1144,771),(1174,809),(1175,843),(1142,875),(1095,890),(984,891),(953,860)],
            ('right','Near'):[(883,815),(908,785),(951,752),(1006,740),(1058,751),(1086,787),(1103,815),(1092,852),(1063,876),(1000,887),(933,875),(901,855)],
            ('right','Far'):[(1270,818),(1289,788),(1324,759),(1364,750),(1408,768),(1440,803),(1450,831),(1430,864),(1398,894),(1321,896),(1287,874),(1273,850)]}
        aperture_region=Image.new('L',size);ImageDraw.Draw(aperture_region).polygon([(u-ox,v-oy) for u,v in aperture_bounds[(side,name)]],fill=255)
        ws=white.astype('int16');seed=(ws.min(2)>130)&(np.ptp(ws,axis=2)<24)&(np.array(aperture_region)>0)
        opening=largest(seed)
        opening=cv2.morphologyEx(opening.astype('uint8'),cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))>0
        opening &= ~hair
        ap=soften(opening,.35);openings[name]=ap
        # Ellipse bounds the iris; color/difference selection removes sclera crescents.
        cx,cy,rx,ry,angle=cfg['ellipse'];ellipse=np.zeros(shape,np.uint8)
        cv2.ellipse(ellipse,((cx-ox,cy-oy),(rx*2,ry*2),angle),255,-1,cv2.LINE_AA)
        delta=np.max(np.abs(signed-white.astype('int16')),2)
        seed=(delta>24)&(ap>100)&(ellipse>0)
        seed=largest(cv2.morphologyEx(seed.astype('uint8'),cv2.MORPH_CLOSE,np.ones((3,3),np.uint8)))
        visible=binary_fill_holes(seed)
        # Preserve anti-aliased ring pixels and specular holes, including dark blue rims.
        visible=cv2.dilate(visible.astype('uint8'),np.ones((3,3),np.uint8))>0
        iris=np.maximum(soften(visible,.3),ellipse*(ap<128))
        iris[ellipse==0]=0;iris_masks[name]=iris
        valid=(ap>240)&(iris>240)
        assert valid.sum()>3000
        _,indices=distance_transform_edt(~valid,return_indices=True)
        irgb=rgb.copy();hidden=(iris>0)&(ap==0)
        irgb[hidden]=rgb[indices[0][hidden],indices[1][hidden]]
        supports[name]=hidden
        # Original visible sclera stays unchanged. The new white fills behind iris.
        wrgb=rgb.copy();wrgb[iris>0]=white[iris>0]
        # Ensure the matte can reproduce original antialias colors without clipping.
        edge_visible=(iris>0)&(ap>0)
        needed=required_alpha(rgb,wrgb)
        iris[edge_visible]=np.maximum(iris[edge_visible],np.rint(needed[edge_visible]*255).astype('uint8'))
        # Unmatte original AA iris boundaries against the replacement white.
        f=iris.astype('float32')[...,None]/255
        edge=(iris>0)&(iris<255)&(ap>0)
        corrected=np.clip(np.rint((rgb.astype('float32')-wrgb*(1-f))/np.maximum(f,1/255)),0,255).astype('uint8')
        irgb[edge]=corrected[edge]
        features[name+'_White']=rgba(wrgb,ap)
        features[name+'_Iris']=rgba(irgb,iris)
        # Select lashes/crease using the original-to-clean-skin difference.
        delta_skin=np.max(np.abs(signed-skin.astype('int16')),2)
        original_white=(rgb.min(2)>125)&(np.ptp(signed,axis=2)<22)&region
        outline=(((delta_skin>12)&(rgb.min(2)<238))|original_white)&region&~hair
        feature=soften(outline,.35)
        feature=np.maximum(feature,ap);feature_union=np.maximum(feature_union,feature)
        # Lids restore source pixels over the eye fill, including antialiased seams.
        fa=feature.astype('float32')/255;aa=ap.astype('float32')/255
        lid=np.rint(np.clip((fa-aa)/np.maximum(1-aa,1/255),0,1)*255).astype('uint8')
        f=lid.astype('float32')[...,None]/255
        iris_alpha=iris.astype('float32')[...,None]/255
        eye_rgb=irgb*iris_alpha+wrgb*(1-iris_alpha)
        under=eye_rgb*aa[:,:,None]+skin*(1-aa[:,:,None])
        target=rgb.astype('float32')
        needed=required_alpha(target,under)
        active=(feature>0)&(ap<255)
        lid[active]=np.maximum(lid[active],np.rint(needed[active]*255).astype('uint8'))
        f=lid.astype('float32')[...,None]/255
        unmatte=np.clip(np.rint((target-under*(1-f))/np.maximum(f,1/255)),0,255).astype('uint8')
        for part,cond in [('UpperLid',yy<cfg['split_y']),('LowerLid',yy>=cfg['split_y'])]:
            features[name+'_'+part]=rgba(unmatte,lid*cond)
        for label,mask in [('Opening',ap),('Iris',iris),('Feature',feature),('HiddenIrisMargin',hidden.astype('uint8')*255)]:
            Image.fromarray(mask).save(dest/'masks'/f'{name}_{label}.png')
        eye_records.append({'name':name,'roi':cfg['roi'],'iris_ellipse':cfg['ellipse'],'clip_to':name+'_White',
                            'hidden_margin_method':'nearest original visible texel, no rescaling; only small gaze checks',
                            'hidden_margin_pixels':int(hidden.sum()),'visible_iris_pixels':int(valid.sum())})
    # Keep original foreground overlaps in a separate layer. Rest of head is context.
    remove=feature_union>0
    remove &= ~hair_union
    band=a.copy();band[remove,:3]=skin[remove]
    band[hair_union]=0
    context=original.copy();context.paste(Image.fromarray(band),(ox,oy))
    foreground=rgba(rgb,a[:,:,3]*hair_union)
    context.save(dest/'layers/Context_Skin_Reference.png')
    foreground.save(dest/'layers/Foreground_Hair_Overlap.png')
    for name,im in features.items():im.save(dest/'layers'/f'{name}.png')

    def render(gaze=(0,0),show_eyes=True,show_iris=True):
        result=context.copy();band=Image.new('RGBA',size)
        if show_eyes:
            for cfg in CONFIG[side]:
                n=cfg['name'];eye=np.array(features[n+'_White']);moving=Image.new('RGBA',size)
                if show_iris:moving.alpha_composite(features[n+'_Iris'],gaze)
                arr=np.array(moving);f=arr[:,:,3].astype('float32')[...,None]/255
                eye[:,:,:3]=np.rint(arr[:,:,:3]*f+eye[:,:,:3]*(1-f)).astype('uint8')
                band.alpha_composite(Image.fromarray(eye))
                band.alpha_composite(features[n+'_UpperLid']);band.alpha_composite(features[n+'_LowerLid'])
        band.alpha_composite(foreground);result.alpha_composite(band,(ox,oy));return result

    neutral=render();neutral.save(dest/'qa/neutral.png')
    render(show_iris=False).save(dest/'qa/iris-hidden.png');render(show_eyes=False).save(dest/'qa/eyes-hidden.png')
    psd=PSDImage.new('RGBA',(2048,2048),color=0)
    g=Group.new('01_Context_and_skin_NOT_full_head_separation',parent=psd);put_layer(psd,g,'Context_Skin_Reference',context)
    for cfg in CONFIG[side]:
        n=cfg['name'];g=Group.new('02_'+n+'_Eye',parent=psd)
        for part in ['White','Iris','UpperLid','LowerLid']:put_layer(psd,g,n+'_'+part,features[n+'_'+part],(ox,oy),part=='Iris')
    g=Group.new('03_Original_foreground_overlap',parent=psd);put_layer(psd,g,'Foreground_Hair_Overlap',foreground,(ox,oy))
    psdpath=dest/f'Rurino_Turn_{side.title()}_Eye_Materials_v034.psd';psd.save(psdpath);del psd;gc.collect()
    reopened=PSDImage.open(psdpath);composite=reopened.composite(force=True);actual=np.array(composite)
    # psd-tools descendants() also yields a clipping layer through its base.
    pixel_layers=list({id(l):l for l in reopened.descendants() if l.kind=='pixel'}.values());clipping=sum(l.clipping_layer for l in pixel_layers)
    composite.save(dest/'qa/saved-psd-neutral.png');del reopened;gc.collect()
    expected=np.array(neutral);difference=np.abs(actual.astype('int16')-expected.astype('int16'))
    original_arr=np.array(original);neutral_delta=np.abs(expected.astype('int16')-original_arr.astype('int16'))
    # Gaze tests move only irises. No eyelid scaling or head turning is simulated.
    gazes=[(-6,0),(0,0),(6,0),(0,-4),(0,4)]
    grid=Image.new('RGB',(768*len(gazes),414),(225,229,237));tests=[]
    for i,gaze in enumerate(gazes):
        frame=render(gaze);tile=frame.crop(box);grid.paste(tile,(i*768,30),tile);ImageDraw.Draw(grid).text((i*768+10,8),f'{side} iris shift {gaze}',fill=(40,45,60))
        frame.crop(box).save(dest/'qa'/f'gaze-{i}.png')
        # Validate exact original interior iris color after an integer translation.
        for cfg in CONFIG[side]:
            n=cfg['name'];iris=np.array(features[n+'_Iris']);valid=(iris[:,:,3]==255)&(openings[n]==255)&~supports[n]
            shifted=np.zeros(shape,bool);dx,dy=gaze
            ys,xs=np.nonzero(valid);ny=ys+dy;nx=xs+dx;inside=(ny>=0)&(ny<shape[0])&(nx>=0)&(nx<shape[1]);ny,nx=ny[inside],nx[inside];sy,sx=ys[inside],xs[inside]
            inside=(openings[n][ny,nx]==255)&~hair_union[ny,nx]
            ny,nx,sy,sx=ny[inside],nx[inside],sy[inside],sx[inside]
            moved=np.array(frame.crop(box));error=np.abs(moved[ny,nx,:3].astype('int16')-rgb[sy,sx].astype('int16'))
            tests.append({'eye':n,'shift':gaze,'interior_pixels':len(ny),'interior_rgb_error_max':int(error.max()) if error.size else None})
    grid.save(dest/'qa/gaze-tests.jpg',quality=95)
    frames=[]
    for t in range(24):
        gaze=(round(6*np.sin(t*2*np.pi/24)),round(3*np.sin(t*4*np.pi/24)))
        frame=render(gaze).crop(box).convert('RGB');ImageDraw.Draw(frame).text((10,10),'EYE MATERIALS ONLY / fixed head and eyelids',fill=(40,45,60));frames.append(frame)
    frames[0].save(dest/'qa/gaze-material-check.png',save_all=True,append_images=frames[1:],duration=85,loop=0,disposal=0,blend=0)
    report={'side':side,'status':'side eye materials only; not head/blink rig','source_sha256':sha(source),'crop_xyxy':box,'plates':plate_records,
            'layer_count':len(pixel_layers),'clipping_layers':int(clipping),'psd_sha256':sha(psdpath),
            'psd_vs_local_render_rgb_max':int(difference[:,:,:3][expected[:,:,3]>0].max()),
            'psd_vs_local_render_alpha_max':int(difference[:,:,3].max()),
            'neutral_vs_original_rgb_mean':float(neutral_delta[:,:,:3].mean()),
            'neutral_vs_original_rgb_max':int(neutral_delta[:,:,:3].max()),
            'neutral_vs_original_alpha_max':int(neutral_delta[:,:,3].max()),
            'eyes':eye_records,'gaze_checks':tests,
            'remaining':['complete concealed eyelid/hair anatomy for head angles','closed and half-closed side keyforms','near/far eye-to-frontal registration','Cubism mesh/parameters and runtime validation']}
    (dest/'qa/checks.json').write_text(json.dumps(report,indent=2)+'\n')
    assert len(pixel_layers)==10 and clipping==2
    assert report['psd_vs_local_render_rgb_max']<=2 and report['psd_vs_local_render_alpha_max']<=1
    assert report['neutral_vs_original_rgb_max']<=2
    assert all(t['interior_pixels']>2000 and t['interior_rgb_error_max']==0 for t in tests)
    (dest/'manifest.json').write_text(json.dumps({'canvas':[2048,2048],'crop_xyxy':box,'layer_pixel_coordinates':'context is full canvas; remaining PNGs use crop-local coordinates',
                 'layers':[{'name':'Context_Skin_Reference','file':'layers/Context_Skin_Reference.png','offset':[0,0]}]+[{'name':n,'file':'layers/'+n+'.png','offset':[ox,oy],'clip_to':n.replace('_Iris','_White') if n.endswith('_Iris') else None} for n in features]+[{'name':'Foreground_Hair_Overlap','file':'layers/Foreground_Hair_Overlap.png','offset':[ox,oy]}]},indent=2)+'\n')
    return report

def main():
    records=json.loads((OUT/'source-crops.json').read_text());reports=[]
    for side,record in records.items():
        reports.append(make_side(side,record));gc.collect()
    (OUT/'checks.json').write_text(json.dumps(reports,indent=2)+'\n')
    print(json.dumps([{k:r[k] for k in ['side','layer_count','clipping_layers','psd_vs_local_render_rgb_max','psd_vs_local_render_alpha_max','neutral_vs_original_rgb_mean','neutral_vs_original_rgb_max']} for r in reports],indent=2))

if __name__=='__main__':main()
