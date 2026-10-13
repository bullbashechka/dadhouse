"""Stage-3 concept geometry. All lengths are millimetres, not building specifications."""
import itertools
import math
from collections import deque

ROOM = [6600, 400, 11600, 5700]


def supported_route(platform, holes, routes, width=1000):
    if not routes:
        return False
    for r in routes:
        if min(r[2]-r[0],r[3]-r[1])<width:
            return False
        if r[0]<platform[0] or r[1]<platform[1] or r[2]>platform[2] or r[3]>platform[3]:
            return False
        if any(footprint_overlap(r,hole) for hole in holes):
            return False
    reached={0}
    changed=True
    while changed:
        changed=False
        for i,a in enumerate(routes):
            if i not in reached:continue
            for j,b in enumerate(routes):
                if j in reached:continue
                if min(a[2],b[2])-max(a[0],b[0])>=width and min(a[3],b[3])-max(a[1],b[1])>=width:
                    reached.add(j);changed=True
    return len(reached)==len(routes)


def lines(profile, thickness=0):
    result = []
    for (a, za), (b, zb) in zip(profile, profile[1:]):
        slope = (zb - za) / (b - a)
        result.append((slope, za - slope * a - thickness * math.hypot(1, slope)))
    return result


def roof_inner(profile, coordinate, thickness):
    if not profile[0][0] <= coordinate <= profile[-1][0]:
        return -math.inf
    return min(m * coordinate + c for m, c in lines(profile, thickness))


def inner_profile(profile, thickness):
    """Intersection of inward-offset planes, with mitred convex ridge/breaks."""
    segments = lines(profile, thickness)
    xs = {profile[0][0], profile[-1][0]}
    for (m, c), (n, d) in itertools.combinations(segments, 2):
        if abs(m - n) > 1e-12:
            x = (d - c) / (m - n)
            if profile[0][0] < x < profile[-1][0]:
                xs.add(x)
    points = [(x, roof_inner(profile, x, thickness)) for x in sorted(xs)]
    out = []
    for p in points:
        while len(out) > 1:
            a, b = out[-2:]
            if abs((b[1]-a[1])*(p[0]-b[0])-(p[1]-b[1])*(b[0]-a[0])) > .01:
                break
            out.pop()
        out.append(p)
    return out


def rectangle_clearance(profile, axis, rectangle, floor_z, thickness):
    return min(roof_inner(profile, rectangle[axis], thickness),
               roof_inner(profile, rectangle[axis+2], thickness)) - floor_z


def passes_height(value):
    return math.isfinite(value) and value >= 2050 - 1e-8


def footprint_overlap(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) + 1e-7 and min(a[3], b[3]) > max(a[1], b[1]) + 1e-7


def corners(rect):
    a, b, c, d = rect
    return [(a, b), (c, b), (c, d), (a, d)]


def transform_rect(rect, position):
    ps = [(6600+u, 400+v) if position == 'north' else (11600-v, 400+u)
          for u, v in corners(rect)]
    return [min(p[0] for p in ps), min(p[1] for p in ps),
            max(p[0] for p in ps), max(p[1] for p in ps)]


