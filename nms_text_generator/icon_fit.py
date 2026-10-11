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
# Storage backs are uniformly calibrated to the Flat Panel's long dimension.
# Their short dimension is slightly smaller; ideal rectangles hide these seams.
FACE_SHORT=1.250976800918579*(3.0078125/2.9921875)/1.260742425918579


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


def visible_loops(shapes,point_test=None):
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
    test=point_test if point_test is not None else lambda p:contains(shapes,p)
    left=test(mid+normal*1e-7);right=test(mid-normal*1e-7)
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


def enlarge_fill(boundary,panels,edge_count):
    """Grow existing fill rectangles before spending parts on their seams.

    A fixed corner/edge/centre keeps the entire old rectangle inside the new
    one. Every candidate uses uniform scale and the full vector boundary test.
    Thus growth cannot uncover an old area, cross a hole, or move an outline.
    """
    grown=0
    for i in range(edge_count,len(panels)):
        x,y,w,a=panels[i];c,s=math.cos(a),math.sin(a)
        best=panels[i]
        for u,v in ((0,0),(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)):
            dx=(u*c*RATIO-v*s)/2;dy=(u*s*RATIO+v*c)/2
            def candidate(width):return (x+dx*(width-w),y+dy*(width-w),width,a)
            low=w;high=w*2
            while high<w*16 and boundary.inside(candidate(high)):low=high;high*=2
            for _ in range(12):
                mid=(low+high)/2
                if boundary.inside(candidate(mid)):low=mid
                else:high=mid
            if low>best[2]*(1+1e-5):best=candidate(low)
        if best[2]>w*(1+1e-5):panels[i]=best;grown+=1
    return grown


def panel_corners(panel,inset=False):
    x,y,w,a=panel;c,s=math.cos(a),math.sin(a)
    u=np.array([c,s])*w*RATIO/2*(.984 if inset else 1)
    v=np.array([-s,c])*w/2*(.967 if inset else 1)
    return np.array([np.array([x,y])+su*u+sv*v for su,sv in ((-1,-1),(1,-1),(1,1),(-1,1))])


def subtract_convex(subject,clip):
    """Exact polygon fragments left after covering with a convex rectangle."""
    remaining=[];inside=subject
    for a,b in zip(clip,np.roll(clip,-1,axis=0)):
        if len(inside)<3:break
        dist=cross(b-a,inside-a);positive=[];negative=[]
        for p,q,dp,dq in zip(inside,np.roll(inside,-1,axis=0),dist,np.roll(dist,-1)):
            (positive if dp>=-1e-12 else negative).append(p)
            if (dp>=-1e-12)!=(dq>=-1e-12):
                point=p+(q-p)*dp/(dp-dq);positive.append(point);negative.append(point)
        if len(negative)>=3:
            polygon=np.array(negative)
            if abs(cross(polygon,np.roll(polygon,-1,axis=0)).sum())>1e-13:remaining.append(polygon)
        inside=np.array(positive)
    return remaining


def prune_contained(panels,edge_count,later_only=False,kept_indices=None):
    """Remove redundant fills covered by neighbours, retaining every outline.

    Polygon subtraction proves collective coverage, not just a pixel/corner
    sample. Conservative inner faces leave overlap for native panel bevels.
    """
    if not panels:return 0
    keep=np.ones(len(panels),bool);removed=0
    corners=[panel_corners(p) for p in panels]
    inner=[panel_corners(p,True) for p in panels]
    lows=np.array([p.min(0) for p in inner]);highs=np.array([p.max(0) for p in inner])
    for i in sorted(range(edge_count,len(panels)),key=lambda i:(panels[i][2],-i)):
        rectangle=corners[i];low=rectangle.min(0);high=rectangle.max(0)
        neighbors=np.flatnonzero(keep&np.all((lows<=high)&(highs>=low),axis=1))
        neighbors=sorted((j for j in neighbors if j!=i and (not later_only or j>i)),key=lambda j:-panels[j][2])
        probes=np.concatenate((rectangle,(rectangle+np.roll(rectangle,-1,axis=0))/2,[rectangle.mean(0)]))
        covered=np.zeros(len(probes),bool)
        for j in neighbors:covered|=panel_mask(panels[j],probes[:,0],probes[:,1],inset=True)
        if not covered.all():continue
        fragments=[rectangle]
        for j in neighbors:
            fragments=[piece for fragment in fragments for piece in subtract_convex(fragment,inner[j])]
            if not fragments:
                keep[i]=False;removed+=1;break
            if len(fragments)>128:break  # Retain the part if proof becomes expensive.
    if kept_indices is not None:kept_indices.extend(np.flatnonzero(keep).tolist())
    panels[:]=[p for i,p in enumerate(panels) if keep[i]]
    return removed


