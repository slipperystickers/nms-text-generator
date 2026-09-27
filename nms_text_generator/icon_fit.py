"""Contour-first fitting of unmodified, fixed-aspect native panel faces.

Vector edges, not raster cells, determine the visible perimeter. Arbitrarily
rotated panels trace that perimeter before a greedy interior fill. Every fill
panel is checked against the vector boundary, including holes. NumPy only.
"""
import math
from functools import lru_cache
import numpy as np
from . import svg_geometry
from . import svg_outline
from .svg_outline import simplify_open, simplify_loop

RATIO=3.0078125/1.260742425918579


class SimplificationRequired(ValueError):
    """Import preflight stops here until the user chooses Simplify & Import."""


def cross(a,b):return a[...,0]*b[...,1]-a[...,1]*b[...,0]
def integral(a):return np.pad(np.cumsum(np.cumsum(a,axis=0),axis=1),((1,0),(1,0)))
def sums(ii,h,w):return ii[h:,w:]-ii[:-h,w:]-ii[h:,:-w]+ii[:-h,:-w]


def contains(shapes,points):
    """Point-in-visible-union; element fill rules are applied before union."""
    points=np.asarray(points).reshape(-1,2);result=np.zeros(len(points),bool)
    for contours,rule in shapes:
        a=np.concatenate(contours);b=np.concatenate([np.roll(c,-1,axis=0) for c in contours])
        low=a.min(0);high=a.max(0)
        ids=np.flatnonzero(~result & np.all((points>=low)&(points<=high),axis=1))
        nonhorizontal=abs(b[:,1]-a[:,1])>1e-14;a=a[nonhorizontal];b=b[nonhorizontal]
        for start in range(0,len(ids),256):
            idx=ids[start:start+256];p=points[idx]
            up=(a[:,1,None]<=p[None,:,1])&(b[:,1,None]>p[None,:,1])
            down=(b[:,1,None]<=p[None,:,1])&(a[:,1,None]>p[None,:,1])
            x=a[:,0,None]+(p[None,:,1]-a[:,1,None])*(b[:,0]-a[:,0])[:,None]/(b[:,1]-a[:,1])[:,None]
            winding=((up.astype(np.int8)-down)*(p[None,:,0]<x)).sum(axis=0)
            result[idx]=(winding%2!=0) if rule=='evenodd' else (winding!=0)
    return result


def visible_loops(shapes):
    """Split vector intersections; discard edges internal to overlapping fills.

    Directed edges keep material on the left, including clockwise hole rings.
    This removes hidden seams in expanded strokes and overlapping SVG elements.
    """
    cs=[c for contours,_ in shapes for c in contours]
    a=np.concatenate(cs);b=np.concatenate([np.roll(c,-1,axis=0) for c in cs])
    good=np.linalg.norm(b-a,axis=1)>1e-10;a=a[good];b=b[good];d=b-a
    if len(a)>12000:raise ValueError('SVG has too many outline segments. Simplify paths before fitting.')
    lo=np.minimum(a,b);hi=np.maximum(a,b);pieces=[]
    for i,(p,q) in enumerate(zip(a,b)):
        ids=np.flatnonzero(np.all((lo<=hi[i]+1e-10)&(hi>=lo[i]-1e-10),axis=1))
        v=d[ids];delta=a[ids]-p;den=cross(d[i],v)
        ok=abs(den)>1e-12;v=v[ok];delta=delta[ok];den=den[ok]
        t=cross(delta,v)/den;u=cross(delta,d[i])/den
        ts=np.unique(np.round(np.r_[0,t[(t>1e-9)&(t<1-1e-9)&(u>=-1e-9)&(u<=1+1e-9)],1],10))
        pieces.extend((p+d[i]*t0,p+d[i]*t1) for t0,t1 in zip(ts,ts[1:]))
        if len(pieces)>30000:raise ValueError('Too many intersecting SVG edges. Simplify the artwork first.')
    a=np.array([p for p,q in pieces]);b=np.array([q for p,q in pieces]);d=b-a
    normal=np.column_stack((-d[:,1],d[:,0]));normal/=np.linalg.norm(normal,axis=1)[:,None]
    mid=(a+b)/2
    left=contains(shapes,mid+normal*1e-7);right=contains(shapes,mid-normal*1e-7)
    edges={}
    def key(p):return tuple(np.round(p,8))
    for p,q,l,r in zip(a,b,left,right):
        if l==r:continue
        if r:p,q=q,p
        kp,kq=key(p),key(q)
        if kp!=kq:edges[kp,kq]=(p,q)
    outgoing={}
    for kp,kq in edges:outgoing.setdefault(kp,[]).append(kq)
    unused=set(edges);loops=[]
    while unused:
        first=min(unused);kp,kq=first;points=[]
        while (kp,kq) in unused:
            p,q=edges[kp,kq];points.append(p);unused.remove((kp,kq))
            if kq==first[0]:break
            choices=[end for end in outgoing.get(kq,[]) if (kq,end) in unused]
            if not choices:break
            direction=q-p
            def turn(end):
                v=edges[kq,end][1]-q
                return math.atan2(cross(direction,v),direction@v)
            kp,kq=kq,max(choices,key=turn)
        if kq==first[0] and len(points)>=3:loops.append(np.array(points))
        else:raise ValueError('SVG outline is not closed after combining shapes. Union/clean the paths and retry.')
    if not loops:raise ValueError('SVG has no visible outline.')
    return loops


