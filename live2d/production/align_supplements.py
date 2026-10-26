"""Register LibTV edits to the approved canvas, preserving original files."""
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
base=cv2.imread(str(ROOT/'rurino_master.png'),cv2.IMREAD_UNCHANGED)
H,W=base.shape[:2]
sift=cv2.SIFT_create(nfeatures=12000)
results={}

for name in ['body_underpaint','expression','hair_underpaint']:
    src=cv2.imread(str(ROOT/f'{name}.png'),cv2.IMREAD_UNCHANGED)
    mask=np.zeros((H,W),np.uint8)
    if name=='body_underpaint':mask[700:,:] = 255
    elif name=='expression':mask[60:680,380:1170]=255
    else:mask[100:1370,:]=255
    mask=np.minimum(mask,(base[:,:,3]>120).astype(np.uint8)*255)
    k1,d1=sift.detectAndCompute(cv2.cvtColor(base[:,:,:3],cv2.COLOR_BGR2GRAY),mask)
    k2,d2=sift.detectAndCompute(cv2.cvtColor(src[:,:,:3],cv2.COLOR_BGR2GRAY),
                             (src[:,:,3]>120).astype(np.uint8)*255)
    matches=cv2.BFMatcher().knnMatch(d2,d1,k=2)
    good=[m for m,n in matches if m.distance < .7*n.distance]
    if len(good)<8:
        results[name]={'status':'needs_manual_alignment','matches':len(good)}
        continue
    p=np.float32([k2[m.queryIdx].pt for m in good])
    q=np.float32([k1[m.trainIdx].pt for m in good])
    matrix,inliers=cv2.estimateAffinePartial2D(p,q,method=cv2.RANSAC,ransacReprojThreshold=3)
    if matrix is None or int(inliers.sum()) < 8:
        results[name]={'status':'needs_manual_alignment','matches':len(good),
                       'inliers':0 if inliers is None else int(inliers.sum())}
        continue
    aligned=cv2.warpAffine(src,matrix,(W,H),flags=cv2.INTER_CUBIC)
    cv2.imwrite(str(ROOT/f'{name}_aligned.png'),aligned)
    results[name]={'status':'aligned','matrix':matrix.tolist(),'matches':len(good),
                   'inliers':int(inliers.sum())}

# The isolated bald head was enlarged by the image model. Anchor its nose and chin
# to the approved drawing; do not claim pixel-perfect registration from text alone.
src=cv2.imread(str(ROOT/'face_underpaint.png'),cv2.IMREAD_UNCHANGED)
scale=(644-500)/(1500-1128)
matrix=np.float32([[scale,0,768-scale*766],[0,scale,500-scale*1128]])
aligned=cv2.warpAffine(src,matrix,(W,H),flags=cv2.INTER_CUBIC)
cv2.imwrite(str(ROOT/'face_underpaint_aligned.png'),aligned)
results['face_underpaint']={'status':'manual_nose_chin_alignment','matrix':matrix.tolist(),
    'source_landmarks':[[766,1128],[766,1500]],'target_landmarks':[[768,500],[768,644]]}
(ROOT/'alignment.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