def exposed_face_points(panels,positions=(.5,),removed_panel=None):
    """Probe every exposed native-face edge interval without a pixel grid.

    Clip each edge against neighbouring rectangles. The intervals left over
    border the union, including cracks too thin to land on a raster sample.
    A point just outside each interval is classified against the target later.
    """
    if not panels:return np.empty((0,2))
    values=np.asarray(panels,float);centres=values[:,:2];widths=values[:,2]
    c=np.cos(values[:,3]);s=np.sin(values[:,3])
    u=np.column_stack((c,s));v=np.column_stack((-s,c))
    half=np.column_stack((widths*RATIO/2,widths*FACE_SHORT/2))
    quads=np.array([centres+su*u*half[:,0,None]+sv*v*half[:,1,None]
                    for su,sv in ((-1,-1),(1,-1),(1,1),(-1,1))]).transpose(1,0,2)
    lows=quads.min(1);highs=quads.max(1);points=[]
    indices=range(len(panels))
    if removed_panel is not None:
        rectangle=panel_corners(removed_panel)
        indices=np.flatnonzero(np.all((lows<=rectangle.max(0)+1e-7)&(highs>=rectangle.min(0)-1e-7),axis=1))
    for i in indices:
        quad=quads[i]
        for p,q in zip(quad,np.roll(quad,-1,axis=0)):
            edge=q-p;length=float(np.linalg.norm(edge))
            if length<1e-9:continue
            normal=np.array([edge[1],-edge[0]])/length
            # Clip just outside this face: coincident aligned edges must not
            # hide each other from the material side.
            probe=p+normal*1e-8
            ids=np.flatnonzero(np.all((lows<=np.maximum(p,q)+1e-7)&(highs>=np.minimum(p,q)-1e-7),axis=1))
            ids=ids[ids!=i]
            delta=probe-centres[ids]
            origin=np.column_stack((np.sum(delta*u[ids],1),np.sum(delta*v[ids],1)))
            direction=np.column_stack((u[ids]@edge,v[ids]@edge))
            lo=np.zeros(len(ids));hi=np.ones(len(ids));possible=np.ones(len(ids),bool)
            for axis in (0,1):
                moving=abs(direction[:,axis])>1e-14
                safe=np.where(moving,direction[:,axis],1)
                t0=(-half[ids,axis]-origin[:,axis])/safe;t1=(half[ids,axis]-origin[:,axis])/safe
                lo=np.maximum(lo,np.where(moving,np.minimum(t0,t1),-np.inf))
                hi=np.minimum(hi,np.where(moving,np.maximum(t0,t1),np.inf))
                possible&=moving|(abs(origin[:,axis])<=half[ids,axis]+1e-12)
            cursor=0.
            for start,end in sorted(zip(lo[possible&(hi>lo)],hi[possible&(hi>lo)])):
                if start>cursor+1e-8:
                    points.extend(probe+edge*(cursor+(start-cursor)*fraction) for fraction in positions)
                cursor=max(cursor,end)
            if cursor<1-1e-8:
                points.extend(probe+edge*(cursor+(1-cursor)*fraction) for fraction in positions)
    points=np.asarray(points).reshape(-1,2)
    if removed_panel is not None:
        points=points[native_face_mask(removed_panel,points[:,0],points[:,1])]
    return points


def boundary_distances(boundary,points):
    distances=np.empty(len(points));nearest=np.empty(len(points),int)
    d=boundary.b-boundary.a;dd=np.sum(d*d,axis=1)
    for start in range(0,len(points),256):
        delta=points[start:start+256,None,:]-boundary.a[None,:,:]
        t=np.clip(np.sum(delta*d,axis=2)/np.maximum(dd,1e-24),0,1)
        squared=np.sum((delta-t[:,:,None]*d)**2,axis=2)
        nearest[start:start+256]=squared.argmin(1)
        distances[start:start+256]=np.sqrt(squared.min(1))
    return distances,nearest


def face_segments_blocked(panels,starts,ends):
    """Whether material separates a seam probe from its nearest contour."""
    starts=np.asarray(starts,float);ends=np.asarray(ends,float)
    values=np.asarray(panels,float);centres=values[:,:2];w=values[:,2]
    c=np.cos(values[:,3]);s=np.sin(values[:,3]);result=[]
    for start,end in zip(starts,ends):
        delta=start-centres;edge=end-start
        origin=np.column_stack((c*delta[:,0]+s*delta[:,1],-s*delta[:,0]+c*delta[:,1]))
        direction=np.column_stack((c*edge[0]+s*edge[1],-s*edge[0]+c*edge[1]))
        half=np.column_stack((w*RATIO/2,w*FACE_SHORT/2))
        lo=np.zeros(len(w));hi=np.ones(len(w));possible=np.ones(len(w),bool)
        for axis in (0,1):
            moving=abs(direction[:,axis])>1e-14;safe=np.where(moving,direction[:,axis],1)
            t0=(-half[:,axis]-origin[:,axis])/safe;t1=(half[:,axis]-origin[:,axis])/safe
            lo=np.maximum(lo,np.where(moving,np.minimum(t0,t1),-np.inf))
            hi=np.minimum(hi,np.where(moving,np.maximum(t0,t1),np.inf))
            possible&=moving|(abs(origin[:,axis])<half[:,axis]-1e-12)
        result.append(bool(np.any(possible&(hi>lo+1e-6))))
    return np.asarray(result,bool)


def expand_face_to_point(boundary,panel,point):
    """Move and uniformly enlarge a face while retaining its entire old face."""
    x,y,w,a=panel;c,s=math.cos(a),math.sin(a)
    axes=np.array([[c,-s],[s,c]]);local=(np.asarray(point).reshape(-1,2)-[x,y])@axes
    factors=np.array([RATIO,FACE_SHORT]);old_half=w*factors/2
    margin=max(2e-6,w*.015)
    low=np.minimum(-old_half,local.min(0)-margin);high=np.maximum(old_half,local.max(0)+margin)
    required=max(w,float(np.max((high-low)/factors)))
    if required>w*2.5:return None
    for width in required*np.array([1.000001,1.005,1.02,1.06,1.15,1.35]):
        half=width*factors/2
        start=high-half;end=low+half
        if np.any(start>end+1e-12):continue
        choices=[np.unique([start[j],end[j],(start[j]+end[j])/2,np.clip(0,start[j],end[j])]) for j in (0,1)]
        candidates=[(u,v) for u in choices[0] for v in choices[1]]
        candidates.sort(key=lambda uv:uv[0]**2+uv[1]**2)
        for uv in candidates:
            centre=np.array([x,y])+np.array(uv)@axes.T
            candidate=(*centre,float(width),a)
            if boundary.inside(candidate):return candidate
    return None


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


