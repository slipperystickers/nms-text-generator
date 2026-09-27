"""Offline SVG silhouette reader. No scripts, URLs, fonts, or external resources.

Paths (including curves/arcs), primitive shapes, group transforms, internal use,
inline presentation styles, fill rules and plain strokes are supported. Features
whose visible result cannot be reproduced are rejected rather than guessed.
"""
import math
import re
import xml.etree.ElementTree as ET
import numpy as np

MAX_BYTES=1_000_000
NUMBER=r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'
TOKEN=re.compile(r'[MmLlHhVvCcSsQqTtAaZz]|'+NUMBER)

def nums(value):return [float(x) for x in re.findall(NUMBER,value)]
def tag(e):return e.tag.rsplit('}',1)[-1]

def transform(value):
    result=np.eye(3)
    for name,arg in re.findall(r'(\w+)\s*\(([^)]*)\)',value or ''):
        p=nums(arg);m=np.eye(3)
        if name=='matrix' and len(p)==6:m=np.array([[p[0],p[2],p[4]],[p[1],p[3],p[5]],[0,0,1.]])
        elif name=='translate' and len(p) in (1,2):m[:2,2]=[p[0],p[1] if len(p)>1 else 0]
        elif name=='scale' and len(p) in (1,2):m[0,0]=p[0];m[1,1]=p[-1]
        elif name=='rotate' and len(p) in (1,3):
            a=math.radians(p[0]);c,s=math.cos(a),math.sin(a);m[:2,:2]=[[c,-s],[s,c]]
            if len(p)==3:m[:2,2]=np.array(p[1:])-m[:2,:2]@np.array(p[1:])
        elif name in ('skewX','skewY') and len(p)==1:m[0 if name=='skewX' else 1,1 if name=='skewX' else 0]=math.tan(math.radians(p[0]))
        else:raise ValueError('Unsupported SVG transform: '+name)
        result=result@m
    if value and re.sub(r'\w+\s*\([^)]*\)|[\s,]','',value):raise ValueError('Invalid SVG transform.')
    if not np.isfinite(result).all():raise ValueError('Non-finite SVG transform.')
    return result

def arc(start,rx,ry,angle,large,sweep,end):
    rx,ry=abs(rx),abs(ry)
    if min(rx,ry)<1e-10 or np.linalg.norm(end-start)<1e-10:return [end]
    a=math.radians(angle);c,s=math.cos(a),math.sin(a);rot=np.array([[c,-s],[s,c]])
    x,y=rot.T@((start-end)/2);ratio=x*x/(rx*rx)+y*y/(ry*ry)
    if ratio>1:rx*=math.sqrt(ratio);ry*=math.sqrt(ratio)
    f=math.sqrt(max(0,(rx*rx*ry*ry-rx*rx*y*y-ry*ry*x*x)/(rx*rx*y*y+ry*ry*x*x)))
    if bool(large)==bool(sweep):f=-f
    cp=np.array([f*rx*y/ry,-f*ry*x/rx]);center=rot@cp+(start+end)/2
    u=(np.array([x,y])-cp)/[rx,ry];v=(-np.array([x,y])-cp)/[rx,ry]
    begin=math.atan2(u[1],u[0]);delta=math.atan2(u[0]*v[1]-u[1]*v[0],u@v)
    if sweep and delta<0:delta+=2*math.pi
    if not sweep and delta>0:delta-=2*math.pi
    return [center+rot@np.array([rx*math.cos(begin+delta*t),ry*math.sin(begin+delta*t)]) for t in np.linspace(0,1,max(2,math.ceil(abs(delta)*16)+1))[1:]]

