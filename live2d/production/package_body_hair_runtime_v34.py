"""Add an authored eight-second waist-sway idle to the verified Cubism export.

Geometry and physics remain the editor output. This script is rerun after exports;
there is no .can3 animation project for this programmatically authored motion.
"""
from pathlib import Path
import json,shutil,math
stage=Path(__file__).resolve().parents[1]/'rebuild_v3_4/body_hair_rig';source=stage/'runtime-body';out=stage/'runtime-desktop'
shutil.copytree(source,out,dirs_exist_ok=True)
for p in out.glob('__qa_*'):p.unlink()
(out/'motions').mkdir(exist_ok=True)
a=6;k=a*math.pi/6
segments=[0,0,1,2/3,k,4/3,a,2,a,1,8/3,a,10/3,k,4,0,1,14/3,-k,16/3,-a,6,-a,1,20/3,-a,22/3,-k,8,0]
motion={'Version':3,'Meta':{'Duration':8,'Fps':30,'Loop':True,'AreBeziersRestricted':True,'CurveCount':1,'TotalSegmentCount':4,'TotalPointCount':13,'UserDataCount':0,'TotalUserDataSize':0},'FadeInTime':1,'FadeOutTime':1,'Curves':[{'Target':'Parameter','Id':'ParamBodyAngleZ','Segments':segments}]}
(out/'motions/idle_sway.motion3.json').write_text(json.dumps(motion,indent=2))
p=out/'Rurino_Body_Hair_v034.model3.json';data=json.loads(p.read_text());data['FileReferences']['Motions']={'Idle':[{'File':'motions/idle_sway.motion3.json','FadeInTime':1,'FadeOutTime':1}]};p.write_text(json.dumps(data,indent=2));print(p)