def close_gaps(boundary,panels,size,limit,tolerance,edge_count,follow_edges=False,coverage_goal=None):
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
    points=np.column_stack((xx[iy,ix],yy[iy,ix]));dist=np.empty(len(points));nearest=np.empty(len(points),np.int32)
    d=boundary.b-boundary.a;dd=np.sum(d*d,axis=1)
    for start in range(0,len(points),256):
        delta=points[start:start+256,None,:]-boundary.a[None,:,:]
        t=np.clip(np.sum(delta*d,axis=2)/np.maximum(dd,1e-24),0,1)
        distances=np.sum((delta-t[:,:,None]*d)**2,axis=2)
        nearest[start:start+256]=distances.argmin(axis=1)
        dist[start:start+256]=np.sqrt(distances.min(axis=1))
    # A minute rim at the contour is native bevel, not an interior hole. Filling
    # it would require panels outside the contour or an unbounded tiny-part tail.
    available=dist>min(tolerance*.5,.0005)
    visible_missing=np.ones(len(points),bool)
    while available.any() and len(panels)<limit:
        idx=int(np.argmax(np.where(available,dist,-1)))
        if follow_edges:
            # Long rectangular interiors have a plateau of equally deep points.
            # Choosing its first raster row clips a large panel at the end of
            # the shape. Start near the centre instead, keeping placement stable.
            ties=np.flatnonzero(available&(dist>=dist[idx]-1e-9))
            centre=(points.min(0)+points.max(0))/2
            idx=int(ties[np.argmin(np.sum((points[ties]-centre)**2,axis=1))])
        x,y=points[idx]
        if dist[idx]<1e-7:available[idx]=False;continue
        best=None;largest=0
        angles=(0,math.pi/4,math.pi/2,3*math.pi/4)
        if follow_edges:
            edge=d[nearest[idx]];tangent=math.atan2(edge[1],edge[0])
            angles=(tangent,tangent+math.pi/2)+angles
        for angle in angles:
            lo=dist[idx]*1.999/math.sqrt(1+RATIO*RATIO);hi=dist[idx]*2
            for _ in range(13):
                width=(lo+hi)/2
                if boundary.inside((x,y,width,angle)):lo=width
                else:hi=width
            if lo>largest:largest=lo;best=(x,y,lo,angle)
        panels.append(best)
        available&=~panel_mask(best,points[:,0],points[:,1],inset=True)
        if coverage_goal is not None:
            visible_missing&=~panel_mask(best,points[:,0],points[:,1])
            if visible_missing.sum()<=len(points)*(1-coverage_goal):break
    return bool(available.any())


def native_face_mask(panel,xx,yy):
    """Calibrated Storage face, used to distinguish actual cracks from bevels."""
    x,y,w,angle=panel;c,s=math.cos(angle),math.sin(angle);dx=xx-x;dy=yy-y
    return ((abs(c*dx+s*dy)<=w*RATIO/2+1e-10)&
            (abs(-s*dx+c*dy)<=w*FACE_SHORT/2+1e-10))


def facet_candidates(boundary):
    """Maximal rectangles anchored to whole vector edges, in either orientation.

    Both sides of a straight band compete for the same covered area. They no
    longer reserve separate small outline pieces. No candidate can cross the
    shared polygon contour, including its holes and neighbouring islands.
    """
    panels=[]
    for p,q in zip(boundary.a,boundary.b):
        delta=q-p;length=float(np.linalg.norm(delta))
        if length<1e-9:continue
        u=delta/length;normal=np.array([-u[1],u[0]])
        for fraction in (.15,.35,.5,.65,.85):
            anchor=p+delta*fraction
            for deep in (False,True):
                angle=math.atan2(u[1],u[0])+(math.pi/2 if deep else 0)
                factor=RATIO if deep else 1
                def candidate(width):return (* (anchor+normal*width*factor/2),width,angle)
                lo=0.;hi=1.
                for _ in range(21):
                    width=(lo+hi)/2
                    if boundary.inside(candidate(width)):lo=width
                    else:hi=width
                if lo>1e-5:panels.append(candidate(lo))
    return panels


def native_seam_probes(boundary,panels,rim_tolerance=.001,removed_panel=None):
    """Find internal cracks separately from the small native outside rim.

    Several points on each exposed interval check its ends as well as its
    middle. Raster coverage alone misses arbitrarily thin native-face cracks.
    """
    points=exposed_face_points(panels,positions=(.01,.25,.5,.75,.99),removed_panel=removed_panel)
    points=points[contains(boundary.shapes,points)]
    if not len(points):return []
    distances,nearest=boundary_distances(boundary,points)
    a=boundary.a[nearest];d=boundary.b[nearest]-a
    t=np.clip(np.sum((points-a)*d,axis=1)/np.maximum(np.sum(d*d,axis=1),1e-24),0,1)
    blocked=face_segments_blocked(panels,points,a+d*t[:,None])
    ids=np.flatnonzero((distances>1e-7)&(blocked|(distances>rim_tolerance)))
    ids=sorted(ids,key=lambda i:(-int(blocked[i]),-distances[i]))
    return [(bool(blocked[i]),float(distances[i]),points[i],int(nearest[i])) for i in ids]


