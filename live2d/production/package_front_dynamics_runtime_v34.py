"""Add external idle/physics files to the unchanged Cubism export.

The cmo3 contains all geometry bindings. This script authors motion/physics JSON;
these external settings are not saved inside the cmo3 and no can3 is supplied.
"""
from pathlib import Path
import json,shutil,math,sys
stage=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'rebuild_v3_4/front_dynamics'
source=stage/('runtime-editor-export' if (stage/'runtime-editor-export').is_dir() else 'runtime')
out=stage/('runtime' if source.name=='runtime-editor-export' else 'runtime-desktop')
shutil.copytree(source,out,dirs_exist_ok=True)
(out/'motions').mkdir(exist_ok=True)
a=5;k=a*math.pi/6
segments=[0,0,1,2/3,k,4/3,a,2,a,1,8/3,a,10/3,k,4,0,1,14/3,-k,16/3,-a,6,-a,1,20/3,-a,22/3,-k,8,0]
motion={'Version':3,'Meta':{'Duration':8,'Fps':30,'Loop':True,'AreBeziersRestricted':True,'CurveCount':1,'TotalSegmentCount':4,'TotalPointCount':13,'UserDataCount':0,'TotalUserDataSize':0},'FadeInTime':1,'FadeOutTime':1,'Curves':[{'Target':'Parameter','Id':'ParamBodyAngleZ','Segments':segments}]}
# Cubism suppresses its auto-blink update while an idle motion is active.
# Supply eye curves in that motion so an always-running idle still blinks.
blink=[(0,1),(1.7,1),(1.8,0),(1.85,0),(2,1),(5.4,1),(5.5,0),(5.55,0),(5.7,1),(8,1)]
for eye in ['ParamEyeLOpen','ParamEyeROpen']:
 seg=list(blink[0])
 for t,value in blink[1:]:seg += [0,t,value]
 motion['Curves'].append({'Target':'Parameter','Id':eye,'Segments':seg})
motion['Meta'].update(CurveCount=3,TotalSegmentCount=22,TotalPointCount=33)
(out/'motions/idle.motion3.json').write_text(json.dumps(motion,indent=2)+'\n')
settings=[]
for i,(name,param,radius,delay) in enumerate([('Large left','ParamHairSide',22,.50),('Large right','ParamHairBack',24,.55)],1):
 settings.append({'Id':f'PhysicsSetting{i}','Input':[{'Source':{'Target':'Parameter','Id':'ParamBodyAngleZ'},'Weight':100,'Type':'Angle','Reflect':False}], 'Output':[{'Destination':{'Target':'Parameter','Id':param},'VertexIndex':1,'Scale':.8,'Weight':100,'Type':'Angle','Reflect':True}], 'Vertices':[{'Position':{'X':0,'Y':0},'Mobility':1,'Delay':1,'Acceleration':1,'Radius':0},{'Position':{'X':0,'Y':radius},'Mobility':.82,'Delay':delay,'Acceleration':1.2,'Radius':radius}], 'Normalization':{'Position':{'Minimum':-10,'Default':0,'Maximum':10},'Angle':{'Minimum':-30,'Default':0,'Maximum':30}}})
physics={'Version':3,'Meta':{'PhysicsSettingCount':2,'TotalInputCount':2,'TotalOutputCount':2,'VertexCount':4,'Fps':60,'EffectiveForces':{'Gravity':{'X':0,'Y':-1},'Wind':{'X':0,'Y':0}},'PhysicsDictionary':[{'Id':s['Id'],'Name':n} for s,n in zip(settings,['Large left','Large right'])]},'PhysicsSettings':settings}
name='Rurino_Front_Dynamics_v034';(out/(name+'.physics3.json')).write_text(json.dumps(physics,indent=2)+'\n')
p=out/(name+'.model3.json');d=json.loads(p.read_text());d['FileReferences']['Physics']=name+'.physics3.json';d['FileReferences']['Motions']={'Idle':[{'File':'motions/idle.motion3.json','FadeInTime':1,'FadeOutTime':1}]};d['Groups']=[{'Target':'Parameter','Name':'EyeBlink','Ids':['ParamEyeLOpen','ParamEyeROpen']},{'Target':'Parameter','Name':'LipSync','Ids':['ParamMouthOpenY']}];p.write_text(json.dumps(d,indent=2)+'\n');print(p)