def prepare_outline(shapes,allow_simplify=True):
    """Clean before the expensive union; recover dense/fragile unions locally."""
    original=sum(len(c) for cs,_ in shapes for c in cs)
    cleaned=[([simplify_loop(c,1e-6) for c in cs],rule) for cs,rule in shapes]
    count=sum(len(c) for cs,_ in cleaned for c in cs)
    info={'input_segments':original,'cleaned_segments':count,
          'outline_recovered':False,'recovery_resolution':0}
    # Intersection testing is quadratic. Many tiny stroke patches are cheaper
    # and more reliable to combine with bounded scan conversion.
    if count<=4000 and len(cleaned)<=256:
        try:
            return visible_loops(cleaned),info
        except ValueError:
            pass
    if not allow_simplify:
        raise SimplificationRequired('This SVG has a very detailed outline. Choose Simplify & Import to continue.')
    loops,recovery=svg_outline.recover(shapes)
    info.update(recovery)
    return loops,info


@lru_cache(maxsize=2)
def read_source(source):
    return svg_geometry.read_svg(source)


@lru_cache(maxsize=4)
def read_outline(source,allow_simplify=True):
    """Reuse source cleanup while the user adjusts accuracy and part budget."""
    shapes,bounds=read_source(source)
    loops,info=prepare_outline(shapes,allow_simplify=allow_simplify)
    return shapes,bounds,loops,info


class Boundary:
    def __init__(self,loops):
        self.loops=loops;self.shapes=[(loops,'nonzero')]
        self.a=np.concatenate(loops);self.b=np.concatenate([np.roll(c,-1,axis=0) for c in loops])
        self.low=np.minimum(self.a,self.b);self.high=np.maximum(self.a,self.b)

    def inside(self,panel):
        """Segment/open-rectangle test, not a corner-only/sample test.

        A valid panel cannot contain or cross any boundary (including a tiny
        hole). Contact with the boundary is permitted within numeric tolerance.
        """
        x,y,w,angle=panel;c,s=math.cos(angle),math.sin(angle)
        half=np.array([w*RATIO/2,w/2]);extent=np.array([abs(c),abs(s)])*half[0]+np.array([abs(s),abs(c)])*half[1]
        centre=np.array([x,y]);ids=np.all((self.low<=centre+extent)&(self.high>=centre-extent),axis=1)
        rot=np.array([[c,-s],[s,c]])
        a=(self.a[ids]-centre)@rot;b=(self.b[ids]-centre)@rot;d=b-a
        inset=half-1e-9
        lower=np.zeros(len(a));upper=np.ones(len(a));possible=np.ones(len(a),bool)
        for axis in (0,1):
            moving=abs(d[:,axis])>1e-14;safe=np.where(moving,d[:,axis],1)
            t0=(-inset[axis]-a[:,axis])/safe;t1=(inset[axis]-a[:,axis])/safe
            lower=np.maximum(lower,np.where(moving,np.minimum(t0,t1),-np.inf))
            upper=np.minimum(upper,np.where(moving,np.maximum(t0,t1),np.inf))
            possible&=moving|(abs(a[:,axis])<inset[axis])
        if np.any(possible&(upper>lower+1e-10)):return False
        return bool(contains(self.shapes,[centre])[0])


