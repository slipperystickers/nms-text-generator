"""Offline solid-paint matching and visible colour regions; NumPy only.

SVG paint is sRGB. Game palette triples are interpreted as linear RGB, as in
Base Builder's material previews. Oklab distance compares perceptual colours.
These are palette estimates: textures, finish, face masks and lighting affect
the rendered result. Station palettes are opt-in until panel use is validated.
"""
import json
import math
import re
from functools import lru_cache
from pathlib import Path
import numpy as np
from . import svg_geometry as svg,svg_outline


@lru_cache(maxsize=1)
def catalog():
    return json.loads(Path(__file__).with_name('color_catalog.json').read_text(encoding='utf-8'))


def parse_color(value):
    value=value.strip().lower()
    value=catalog()['css_names'].get(value,value)
    if value=='transparent':return (0.,0.,0.),0.
    if re.fullmatch(r'#[0-9a-f]{3,4}',value):value='#'+''.join(c*2 for c in value[1:])
    if re.fullmatch(r'#[0-9a-f]{6}(?:[0-9a-f]{2})?',value):
        numbers=[int(value[i:i+2],16)/255 for i in range(1,len(value),2)]
        return tuple(numbers[:3]),numbers[3] if len(numbers)==4 else 1.
    match=re.fullmatch(r'(rgb|rgba)\(([^()]*)\)',value)
    if match:
        values=re.split(r'\s*[,/]\s*|\s+',match[2].strip())
        if len(values) in (3,4):
            try:
                rgb=[float(c[:-1])/100 if c.endswith('%') else float(c)/255 for c in values[:3]]
                a=values[3] if len(values)==4 else '1'
                alpha=float(a[:-1])/100 if a.endswith('%') else float(a)
                if all(math.isfinite(c) for c in (*rgb,alpha)):
                    return tuple(max(0,min(1,c)) for c in rgb),max(0,min(1,alpha))
            except ValueError:pass
    raise ValueError('Unsupported colour paint: '+value[:60]+'. Use solid hex, rgb(), or named colours; turn off Match SVG colours for a silhouette.')


def linear(srgb):
    a=np.asarray(srgb,float)
    return np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4)


def srgb(rgb):
    a=np.asarray(rgb,float)
    return np.clip(np.where(a<=.0031308,a*12.92,1.055*np.maximum(a,0)**(1/2.4)-.055),0,1)


def oklab(rgb):
    a=np.asarray(rgb,float)
    lms=a@np.array([[.4122214708,.2119034982,.0883024619],
                    [.5363325363,.6806995451,.2817188376],
                    [.0514459929,.1073969566,.6299787005]])
    return np.cbrt(lms)@np.array([[.2104542553,1.9779984951,.0259040371],
                                [.7936177850,-2.4285922050,.7827717662],
                                [-.0040720468,.4505937099,-.8086757660]])


@lru_cache(maxsize=2)
def candidates(include_station=False):
    # Keep default finishes. Other finishes change surface response and their
    # interpretation depends on the part. Do not guess a secondary-slot swap.
    entries=[]
    for p in catalog()['palettes']:
        if p['index']>=115 and not include_station:continue
        entries.append({'index':p['index'],'id':p['id'],'finish':0,'rgb':p['p'],
                        'user_data':p['index']})
    return entries


def nearest(rgb,include_station=False):
    entries=candidates(include_station)
    labs=oklab([e['rgb'] for e in entries]);target=oklab(linear(rgb))
    distances=np.linalg.norm(labs-target,axis=1)
    chroma=float(np.linalg.norm(target[1:]));available=np.linalg.norm(labs[:,1:],axis=1)
    # A brightness-only advantage can otherwise turn dark blue into grey.
    # For clearly coloured paint, keep a similar hue whenever the palette has
    # one, then minimize perceptual distance within that set. Neutral paint
    # and colours with no nearby hue still use the full palette.
    if chroma>=.04:
        cosine=(labs[:,1:]@target[1:])/np.maximum(available*chroma,1e-15)
        similar=(available>=.02)&(cosine>=math.cos(math.radians(20)))
        if similar.any():distances=np.where(similar,distances,np.inf)
    i=int(distances.argmin())
    return {**entries[i],'distance':float(distances[i]),'source_rgb':list(rgb)}


def color_key(rgb):
    return '#'+''.join(f'{round(c*255):02X}' for c in rgb)


