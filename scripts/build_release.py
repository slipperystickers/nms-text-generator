"""Deterministic offline build: allowlisted source/data/docs, no game assets."""
import ast
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED
from build_instructions import build_page

ROOT=Path(__file__).resolve().parents[1]
ADDON=ROOT/'nms_text_generator'
tree=ast.parse((ADDON/'__init__.py').read_text(encoding='utf-8'))
info=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='bl_info' for t in n.targets))
version='.'.join(map(str,info['version']))
out=ROOT/'dist';out.mkdir(exist_ok=True)
instructions=build_page(out/'NMScribe_Instructions.html',version)
launch_notes=out/f'NMScribe_{version}_Release_Notes.md'
launch_notes.write_bytes((ROOT/'RELEASE_NOTES.md').read_bytes())
files={p.relative_to(ROOT).as_posix():p for p in ADDON.rglob('*')
       if p.is_file() and '__pycache__' not in p.parts and p.name!='furiousfurby.png' and p.suffix in ('.py','.json','.png')}
for name in ('README.md','USER_GUIDE.md','NOTICE.md','LICENSE','CHANGELOG.md'):
    files['nms_text_generator/'+name]=ROOT/name
files['nms_text_generator/NMScribe_Instructions.html']=instructions
files['nms_text_generator/RELEASE_NOTES.md']=launch_notes
assert all(p.exists() for p in files.values())
assert len(files)==29,len(files)
archive=out/f'NMS_Text_Generator_{version}.zip'
with ZipFile(archive,'w',ZIP_DEFLATED,compresslevel=9) as z:
    for name,path in sorted(files.items()):
        data=path.read_bytes()
        if name.endswith('README.md'):
            data=data.replace(b'(nms_text_generator/previews/',b'(previews/')
        # Deterministic per-version mtimes also invalidate timestamp-based Python
        # caches on updates where a source file's size happens to stay the same.
        major,minor,patch=info['version']
        record=ZipInfo(name,(2026,1,1,major%24,minor%60,(patch%30)*2));record.compress_type=ZIP_DEFLATED
        record.external_attr=0o644<<16
        z.writestr(record,data)
with ZipFile(archive) as z:
    assert z.testzip() is None
    assert all(name.startswith('nms_text_generator/') for name in z.namelist())
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
(out/'SHA256SUMS.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in (archive,instructions,launch_notes)),encoding='utf-8')
print(json.dumps({'version':version,'zip':str(archive),'instructions':str(instructions),'release_notes':str(launch_notes),'files':len(files),'sha256':digest},indent=2))
