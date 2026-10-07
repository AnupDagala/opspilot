"""Create the sanitized source deliverable; exclude account/runtime credentials."""
from pathlib import Path
import zipfile
root=Path(__file__).resolve().parent.parent
out=root/'artifacts/dealerops-source.zip';out.parent.mkdir(exist_ok=True)
files=[]
for folder in ['worker','tests','scripts','python','n8n','docs','evidence']:
 for p in (root/folder).rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts or p.name=='index.js' or p.suffix=='.pyc':continue
  files.append(p)
files += [root/f for f in ['README.md','.gitignore','docker-compose.yml','package.json']]
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in sorted(files):
  info=zipfile.ZipInfo('dealerops/'+p.relative_to(root).as_posix(),date_time=(2026,10,7,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
  z.writestr(info,p.read_bytes())
print('Sanitized source archive: '+str(out))