def overrides_json(value='{}'):
    """Canonical, validated choices for cache keys and saved icon settings."""
    values=json.loads(value) if isinstance(value,str) else value
    if not isinstance(values,dict):raise ValueError('Invalid SVG colour choices.')
    valid={p['index'] for p in catalog()['palettes']}
    result={}
    for paint,code in values.items():
        if not isinstance(paint,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',paint):raise ValueError('Invalid source colour.')
        if type(code) is not int or code not in valid:raise ValueError('Invalid NMS colour choice.')
        result[paint.upper()]=code
    return json.dumps(result,sort_keys=True,separators=(',',':'))


@lru_cache(maxsize=8)
def read_paints(source,include_station=False,overrides='{}'):
    shapes,bounds,paints=svg.read_svg(source,with_colors=True)
    choices=json.loads(overrides_json(overrides));entries={p['user_data']:p for p in candidates(True)}
    matches=[]
    for rgb in paints:
        code=choices.get(color_key(rgb))
        matches.append(nearest(rgb,include_station) if code is None else
                       {**entries[code],'distance':float(np.linalg.norm(oklab(entries[code]['rgb'])-oklab(linear(rgb)))),
                        'source_rgb':list(rgb),'manual':True})
    return shapes,bounds,matches


def labels_at(shapes,matches,points):
    from .icon_fit import contains
    labels=np.full(len(points),-1,np.int64)
    for shape,match in zip(shapes,matches):
        labels[contains([shape],points)]=match['user_data']
    return labels


@lru_cache(maxsize=4)
def read_regions(source,include_station=False,allow_simplify=True,overrides='{}'):
    from .icon_fit import visible_loops,SimplificationRequired
    shapes,bounds,matches=read_paints(source,include_station,overrides)
    # Clean every path before intersection work, using the same tolerance as
    # the silhouette reader. All regions share one normalization and crop.
    shapes=[([svg_outline.simplify_loop(c,1e-6) for c in cs],r) for cs,r in shapes]
    count=sum(len(c) for cs,_ in shapes for c in cs)
    codes=sorted({m['user_data'] for m in matches});regions=[];recovered=False
    info={'input_segments':count,'cleaned_segments':count,'outline_recovered':False,'recovery_resolution':0}
    for code in codes:
        loops=None
        if count<=4000 and len(shapes)<=256:
            # Reuse vector intersections, but classify edges by the topmost
            # visible paint rather than by the monochrome union.
            try:loops=visible_loops(shapes,lambda points:labels_at(shapes,matches,points)==code)
            except ValueError as exc:
                if str(exc)=='SVG has no visible outline.':continue  # Fully occluded paint.
        if loops is None:
            if not allow_simplify:
                raise SimplificationRequired('This SVG has detailed colour boundaries. Choose Simplify & Import to continue.')
            # Recovery preserves painter order and holes, at a bounded size.
            size=2048;mask=np.zeros((size,size),bool)
            for shape,match in zip(shapes,matches):
                area=svg.rasterize([shape],size)
                mask[area]=match['user_data']==code
            if not mask.any():continue
            loops=svg_outline.trace_mask(mask);recovered=True
        if loops:
            match=next(m for m in matches if m['user_data']==code)
            regions.append((loops,match))
    if not regions:raise ValueError('SVG has no visible colour regions.')
    if len(regions)>32:raise ValueError('SVG uses more than 32 matched colours. Reduce its colours or turn off Match SVG colours.')
    info.update(outline_recovered=recovered,recovery_resolution=2048 if recovered else 0)
    return bounds,regions,info


def preflight(source,include_station=False,allow_simplify=False):
    return read_regions(source,include_station,allow_simplify)


def fit_svg(source,accuracy=50,max_parts=300,include_station=False,overrides='{}'):
    """Choose continuous backing/inlays when they improve the same-budget fit."""
    from .icon_fit import prepare_outline
    accuracy=max(0,min(100,int(accuracy)));max_parts=max(1,min(2000,int(max_parts)))
    from .preview_jobs import report
    report('Reading SVG colours')
    overrides=overrides_json(overrides)
    bounds,regions,info=read_regions(source,include_station,overrides=overrides)
    shapes,_,matches=read_paints(source,include_station,overrides)
    # Keep a small, bounded reserve for the final native-face seam audit.
    # The public limit is still the cap for the complete repaired icon.
    fitting_budget=max_parts-min(12,max_parts//25)
    from .preview_jobs import report
    report('Fitting coloured outlines')
    if len(shapes)>24:
        best=fit_layers(shapes,bounds,matches,info,accuracy,fitting_budget)
        best['fit_strategy']='source_layers'
    else:
        best=fit_regions(source,accuracy,fitting_budget,include_station,overrides)
        best['layered']=False;best['fit_strategy']='regions'
    if len(regions)<2:return repair_seams(best,regions,max_parts)
    candidates=[] if len(shapes)>24 else [('source_layers',shapes,matches)]
    # A flattened SVG may describe a frame and its inset as adjacent regions.
    # Rebuild a solid backing from their visible union, retaining transparent
    # holes. Other colours sit above it instead of carving into that backing.
    loops,_=prepare_outline(shapes)
    n=128+round(accuracy*1.28)
    areas=[int(svg.rasterize([(ls,'nonzero')],n).sum()) for ls,_ in regions]
    a=np.concatenate(loops);b=np.concatenate([np.roll(c,-1,axis=0) for c in loops]);v=b-a
    lengths=np.linalg.norm(v,axis=1);normal=np.column_stack((-v[:,1],v[:,0]))/np.maximum(lengths[:,None],1e-15)
    edge_codes=labels_at(shapes,matches,(a+b)/2+normal*1e-7)
    edge_lengths={m['user_data']:float(lengths[edge_codes==m['user_data']].sum()) for _,m in regions}
    # The colour already covering the silhouette boundary is usually the
    # useful backing (for example, an outline around a larger interior fill).
    base=max(range(len(regions)),key=lambda i:(edge_lengths[regions[i][1]['user_data']],areas[i],-i))
    backing=[(loops,'nonzero')]+[(ls,'nonzero') for i,(ls,_) in enumerate(regions) if i!=base]
    paints=[regions[base][1]]+[m for i,(_,m) in enumerate(regions) if i!=base]
    candidates.append(('backing_inlays',backing,paints))
    measure_edges(best,loops)
    for strategy,layers,paints in candidates:
        report('Fitting solid backing and inlays' if strategy=='backing_inlays' else 'Fitting paint layers')
        result=fit_layers(layers,bounds,paints,info,accuracy,fitting_budget,source_matches=matches)
        result['fit_strategy']=strategy
        measure_edges(result,loops)
        # Don't trade away visible foreground colour merely to claim fewer
        # parts. Tiny raster differences are allowed only with an actual saving.
        edge_gain=result['silhouette_edge_coverage']-best['silhouette_edge_coverage']
        if ((edge_gain>.01 and result['coverage']>=best['coverage']-.02) or
            (edge_gain>=-.005 and (result['coverage']>best['coverage']+.001 or
             (result['coverage']>=best['coverage']-.001 and result['part_count']<best['part_count'])))):
            best=result
    return repair_seams(best,regions,max_parts)


def measure_edges(result,loops):
    """Length-weighted coverage just inside the complete vector silhouette."""
    from .icon_fit import contains,panel_mask
    a=np.concatenate(loops);b=np.concatenate([np.roll(c,-1,axis=0) for c in loops]);v=b-a
    length=np.linalg.norm(v,axis=1);normal=np.column_stack((-v[:,1],v[:,0]))/np.maximum(length[:,None],1e-15)
    points=np.concatenate([a+v*t+normal*.002 for t in (.1,.3,.5,.7,.9)])
    weights=np.tile(length,5)
    valid=contains([(loops,'nonzero')],points)
    covered=np.zeros(len(points),bool)
    for panel in result['panels']:covered|=panel_mask(panel,points[:,0],points[:,1])
    result['silhouette_edge_coverage']=float(weights[covered&valid].sum()/max(1e-12,weights[valid].sum()))


def fit_components(loops,bounds,info,accuracy,budget,edge_priority=False):
    """Fit disconnected details in local coordinates, with uniform scaling.

    A small hook must not be fitted on the same coarse pixel grid as the whole
    emblem. Keep holes with their containing island, fit each island at full
    precision, then put every native rectangle back in the shared coordinates.
    """
    from .icon_fit import contains,fit_outline
    signed=[float(np.sum(c[:,0]*np.roll(c[:,1],-1)-c[:,1]*np.roll(c[:,0],-1))/2) for c in loops]
    outers=[i for i,a in enumerate(signed) if a>0]
    if not outers:outers=list(range(len(loops)))
    components={i:[loops[i]] for i in outers}
    for j,a in enumerate(signed):
        if j in components:continue
        parents=[i for i in outers if contains([([loops[i]],'nonzero')],[loops[j][0]])[0]]
        if parents:components[min(parents,key=lambda i:abs(signed[i]))].append(loops[j])
    areas={i:max(1e-12,abs(signed[i])-sum(abs(float(np.sum(c[:,0]*np.roll(c[:,1],-1)-c[:,1]*np.roll(c[:,0],-1))/2)) for c in cs[1:])) for i,cs in components.items()}
    order=sorted(components,key=lambda i:(-areas[i],i))[:budget]
    weights=np.sqrt([areas[i] for i in order]);weights/=weights.sum()
    quota=weights*(budget-len(order));counts=np.floor(quota).astype(int)+1
    for j in sorted(range(len(order)),key=lambda j:(-(quota[j]%1),j))[:budget-int(counts.sum())]:counts[j]+=1
    results={}
    def fit_one(i,cap):
        points=np.concatenate(components[i]);low=points.min(0);extent=points.max(0)-low
        span=float(max(extent));local=[(c-low)/span for c in components[i]]
        try:
            # Keep curve error in artwork coordinates. Normalizing a tiny hook
            # must not make its contour hundreds of times finer than the ring.
            tolerance=.004*(.15**(accuracy/100))/span
            r=fit_outline([(local,'nonzero')],list(extent/span),local,info,accuracy,int(cap),outline_tolerance=tolerance,optimize_fill=True)
            # Tiny quotas cannot always support both a perimeter and an
            # interior. Retain solid detail in that case, without allowing a
            # minor coverage gain to replace a completed, clean contour.
            if r['coverage']<.9 and not edge_priority:
                fill=fit_outline([(local,'nonzero')],list(extent/span),local,info,accuracy,int(cap),fill_first=True,coverage_goal=.995)
                if fill['coverage']>r['coverage']+.025:r=fill
        except ValueError as exc:
            if str(exc) not in ('Shape details are too thin. Increase accuracy or expand strokes.',
                               'No visible SVG area at this accuracy. Increase accuracy or simplify the artwork.'):raise
            return None
        r['panels']=[(x*span+low[0],y*span+low[1],w*span,a) for x,y,w,a in r['panels']]
        r['_fill_loops']=[(np.asarray(c)*span+low).tolist() for c in r['_fill_loops']]
        return r
    for i,cap in zip(order,counts):results[i]=fit_one(i,cap)
    for _ in range(2):
        for i in order:
            r=results[i]
            if r is not None and not r['unfilled']:continue
            spare=budget-sum(x['part_count'] for x in results.values() if x is not None)
            if spare<=0:break
            results[i]=fit_one(i,(r['part_count'] if r else 0)+spare)
    rows=[results[i] for i in sorted(results) if results[i] is not None]
    panels=[p for r in rows for p in r['panels']]
    if not panels:return None
    missing=len(rows)<len(components)
    return {'panels':panels,'part_count':len(panels),'coverage':0 if missing else min(r['coverage'] for r in rows),
            '_fill_loops':[c for r in rows for c in r['_fill_loops']],
            'panel_is_outline':[j<r['outline_parts'] for r in rows for j in range(r['part_count'])],
            'unfilled':missing or any(r['unfilled'] for r in rows),
            'budget_hit':missing or any(r['budget_hit'] for r in rows),
            'outline_parts':sum(r['outline_parts'] for r in rows),
            'outline_omissions':sum(r['outline_omissions'] for r in rows),
            'outline_relaxed':any(r['outline_relaxed'] for r in rows)}


def fit_regions(source,accuracy=50,max_parts=300,include_station=False,overrides='{}'):
    from .icon_fit import fit_outline,panel_mask
    accuracy=max(0,min(100,int(accuracy)));max_parts=max(1,min(2000,int(max_parts)))
    overrides=overrides_json(overrides)
    bounds,regions,info=read_regions(source,include_station,overrides=overrides)
    shapes,_,matches=read_paints(source,include_station,overrides)
    n=128+round(accuracy*1.28)
    areas=[int(svg.rasterize([(loops,'nonzero')],n).sum()) for loops,_ in regions]
    # Reserve at least one part per visible colour where the global cap allows
    # it, then allocate the remainder by sqrt(area) to retain small details.
    order=sorted(range(len(regions)),key=lambda i:(-areas[i],i))[:max_parts]
    weights=np.sqrt([max(1,areas[i]) for i in order]);weights/=weights.sum()
    quota=weights*(max_parts-len(order));budgets=np.floor(quota).astype(int)+1
    for i in sorted(range(len(order)),key=lambda i:(-(quota[i]%1),i))[:max_parts-int(budgets.sum())]:budgets[i]+=1
    results={}
    def fit_region(i,budget):
        loops,_=regions[i]
        return fit_components(loops,bounds,info,accuracy,int(budget))
    for i,budget in zip(order,budgets):results[i]=fit_region(i,budget)
    # Simple colours often need far fewer parts than their quota. Give that
    # unused capacity to incomplete regions instead of silently wasting it.
    for _ in range(2):
        for i in order:
            current=results[i]
            if current is not None and not current['unfilled']:continue
            used=sum(r['part_count'] for r in results.values() if r is not None)
            spare=max_parts-used
            if spare<=0:break
            results[i]=fit_region(i,(current['part_count'] if current else 0)+spare)
    preview=np.empty((n,n,4),np.float32);preview[:]=(.055,.065,.08,1)
    target=np.zeros((n,n),bool);covered=np.zeros_like(target)
    yy,xx=np.mgrid[:n,:n];xx=(xx+.5)/n;yy=(yy+.5)/n
    for loops,_ in regions:target|=svg.rasterize([(loops,'nonzero')],n)
    preview[target]=(.55,.19,.19,1)
    fitted=[];userdata=[];region_stats=[];edge_count=0;budget_hit=len(order)<len(regions);omissions=0;relaxed=False;unfilled=False
    for i in order:
        loops,match=regions[i];shapes=[(loops,'nonzero')]
        result=results[i]
        if result is None:
            budget_hit=True;unfilled=True;continue
        fitted.extend(result['panels']);userdata.extend([match['user_data']]*result['part_count'])
        area=np.zeros_like(target)
        for panel in result['panels']:area|=panel_mask(panel,xx,yy)
        covered|=area;preview[area]=(*srgb(match['rgb']),1)
        source_matches=read_paints(source,include_station,overrides)[2]
        source_rgbs=sorted({tuple(m['source_rgb']) for m in source_matches if m['user_data']==match['user_data']})
        region_stats.append({**match,'source_rgbs':source_rgbs,'parts':result['part_count'],'coverage':result['coverage']})
        edge_count+=result['outline_parts'];omissions+=result['outline_omissions']
        budget_hit|=result['budget_hit'];relaxed|=result['outline_relaxed'];unfilled|=result['unfilled']
    if not fitted:raise ValueError('Colour details are too thin for this part limit. Raise the limit or simplify the artwork.')
    return {**info,'panels':fitted,'panel_userdata':userdata,'part_count':len(fitted),
            'coverage':float((covered&target).sum()/max(1,target.sum())),
            'excess':float((covered&~target).sum()/max(1,target.sum())),
            'bounds':bounds,'resolution':n,'preview':preview,'outline_parts':edge_count,
            'outline_omissions':omissions,'outline_relaxed':relaxed,'unfilled':unfilled or len(order)<len(regions),
            'budget_hit':budget_hit,'color_matches':region_stats,'color_count':len(regions),
            '_layer_indices':[int(i) for i in order if results[i] is not None for _ in results[i]['panels']],
            '_outline_flags':[flag for i in order if results[i] is not None for flag in results[i]['panel_is_outline']],
            '_repair_regions':[{'code':regions[i][1]['user_data'],'layer':int(i),'loops':results[i]['_fill_loops']}
                               for i in order if results[i] is not None]}


def fit_layers(shapes,bounds,matches,info,accuracy,max_parts,source_matches=None):
    """Preserve painter order instead of fragmenting complex layered artwork.

    Background parts may extend behind foreground paint, but never outside
    their own vector path. The global cap remains strict. Coverage measures
    the correct final palette, so an exposed background cannot hide a missing
    foreground in the reported quality.
    """
    from .icon_fit import prepare_outline,fit_outline,panel_mask,prune_contained
    n=128+round(accuracy*1.28);labels=np.full((n,n),-1,np.int32)
    owners=np.full_like(labels,-1)
    for i,(shape,match) in enumerate(zip(shapes,matches)):
        area=svg.rasterize([shape],n);code=match['user_data']
        changed=area&(labels!=code)
        owners[changed]=i;labels[area]=code
    areas=np.bincount(owners[owners>=0],minlength=len(shapes))
    order=sorted(np.flatnonzero(areas),key=lambda i:(-areas[i],i))[:max_parts]
    weights=np.sqrt(areas[order]);weights/=weights.sum()
    quota=weights*(max_parts-len(order));budgets=np.floor(quota).astype(int)+1
    for j in sorted(range(len(order)),key=lambda j:(-(quota[j]%1),j))[:max_parts-int(budgets.sum())]:budgets[j]+=1
    first=None
    if len(shapes)>24 and len(order)>1:
        # The dominant visible backing establishes the outside contour. Give it
        # enough capacity to close that contour before distributing detail.
        union,_=prepare_outline(shapes)
        a=np.concatenate(union);b=np.concatenate([np.roll(c,-1,axis=0) for c in union]);v=b-a
        length=np.linalg.norm(v,axis=1);normal=np.column_stack((-v[:,1],v[:,0]))/np.maximum(length[:,None],1e-15)
        probes=(a+b)/2+normal*1e-6
        from .icon_fit import contains
        edge_owner=np.full(len(probes),-1,int)
        for i,shape in enumerate(shapes):edge_owner[contains([shape],probes)]=i
        first=max(order,key=lambda i:float(length[edge_owner==i].sum()))
        j=order.index(first) if isinstance(order,list) else list(order).index(first)
        reserve=min(max_parts,max(1,round(max_parts*.25)))
        spare=max_parts-reserve
        other=[k for k in range(len(order)) if k!=j]
        w=weights[other];q=w/w.sum()*spare
        counts=np.floor(q).astype(int)
        for k in np.argsort(-(q%1))[:spare-int(counts.sum())]:counts[k]+=1
        budgets[j]=reserve
        for k,count in zip(other,counts):budgets[k]=max(0,count)
    results={}
    from .preview_jobs import report
    for step,(i,budget) in enumerate(zip(order,budgets)):
        report(f'Fitting layer {step+1} of {len(order)}')
        if budget<=0:continue
        loops,cleanup=prepare_outline([shapes[i]])
        result=fit_components(loops,bounds,cleanup,accuracy,int(budget),edge_priority=(i==first))
        if result is not None:results[i]=result
    for _ in range(2):
        incomplete=[i for i in order if i not in results or results[i]['unfilled']]
        spare=max_parts-sum(r['part_count'] for r in results.values())
        if not incomplete or spare<=0:break
        # Balance relative error with size so a small hook is not starved while
        # nearly complete backing layers consume every reclaimed part.
        weights=np.array([areas[i]**.25*(max(.001,1-results[i]['coverage']) if i in results else 1) for i in incomplete])
        quota=weights/weights.sum()*spare;extra=np.floor(quota).astype(int)
        for j in sorted(range(len(incomplete)),key=lambda j:(-(quota[j]%1),j))[:spare-int(extra.sum())]:extra[j]+=1
        for i,increment in zip(incomplete,extra):
            if increment<=0:continue
            current=results.get(i)
            loops,cleanup=prepare_outline([shapes[i]])
            result=fit_components(loops,bounds,cleanup,accuracy,(current['part_count'] if current else 0)+int(increment),edge_priority=(i==first))
            if result is not None:results[i]=result
    fitted=[];userdata=[];depths=[];layer_indices=[];outline_flags=[];composed=np.full_like(labels,-1)
    yy,xx=np.mgrid[:n,:n];xx=(xx+.5)/n;yy=(yy+.5)/n
    total=sum(r['part_count'] for r in results.values())
    denominator=max(1,total-1+10*(len(results)-1))
    for rank,i in enumerate(sorted(results)):
        result=results[i];code=matches[i]['user_data']
        start=len(fitted)
        fitted.extend(result['panels']);userdata.extend([code]*result['part_count'])
        layer_indices.extend([int(i)]*result['part_count'])
        outline_flags.extend(result['panel_is_outline'])
        # Distinct colour layers receive a stable surface step. A much smaller
        # step within each layer keeps overlapping native textures from fighting.
        count=result['part_count']
        # Retain a practical separation between every overlapping native face.
        # Too-small within-layer offsets collapse at float precision and create
        # black pinwheel artifacts in the native textured render.
        depths.extend((start+j+10*rank)/denominator for j in range(count))
        for panel in result['panels']:composed[panel_mask(panel,xx,yy)]=code
    if not fitted:raise ValueError('Colour details are too thin for this part limit. Raise the limit or simplify the artwork.')
    # A backing panel entirely hidden by later paint contributes nothing to
    # the visible icon. Keep painter order and prove full geometric coverage.
    retained=[];removed=prune_contained(fitted,0,later_only=True,kept_indices=retained)
    userdata=[userdata[i] for i in retained];depths=[depths[i] for i in retained]
    layer_indices=[layer_indices[i] for i in retained]
    if len(shapes)>24:
        # Coarsening concave contours can protrude through an intentional hole.
        # Constrain the final rectangles to the complete original silhouette.
        from .icon_fit import Boundary,contains
        union,_=prepare_outline(shapes);boundary=Boundary(union);keep=[]
        for j,panel in enumerate(fitted):
            if boundary.inside(panel):keep.append(j);continue
            x,y,width,angle=panel
            if not contains(boundary.shapes,[(x,y)])[0]:continue
            low=0.;high=width
            for _ in range(20):
                middle=(low+high)/2
                if boundary.inside((x,y,middle,angle)):low=middle
                else:high=middle
            if low>width*.1:
                fitted[j]=(x,y,low,angle);keep.append(j)
        fitted=[fitted[j] for j in keep];userdata=[userdata[j] for j in keep]
        depths=[depths[j] for j in keep];layer_indices=[layer_indices[j] for j in keep]
        retained=[retained[j] for j in keep]
        composed[:]=-1
        for panel,code in zip(fitted,userdata):composed[panel_mask(panel,xx,yy)]=code
    target=labels>=0;covered=composed>=0;correct=target&(labels==composed)
    preview=np.empty((n,n,4),np.float32);preview[:]=(.055,.065,.08,1);preview[target]=(.55,.19,.19,1)
    region_stats=[]
    for code in sorted(set(userdata)):
        match=next(m for m in matches if m['user_data']==code)
        preview[composed==code]=(*srgb(match['rgb']),1)
        source_rgbs=sorted({tuple(m['source_rgb']) for m in (source_matches or matches) if m['user_data']==code})
        region_stats.append({**match,'source_rgbs':source_rgbs,'parts':userdata.count(code)})
    coverage=float(correct.sum()/max(1,target.sum()))
    return {**info,'panels':fitted,'panel_userdata':userdata,'panel_depths':depths,'part_count':len(fitted),
            'coverage':coverage,'excess':float((covered&~target).sum()/max(1,target.sum())),
            'silhouette_coverage':float((covered&target).sum()/max(1,target.sum())),
            'bounds':bounds,'resolution':n,'preview':preview,
            'outline_parts':sum(outline_flags[i] for i in retained),
            'outline_omissions':sum(r['outline_omissions'] for r in results.values()),
            'outline_relaxed':any(r['outline_relaxed'] for r in results.values()),'unfilled':coverage<.99,
            'budget_hit':any(r['budget_hit'] for r in results.values()),'color_matches':region_stats,
            'color_count':len({m['user_data'] for i,m in enumerate(matches) if areas[i]}),
            'layer_stats':[{'index':int(i),'parts':layer_indices.count(int(i)),'coverage':r['coverage']} for i,r in sorted(results.items())],
            'occluded_parts_removed':removed,
            'layered':True,
            '_layer_indices':layer_indices,'_outline_flags':[outline_flags[i] for i in retained],
            '_repair_regions':[{'code':matches[i]['user_data'],'layer':int(i),'loops':r['_fill_loops']}
                               for i,r in sorted(results.items())]}


def apply_userdata(base,matched):
    # Mirror Base Builder's safe palette fields; retain all other payload bits.
    color_mask=0xFFFFFF&~((1<<8)|(1<<16)|(1<<17))
    mask=color_mask|(0xFF<<24)
    return (int(base)&~mask)|(int(matched)&mask)


def repair_seams(result,regions,max_parts):
    """Spend reclaimed capacity on exposed native seams after final pruning.

    Repairs are confined to BOTH the fitted contour and the visible source
    colour. This preserves faceted edges, intentional holes and painter order.
    """
    from .preview_jobs import report
    report('Checking native panel seams')
    from .icon_fit import Boundary,contains,exposed_face_points,boundary_distances,face_segments_blocked,panel_mask,prune_contained,expand_face_to_point,enlarge_fill
    # This finishing pass addresses small residual seams. Larger omissions
    # already have a budget warning and need the main contour/fill allocation.
    if result['coverage']<.97:
        for name in ('_repair_regions','_layer_indices','_outline_flags'):result.pop(name,None)
        result.update(seam_repairs=0,seam_growth=0,seam_reclaimed=0,seam_check_complete=False)
        return result
    boundaries=[(row['code'],row['layer'],Boundary([np.asarray(c) for c in row['loops']]))
                for row in result.pop('_repair_regions',[])]
    visible={m['user_data']:Boundary(loops) for loops,m in regions}
    panels=result['panels'];codes=result['panel_userdata'];original_count=len(panels)
    layers=result.pop('_layer_indices',[r['index'] for r in result.get('layer_stats',[]) for _ in range(r['parts'])])
    if not layers:layers=[-1]*len(panels)
    paint_order=list(dict.fromkeys(layers))
    have_outline_flags='_outline_flags' in result
    outline_flags=result.pop('_outline_flags',[False]*len(panels))
    depths=[d*max(1,original_count-1) for d in result.get('panel_depths',[i/max(1,original_count-1) for i in range(original_count)])]
    added=removed=grown=0
    grown_panels=set()
    owner_boundaries={layer:boundary for _,layer,boundary in boundaries}
    class RepairBoundary:
        def __init__(self,outline,paint):self.outline=outline;self.paint=paint
        def inside(self,panel):return self.outline.inside(panel) and self.paint.inside(panel)
    def prune_layers():
        # Original parts in one paint layer share a colour and depth interval.
        # Either an earlier or later neighbour can cover a redundant part;
        # using only later parts wastes otherwise reclaimable capacity.
        nonlocal removed
        keep=set(range(len(panels)))
        for layer in sorted(set(layers)):
            if layer<0:continue
            ids=[i for i,value in enumerate(layers) if value==layer]
            group=[panels[i] for i in ids];retained=[]
            prune_contained(group,0,kept_indices=retained)
            keep.difference_update(ids[i] for i in set(range(len(ids)))-set(retained))
        if len(keep)==len(panels):return
        removed+=len(panels)-len(keep)
        retained=sorted(keep)
        for values in (panels,codes,layers,outline_flags,depths):values[:]=[values[i] for i in retained]
    def candidates():
        points=exposed_face_points(panels);found=[]
        visible_ids={code:contains(b.shapes,points) for code,b in visible.items()}
        for code,layer,boundary in boundaries:
            if code not in visible:continue
            ids=np.flatnonzero(visible_ids[code]&contains(boundary.shapes,points))
            if not len(ids):continue
            distance,nearest=boundary_distances(boundary,points[ids])
            colour_distance,_=boundary_distances(visible[code],points[ids])
            a=boundary.a[nearest];d=boundary.b[nearest]-a
            t=np.clip(np.sum((points[ids]-a)*d,axis=1)/np.maximum(np.sum(d*d,axis=1),1e-24),0,1)
            blocked=face_segments_blocked(panels,points[ids],a+d*t[:,None])
            # A calibrated native rim opens directly onto the contour. An
            # internal crack has material between it and that contour. Reserve
            # capacity for these cracks before small boundary approximations.
            for j in np.flatnonzero((distance>1e-7)&(colour_distance>1e-7)&(blocked|(distance>.002))):
                item=(float(min(distance[j],colour_distance[j])),points[ids[j]],code,layer,boundary,int(nearest[j]))
                found.append((bool(blocked[j]),item))
        return [item for _,item in sorted(found,key=lambda row:(-int(row[0]),-row[1][0]))]
    prune_layers()
    pending=candidates()
    for _ in range(min(64,max_parts)):
        if not pending:break
        accepted=False
        # First try a continuous translation/scale, keeping each previous native
        # face inside its replacement. No budget or previously filled area is lost.
        for _,point,code,_,_,_ in pending[:4]:
            neighbours=sorted((i for i,c in enumerate(codes) if c==code and layers[i] in owner_boundaries and tuple(panels[i]) not in grown_panels),
                              key=lambda i:float(np.linalg.norm(point-np.asarray(panels[i][:2]))))[:6]
            for i in neighbours:
                boundary=owner_boundaries[layers[i]]
                cluster=np.array([p for _,p,c,layer,_,_ in pending if c==code and layer==layers[i] and np.linalg.norm(p-point)<panels[i][2]*.65])
                candidate=expand_face_to_point(boundary,panels[i],cluster if len(cluster) else point)
                if candidate is None and len(cluster)>1:candidate=expand_face_to_point(boundary,panels[i],point)
                if candidate is not None:
                    panels[i]=candidate;grown_panels.add(tuple(candidate));grown+=1;accepted=True;break
            if accepted:break
        if accepted:
            prune_layers()
            pending=candidates();continue
        for distance,point,code,layer,boundary,edge_index in pending[:4]:
            edge=boundary.b[edge_index]-boundary.a[edge_index]
            tangent=math.atan2(edge[1],edge[0]);best=None
            for angle in (tangent,tangent+math.pi/2,0,math.pi/4,math.pi/2,3*math.pi/4):
                lo=0.;hi=distance*2
                for _ in range(16):
                    width=(lo+hi)/2;candidate=(*point,width,angle)
                    if boundary.inside(candidate) and visible[code].inside(candidate):lo=width
                    else:hi=width
                candidate=(*point,lo,angle)
                if best is None or lo>best[2]:best=candidate
            if best[2]<1e-8:continue
            # A crack beside an edge is a poor centre for a large rectangle.
            # Retain that first patch while sliding/growing into the interior,
            # so one piece can bridge the whole seam instead of a tiny ladder.
            expanded=[best];enlarge_fill(RepairBoundary(boundary,visible[code]),expanded,0)
            best=expanded[0]
            # A larger repair can replace already covered filler parts, even
            # when the budget is full. Stage and prove this before accepting.
            staged=panels+[best];retained=[]
            reclaimed=prune_contained(staged,0,later_only=True,kept_indices=retained)
            if len(staged)>max_parts:continue
            codes[:]=[(codes+[code])[i] for i in retained]
            layers[:]=[(layers+[layer])[i] for i in retained]
            outline_flags[:]=[(outline_flags+[False])[i] for i in retained]
            depths[:]=[(depths+[max(depths,default=0)+1])[i] for i in retained]
            panels[:]=staged;added+=1;removed+=reclaimed;accepted=True
            break
        if not accepted:break
        prune_layers()
        pending=candidates()
    count=len(panels)
    if added or grown or removed:
        # Place a repair at the top of its own paint layer, retaining the full
        # source order between different colours and the bounded height range.
        ranks={layer:i for i,layer in enumerate(paint_order)}
        order=sorted(range(count),key=lambda i:(ranks[layers[i]],depths[i]))
        for values in (panels,codes,layers,outline_flags,depths):values[:]=[values[i] for i in order]
        denominator=max(1,count-1+10*(len(paint_order)-1))
        result['panel_depths']=[(i+10*ranks[layer])/denominator for i,layer in enumerate(layers)]
        for row in result['color_matches']:row['parts']=codes.count(row['user_data'])
        for row in result.get('layer_stats',[]):
            if any(layer>=0 for layer in layers):row['parts']=layers.count(row['index'])
        if have_outline_flags:result['outline_parts']=sum(outline_flags)
        n=result['resolution'];yy,xx=np.mgrid[:n,:n];xx=(xx+.5)/n;yy=(yy+.5)/n
        labels=np.full((n,n),-1,np.int32);painted=np.full_like(labels,-1)
        for loops,match in regions:labels[svg.rasterize([(loops,'nonzero')],n)]=match['user_data']
        for panel,code in zip(panels,codes):painted[panel_mask(panel,xx,yy)]=code
        target=labels>=0;covered=painted>=0
        result['coverage']=float(((painted==labels)&target).sum()/max(1,target.sum()))
        result['excess']=float((covered&~target).sum()/max(1,target.sum()))
        if 'silhouette_coverage' in result:result['silhouette_coverage']=float((covered&target).sum()/max(1,target.sum()))
        preview=result['preview'];preview[:]=(.055,.065,.08,1);preview[target]=(.55,.19,.19,1)
        for row in result['color_matches']:preview[painted==row['user_data']]=(*srgb(row['rgb']),1)
    result['part_count']=count;result['seam_repairs']=added;result['seam_growth']=grown;result['seam_reclaimed']=removed;result['remaining_seams']=len(pending)
    result['seam_check_complete']=not pending
    result['unfilled']=result['unfilled'] or bool(pending)
    result['budget_hit']=result['budget_hit'] or (bool(pending) and count>=max_parts)
    return result
