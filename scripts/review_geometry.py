"""Conservative door sweeps in mm; stdlib only. Tangents enclose rotation arcs."""
import math
from pathlib import Path

EPS = 1e-5


def rotate(point, degrees):
    a = math.radians(degrees)
    x, y = point
    return x*math.cos(a)-y*math.sin(a), x*math.sin(a)+y*math.cos(a)


def hull(points):
    points = sorted(set(tuple(p) for p in points))
    if len(points) < 3:
        return points
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    halves = []
    for order in (points, points[::-1]):
        half = []
        for p in order:
            while len(half)>=2 and cross(half[-2], half[-1], p)<=EPS:
                half.pop()
            half.append(p)
        halves.append(half[:-1])
    return halves[0]+halves[1]


def bounds(poly):
    return min(p[0] for p in poly), min(p[1] for p in poly), max(p[0] for p in poly), max(p[1] for p in poly)


def boxes_overlap(a, b):
    return a[0]<b[2]+EPS and b[0]<a[2]+EPS and a[1]<b[3]+EPS and b[1]<a[3]+EPS


def segment_inside(a, b, poly):
    low, high = 0.0, 1.0
    for p, q in zip(poly, poly[1:]+poly[:1]):
        dx, dy = q[0]-p[0], q[1]-p[1]
        length = math.hypot(dx, dy)
        c = dx*(a[1]-p[1])-dy*(a[0]-p[0])-EPS*length
        slope = dx*(b[1]-a[1])-dy*(b[0]-a[0])
        if abs(slope)<EPS:
            if c<=0:
                return False
        elif slope>0:
            low = max(low, -c/slope)
        else:
            high = min(high, -c/slope)
        if low>=high:
            return False
    return low<high


def intersects(a, b):
    """Strict interior overlap, including containment and projected segments."""
    if not a or not b or not boxes_overlap(bounds(a), bounds(b)):
        return False
    if len(b)<3:
        return segment_inside(b[0], b[-1], a)
    if len(a)<3:
        return segment_inside(a[0], a[-1], b)
    for poly in (a, b):
        for p, q in zip(poly, poly[1:]+poly[:1]):
            nx, ny = p[1]-q[1], q[0]-p[0]
            length = math.hypot(nx, ny)
            if length<EPS:
                continue
            av = [x*nx+y*ny for x, y in a]
            bv = [x*nx+y*ny for x, y in b]
            if min(max(av), max(bv))-max(min(av), min(bv))<=EPS*length:
                return False
    return True


def door_model(opening, wall, width=None, position=None):
    lo, hi = opening['interval_mm']
    width = hi-lo if width is None else width
    lo = lo if position is None else position
    clear_lo, clear_hi = lo+55, lo+width-55
    closed = (0 if opening['axis']=='x' else 90)+(180 if opening['hinge']=='high' else 0)
    x0, y0, x1, y1 = wall['rect_mm']
    along = clear_hi if opening['hinge']=='high' else clear_lo
    center = (y0+y1)/2 if opening['axis']=='x' else (x0+x1)/2
    pivot = (along, center) if opening['axis']=='x' else (center, along)
    sign = opening['swing_sign']
    offset = rotate((0, sign*20), closed)
    pivot = [pivot[0]+offset[0], pivot[1]+offset[1]]
    low_y, high_y = (-40, 0) if sign>0 else (0, 40)
    length = clear_hi-clear_lo-3
    return dict(pivot=pivot, closed_angle=closed, sign=sign,
                local_polygon=[(0, low_y), (length, low_y), (length, high_y), (0, high_y)],
                frame_clear_mm=clear_hi-clear_lo, leaf_length_mm=length,
                opening_width_mm=width, opening_position_mm=lo)


def polygon_at(door, angle):
    px, py = door['pivot']
    return hull([(px+x, py+y) for x, y in
                 [rotate(p, door['closed_angle']+door['sign']*angle) for p in door['local_polygon']]])


def sweep(door, start=0, stop=90, error=.25):
    radius = max(math.hypot(*p) for p in door['local_polygon'])
    maximum = math.degrees(2*math.acos(radius/(radius+error))) if radius else 90
    count = max(1, math.ceil((stop-start)/maximum))
    result = []
    px, py = door['pivot']
    for i in range(count):
        a, b = start+(stop-start)*i/count, start+(stop-start)*(i+1)/count
        factor = 1/math.cos(math.radians((b-a)/2))
        points = polygon_at(door, a)+polygon_at(door, b)
        for x, y in door['local_polygon']:
            x, y = rotate((x*factor, y*factor), door['closed_angle']+door['sign']*(a+b)/2)
            points.append((px+x, py+y))
        polygon = hull(points)
        result.append(dict(start=a, stop=b, polygon=polygon, bounds=bounds(polygon),
                           error_mm=radius*(factor-1)))
    return result


