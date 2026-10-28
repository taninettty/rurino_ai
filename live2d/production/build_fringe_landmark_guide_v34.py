from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[1]/'rebuild_v3_4/turn_redraw';out=root/'fringe_overlap_separation/qa';out.mkdir(exist_ok=True)
a=Image.open(root/'hair_structure_assembly/qa/saved-psd-open.png').convert('RGBA');bg=Image.new('RGBA',a.size,'#e2e9f0');bg.alpha_composite(a)
box=(460,80,1420,900);im=bg.crop(box);sheet=Image.new('RGB',(1420,1030),'#edf1f6');sheet.paste(im,(30,80),im);d=ImageDraw.Draw(sheet);f=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',23);small=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',19)
d.text((30,20),'头顶与刘海：可见节点核对',font=f,fill='#26394f')
# Coordinates reference the actual 1024 view. Tips are landmarks, not a layer count.
pts=[('A',(319,378),'左侧额前可见尖端'),('B',(477,391),'右侧靠额头的细尖'),('C',(551,376),'右侧中间可见尖端'),('D',(574,391),'右侧外侧可见尖端')]
for i,(letter,(x,y),label) in enumerate(pts):
 px=30+2*x-box[0];py=80+2*y-box[1];d.ellipse((px-7,py-7,px+7,py+7),fill='#bc3b69',outline='white',width=2);d.text((px+10,py-25),letter,font=f,fill='#9f2451');d.text((1020,340+i*57),letter+'  '+label,font=small,fill='#26394f')
d.multiline_text((1020,85),'头顶 ↔ 刘海\n连续共用发面\n\n原画没有完整分界线\n暂不强行横切',font=f,fill='#425974',spacing=12)
d.multiline_text((1020,610),'眉线横跨发束前方\n本轮只分出覆盖区\n\n尖端数量不等于发束数\n根部与前后关系仍待核对',font=small,fill='#425974',spacing=14)
d.text((30,945),'A—D 为本轮核对用的可见尖端附近定位；不是已确认的独立发束，不包含所有侧发尖端。',font=small,fill='#52647a')
d.text((30,980),'眉毛遮挡下的头发颜色没有补画；覆盖区已另层保留，仍按先拆分、最后统一修整。',font=small,fill='#52647a')
sheet.save(out/'crown-fringe-landmarks.jpg',quality=96)