def facet_samples(boundary,size,rim_tolerance):
    """Global interior probes plus locally scaled probes for tiny islands."""
    target=svg_geometry.rasterize(boundary.shapes,size)
    iy,ix=np.nonzero(target);points=np.column_stack(((ix+.5)/size,(iy+.5)/size))
    tolerances=np.full(len(points),rim_tolerance)
    islands=[loop for loop in boundary.loops if cross(loop,np.roll(loop,-1,axis=0)).sum()>0]
    # A tiny detached feature may fall between global pixels, and its whole
    # width may be smaller than the usual outer-rim allowance. Sample such
    # features in their own bounds and scale the allowance to the feature.
    for loop in islands:
        low=loop.min(0);span=loop.max(0)-low
        if min(span)>=rim_tolerance*20:continue
        sy,sx=np.mgrid[:32,:32]
        local=low+np.column_stack(((sx.ravel()+.5)/32,(sy.ravel()+.5)/32))*span
        local=local[contains(boundary.shapes,local)]
        points=np.concatenate((points,local))
        tolerances=np.r_[tolerances,np.full(len(local),min(rim_tolerance,min(span)*.01))]
    return points,tolerances,islands


def island_owners(islands,panels):
    owners=np.full(len(panels),-1)
    centres=np.asarray([p[:2] for p in panels]).reshape(-1,2)
    for i in sorted(range(len(islands)),key=lambda j:-abs(cross(islands[j],np.roll(islands[j],-1,axis=0)).sum())):
        owners[contains([([islands[i]],'nonzero')],centres)]=i
    return owners


def repair_facet_gaps(boundary,panels,limit,size=512,rim_tolerance=.001):
    """Bridge seams while retaining one coherent polygon, never dilating it."""
    points,tolerances,islands=facet_samples(boundary,size,rim_tolerance)
    missing=np.ones(len(points),bool)
    for panel in panels:missing&=~native_face_mask(panel,points[:,0],points[:,1])
    points=points[missing];tolerances=tolerances[missing]
    distances,nearest=boundary_distances(boundary,points)
    available=distances>tolerances
    added=0
    pending=native_seam_probes(boundary,panels,rim_tolerance)
    while len(panels)<limit:
        choices=pending[:6]
        # An untouched island/interior has no existing face edge to probe.
        # Independently search the entire target so it cannot go unnoticed.
        if available.any():
            i=int(np.argmax(np.where(available,distances,-1)))
            choices=[(True,float(distances[i]),points[i],int(nearest[i]))]+choices
        if not choices:break
        best=None
        for _,distance,point,edge_index in choices:
            d=boundary.b[edge_index]-boundary.a[edge_index]
            tangent=math.atan2(d[1],d[0]);patch=None
            for angle in (tangent,tangent+math.pi/2,0,math.pi/4,math.pi/2,3*math.pi/4):
                lo=0.;hi=distance*2
                for _ in range(18):
                    width=(lo+hi)/2
                    if boundary.inside((*point,width,angle)):lo=width
                    else:hi=width
                if patch is None or lo>patch[2]:patch=(*point,lo,angle)
            if patch[2]<1e-8:continue
            expanded=[patch];enlarge_fill(boundary,expanded,0);patch=expanded[0]
            if not native_face_mask(patch,point[0],point[1]):continue
            best=patch;break
        if best is None:break
        panels.append(best);added+=1
        available&=~native_face_mask(best,points[:,0],points[:,1])
        pending=native_seam_probes(boundary,panels,rim_tolerance)
    # Preserve each material component even if it was below both sampling
    # resolutions. Assign nested islands to their innermost positive contour.
    owners=island_owners(islands,panels)
    missing_islands=len(set(range(len(islands)))-set(owners.tolist()))
    return {'seam_repairs':added,'remaining_seams':sum(row[0] for row in pending),
            'remaining_edge_pockets':sum(not row[0] for row in pending),
            'remaining_interior_samples':int(available.sum()),
            'remaining_islands':missing_islands,
            'seam_check_complete':not pending and not available.any() and not missing_islands}


def prune_facet_panels(boundary,panels,size=768,rim_tolerance=.001):
    """Drop surplus rim pieces from an already complete fit without opening seams.

    Preserve all sampled interior coverage and every material island. A removal
    can expose new edges only inside its old face; inspect those locally, then
    verify the complete union once at the end. The outside allowance is the
    same minute native rim used by repair, independent of the Accuracy slider.
    """
    points,tolerances,islands=facet_samples(boundary,size,rim_tolerance)
    if len(points)*len(panels)>100_000_000:return 0
    distances,_=boundary_distances(boundary,points);core=distances>tolerances
    masks=np.array([native_face_mask(p,points[:,0],points[:,1]) for p in panels])
    counts=masks.sum(axis=0);keep=np.ones(len(panels),bool)
    if np.any((counts==0)&core):return 0
    owners=island_owners(islands,panels)
    for i in sorted(range(len(panels)),key=lambda i:(panels[i][2],-i)):
        lost=masks[i]&(counts==1)
        if np.any(lost&core) or (np.count_nonzero(counts)-lost.sum())<len(points)*.995:continue
        if owners[i]>=0 and np.count_nonzero((owners==owners[i])&keep)<=1:continue
        proposal=[p for j,p in enumerate(panels) if keep[j] and j!=i]
        if native_seam_probes(boundary,proposal,rim_tolerance,removed_panel=panels[i]):continue
        keep[i]=False;counts-=masks[i]
    proposal=[p for i,p in enumerate(panels) if keep[i]]
    if native_seam_probes(boundary,proposal,rim_tolerance):return 0
    removed=len(panels)-len(proposal);panels[:]=proposal
    return removed


