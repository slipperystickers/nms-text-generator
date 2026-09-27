"""Author thirteen punctuation glyphs using unmodified, uniformly scaled native panels.

Run in a separate factory-startup background Blender. This never edits the
approved alphanumeric recipes or the installed Base Builder/Forge packages.
"""
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from native_bootstrap import enable_dependencies
assert bpy.app.background
enable_dependencies()
import nms_text_generator as addon


def path(points,t):
    """Extend strips to their calculated outer corner intersections."""
    units=[]
    for a,b in zip(points,points[1:]):
        length=math.dist(a,b)
        units.append(((b[0]-a[0])/length,(b[1]-a[1])/length))
    extensions=[0.]
    for u,v in zip(units,units[1:]):
        dot=max(-1.,min(1.,sum(x*y for x,y in zip(u,v))))
        assert dot>-.95
        extensions.append(t/2*math.sqrt((1-dot)/(1+dot)))
    extensions.append(0.)
    return [(a[0]-u[0]*extensions[i],a[1]-u[1]*extensions[i],
             b[0]+u[0]*extensions[i+1],b[1]+u[1]*extensions[i+1],t)
            for i,(a,b,u) in enumerate(zip(points,points[1:],units))]


def recipes(key):
    # Match the existing stroke weights. Forge's horizontal slabs are thinner.
    t={'FUTURE_Z':1.,'INDUSTRIAL':.7,'ORBITAL':.62,'FOUNDRY':.68,'VECTOR':.64}[key]
    w={'FUTURE_Z':5.4,'INDUSTRIAL':3.,'ORBITAL':3.65,'FOUNDRY':3.65,'VECTOR':4.2}[key]
    h=.46 if key=='FOUNDRY' else t
    def horizontal(y,a,b,th=h):return (a,y,b,y,th)
    def vertical(x,a,b,th=t):return (x,a,x,b,th)
    # Framing punctuation overshoots cap/baseline by 6% on each side.
    # Change strip lengths, not native mesh proportions or stroke weight.
    bottom,top=-.3,5.3
    span=top-bottom
    dash=w*.64
    data={'-':(dash,[horizontal(2.5,0,dash)]),
          '_':(w,[horizontal(h/2,0,w)]),
          '|':(t,[vertical(t/2,bottom,top)]),
          '+':(dash,[horizontal(2.5,0,dash),vertical(dash/2,2.5-dash/2,2.5+dash/2)]),
          '=':(dash,[horizontal(2.5-.9*h,0,dash),horizontal(2.5+.9*h,0,dash)]),
          ':':(t,[horizontal(1.25,0,t,t),horizontal(3.75,0,t,t)]),
          '.':(t,[horizontal(t/2,0,t,t)])}
    # Diagonals use full-width panels. Choose endpoints so the native corners
    # meet the taller framing bounds, with no kickdown or tilted mounting faces.
    dx=2.25 if key=='INDUSTRIAL' else 2.65
    angle=math.atan2(span,dx)
    for _ in range(12):angle=math.atan2(span-t*math.cos(angle),dx)
    ex=t/2*math.sin(angle);ey=t/2*math.cos(angle)
    slash=(ex,bottom+ey,ex+dx,top-ey,t)
    sw=dx+2*ex
    data['/']=(sw,[slash])
    data['\\']=(sw,[(sw-slash[0],slash[1],sw-slash[2],slash[3],t)])
    bw=1.8 if key!='FUTURE_Z' else 2.4
    bracket=[vertical(t/2,bottom,top),horizontal(top-h/2,0,bw),horizontal(bottom+h/2,0,bw)]
    data['[']=(bw,bracket)
    data[']']=(bw,[(bw-a,b,bw-c,d,e) for a,b,c,d,e in bracket])
    ew=1.65 if key=='FOUNDRY' else t
    bang=[vertical(ew/2,1.55*t,5),horizontal(t/2,ew/2-t/2,ew/2+t/2,t)]
    if key=='FOUNDRY':bang.append(horizontal(5-h/2,0,ew))
    data['!']=(ew,bang)
    l,r=t/2,w-t/2
    mid=w/2
    dot=horizontal(t/2,mid-t/2,mid+t/2,t)
    if key=='INDUSTRIAL':
        hook=[vertical(l,3.75,5),horizontal(5-t/2,0,w,t),
              vertical(r,2.5,5),horizontal(2.5,l+t/2,w,t),vertical(mid,1.55*t,2.5+t/2)]
        # Middle horizontal starts at the center stem, not a leftward overhang.
        hook[3]=horizontal(2.5,mid-t/2,w,t)
    elif key=='FOUNDRY':
        hook=[vertical(l,3.85,5),horizontal(5-h/2,0,w),vertical(r,2.5,5),
              horizontal(2.5,mid-t/2,w),vertical(mid,1.55*t,2.5+h/2),
              horizontal(3.85,0,1.2)]
    else:
        cut=.52 if key!='FUTURE_Z' else .66
        start=3.25 if key=='FUTURE_Z' else 3.8
        hook=path([(l,start),(l,5-t/2-cut),(l+cut,5-t/2),
                   (r-cut,5-t/2),(r,5-t/2-cut),(r,3.05),
                   (r-cut,2.5),(mid,2.5),(mid,1.55*t)],t)
    data['?']=(w,hook+[dot])
    return data


