"""Package selected direction drawings only; this contains no runtime model."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];STAGE=ROOT/'rebuild_v3_4/turn_redraw/corner_redraw';OUT=ROOT/'releases/materials-v0.3.4'
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
 OUT.mkdir(parents=True,exist_ok=True);selection=json.loads((STAGE/'selection.json').read_text());files={};manifest={}
 for key,record in selection['selected'].items():
  data=(ROOT/record['file']).read_bytes();assert sha(data)==record['sha256'];name='references/'+key+'.png';files[name]=data
  manifest[key]={'file':name,'source_file':record['file'],'sha256':sha(data),'review':record['review']}
 assert len(manifest)==9
 for name in ['nine-direction-review.jpg','corner-face-detail.jpg','corner-revision-comparison.jpg']:files['preview/'+name]=(STAGE/'qa'/name).read_bytes()
 files['README.md']=('''# 瑠璃乃九方向绘画参考 v0.3.4（未绑定）

先打开 preview/nine-direction-review.jpg。references/ 中是 9 张 2048×2048 选用原图：front 正面、left/right 朝画面左/右、up/down 抬头/低头，left-up/right-up/left-down/right-down 为组合方向。

这是便于查看的小包，不含 PSD、cmo3、moc3 或运行程序；不要把整图切换当作连续 Live2D。头部尺度和颈根仍待配准，完整拆层、隐藏结构补绘及 Cubism 组合参数绑定尚未完成。

SOURCE_MANIFEST.json 记录小包文件与完整源码包的来源路径、SHA256、静态审阅意见。详细制作说明保留在 STAGE_NOTES.md，其路径是指完整源码包。原始生成候选、提示词、任务、资源回执、先前 PSD 和脚本均在较大的 Rurino_Head_Materials_v0.3.4_WORK_IN_PROGRESS.zip 内。
''').encode()
 files['STAGE_NOTES.md']=(STAGE/'STATUS.md').read_bytes();files['SOURCE_MANIFEST.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
 files['SHA256SUMS.txt']=(''.join(sha(data)+'  '+name+'\n' for name,data in sorted(files.items()))).encode()
 archive=OUT/'Rurino_Nine_Direction_References_v0.3.4.zip';prefix='Rurino_Nine_Direction_References_v0.3.4/'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for name,data in sorted(files.items()):z.writestr(prefix+name,data)
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for name,data in files.items():assert sha(z.read(prefix+name))==sha(data)
 checksum=sha(archive.read_bytes());(OUT/'DIRECTION_SHA256SUMS.txt').write_text(checksum+'  '+archive.name+'\n')
 record={'file':archive.name,'bytes':archive.stat().st_size,'sha256':checksum,'selected_drawings':9,'files':len(files),'runtime_model_included':False}
 (OUT/'direction-package.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
if __name__=='__main__':main()
