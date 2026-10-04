import sys,time
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import nms_text_generator as a
a.register()
jobs=a.preview_jobs.Jobs()
j=jobs.start('native',1,{'kind':'icon','args':['<svg><rect width="20" height="10" fill="red"/></svg>',50,30,True,False,'{}']})
deadline=time.monotonic()+30
while not j.poll():
 assert time.monotonic()<deadline
 time.sleep(.02)
r=j.result();assert r['coverage']>.99 and r['part_count']<=30
print('BUNDLED_PYTHON_PREVIEW_PASSED',bpy.app.version_string,a.preview_jobs.python_binary(),flush=True)
jobs.close();a.unregister()