def make_layout(position, stair_type, furniture, shape='u'):
    length, depth = (5000, 5300) if position == 'north' else (5300, 5000)
    risers, tread = (18, 260) if stair_type == 'ordinary' else (16, 180)
    rise = 3100 / risers
    half = risers // 2
    run = (half-1)*tread
    stair_left, width, gap = length/2-400, 900, 100
    turn_front, turn_back = 100, 1100
    end = turn_back+run
    upper_left = stair_left+width+gap
    t = lambda r: transform_rect(r, position)
    steps = []
    for i in range(1, half):
        steps.append(dict(rect=t([stair_left, end-i*tread, stair_left+width, end-(i-1)*tread]),
                          z=i*rise, role='lower_tread'))
        steps.append(dict(rect=t([upper_left, turn_back+(i-1)*tread, upper_left+width, turn_back+i*tread]),
                          z=(half+i)*rise, role='upper_tread'))
    if shape == 'l':
        corner = 3100
        upper_left = corner
        steps = [dict(rect=t([corner-run+(i-1)*tread, turn_front, corner-run+i*tread, turn_front+width]),
                      z=i*rise, role='lower_tread') for i in range(1, half)]
        steps += [dict(rect=t([corner, turn_back+(i-1)*tread, corner+width, turn_back+i*tread]),
                       z=(half+i)*rise, role='upper_tread') for i in range(1, half)]
        stair_left = corner
    turn = dict(rect=t([stair_left, turn_front, upper_left+width, turn_back]),
                z=half*rise, role='stair_landing')
    steps.append(turn)
    platform_start = end
    routes = [t([1000, end, length-1000, end+1000])]
    beds = []
    if furniture == 'loungers':
        beds = [dict(rect=t([100, depth-2000, 1000, depth]), z=250, label='Лежанка 900 × 2000'),
                dict(rect=t([length-1000, depth-2000, length-100, depth]), z=250, label='Лежанка 900 × 2000')]
        for a, b in [(1000, 2000), (length-2000, length-1000)]:
            routes.append(t([a, end, b, max(end+1000, depth-1000)]))
    else:
        bed_u = length-1900
        bed_v = depth-2150
        platform_start = min(end, bed_v-1000)
        beds = [dict(rect=t([bed_u, bed_v, length-100, depth-50]), z=500,
                     label='Кровать: внешний габарит 1800 × 2100')]
        routes += [t([bed_u, bed_v-1000, length-100, bed_v]),
                   t([bed_u-1000, bed_v-1000, bed_u, max(end+1000, depth-1000)])]
    opening = t([upper_left, platform_start, upper_left+width, end]) if platform_start < end else None
    platform = t([0, platform_start, length, depth])
    reqs = [dict(rect=r, z=3100, role='upper_route') for r in routes]
    reqs += [dict(rect=s['rect'], z=s['z'], role=s['role']) for s in steps]
    reqs.append(dict(rect=t([upper_left-100, end, upper_left+width, end+1000]), z=3100, role='exit'))
    issues = []
    if not supported_route(platform,[opening] if opening else [],routes):
        issues.append('Не подтверждён непрерывный метровый маршрут с опорой на площадку.')
    if opening and any(footprint_overlap(r, opening) for r in routes):
        issues.append('Маршрут к кровати пересекает лестничный проём; требуется другая компоновка.')
    if any(footprint_overlap(r, b['rect']) for r in routes for b in beds):
        issues.append('Маршрут наверху пересекает габарит спального места.')
    if any(b['rect'][0] < platform[0] or b['rect'][1] < platform[1] or b['rect'][2] > platform[2] or b['rect'][3] > platform[3] for b in beds):
        issues.append('Спальное место выходит за границу площадки.')
    return dict(position=position, stair_type=stair_type, furniture=furniture,
                room_mm=ROOM, floor_z=3100, sleepers=2, platform=platform, opening=opening,
                beds=beds, routes=routes, requirements=reqs, layout_issues=issues,
                platform_area_m2=((platform[2]-platform[0])*(platform[3]-platform[1])-
                                 ((opening[2]-opening[0])*(opening[3]-opening[1]) if opening else 0))/1e6,
                stair=dict(shape=shape, risers=risers, rise=rise, tread=tread, width=width, gap=gap,
                           slope_deg=math.degrees(math.atan(rise/tread)),
                           footprint=t([stair_left, turn_front, upper_left+width, end]),
                           exit=t([upper_left-100, end, upper_left+width, end+1000]), steps=steps))


def fit_profile(family, domain, requirements, symmetric=True, allowed_axes=(0, 1)):
    candidates = []
    eave = 4150 if family == 'high_kitchen' else 3550
    for axis in allowed_axes:
        a, b = domain[axis], domain[axis+2]
        ratios = [.5] if symmetric else [.25, .30, .35, .4, .45, .5, .55, .6, .65, .7, .75]
        for ratio in ratios:
            ridge = a+(b-a)*ratio
            for lower_angle in ([None] if family != 'mansard' else [45, 50, 55, 60, 65, 70, 75]):
                def shape(h):
                    if lower_angle is None:
                        return [(a, eave), (ridge, h), (b, eave)]
                    left, right = a+(ridge-a)*.4, b-(b-ridge)*.4
                    slope = math.tan(math.radians(lower_angle))
                    return [(a,eave),(left,eave+(left-a)*slope),(ridge,h),
                            (right,eave+(b-right)*slope),(b,eave)]
                low, high = eave+100, 25000
                if lower_angle is not None:
                    slope = math.tan(math.radians(lower_angle))
                    low = max(eave+(ridge-a)*.4*slope+(ridge-a)*.6*math.tan(math.radians(15)),
                              eave+(b-ridge)*.4*slope+(b-ridge)*.6*math.tan(math.radians(15)))
                    high = min(eave+(ridge-a)*slope, eave+(b-ridge)*slope)
                    if high <= low:
                        continue
                def valid(h):
                    p = shape(h)
                    return all(rectangle_clearance(p, axis, q['rect'], q['z'], 450) >= 2060 for q in requirements)
                if not valid(high):
                    continue
                for _ in range(34):
                    mid = (low+high)/2
                    if valid(mid): high=mid
                    else: low=mid
                height = math.ceil(high/10)*10
                p = shape(height)
                slopes = [math.degrees(math.atan(m)) for m, _ in lines(p)]
                if any(abs(s) > 75 for s in slopes) or not valid(height):
                    continue
                candidates.append(dict(axis=axis, profile=p, ridge_z=height, ridge_coordinate=ridge,
                                       symmetric=symmetric, slopes_deg=slopes, domain=domain))
    if not candidates:
        return None
    return min(candidates, key=lambda p: (p['ridge_z'], max(abs(s) for s in p['slopes_deg'])))