def paths(value):
    if re.sub(TOKEN,'',value).strip(' ,\t\r\n'):raise ValueError('Invalid or unsupported SVG path command.')
    tokens=TOKEN.findall(value);i=0;cmd=None;current=np.zeros(2);start=current.copy();line=[];out=[];last='';control=None
    sizes={'M':2,'L':2,'H':1,'V':1,'C':6,'S':4,'Q':4,'T':2,'A':7}
    while i<len(tokens):
        if tokens[i].isalpha():cmd=tokens[i];i+=1
        if cmd is None:raise ValueError('SVG path has no command.')
        upper=cmd.upper();relative=cmd.islower()
        if upper=='Z':
            if line:out.append((line,True));line=[]
            current=start.copy();last='Z';control=None;cmd=None;continue
        count=sizes[upper]
        if i+count>len(tokens) or any(t.isalpha() for t in tokens[i:i+count]):raise ValueError('Incomplete SVG path command.')
        p=list(map(float,tokens[i:i+count]));i+=count
        if not all(math.isfinite(v) for v in p):raise ValueError('SVG coordinates are invalid.')
        def point(j):return np.array(p[j:j+2])+(current if relative else 0)
        if upper=='M':
            if line:out.append((line,False))
            current=point(0);start=current.copy();line=[current.copy()];cmd='l' if relative else 'L'
        else:
            if not line:line=[current.copy()]
            if upper=='L':end=point(0);line.append(end)
            elif upper=='H':end=np.array([p[0]+(current[0] if relative else 0),current[1]]);line.append(end)
            elif upper=='V':end=np.array([current[0],p[0]+(current[1] if relative else 0)]);line.append(end)
            elif upper in ('C','S'):
                c1=point(0) if upper=='C' else (2*current-control if last in ('C','S') else current)
                c2=point(2 if upper=='C' else 0);end=point(4 if upper=='C' else 2)
                line.extend([(1-t)**3*current+3*(1-t)**2*t*c1+3*(1-t)*t*t*c2+t**3*end for t in np.linspace(0,1,25)[1:]])
                control=c2
            elif upper in ('Q','T'):
                c1=point(0) if upper=='Q' else (2*current-control if last in ('Q','T') else current)
                end=point(2 if upper=='Q' else 0)
                line.extend([(1-t)**2*current+2*(1-t)*t*c1+t*t*end for t in np.linspace(0,1,25)[1:]])
                control=c1
            elif upper=='A':
                if p[3] not in (0,1) or p[4] not in (0,1):raise ValueError('Invalid SVG arc flags.')
                end=point(5);line.extend(arc(current,*p[:5],end))
            current=end.copy()
        last=upper
        if upper not in ('C','S','Q','T'):control=None
        if sum(len(a) for a,_ in out)+len(line)>40000:
            from .svg_outline import simplify_open, simplify_loop
            def compact(points,closed):
                arr=np.asarray(points,float)
                if not np.isfinite(arr).all():raise ValueError('SVG coordinates are invalid.')
                tolerance=float(np.ptp(arr,axis=0).max())*1e-6
                return list((simplify_loop if closed else simplify_open)(arr,tolerance))
            out=[(compact(a,closed),closed) for a,closed in out]
            line=compact(line,False) if line else []
            if sum(len(a) for a,_ in out)+len(line)>40000:
                raise ValueError('SVG still has too many fine details after automatic cleanup. Try exporting a simpler silhouette.')
    if line:out.append((line,False))
    return out

def length(e,key,default=0):
    value=str(e.get(key,default)).strip()
    if not re.fullmatch(NUMBER+r'(?:px)?',value):raise ValueError('Use SVG user units or px, not percentages/physical units for '+key+'.')
    return float(re.match(NUMBER,value)[0])

def painted(value):
    value=value.strip().lower()
    if value in ('none','transparent'):return False
    if value.startswith('rgba('):
        channels=nums(value)
        if len(channels)==4 and channels[-1]==0:return False
    if re.fullmatch(r'#[0-9a-f]{8}',value) and value[-2:]=='00':return False
    if re.fullmatch(r'#[0-9a-f]{4}',value) and value[-1]=='0':return False
    if value.startswith('url(') and not re.match(r'url\(\s*[\"\']?#',value):raise ValueError('External SVG paint resources are not supported.')
    return True

def circle(x,y,rx,ry):
    return [np.array([x+rx*math.cos(a),y+ry*math.sin(a)]) for a in np.linspace(0,2*math.pi,97)[:-1]]

