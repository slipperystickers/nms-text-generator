"""Import a reviewed native glyph library; no game meshes or font files."""
import argparse,json,string
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('source',type=Path)
args=parser.parse_args()
data=json.loads(args.source.read_text())
assert set(data['glyphs'])==set(string.ascii_uppercase+string.digits)
assert sum(map(len,data['glyphs'].values()))==966
assert set(data['widths'].values())=={4.9}
assert all(p['ObjectID']=='^BUILDFLATPANEL' for rows in data['glyphs'].values() for p in rows)
data['name']='Vector'
data['max_parts_per_character']=max(map(len,data['glyphs'].values()))
# The slender I must not inherit the full-width cell's 2.13-unit side bearings.
for part in data['glyphs']['I']:
    part['Position'][0]-=(4.9-.64)/2
data['widths']['I']=.64
dest=Path(__file__).resolve().parents[1]/'nms_text_generator/fonts/vector.json'
dest.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
print('VECTOR_IMPORTED',dest)
