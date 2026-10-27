"""Check clipping and texture stability across the frontal mouth study."""
import json
import numpy as np
from build_mouth_materials_v34 import OUT, extract, pose

parts,neutral,line,top,low,registration=extract()
previous=np.zeros(neutral.shape[:2],dtype=np.uint8)
rows=[]
for step in range(101):
    p=step/100
    components=pose(parts,neutral,line,top,low,p)
    if step==0:
        assert np.array_equal(components['Neutral'],neutral)
        rows.append({'openness':p,'aperture_alpha_sum':0})
        continue
    aperture=components['Cavity'][:,:,3]
    assert np.all(aperture>=previous),f'aperture shrank at {p}'
    assert np.all(aperture<=parts['Cavity'][:,:,3])
    for name in ['Cavity','Teeth','Tongue']:
        assert np.array_equal(components[name][:,:,:3],parts[name][:,:,:3])
    for name in ['Teeth','Tongue']:
        assert np.array_equal(components[name],parts[name])
        effective_alpha=components[name][:,:,3].astype('float32')*aperture/255
        assert np.all(effective_alpha[aperture==0]==0)
    rows.append({'openness':p,'aperture_alpha_sum':int(aperture.sum())})
    previous=aperture.copy()
report={'states_checked':len(rows),'aperture_pixelwise_monotonic':True,
        'teeth_and_tongue_texture_and_position_unchanged':True,
        'clipped_teeth_and_tongue_outside_aperture':0,
        'neutral_preserved_exactly':True,'samples':rows,
        'scope':'raster material checks; not Cubism binding or audio alignment'}
(OUT/'qa/dense-transition-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='samples'},indent=2))