def scan_motion(door, collides):
    radius = max(math.hypot(*p) for p in door['local_polygon'])
    def interval(a, b):
        piece = sweep(door, a, b)[0]
        if not collides(piece['polygon']):
            return None
        if math.radians(b-a)*radius<=.5:
            for angle in (a, (a+b)/2, b):
                if collides(polygon_at(door, angle)):
                    return dict(status='collision', angle_deg=angle, clear_until_deg=a, interval_deg=[a, b])
            return dict(status='conditional', interval_deg=[a, b], clear_until_deg=a)
        middle = (a+b)/2
        return interval(a, middle) or interval(middle, b)
    for piece in sweep(door):
        result = interval(piece['start'], piece['stop'])
        if result:
            return result
    return dict(status='clear', clear_until_deg=90)


def first_collision(door, obstacle):
    return scan_motion(door, lambda p: intersects(p, obstacle))


def pair_collision(a, b):
    uncertain = None
    for ap in sweep(a):
        for bp in sweep(b):
            if not boxes_overlap(ap['bounds'], bp['bounds']) or not intersects(ap['polygon'], bp['polygon']):
                continue
            for aa in (ap['start'], (ap['start']+ap['stop'])/2, ap['stop']):
                for bb in (bp['start'], (bp['start']+bp['stop'])/2, bp['stop']):
                    if intersects(polygon_at(a, aa), polygon_at(b, bb)):
                        return dict(status='collision', angles_deg=[aa, bb])
            uncertain = dict(status='conditional', intervals_deg=[[ap['start'], ap['stop']], [bp['start'], bp['stop']]])
    return uncertain or dict(status='clear')


def clip_z(poly, level, keep_above):
    out = []
    for a, b in zip(poly, poly[1:]+poly[:1]):
        da, db = a[2]-level, b[2]-level
        inside_a, inside_b = (da>=0, db>=0) if keep_above else (da<=0, db<=0)
        if inside_a:
            out.append(a)
        if inside_a!=inside_b:
            t = da/(da-db)
            out.append(tuple(a[i]+t*(b[i]-a[i]) for i in range(3)))
    return out


def obstacle_from_mesh(name, vertices, faces, bottom=10, top=2045):
    if max(p[2] for p in vertices)<=bottom+EPS or min(p[2] for p in vertices)>=top-EPS:
        return None
    projected, sections = [], []
    middle = (bottom+top)/2
    for face in faces:
        polygon = [vertices[i] for i in face]
        clipped = clip_z(clip_z(polygon, bottom+EPS, True), top-EPS, False)
        if clipped:
            planar = hull([p[:2] for p in clipped])
            if planar:
                projected.append(dict(polygon=planar, bounds=bounds(planar)))
        points = []
        for p, q in zip(polygon, polygon[1:]+polygon[:1]):
            if (p[2]<middle)!=(q[2]<middle):
                t = (middle-p[2])/(q[2]-p[2])
                points.append(tuple(p[i]+t*(q[i]-p[i]) for i in range(2)))
        if len(points)==2 and math.dist(*points)>EPS:
            sections.append(points)
    if not projected:
        return None
    return dict(name=name, surfaces=projected, section=sections,
                bounds=bounds([p for surface in projected for p in surface['polygon']]))


def point_in_section(point, segments):
    x, y = point
    count = 0
    for a, b in segments:
        if (a[1]>y)!=(b[1]>y):
            xx = a[0]+(b[0]-a[0])*(y-a[1])/(b[1]-a[1])
            if xx>x:
                count += 1
    return count%2==1


def hits_obstacle(poly, obstacle):
    bb = bounds(poly)
    if not boxes_overlap(bb, obstacle['bounds']):
        return False
    for face in obstacle['surfaces']:
        if boxes_overlap(bb, face['bounds']) and intersects(poly, face['polygon']):
            return True
    return point_in_section(tuple(sum(p[i] for p in poly)/len(poly) for i in (0, 1)), obstacle['section'])


def require_scene(actual, expected):
    if Path(actual).resolve()!=Path(expected).resolve():
        raise ValueError('Wrong scene: expected '+str(expected)+', got '+str(actual))