def geometry(e):
    kind=tag(e)
    if kind=='path':return paths(e.get('d',''))
    if kind in ('polygon','polyline'):
        p=nums(e.get('points',''))
        if len(p)%2:raise ValueError('Invalid SVG point list.')
        return [(list(np.array(p).reshape(-1,2)),kind=='polygon')]
    if kind=='line':return [([np.array([length(e,'x1'),length(e,'y1')]),np.array([length(e,'x2'),length(e,'y2')])],False)]
    if kind in ('circle','ellipse'):
        rx=length(e,'r') if kind=='circle' else length(e,'rx');ry=rx if kind=='circle' else length(e,'ry')
        return [(circle(length(e,'cx'),length(e,'cy'),rx,ry),True)] if min(rx,ry)>0 else []
    if kind=='rect':
        x,y,w,h=[length(e,k) for k in ('x','y','width','height')]
        if min(w,h)<=0:return []
        rx=min(w/2,max(0,length(e,'rx',e.get('ry',0))));ry=min(h/2,max(0,length(e,'ry',e.get('rx',0))))
        if not rx or not ry:return [([np.array(p) for p in [(x,y),(x+w,y),(x+w,y+h),(x,y+h)]],True)]
        line=[]
        for cx,cy,a in [(x+w-rx,y+ry,-90),(x+w-rx,y+h-ry,0),(x+rx,y+h-ry,90),(x+rx,y+ry,180)]:
            line.extend(np.array([cx+rx*math.cos(b),cy+ry*math.sin(b)]) for b in np.linspace(math.radians(a),math.radians(a+90),13))
        return [(line,True)]
    raise ValueError('Unsupported SVG element: '+kind+'. Convert it to plain paths first.')