def valid_facets(original,facets):
    """Do not trade holes, disconnected features or simple loops for fewer edges."""
    if len(original)!=len(facets):return False
    for before,after in zip(original,facets):
        a=cross(before,np.roll(before,-1,axis=0)).sum()
        b=cross(after,np.roll(after,-1,axis=0)).sum()
        if a*b<=0:return False
    boundary=Boundary(facets);a=boundary.a;b=boundary.b;d=b-a
    owner=np.concatenate([np.full(len(loop),i) for i,loop in enumerate(facets)])
    offsets=np.cumsum([0]+[len(loop) for loop in facets])
    for i,(p,q) in enumerate(zip(a,b)):
        ids=np.arange(i+1,len(a))
        adjacent=(owner[ids]==owner[i])&((ids==i+1)|((i==offsets[owner[i]])&(ids==offsets[owner[i]+1]-1)))
        ids=ids[~adjacent]
        if not len(ids):continue
        overlap=np.all((boundary.low[ids]<=boundary.high[i]+1e-10)&(boundary.high[ids]>=boundary.low[i]-1e-10),axis=1)
        ids=ids[overlap];delta=a[ids]-p;den=cross(d[i],d[ids])
        parallel=abs(den)<1e-12
        if np.any(parallel&(abs(cross(delta,d[i]))<1e-12)):return False
        ids=ids[~parallel];delta=delta[~parallel];den=den[~parallel]
        t=cross(delta,d[ids])/den;u=cross(delta,d[i])/den
        if np.any((t>=-1e-9)&(t<=1+1e-9)&(u>=-1e-9)&(u<=1+1e-9)):return False
    # Compare each contour's nesting using anchors from the matching version.
    # Regularization can move a whole island/hole across another boundary
    # without a final intersection; testing its old anchor would miss this.
    for i,(before,after) in enumerate(zip(original,facets)):
        old_anchors=[loop[0] for j,loop in enumerate(original) if j!=i]
        new_anchors=[loop[0] for j,loop in enumerate(facets) if j!=i]
        if old_anchors and not np.array_equal(contains([([before],'nonzero')],old_anchors),
                                              contains([([after],'nonzero')],new_anchors)):return False
    return True


def band_connection_clear(boundary,i,j):
    """The open connector between opposed edge centres must stay in material."""
    p=(boundary.a[i]+boundary.b[i])/2;q=(boundary.a[j]+boundary.b[j])/2
    delta=q-p;length_squared=delta@delta
    if length_squared<1e-20:return False
    edges=boundary.b-boundary.a;relative=boundary.a-p
    determinant=cross(delta,edges);parallel=abs(determinant)<1e-12
    safe=np.where(parallel,1,determinant)
    along=cross(relative,edges)/safe;across=cross(relative,delta)/safe
    others=np.ones(len(edges),bool);others[[i,j]]=False
    intersects=(~parallel)&(along>1e-8)&(along<1-1e-8)&(across>=-1e-8)&(across<=1+1e-8)
    if np.any(others&intersects):return False
    collinear=parallel&(abs(cross(relative,delta))<1e-12)
    start=relative@delta/length_squared;end=(boundary.b-p)@delta/length_squared
    overlap=np.minimum(np.maximum(start,end),1-1e-8)-np.maximum(np.minimum(start,end),1e-8)
    if np.any(others&collinear&(overlap>0)):return False
    return bool(contains(boundary.shapes,[(p+q)/2])[0])