def outline_panels(boundary,tolerance,limit):
    panels=[];omitted=0
    def edge(p,q,depth=0):
        nonlocal omitted
        v=q-p;length=float(np.linalg.norm(v))
        if length<1e-9:return
        normal=np.array([-v[1],v[0]])/length
        # On concave joins, extending an edge stays INSIDE the silhouette and
        # covers the neighbour's beveled end. The vector check forbids extension
        # through convex corners. No extra seam-covering parts are needed.
        for deep in (True,False):
            for before,after in ((.03,.03),(.03,0),(0,.03),(0,0)):
                start=p-v*before;end=q+v*after;span=length*(1+before+after)
                panel_depth=span*RATIO if deep else span/RATIO
                centre=(start+end)/2+normal*panel_depth/2
                panel=(*centre,span if deep else panel_depth,
                       math.atan2(normal[1],normal[0]) if deep else math.atan2(v[1],v[0]))
                if boundary.inside(panel):panels.append(panel);return
        if depth>=12 or length<tolerance*.6 or len(panels)>=limit:
            omitted+=1;return
        mid=(p+q)/2;edge(p,mid,depth+1);edge(mid,q,depth+1)
    for loop in boundary.loops:
        for p,q in zip(loop,np.roll(loop,-1,axis=0)):
            edge(p,q)
            if len(panels)>limit:return panels,omitted
    return panels,omitted


def panel_mask(panel,xx,yy,inset=False):
    x,y,w,angle=panel;c,s=math.cos(angle),math.sin(angle);dx=xx-x;dy=yy-y
    # Native Flat Panels have a beveled rim: the planar face is smaller than the
    # outer footprint. Cleanup uses a conservative inner face to force overlap.
    long_factor,short_factor=(.984,.967) if inset else (1,1)
    return (abs(c*dx+s*dy)<=w*RATIO/2*long_factor+1e-10)&(abs(-s*dx+c*dy)<=w/2*short_factor+1e-10)


def fill_interior(boundary,target,panels,n,limit):
    yy,xx=np.mgrid[:n,:n];xx=(xx+.5)/n;yy=(yy+.5)/n
    covered=np.zeros_like(target)
    for panel in panels:covered|=panel_mask(panel,xx,yy)
    remaining=target&~covered
    m=math.ceil(n*math.sqrt(2))+4;gy,gx=np.mgrid[:m,:m];gx=(gx+.5-m/2)/n;gy=(gy+.5-m/2)/n
    rotations=[]
    for angle in (0,math.pi/4,math.pi/2,3*math.pi/4):
        c,s=math.cos(angle),math.sin(angle)
        ix=np.floor((c*gx-s*gy+.5)*n).astype(int);iy=np.floor((s*gx+c*gy+.5)*n).astype(int)
        inside=(ix>=0)&(ix<n)&(iy>=0)&(iy<n);ix=np.clip(ix,0,n-1);iy=np.clip(iy,0,n-1)
        ii=integral((inside&target[iy,ix]).astype(np.int32));options=[]
        for h in (2,3,4,6,8,11,15,21,29,40,56,80,112,160,224):
            w=math.ceil(h*RATIO)
            if w>m:continue
            valid=sums(ii,h,w)==h*w
            if valid.any():options.append((h,w,valid))
        rotations.append((angle,ix,iy,inside,options))
    attempts=0
    while len(panels)<limit and remaining.any():
        best=None;score=0
        for angle,ix,iy,inside,options in rotations:
            ii=integral((inside&remaining[iy,ix]).astype(np.int32))
            for h,w,valid in options:
                gain=np.where(valid,sums(ii,h,w),0);idx=int(gain.argmax());value=int(gain.flat[idx])
                if value>score:
                    row,col=np.unravel_index(idx,gain.shape);score=value;best=(angle,h,w,row,col,valid)
        if best is None or score<1:break
        angle,h,w,row,col,valid=best;valid[row,col]=False;c,s=math.cos(angle),math.sin(angle)
        lx=(col+w/2-m/2)/n;ly=(row+h/2-m/2)/n
        panel=(c*lx-s*ly+.5,s*lx+c*ly+.5,h/n,angle)
        # A coarse raster only nominates candidates. The vector test is decisive.
        if not boundary.inside(panel):
            attempts+=1
            if attempts>96:break
            continue
        area=panel_mask(panel,xx,yy)
        if not (area&remaining).any():continue
        panels.append(panel);covered|=area;remaining&=~area
    return covered,remaining


