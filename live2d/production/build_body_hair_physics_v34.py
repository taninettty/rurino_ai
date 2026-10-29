"""Write the Cubism physics settings for the four independently bound tails."""
import json
from pathlib import Path
out=Path(__file__).resolve().parents[1]/'rebuild_v3_4/body_hair_rig';out.mkdir(exist_ok=True)
settings=[]
for k,(name,param,radius,delay,mobility,scale) in enumerate([
 ('Small left','ParamHairSmallL',10,.25,.78,1.0),
 ('Small right','ParamHairSmallR',11,.28,.78,1.0),
 ('Large left','ParamHairSide',22,.50,.82,1.2),
 ('Large right','ParamHairBack',24,.55,.82,1.2),
],1):
 settings.append({'Id':f'PhysicsSetting{k}','Input':[{'Source':{'Target':'Parameter','Id':'ParamBodyAngleZ'},'Weight':100,'Type':'Angle','Reflect':False}],
 'Output':[{'Destination':{'Target':'Parameter','Id':param},'VertexIndex':1,'Scale':scale,'Weight':100,'Type':'Angle','Reflect':True}],
 'Vertices':[{'Position':{'X':0,'Y':0},'Mobility':1,'Delay':1,'Acceleration':1,'Radius':0}, {'Position':{'X':0,'Y':radius},'Mobility':mobility,'Delay':delay,'Acceleration':1.2,'Radius':radius}],
 'Normalization':{'Position':{'Minimum':-10,'Default':0,'Maximum':10},'Angle':{'Minimum':-30,'Default':0,'Maximum':30}}})
data={'Version':3,'Meta':{'PhysicsSettingCount':4,'TotalInputCount':4,'TotalOutputCount':4,'VertexCount':8,'Fps':60,'EffectiveForces':{'Gravity':{'X':0,'Y':-1},'Wind':{'X':0,'Y':0}},'PhysicsDictionary':[{'Id':s['Id'],'Name':n} for s,n in zip(settings,['Small left','Small right','Large left','Large right'])]},'PhysicsSettings':settings}
p=out/'Rurino_Body_Hair_v034.physics3.json';p.write_text(json.dumps(data,indent=2));print(p)
