"""Offline review of the two user-supplied traces; writes only test_output."""
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
sys.path.insert(0,str(Path(__file__).parent))
from test_svg_icons import svg,icon_fit

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'test_output/heart_pirates'
OUT.mkdir(parents=True,exist_ok=True)
sheet=Image.new('RGB',(1800,1320),'#e5e7eb');draw=ImageDraw.Draw(sheet)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
records=[]
for row,name in enumerate(('icon_heart_pirates','icon_heart_pirates_outline')):
    source=(ROOT/'tests/fixtures'/f'{name}.svg').read_text()
    shapes,bounds,loops,info=icon_fit.read_outline(source)
    before=svg.rasterize(shapes,1024);after=svg.rasterize([(loops,'nonzero')],1024)
    record={'file':name,'cleanup':info,'recovery_iou':float((before&after).sum()/(before|after).sum()),'fits':[]}
    original=Image.open(OUT/f'{name}-original.png').convert('RGB')
    sheet.paste(original,(0,row*660+50))
    draw.text((20,row*660+15),'Original SVG / '+('filled' if row==0 else 'thin outline'),font=font,fill='black')
    for col,limit in enumerate((300,1000),1):
        result=icon_fit.fit_svg(source,50,limit)
        record['fits'].append({k:result[k] for k in ('part_count','coverage','excess','outline_tolerance')})
        preview=Image.fromarray((result['preview'][:,:,:3]*255).astype(np.uint8)).resize((600,600))
        sheet.paste(preview,(col*600,row*660+50))
        draw.text((col*600+20,row*660+15),f'{limit} panels / {result["coverage"]:.1%} sampled coverage',font=font,fill='black')
    # A convenience silhouette for existing releases, without expanded strokes.
    commands=[]
    for loop in loops:
        commands.append('M'+' L'.join(f'{x*1000:.5f},{y*1000:.5f}' for x,y in loop)+' Z')
    (OUT/f'{name}-clean.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000"><path fill="#020202" fill-rule="nonzero" d="'+' '.join(commands)+'"/></svg>')
    records.append(record)
    print(json.dumps(record),flush=True)
sheet.save(OUT/'comparison.png')
(OUT/'report.json').write_text(json.dumps(records,indent=2))
