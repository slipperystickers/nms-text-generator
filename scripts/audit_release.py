"""Audit the exact launch artifacts, not just the development checkout."""
import ast
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1];out=ROOT/'dist'
source_module=ast.parse((ROOT/'nms_text_generator/__init__.py').read_text(encoding='utf-8'))
source_info=next(ast.literal_eval(n.value) for n in source_module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='bl_info' for t in n.targets))
version='.'.join(map(str,source_info['version']))
archive=out/f'NMS_Text_Generator_{version}.zip'
with ZipFile(archive) as z:
    assert z.testzip() is None
    names=z.namelist();assert len(names)==len(set(names))==36
    for name in names:
        path=Path(name)
        assert path.parts[0]=='nms_text_generator' and '..' not in path.parts and not path.is_absolute()
        assert path.suffix.lower() not in ('.blend','.fbx','.obj','.ttf','.otf','.pyc','.svg')
        assert not any(part in ('test_output','tests','design','__pycache__') for part in path.parts)
        data=z.read(name)
        if path.suffix=='.py':compile(data,name,'exec')
        if path.suffix in ('.py','.md','.html','.json'):
            assert b'C:\\Users\\kengo' not in data and b'C:/Users/kengo' not in data
    module=ast.parse(z.read('nms_text_generator/__init__.py'))
    info=next(ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='bl_info' for t in n.targets))
    assert info['version']==source_info['version']
    palette=json.loads(z.read('nms_text_generator/color_catalog.json'))
    assert len(palette['palettes'])==151
    assert [p['id'] for p in palette['palettes'][115:]]==[f'STATION{i}' for i in range(36)]
    assert z.read('nms_text_generator/NMScribe_Instructions.html')==(out/'NMScribe_Instructions.html').read_bytes()
    assert z.read('nms_text_generator/USER_GUIDE.md')==(ROOT/'USER_GUIDE.md').read_bytes()
    assert z.read('nms_text_generator/RELEASE_NOTES.md')==(ROOT/'RELEASE_NOTES.md').read_bytes()
for line in (out/'SHA256SUMS.txt').read_text().splitlines():
    digest,name=line.split('  ',1)
    assert hashlib.sha256((out/name).read_bytes()).hexdigest()==digest
print(json.dumps({'status':'LAUNCH_ARTIFACT_AUDIT_PASSED','version':version,'files':len(names),'zip_bytes':archive.stat().st_size},indent=2))
