"""Import the verified coplanar library and corrected C; no game assets."""
import argparse, json, string
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('optimized',type=Path)
parser.add_argument('corrected_c',type=Path)
args=parser.parse_args()
data=json.loads(args.optimized.read_text())
correction=json.loads(args.corrected_c.read_text())
assert set(data['glyphs'])==set(string.ascii_uppercase+string.digits)
assert sum(map(len,data['glyphs'].values()))==616
assert data['widths']['I']==.64
assert len(correction['glyphs']['C'])==23
data['glyphs']['C']=correction['glyphs']['C']
data['name']='Vector'
data['revision']=4
data['max_parts_per_character']=max(map(len,data['glyphs'].values()))
assert sum(map(len,data['glyphs'].values()))==626
assert sum(len(data['glyphs'][c]) for c in 'TYNDUSTRIALASTRONAUTICS')==367
assert all(r['ObjectID']=='^BUILDFLATPANEL' for rows in data['glyphs'].values() for r in rows)
dest=Path(__file__).resolve().parents[1]/'nms_text_generator/fonts/vector.json'
dest.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
print('OPTIMIZED_VECTOR_IMPORTED',dest,flush=True)