builder=addon.get_builder()
probe=builder.add_part('BUILDFLATPANEL',high_res=True,build_rigs=False)
obj=probe.object
local=[Vector(v) for v in obj.bound_box]
length=max(v.x for v in local)-min(v.x for v in local)
width=max(v.z for v in local)-min(v.z for v in local)
center=Vector(((min(v.x for v in local)+max(v.x for v in local))/2,0,
               (min(v.z for v in local)+max(v.z for v in local))/2))
assert abs(length-addon.panels.FLAT_FOOTPRINT[0])<.01
assert abs(width-addon.panels.FLAT_FOOTPRINT[1])<.01
ratio=length/width


def tile(strokes):
    records=[]
    for x1,y1,x2,y2,t in strokes:
        distance=math.hypot(x2-x1,y2-y1)
        ux,uy=(x2-x1)/distance,(y2-y1)/distance
        pl=min(ratio*t,distance);pw=pl/ratio
        overlap=min(.08,t*.15,pw*.2,pl*.2)
        nx=max(1,math.ceil((distance-overlap)/(pl-overlap)-1e-7))
        ny=max(1,math.ceil((t-overlap)/(pw-overlap)-1e-7))
        for ix in range(nx):
            along=0 if nx==1 else -(distance-pl)/2+ix*(distance-pl)/(nx-1)
            for iy in range(ny):
                across=0 if ny==1 else -(t-pw)/2+iy*(t-pw)/(ny-1)
                s=pl/length
                rotation=Matrix.Rotation(math.atan2(uy,ux),4,'Z')@Matrix.Rotation(math.pi/2,4,'X')
                position=Vector(((x1+x2)/2+ux*along-uy*across,
                                 (y1+y2)/2+uy*along+ux*across,.02+.000025*len(records)))
                position-=rotation.to_3x3()@(center*s)
                position.z-=addon.panels.FLAT_FACE_Y*s
                obj.matrix_world=Matrix.Translation(position)@rotation@Matrix.Scale(s,4)
                bpy.context.view_layer.update()
                record=probe.serialise()
                record.pop('Timestamp',None)
                records.append(record)
    return records


report={}
for key,name,file in addon.layout.FONTS:
    dest=ROOT/'nms_text_generator'/file
    data=json.loads(dest.read_text(encoding='utf-8'))
    original={c:data['glyphs'][c] for c in addon.layout.CHARACTERS[:36]}
    report[name]={}
    for char,(advance,strokes) in recipes(key).items():
        data['glyphs'][char]=tile(strokes)
        data['widths'][char]=advance
        report[name][char]=len(data['glyphs'][char])
    data['max_parts_per_character']=max(map(len,data['glyphs'].values()))
    assert original=={c:data['glyphs'][c] for c in original}
    dest.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8',newline='\n')
addon.layout.library.cache_clear()
for key,_,_ in addon.layout.FONTS:assert len(addon.layout.library(key)['glyphs'])==49
print('SYMBOL_BUILD_PASSED '+json.dumps(report),flush=True)