def read_svg(source, *, cleanup=True):
    if len(source.encode('utf-8'))>MAX_BYTES:raise ValueError('SVG is larger than 1 MB. Simplify it before import.')
    # Illustrator's external SVG 1.1 DTD is only a format declaration. Discard
    # it locally; never resolve its URL. Custom/internal entities stay forbidden.
    if '<!ENTITY' in source.upper():raise ValueError('SVG entity declarations are not supported.')
    declaration=re.compile(r'<!DOCTYPE\s+svg\s*(?:(?:PUBLIC\s+([\"\'])[^\"\']*\1\s+([\"\'])[^\"\']*\2)|(?:SYSTEM\s+([\"\'])[^\"\']*\3))?\s*>',re.I)
    source=declaration.sub('',source)
    if '<!DOCTYPE' in source.upper():raise ValueError('SVG internal DTD subsets are not supported.')
    try:root=ET.fromstring(source)
    except ET.ParseError as exc:raise ValueError('Invalid SVG: '+str(exc)) from exc
    if tag(root)!='svg':raise ValueError('The file does not contain an SVG document.')
    elements=list(root.iter())
    if len(elements)>4096:raise ValueError('SVG has more than 4096 elements. Simplify it first.')
    if any(tag(e)=='style' and (e.text or '').strip() for e in elements):raise ValueError('SVG stylesheets are not supported. Export with inline styles or presentation attributes.')
    ids={e.get('id'):e for e in elements if e.get('id')};shapes=[];visits=0;points_used=0
    def add(contours,rule,matrix):
        nonlocal points_used
        cs=[]
        for contour in contours:
            if len(contour)<3:continue
            arr=np.asarray(contour,float);arr=(matrix@np.column_stack((arr,np.ones(len(arr)))).T).T[:,:2]
            if not np.isfinite(arr).all() or abs(arr).max()>1e9:raise ValueError('SVG coordinates are invalid or too large.')
            cs.append(arr);points_used+=len(arr)
        if points_used>100000:raise ValueError('SVG is too complex; simplify paths first.')
        if cs:shapes.append((cs,rule))
    def visit(e,matrix,style,depth=0):
        nonlocal visits
        visits+=1
        if visits>8192 or depth>32:raise ValueError('SVG nesting/use references are too complex or recursive.')
        kind=tag(e);style=dict(style)
        # Opacity multiplies through groups. Fill/stroke opacity are inherited.
        inherited_opacity=float(style.pop('_opacity',1))
        for k in ('fill','fill-rule','fill-opacity','stroke','stroke-width','stroke-opacity','stroke-linecap','stroke-linejoin','stroke-miterlimit','display','visibility','opacity','clip-path','mask','filter','stroke-dasharray','vector-effect'):
            if k in e.attrib:style[k]=e.get(k)
        style.update(dict((a.strip(),b.strip()) for a,b in (part.split(':',1) for part in e.get('style','').split(';') if ':' in part)))
        opacity=inherited_opacity*float(style.pop('opacity',1));style['_opacity']=opacity
        if style.get('display')=='none' or style.get('visibility') in ('hidden','collapse') or opacity<=0:return
        if any(style.get(k,'none')!='none' for k in ('clip-path','mask','filter','stroke-dasharray','vector-effect')):
            raise ValueError('Clipping, masks, filters, dashed/non-scaling strokes need to be expanded to plain paths first.')
        matrix=matrix@transform(e.get('transform',''))
        if kind in ('defs','title','desc','metadata','linearGradient','radialGradient','namedview'):return
        if kind in ('svg','g','a','symbol'):
            if kind=='svg' and e is not root:raise ValueError('Nested SVG viewports must be flattened before import.')
            for child in e:visit(child,matrix,style,depth+1)
            return
        if kind=='use':
            ref=e.get('href',e.get('{http://www.w3.org/1999/xlink}href',''))
            if not ref.startswith('#') or ref[1:] not in ids:raise ValueError('Only internal SVG use references are supported.')
            target=ids[ref[1:]]
            if tag(target)=='symbol' and target.get('viewBox'):raise ValueError('Expand symbol instances to plain paths first.')
            visit(target,matrix@transform(f'translate({length(e,"x")} {length(e,"y")})'),style,depth+1);return
        if kind in ('text','image','foreignObject','script'):
            raise ValueError('SVG '+kind+' is not supported. Convert text/strokes to paths; bitmap images cannot be fitted.')
        lines=geometry(e)
        if cleanup and lines:
            # Remove exporter oversampling before expanding the stroke. Work in
            # transformed coordinates so non-uniform SVG transforms do not
            # magnify the cleanup error. Retain local coordinates for stroking.
            from .svg_outline import simplify_open, simplify_loop
            reduced=[]
            for line,closed in lines:
                arr=np.asarray(line,float)
                if not np.isfinite(arr).all():raise ValueError('SVG coordinates are invalid.')
                if len(arr)<4:
                    reduced.append((line,closed));continue
                projected=(matrix[:2,:2]@arr.T).T
                if not np.isfinite(projected).all():raise ValueError('SVG coordinates are invalid.')
                tolerance=float(np.ptp(projected,axis=0).max())*1e-5
                # Simplification selects existing points; recover their local
                # coordinates without inverting possibly singular transforms.
                chosen=(simplify_loop if closed else simplify_open)(projected,tolerance)
                indices={tuple(p):i for i,p in enumerate(projected)}
                reduced.append(([arr[indices[tuple(p)]] for p in chosen],closed))
            lines=reduced
        if painted(style.get('fill','black')) and float(style.get('fill-opacity',1))>0 and kind!='line':
            rule=style.get('fill-rule','nonzero')
            if rule not in ('nonzero','evenodd'):raise ValueError('Unsupported SVG fill rule.')
            add([line for line,_ in lines],rule,matrix)
        if painted(style.get('stroke','none')) and float(style.get('stroke-opacity',1))>0:
            sw=style.get('stroke-width','1')
            if not re.fullmatch(NUMBER+r'(?:px)?',sw):raise ValueError('Stroke widths must use SVG user units or px.')
            half=float(re.match(NUMBER,sw)[0])/2
            if half<=0:return
            cap=style.get('stroke-linecap','butt');join=style.get('stroke-linejoin','miter')
            if cap not in ('butt','square','round') or join not in ('miter','bevel','round'):raise ValueError('Unsupported stroke join/cap.')
            stroke_contours=[];stroke_points=0
            def stroke_add(contour):
                nonlocal stroke_points
                arr=np.asarray(contour,float)
                signed=np.sum(arr[:,0]*np.roll(arr[:,1],-1)-arr[:,1]*np.roll(arr[:,0],-1))
                if abs(signed)>1e-18:
                    stroke_points+=len(arr)
                    if points_used+stroke_points>100000:
                        raise ValueError('SVG still has too many stroke details after automatic cleanup. Try exporting a simpler silhouette.')
                    stroke_contours.append(arr if signed>0 else arr[::-1])
            for line,closed in lines:
                clean=[]
                for p in line:
                    if not clean or np.linalg.norm(p-clean[-1])>1e-10:clean.append(np.array(p))
                if len(clean)<2:continue
                if closed and np.linalg.norm(clean[-1]-clean[0])>1e-10:clean.append(clean[0])
                segs=[]
                for a,b in zip(clean,clean[1:]):
                    u=(b-a)/np.linalg.norm(b-a);n=np.array([-u[1],u[0]])*half;segs.append((a,b,u,n))
                    stroke_add([a+n,b+n,b-n,a-n])
                pairs=list(zip(segs,segs[1:]))
                if closed:pairs.append((segs[-1],segs[0]))
                for first,second in pairs:
                    a,b,u,n=first;_,_,v,m=second
                    if join=='round':stroke_add(circle(*b,half,half));continue
                    for sign in (-1,1):
                        p=b+n*sign;q=b+m*sign;corner=[b,p,q]
                        det=u[0]*v[1]-u[1]*v[0]
                        if join=='miter' and abs(det)>1e-8:
                            d=q-p;k=(d[0]*v[1]-d[1]*v[0])/det;tip=p+u*k
                            if np.linalg.norm(tip-b)<=half*float(style.get('stroke-miterlimit',4)):corner=[b,p,tip,q]
                        stroke_add(corner)
                if not closed:
                    for a,_,u,n in (segs[0],(segs[-1][1],None,-segs[-1][2],segs[-1][3])):
                        if cap=='round':stroke_add(circle(*a,half,half))
                        elif cap=='square':stroke_add([a+n,a-n,a-u*half-n,a-u*half+n])
            # Consistent winding combines all stroke patches as one union;
            # overlapping patches cannot cancel each other or punch out holes.
            add(stroke_contours,'nonzero',matrix)
    visit(root,np.eye(3),{})
    if not shapes:raise ValueError('SVG has no visible filled shapes or strokes.')
    allp=np.concatenate([c for contours,_ in shapes for c in contours]);low=allp.min(0);high=allp.max(0)
    span=high-low
    if min(span)<=1e-9:raise ValueError('SVG silhouette has no area.')
    # Normalized geometry, tightly cropped to artwork, independent of page units.
    shapes=[([(c-low)/max(span) for c in cs],rule) for cs,rule in shapes]
    return shapes,(span/max(span)).tolist()