def regularize_contours(loops,movement,max_angle):
    """Simplify whole bands and near-square convex corners for rectangular parts.

    Directions are shared locally, never snapped to world axes. Existing square
    details retain their orientation. Matched vertices stay within both the
    accuracy allowance and a quarter of nearby feature clearance; panels still
    fit strictly inside the resulting continuous polygon.
    """
    if movement<=0 or max_angle<=0 or sum(map(len,loops))>256:return loops
    boundary=Boundary(loops);vectors=boundary.b-boundary.a
    lengths=np.linalg.norm(vectors,axis=1)
    if np.any(lengths<1e-9):return loops
    tangents=vectors/lengths[:,None]
    normals=np.column_stack((-tangents[:,1],tangents[:,0]))
    midpoints=(boundary.a+boundary.b)/2
    angles=np.arctan2(tangents[:,1],tangents[:,0])
    count=len(lengths);parent=np.arange(count)
    previous=np.empty(count,int);following=np.empty(count,int);owners=np.empty(count,int)
    offset=0
    for owner,loop in enumerate(loops):
        ids=np.arange(offset,offset+len(loop))
        previous[ids]=np.roll(ids,1);following[ids]=np.roll(ids,-1);owners[ids]=owner
        offset+=len(loop)

    def group(i):
        while parent[i]!=i:i=parent[i]
        return i

    constraints=[];protected=np.zeros(count,bool)
    for i,j in enumerate(previous):
        error=abs(math.asin(np.clip(tangents[i]@tangents[j],-1,1)))
        if error<math.radians(2):protected[[i,j]]=True
        # Broad corner changes are only useful on convex material corners.
        # Squaring a concave junction instead can tilt the stem of a T shape.
        if error<max_angle and cross(tangents[j],tangents[i])>0:
            constraints.append((error,i,int(j)))
    for i in range(count):
        delta=midpoints-midpoints[i];gap=delta@normals[i]
        start=(boundary.a-boundary.a[i])@tangents[i]
        end=(boundary.b-boundary.a[i])@tangents[i]
        overlap=np.minimum(lengths[i],np.maximum(start,end))-np.maximum(0,np.minimum(start,end))
        ids=np.flatnonzero((np.sum(tangents*tangents[i],axis=1)<-math.cos(max_angle))
            &(gap>1e-4)&(gap<.15)&(np.sum(-delta*normals,axis=1)>1e-4)
            &(overlap>np.minimum(lengths,lengths[i])*.25))
        for j in ids:
            if j<=i:continue
            if not band_connection_clear(boundary,i,j):continue
            error=math.acos(np.clip(-tangents[i]@tangents[j],-1,1))
            constraints.append((error,i,int(j)))
            if error<math.radians(2):protected[[i,j]]=True

    limits=np.full(count,movement)
    def point_distance(point,a,b):
        edge=b-a;t=np.clip(np.dot(point-a,edge)/np.dot(edge,edge),0,1)
        return np.linalg.norm(point-a-edge*t)
    for i in range(count):
        for j in range(i+1,count):
            if following[i]==j or following[j]==i:continue
            if owners[i]==owners[j]:
                if tangents[i]@tangents[j]>-.5:continue
                projections=np.array([(boundary.a[j]-boundary.a[i])@tangents[i],
                                      (boundary.b[j]-boundary.a[i])@tangents[i]])
                if min(lengths[i],max(projections))-max(0,min(projections))<=0:continue
            distance=min(point_distance(boundary.a[i],boundary.a[j],boundary.b[j]),
                         point_distance(boundary.b[i],boundary.a[j],boundary.b[j]),
                         point_distance(boundary.a[j],boundary.a[i],boundary.b[i]),
                         point_distance(boundary.b[j],boundary.a[i],boundary.b[i]))
            ids=[i,j,following[i],following[j]]
            limits[ids]=np.minimum(limits[ids],distance*.25)

    applied=angles.copy();vertices=boundary.a.copy()
    for _,i,j in sorted(constraints):
        first,second=group(i),group(j)
        if first==second:continue
        ids=np.array([k for k in range(count) if group(k) in (first,second)])
        phase=np.angle(np.sum(lengths[ids]**2*np.exp(4j*angles[ids])))/4
        desired=phase+np.round((angles[ids]-phase)/(math.pi/2))*(math.pi/2)
        # Keep existing rectangular bars/cutouts from joining a slanted family.
        allowance=np.where(protected[ids],math.radians(.25),max_angle)
        if np.any(abs(desired-angles[ids])>allowance):continue
        proposal=applied.copy();proposal[ids]=desired
        directions=np.column_stack((np.cos(proposal),np.sin(proposal)))
        before=directions[previous];after=directions
        determinant=cross(before,after)
        if np.any(abs(determinant)<1e-8):continue
        t=cross(midpoints-midpoints[previous],after)/determinant
        moved=midpoints[previous]+before*t[:,None]
        if np.any(np.linalg.norm(moved-boundary.a,axis=1)>limits):continue
        if np.any(np.linalg.norm(moved[following]-moved,axis=1)<lengths*.25):continue
        parent[second]=first;applied=proposal;vertices=moved
    output=[];offset=0
    for loop in loops:
        output.append(vertices[offset:offset+len(loop)].copy());offset+=len(loop)
    return output if valid_facets(loops,output) else loops


@lru_cache(maxsize=4)
def contour_plan(source,max_parts):
    """A stable coarse-to-fine hierarchy, independent of slider movement.

    Derive the budget's finest contour once. Lower accuracy can only remove
    vertices from that contour; it cannot restart the budget retries at a
    different tolerance and accidentally restore more detail.
    """
    _,_,loops,_=read_outline(source)
    floor=.0006
    for retry in range(7):
        finest=[simplify_loop(loop,floor) for loop in loops]
        boundary=Boundary(finest)
        panels,_=outline_panels(boundary,floor,max_parts*2)
        if len(panels)<=max_parts*.8:break
        if retry<6:floor*=1.6
    if sum(map(len,finest))>256 or not valid_facets(loops,finest):return None
    levels=[None]*101;previous=finest;accepted=floor
    for accuracy in range(100,-1,-1):
        tolerance=floor*.15**((accuracy-100)/100)
        proposed=[simplify_loop(loop,tolerance) for loop in loops]
        # simplify_loop deliberately restores tiny islands rather than erase
        # them. Retain their previous facets instead of restoring their detail.
        proposed=[new if len(new)<=len(old) else old for new,old in zip(proposed,previous)]
        valid=valid_facets(loops,proposed)
        if valid:previous=proposed;accepted=tolerance
        levels[accuracy]={'loops':previous,'tolerance':accepted,
                          'relaxed':floor>.000600001,'limited':not valid}
    return levels


