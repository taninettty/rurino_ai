"""Exercise the exported idle using the desktop host's restart-on-finish policy."""
import sys,json,live2d,numpy as np
from pathlib import Path
p=Path(sys.argv[1]).resolve();out=p.parent.parent/'qa-body';live2d.init();m=live2d.Model();m.LoadModelJson(str(p),False);m.SetAutoBlink(False);m.SetAutoBreath(False);assert 'Idle' in m.GetMotionGroups();m.StartRandomMotion('Idle',1)
a=[];starts=1
for i in range(1200):
 m.Update(1/60)
 if m.IsMotionFinished():m.StartRandomMotion('Idle',1);starts+=1
 a.append([m.GetParamValueById(n) for n in ['ParamBodyAngleZ','ParamHairSmallL','ParamHairSmallR','ParamHairSide','ParamHairBack']])
a=np.array(a);assert np.isfinite(a).all();assert a[:,0].min()<-5.8 and a[:,0].max()>5.8 and np.abs(a[:,0]).max()<6.01;assert (np.ptp(a[:,1:],axis=0)>.1).all();assert (np.abs(a[:,1:]).max(0)<1).all();assert np.ptp(a[960:,0])>5
r={'passed':True,'model':p.name,'seconds':20,'body_range':[float(a[:,0].min()),float(a[:,0].max())],'tail_peak_abs':np.abs(a[:,1:]).max(0).tolist(),'playback_starts':starts,'continues_after_16_seconds':True,'policy':'StartRandomMotion Idle when IsMotionFinished, matching desktop/app.py'};out.mkdir(exist_ok=True);(out/'idle-runtime-report.json').write_text(json.dumps(r,indent=2));print(r)