def rasterize(shapes,size):
    """Pixel-centre scan conversion, holes obey each element's fill rule."""
    mask=np.zeros((size,size),bool)
    for contours,rule in shapes:
        points=np.concatenate(contours)
        low=np.maximum(0,np.ceil(points.min(0)*size-.5).astype(int))
        high=np.minimum(size,np.ceil(points.max(0)*size-.5).astype(int))
        x0,y0=low;x1,y1=high
        if x1<=x0 or y1<=y0:continue
        winding=np.zeros((y1-y0,x1-x0),np.int32)
        xs=(np.arange(x0,x1)+.5)/size
        for contour in contours:
            for p,q in zip(contour,np.roll(contour,-1,axis=0)):
                if abs(p[1]-q[1])<1e-14:continue
                lo=max(y0,int(math.ceil(min(p[1],q[1])*size-.5)));hi=min(y1,int(math.ceil(max(p[1],q[1])*size-.5)))
                if lo>=hi:continue
                ys=(np.arange(lo,hi)+.5)/size
                crossing=p[0]+(ys-p[1])*(q[0]-p[0])/(q[1]-p[1])
                winding[lo-y0:hi-y0]+=(xs[None,:]<crossing[:,None])*(1 if q[1]>p[1] else -1)
        mask[y0:y1,x0:x1]|=(winding%2!=0) if rule=='evenodd' else (winding!=0)
    return mask