def close_gaps(boundary,panels,size,limit,tolerance,edge_count):
    """Oversampled cleanup with off-grid overlapping panels.

    A raster is used only to find uncovered locations. Panel position/scale are
    continuous; the vector containment test still guards the entire rectangle.
    Choosing the deepest missing point first avoids a swarm of tiny filler parts.
    """
    target=svg_geometry.rasterize(boundary.shapes,size)
    yy,xx=np.mgrid[:size,:size];xx=(xx+.5)/size;yy=(yy+.5)/size
    covered=np.zeros_like(target)
    for i,panel in enumerate(panels):covered|=panel_mask(panel,xx,yy,inset=i>=edge_count)
    iy,ix=np.nonzero(target&~covered)
    points=np.column_stack((xx[iy,ix],yy[iy,ix]));dist=np.empty(len(points))
    d=boundary.b-boundary.a;dd=np.sum(d*d,axis=1)
    for start in range(0,len(points),256):
        delta=points[start:start+256,None,:]-boundary.a[None,:,:]
        t=np.clip(np.sum(delta*d,axis=2)/np.maximum(dd,1e-24),0,1)
        dist[start:start+256]=np.sqrt(np.sum((delta-t[:,:,None]*d)**2,axis=2).min(axis=1))
    # A minute rim at the contour is native bevel, not an interior hole. Filling
    # it would require panels outside the contour or an unbounded tiny-part tail.
    available=dist>min(tolerance*.5,.0005)
    while available.any() and len(panels)<limit:
        idx=int(np.argmax(np.where(available,dist,-1)));x,y=points[idx]
        if dist[idx]<1e-7:available[idx]=False;continue
        best=None;largest=0
        for angle in (0,math.pi/4,math.pi/2,3*math.pi/4):
            lo=dist[idx]*1.999/math.sqrt(1+RATIO*RATIO);hi=dist[idx]*2
            for _ in range(13):
                width=(lo+hi)/2
                if boundary.inside((x,y,width,angle)):lo=width
                else:hi=width
            if lo>largest:largest=lo;best=(x,y,lo,angle)
        panels.append(best)
        available&=~panel_mask(best,points[:,0],points[:,1],inset=True)
    return bool(available.any())


def fit_svg(source,accuracy=50,max_parts=300):
    accuracy=max(0,min(100,int(accuracy)));max_parts=max(1,min(2000,int(max_parts)))
    shapes,bounds,loops,cleanup=read_outline(source)
    tolerance=.004*(.15**(accuracy/100))
    # Keep budget available for filling. Relax an over-budget contour as a whole
    # instead of chopping random edges from the logo.
    relaxed=False
    for retry in range(7):
        boundary=Boundary([simplify_loop(loop,tolerance) for loop in loops])
        panels,omitted=outline_panels(boundary,tolerance,max_parts*2)
        if len(panels)<=max_parts*.8:break
        if retry<6:tolerance*=1.6;relaxed=True
    if len(panels)>max_parts:
        panels=sorted(panels,key=lambda p:p[2],reverse=True)[:max_parts];relaxed=True
    edge_count=len(panels)
    n=128+round(accuracy*1.28)
    target=svg_geometry.rasterize(boundary.shapes,n)
    reference=svg_geometry.rasterize(shapes,n)
    if not target.any():raise ValueError('No visible SVG area at this accuracy. Increase accuracy or simplify the artwork.')
    covered,remaining=fill_interior(boundary,target,panels,n,max_parts)
    unfilled=close_gaps(boundary,panels,512+round(accuracy*2.56),max_parts,tolerance,edge_count)
    if not panels:raise ValueError('Shape details are too thin. Increase accuracy or expand strokes.')
    yy,xx=np.mgrid[:n,:n];covered=np.zeros_like(target)
    for panel in panels:covered|=panel_mask(panel,(xx+.5)/n,(yy+.5)/n)
    coverage=float((covered&reference).sum()/max(1,reference.sum()))
    excess=float((covered&~reference).sum()/max(1,reference.sum()))
    preview=np.empty((n,n,4),np.float32);preview[:]=(.055,.065,.08,1)
    preview[reference]=(.55,.19,.19,1);preview[covered]=(.95,.69,.28,1)
    return {**cleanup,'panels':panels,'part_count':len(panels),'coverage':coverage,'excess':excess,
            'bounds':bounds,'resolution':n,'preview':preview,'outline_parts':edge_count,
            'outline_tolerance':tolerance,'outline_omissions':omitted,
            'outline_relaxed':relaxed,'unfilled':unfilled,
            'budget_hit':relaxed or (len(panels)>=max_parts and unfilled)}
