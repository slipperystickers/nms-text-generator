"""Bounded outline recovery for dense or numerically troublesome SVG unions.

The normal path uses vector union. Recovery scan-converts the painted union at
high resolution, traces closed contours (including holes), and simplifies those
contours before vector panel fitting. It never fits panels to individual pixels.
"""
import numpy as np
from . import svg_geometry


def simplify_open(points, tolerance):
    """Iterative RDP: densely exported paths must not exhaust Python's stack."""
    points = np.asarray(points, float)
    if len(points) <= 2:
        return points
    keep = np.zeros(len(points), bool)
    keep[[0, -1]] = True
    pending = [(0, len(points) - 1)]
    while pending:
        start, end = pending.pop()
        if end <= start + 1:
            continue
        v = points[end] - points[start]
        section = points[start:end + 1]
        t = np.clip((section - points[start]) @ v / max(v @ v, 1e-24), 0, 1)
        distances = np.sum((section - (points[start] + t[:, None] * v)) ** 2, axis=1)
        i = int(distances.argmax())
        if distances[i] > tolerance * tolerance:
            split = start + i
            keep[split] = True
            pending.extend(((start, split), (split, end)))
    return points[keep]


def simplify_loop(points, tolerance):
    points = np.asarray(points, float)
    if len(points) < 4:
        return points
    i = int(np.argmax(np.linalg.norm(points - points[0], axis=1)))
    first = simplify_open(points[:i + 1], tolerance)
    second = simplify_open(np.concatenate((points[i:], points[:1])), tolerance)
    result = np.concatenate((first[:-1], second[:-1]))
    # Do not erase a small island or hole, even if it is below the tolerance.
    return result if len(result) >= 3 else points


def trace_mask(mask):
    """Marching squares with integer endpoint identities; material on the left.

    Ambiguous diagonal contacts keep foreground islands separate. Padding closes
    artwork touching its tightly cropped bounds. Integer keys avoid the rounded
    float endpoint cracks that can occur in a large vector intersection graph.
    """
    height, width = mask.shape
    padded = np.pad(mask.astype(np.uint8), 1)
    cases = (padded[:-1, :-1] + 2 * padded[:-1, 1:]
             + 4 * padded[1:, 1:] + 8 * padded[1:, :-1])
    top, right, bottom, left = (1, 0), (2, 1), (1, 2), (0, 1)
    routes = {1: [(top, left)], 2: [(right, top)], 3: [(right, left)],
              4: [(bottom, right)], 5: [(top, left), (bottom, right)],
              6: [(bottom, top)], 7: [(bottom, left)], 8: [(left, bottom)],
              9: [(top, bottom)], 10: [(right, top), (left, bottom)],
              11: [(right, bottom)], 12: [(left, right)],
              13: [(top, right)], 14: [(left, top)]}
    stride = 2 * (width + 2)
    outgoing = {}
    for case, segments in routes.items():
        yy, xx = np.nonzero(cases == case)
        for p, q in segments:
            starts = (2 * yy + p[1]) * stride + 2 * xx + p[0]
            ends = (2 * yy + q[1]) * stride + 2 * xx + q[0]
            if len(outgoing) + len(starts) > 200000:
                raise ValueError('SVG contains too many tiny details for a responsive preview.')
            outgoing.update(zip(starts.tolist(), ends.tolist()))
    unused = set(outgoing)
    loops = []
    for first in outgoing:
        if first not in unused:
            continue
        node = first
        points = []
        while node in unused:
            unused.remove(node)
            y, x = divmod(node, stride)
            points.append(((x - 1) / (2 * width), (y - 1) / (2 * height)))
            node = outgoing[node]
        if node != first:
            raise ValueError('Could not reconstruct a closed SVG outline.')
        if len(points) >= 3:
            loops.append(np.asarray(points))
    if not loops:
        raise ValueError('No visible SVG detail at the recovery resolution.')
    return loops


def recover(shapes, size=2048):
    """Recover the union at a fixed resolution, independent of the part budget."""
    mask = svg_geometry.rasterize(shapes, size)
    raw = trace_mask(mask)
    # Less than one recovery pixel: smooth stair steps without erasing islands.
    loops = [simplify_loop(c, .65 / size) for c in raw]
    if sum(map(len, loops)) > 12000:
        raise ValueError('SVG still has too many separate outline details after automatic cleanup. Try exporting a simpler silhouette.')
    return loops, {'outline_recovered': True, 'recovery_resolution': size,
                   'recovered_segments': sum(map(len, loops))}


def rebuild_svg(source, with_colors=False, strengthen=False, size=2048):
    """Trace the visible artwork into a new, self-contained SVG, offline.

    This is a bounded recovery path for dense exporter geometry. It does not
    invent missing content or execute external resources. Unsupported artwork
    still gets the reader's actionable error. Colour mode traces the topmost
    visible paint, so white cutouts do not become black silhouette fills.
    """
    from xml.etree.ElementTree import Element,SubElement,tostring
    parsed=svg_geometry.read_svg(source,with_colors=with_colors,rebuild=True)
    shapes,bounds=parsed[:2]
    if with_colors:
        paints=parsed[2];labels=np.full((size,size),-1,np.int32)
        colors=list(dict.fromkeys(tuple(p) for p in paints))
        if len(colors)>64:raise ValueError('Rebuilding supports up to 64 solid colours. Reduce colours or turn off Match colours.')
        for shape,paint in zip(shapes,paints):
            labels[svg_geometry.rasterize([shape],size)]=colors.index(tuple(paint))
        masks=((labels==i,'#'+''.join(f'{round(c*255):02x}' for c in color)) for i,color in enumerate(colors))
    else:masks=((svg_geometry.rasterize(shapes,size),'#020202'),)
    root=Element('svg',xmlns='http://www.w3.org/2000/svg',viewBox=f'0 0 {size} {size}')
    segments=0;regions=0
    for mask,paint in masks:
        if not mask.any():continue
        if strengthen:
            # Explicit opt-in: grow the visible ink by two recovery pixels.
            # This helps traced hairlines without filling enclosed regions.
            padded=np.pad(mask,2)
            mask=np.logical_or.reduce([padded[2+y:2+y+size,2+x:2+x+size]
                                       for y in range(-2,3) for x in range(-2,3) if x*x+y*y<=4])
        loops=[simplify_loop(loop,.65/size) for loop in trace_mask(mask)]
        segments+=sum(map(len,loops));regions+=len(loops)
        if segments>12000:raise ValueError('Rebuilt SVG still has too many details. Reduce small marks in the original artwork.')
        commands=['M'+' L'.join(f'{x*size:.4f},{y*size:.4f}' for x,y in loop)+' Z' for loop in loops]
        SubElement(root,'path',{'fill':paint,'fill-rule':'nonzero','d':' '.join(commands)})
    if not regions:raise ValueError('No visible SVG features could be traced.')
    rebuilt=tostring(root,encoding='unicode')
    if len(rebuilt.encode('utf-8'))>svg_geometry.MAX_BYTES:raise ValueError('Rebuilt SVG exceeds the import size limit.')
    return rebuilt,{'rebuilt':True,'rebuild_resolution':size,'rebuild_segments':segments,
                    'rebuild_regions':regions,'strengthened_lines':strengthen}