def facet_fit(shapes,bounds,loops,cleanup,accuracy,max_parts,baseline):
    """Share clean faceted edges, then spend the saved capacity on native joins.

    The complete simplified contour is selected before assembling panels. A
    geometric containment check forbids per-panel overdraw. The alternative
    is accepted by the caller only when both its shape and seam checks pass.
    """
    from .preview_jobs import report
    boundary=Boundary([np.asarray(c) for c in baseline['_fill_loops']])
    # Bound candidate memory and work for complex artwork; the normal contour
    # fitter remains available when this alternate search is unsuitable.
    if len(boundary.a)>256 or not valid_facets(loops,boundary.loops):return None
    report('Fitting shared polygon edges')
    candidates=facet_candidates(boundary)
    if not candidates:return None
    n=512;target=svg_geometry.rasterize(boundary.shapes,n)
    iy,ix=np.nonzero(target);x=(ix+.5)/n;y=(iy+.5)/n
    # Keep dense solid shapes from allocating an unbounded candidate matrix.
    stride=max(1,math.ceil(len(x)*len(candidates)/100_000_000))
    x=x[::stride];y=y[::stride]
    masks=np.array([panel_mask(p,x,y,inset=True) for p in candidates])
    remaining=np.ones(len(x),bool);native_remaining=remaining.copy()
    gains=masks.sum(axis=1);panels=[]
    # Simpler polygons need fewer competing edge seeds. Keep capacity for
    # useful joins instead of spending half the cap on redundant rim pieces.
    seed_limit=min(max_parts//2,max(1,len(boundary.a)*7//6))
    for _ in range(seed_limit):
        i=int(gains.argmax())
        if gains[i]<1:break
        panels.append(candidates[i]);new=masks[i]&remaining
        # Update only newly covered samples, rather than rescanning every
        # candidate's whole mask after every selection.
        gains-=masks[:,new].sum(axis=1);remaining&=~new
        native_remaining&=~native_face_mask(candidates[i],x,y)
        if native_remaining.sum()<=len(x)*.003:break
    del masks
    if not panels:return None
    edge_count=len(panels)
    report('Closing joins inside the polygon')
    checks=repair_facet_gaps(boundary,panels,max_parts,size=768)
    edge_panels=set(panels[:edge_count])
    removed=prune_facet_panels(boundary,panels) if checks['seam_check_complete'] else 0
    edge_count=sum(p in edge_panels for p in panels)
    qn=768;reference=svg_geometry.rasterize(shapes,qn)
    target=svg_geometry.rasterize(boundary.shapes,qn)
    yy,xx=np.mgrid[:qn,:qn];xx=(xx+.5)/qn;yy=(yy+.5)/qn
    face=np.zeros_like(target);footprint=np.zeros_like(target)
    for panel in panels:
        face|=native_face_mask(panel,xx,yy);footprint|=panel_mask(panel,xx,yy)
    preview_n=128+round(accuracy*1.28)
    preview_target=svg_geometry.rasterize(shapes,preview_n)
    py,px=np.mgrid[:preview_n,:preview_n];px=(px+.5)/preview_n;py=(py+.5)/preview_n
    preview_face=np.zeros_like(preview_target)
    for panel in panels:preview_face|=native_face_mask(panel,px,py)
    preview=np.empty((preview_n,preview_n,4),np.float32);preview[:]=(.055,.065,.08,1)
    preview[preview_target]=(.55,.19,.19,1);preview[preview_face]=(.95,.69,.28,1)
    total=max(1,int(reference.sum()));target_total=max(1,int(target.sum()))
    return {**cleanup,**checks,'panels':panels,'part_count':len(panels),'removed_parts':removed,
            'coverage':float((face&reference).sum()/total),
            'face_coverage':float((face&target).sum()/target_total),
            'target_coverage':float((footprint&target).sum()/target_total),
            'excess':float((footprint&~reference).sum()/total),
            'shape_change':float((target^reference).sum()/total),
            'quality_resolution':qn,'bounds':bounds,'resolution':preview_n,'preview':preview,
            'outline_parts':edge_count,'_fill_loops':[c.tolist() for c in boundary.loops],
            'outline_tolerance':baseline['outline_tolerance'],'outline_omissions':0,
            'outline_relaxed':baseline['outline_relaxed'],'unfilled':not checks['seam_check_complete'],
            'budget_hit':len(panels)>=max_parts and not checks['seam_check_complete'],
            'faceted_fit':True}


def fit_svg(source,accuracy=50,max_parts=300):
    accuracy=max(0,min(100,int(accuracy)));max_parts=max(1,min(2000,int(max_parts)))
    shapes,bounds,loops,cleanup=read_outline(source)
    levels=contour_plan(source,max_parts)
    plan=levels[accuracy] if levels is not None else None
    if plan is not None and accuracy<100:
        # Only the selected level is regularized; cached hierarchy arrays stay
        # untouched. Lower accuracy allows whole corners/bands to become simpler.
        strength=100-accuracy
        adjusted=regularize_contours(plan['loops'],min(.016,strength*.0004),
                                     math.radians(min(28,strength*.7)))
        plan={**plan,'loops':adjusted}
    result=fit_outline(shapes,bounds,loops,cleanup,accuracy,max_parts,planned_contour=plan)
    # Use the shared-edge assembler at every accuracy. Accuracy selects the
    # polygon, not the algorithm; both assemblies use exactly that polygon.
    if plan is not None:
        candidate=facet_fit(shapes,bounds,loops,cleanup,accuracy,max_parts,result)
        if (candidate is not None and candidate['part_count']<=max_parts
                and (result['unfilled'] or candidate['part_count']<=result['part_count'])
                and candidate['face_coverage']>=.995 and candidate['seam_check_complete']):
            candidate['simplification_limited']=plan['limited']
            return candidate
    # Relaxing the two sides of a traced hairline independently can displace
    # the whole line. If that happens, fit within the recovered features and
    # report missing coverage rather than inventing broad wedges outside them.
    if result['excess']>.05 and result['coverage']<.8:
        try:candidate=fit_outline(shapes,bounds,loops,cleanup,accuracy,max_parts,fill_first=True)
        except ValueError:return result
        if candidate['coverage']>result['coverage'] and candidate['excess']<result['excess']:
            candidate['feature_fit']=True
            return candidate
    return result


def fit_outline(shapes,bounds,loops,cleanup,accuracy=50,max_parts=300,fill_first=False,coverage_goal=None,outline_tolerance=None,optimize_fill=False,planned_contour=None):
    """Fit a visible colour region in the artwork's shared coordinate space."""
    tolerance=.004*(.15**(accuracy/100)) if outline_tolerance is None else outline_tolerance
    if fill_first:
        # Visible colour regions have many disconnected rims and braces. Fit
        # their solid interiors against the original boundary, following the
        # nearest edge's angle, before the part cap can be spent on contours.
        boundary=Boundary(loops);panels=[];n=128+round(accuracy*1.28)
        reference=svg_geometry.rasterize(shapes,n)
        if not reference.any():raise ValueError('No visible SVG area at this accuracy. Increase accuracy or simplify the artwork.')
        unfilled=close_gaps(boundary,panels,256+round(accuracy*1.28),max_parts,tolerance,0,follow_edges=True,coverage_goal=coverage_goal)
        if not panels:raise ValueError('Shape details are too thin. Increase accuracy or expand strokes.')
        yy,xx=np.mgrid[:n,:n];covered=np.zeros_like(reference)
        for panel in panels:covered|=panel_mask(panel,(xx+.5)/n,(yy+.5)/n)
        preview=np.empty((n,n,4),np.float32);preview[:]=(.055,.065,.08,1)
        preview[reference]=(.55,.19,.19,1);preview[covered]=(.95,.69,.28,1)
        return {**cleanup,'panels':panels,'part_count':len(panels),
                'coverage':float((covered&reference).sum()/max(1,reference.sum())),
                'excess':float((covered&~reference).sum()/max(1,reference.sum())),
                'bounds':bounds,'resolution':n,'preview':preview,'outline_parts':0,
                '_fill_loops':[c.tolist() for c in boundary.loops],
                'outline_tolerance':tolerance,'outline_omissions':0,'outline_relaxed':False,
                'unfilled':unfilled,'budget_hit':len(panels)>=max_parts and unfilled}
    # Keep budget available for filling. Relax an over-budget contour as a whole
    # instead of chopping random edges from the logo.
    relaxed=False
    if planned_contour is not None:
        tolerance=planned_contour['tolerance'];relaxed=planned_contour['relaxed']
        boundary=Boundary(planned_contour['loops'])
        panels,omitted=outline_panels(boundary,tolerance,max_parts*2)
    else:
        for retry in range(7):
            boundary=Boundary([simplify_loop(loop,tolerance) for loop in loops])
            panels,omitted=outline_panels(boundary,tolerance,max_parts*2)
            if len(panels)<=max_parts*.8:break
            if retry<6:tolerance*=1.6;relaxed=True
    if len(panels)>max_parts:
        panels=sorted(panels,key=lambda p:p[2],reverse=True)[:max_parts];relaxed=True
    n=128+round(accuracy*1.28)
    target=svg_geometry.rasterize(boundary.shapes,n)
    reference=svg_geometry.rasterize(shapes,n)
    if not target.any():raise ValueError('No visible SVG area at this accuracy. Increase accuracy or simplify the artwork.')
    edge_count=len(panels)
    covered,remaining=fill_interior(boundary,target,panels,n,max_parts)
    grown=removed=0
    if optimize_fill:
        grown=enlarge_fill(boundary,panels,edge_count)
        removed=prune_contained(panels,edge_count)
    unfilled=close_gaps(boundary,panels,512+round(accuracy*2.56),max_parts,tolerance,edge_count,follow_edges=optimize_fill)
    if optimize_fill:removed+=prune_contained(panels,edge_count)
    if not panels:raise ValueError('Shape details are too thin. Increase accuracy or expand strokes.')
    yy,xx=np.mgrid[:n,:n];covered=np.zeros_like(target)
    for panel in panels:covered|=panel_mask(panel,(xx+.5)/n,(yy+.5)/n)
    coverage=float((covered&reference).sum()/max(1,reference.sum()))
    excess=float((covered&~reference).sum()/max(1,reference.sum()))
    preview=np.empty((n,n,4),np.float32);preview[:]=(.055,.065,.08,1)
    preview[reference]=(.55,.19,.19,1);preview[covered]=(.95,.69,.28,1)
    return {**cleanup,'panels':panels,'part_count':len(panels),'coverage':coverage,'excess':excess,
            '_fill_loops':[c.tolist() for c in boundary.loops],
            'bounds':bounds,'resolution':n,'preview':preview,'outline_parts':edge_count,
            'outline_tolerance':tolerance,'outline_omissions':omitted,
            'outline_relaxed':relaxed,'unfilled':unfilled,
            'budget_hit':relaxed or (len(panels)>=max_parts and unfilled),
            'grown_parts':grown,'removed_parts':removed}