def ground_furniture():
    return [dict(name='Kitchen_Counter', rect=[11000,3000,11600,5050], z=900, label='Кухня: мойка, плита, рабочая поверхность'),
            dict(name='Fridge', rect=[10900,5050,11600,5700], z=2000, label='Холодильник'),
            dict(name='Sofa', rect=[6700,500,7550,2200], z=850, label='Диван 1700 × 850'),
            dict(name='Dining_Table', rect=[8400,4300,9600,5100], z=750, label='Стол 1200 × 800; раскладывание до 1800'),
            *[dict(name=f'Chair_{i}', rect=r, z=850, label='Стул / место посадки') for i,r in enumerate([
                [8500,3700,8950,4300],[9050,3700,9500,4300],
                [8500,5100,8950,5700],[9050,5100,9500,5700]])]]


def ground_check(layout):
    stair = layout['stair']['footprint']
    furniture = ground_furniture()
    collisions = [f['name'] for f in furniture if any(footprint_overlap(f['rect'], s['rect']) and s['z']-100 < f['z'] for s in layout['stair']['steps'])]
    six = [[8100,4300,9900,5100],[7500,4450,8100,4950],[9900,4450,10500,4950]]
    six_collisions = [r for r in six if any(footprint_overlap(r,s['rect']) and s['z']-100 < 900 for s in layout['stair']['steps'])]
    obstacles = stair_ground_obstacles(layout)+[f['rect'] for f in furniture]
    radius, step = 450, 50
    xmin, ymin, xmax, ymax = ROOM
    def free(p):
        x,y=p
        return xmin+radius <= x <= xmax-radius and ymin+radius <= y <= ymax-radius and not any(
            r[0]-radius < x < r[2]+radius and r[1]-radius < y < r[3]+radius for r in obstacles)
    nodes = {(x,y) for x in range(xmin+radius,xmax-radius+1,step)
             for y in range(ymin+radius,ymax-radius+1,step) if free((x,y))}
    targets = dict(west_entry=(7800,3150), north_entry=(7800,4600), terrace=(11150,1100),
                   kitchen=(10550,4500), sofa=(8000,1400))
    reached=set();parents={}
    start=targets['west_entry']
    if start in nodes:
        queue=deque([start]);reached.add(start)
        while queue:
            x,y=queue.popleft()
            for p in ((x-step,y),(x+step,y),(x,y-step),(x,y+step)):
                if p in nodes and p not in reached:
                    reached.add(p);parents[p]=(x,y);queue.append(p)
    access={name: point in reached for name,point in targets.items()}
    paths={}
    for name,point in targets.items():
        if point in reached:
            path=[point]
            while path[-1]!=start:path.append(parents[path[-1]])
            paths[name]=list(reversed(path))
    return dict(furniture_collisions=collisions, six_seat_stair_collisions=six_collisions,
                route_width_mm=900, grid_mm=50, access=access,paths=paths,
                ok=not collisions and not six_collisions and all(access.values()),
                method='Tread undersides below 2050 mm, rectangle furniture and 900-mm corridor; door sweeps checked separately.')


def stair_ground_obstacles(layout):
    result=[]
    for s in layout['stair']['steps']:
        if s['z']-100>=2050:continue
        r=list(s['rect'])
        axis=0 if layout['position']=='north' else 1
        r[axis]-=60;r[axis+2]+=60
        result.append(r)
    return result
