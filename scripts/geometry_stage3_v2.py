"""Deterministic spatial checks; local XY millimetres in the 5000 x 5300 room.
Routes are conservative square swept envelopes, including occupied chair zones.
"""
import math
from collections import deque
from geometry_stage3 import corners, footprint_overlap, supported_route

ROOM=[0,0,5000,5300]
STARTS={'D06':(1200,2750),'D05':(1200,4250)}

def connected_paths(obstacles, starts, targets, forbidden=()):
    obstacles=list(obstacles)+list(forbidden)
    def free(p):
        x,y=p
        return 450<=x<=4550 and 450<=y<=4850 and not any(r[0]-450<x<r[2]+450 and r[1]-450<y<r[3]+450 for r in obstacles)
    nodes={(x,y) for x in range(450,4551,50) for y in range(450,4851,50) if free((x,y))}
    access={};paths={}
    for name,start in starts.items():
        start=tuple(start);parents={start:None} if start in nodes else {};queue=deque(parents)
        while queue:
            x,y=queue.popleft()
            for q in ((x-50,y),(x+50,y),(x,y-50),(x,y+50)):
                if q in nodes and q not in parents:parents[q]=(x,y);queue.append(q)
        for target,q in targets.items():
            q=tuple(q);key=name+':'+target;access[key]=q in parents
            if q in parents:
                path=[]
                while q is not None:path.append(q);q=parents[q]
                paths[key]=list(reversed(path))
    return {'ok':all(access.values()),'access':access,'paths':paths,'width_mm':900}

def segment_clear(start,end,boxes):
    for box in boxes:
        lo,hi=0.,1.
        for axis in range(3):
            delta=end[axis]-start[axis]
            if abs(delta)<1e-9:
                if start[axis]<box[axis] or start[axis]>box[axis+3]:lo,hi=1,0;break
            else:
                a=(box[axis]-start[axis])/delta;b=(box[axis+3]-start[axis])/delta
                lo=max(lo,min(a,b));hi=min(hi,max(a,b))
        if lo<=hi:return False
    return True

def furniture(rect,name,height=850):return {'rect':rect,'name':name,'z':height}

def make_candidate(stair_type='compact',platform_width=3100,dining_x=2600):
    count,tread=(16,170) if stair_type=='compact' else (18,260)
    half=count//2;rise=3100/count;end=900+(half-1)*tread
    steps=[]
    for i in range(1,half):
        steps.extend([{'rect':[100,end-i*tread,1000,end-(i-1)*tread],'z':i*rise,'role':'lower'},
                      {'rect':[1100,900+(i-1)*tread,2000,900+i*tread],'z':(half+i)*rise,'role':'upper'}])
    steps.append({'rect':[100,0,2000,900],'z':half*rise,'role':'landing'})
    platform=[0,0,platform_width,5300];holes=[[0,0,2060,end]]
    routes=[[1060,end,platform_width,end+1000],[1060,end,2060,4400],
            [0,3400,2060,4400],[platform_width-1000,2000,platform_width,end+1000]]
    beds=[furniture([platform_width-900,0,platform_width,2000],'Lounger_1',250),
          furniture([0,4400,2000,5300],'Lounger_2',250)]
    fixed=[furniture([0,3300,600,4500],'Kitchen',900),furniture([1200,1200,1900,1900],'Fridge',1700),
           furniture([2400,1400,4000,2250],'Sofa'),furniture([2800,0,3800,60],'TV',1600)]
    ground={}
    for mode in ('daily','guests'):
        tx=dining_x if mode=='daily' else 2900;ty=3900 if mode=='daily' else 3450
        table=[tx,ty,tx+1200,ty+800] if mode=='daily' else [tx-300,ty,tx+1500,ty+800]
        chairs=[[tx+100,ty-600,tx+550,ty],[tx+650,ty-600,tx+1100,ty],
                [tx+100,ty+800,tx+550,ty+1400],[tx+650,ty+800,tx+1100,ty+1400]]
        if mode=='guests':chairs += [[tx-900,ty+150,tx-300,ty+650],[tx+1500,ty+150,tx+2100,ty+650]]
        mode_fixed=[dict(f) for f in fixed]
        if mode=='guests':
            mode_fixed[2]=furniture([2400,1100,4000,1950],'Sofa')
        objects=mode_fixed+[furniture(table,'Table',750)]+[furniture(r,'Chair_'+str(i)) for i,r in enumerate(chairs)]
        ground[mode]={'table':table,'chairs':chairs,'objects':objects,'extra_chair_storage':'Два складных стула у южной стены под лестницей, в отдельном конверте хранения.'}
    c={'stair_type':stair_type,'position':'west','floor_z':3100,'floor_thickness':400,'sleepers':2,
       'platform':platform,'holes':holes,'beds':beds,'routes':routes,
       'platform_area_m2':(platform_width*5300-2060*end)/1e6,
       'stair':{'steps':steps,'footprint':[40,0,2060,end],'rise':rise,'risers':count,'tread':tread,'width':900,
                'slope_deg':math.degrees(math.atan(rise/tread)),'exit':[1060,end,2060,end+1000]},
       'ground':ground,'media_zone':[2400,60,4000,1400]}
    return c

def check_candidate(c):
    issues=[];p=c['platform'];holes=c['holes'];stair=c['stair'];routes=c['routes']
    if not supported_route(p,holes,routes):issues.append('Верхний метровый маршрут не полностью поддержан площадкой.')
    if any(footprint_overlap(r,b['rect']) for r in routes for b in c['beds']):issues.append('Верхний маршрут пересекает лежанку.')
    obstacles=opened_door_bounds()
    for s in stair['steps']:
        if s['z']-200<2050:
            a,b,d,e=s['rect'];obstacles.append([a-60,b,d+60,e])
    for mode,g in c['ground'].items():
        objects=g['objects'];rects=[f['rect'] for f in objects]
        collisions=[]
        for i,f in enumerate(objects):
            r=f['rect']
            if min(r[:2])<0 or r[2]>5000 or r[3]>5300:collisions.append(f['name']+': за стеной')
            if any(footprint_overlap(r,s['rect']) and s['z']-200<f['z'] for s in stair['steps']):collisions.append(f['name']+': лестница')
            for other in objects[:i]:
                if footprint_overlap(r,other['rect']):collisions.append(f['name']+': '+other['name'])
        targets={'terrace':(4550,700),'kitchen':(1150,3700),'fridge':(1550,2550),'sofa':(4500,1850),'stair':(550,2550)}
        g['circulation']=connected_paths(obstacles+rects,STARTS,targets,[[2400,60,4000,1400 if mode=='daily' else 1100]])
        g['collisions']=collisions
        if collisions or not g['circulation']['ok']:issues.append(mode+': конфликт мебели или прохода 900 мм')
        # Each occupied chair must have a 450-mm side approach connected to the circulation space.
        def small_access():
            def free(x,y):
                return 225<=x<=4775 and 225<=y<=5075 and not any(r[0]-225<x<r[2]+225 and r[1]-225<y<r[3]+225 for r in obstacles+rects)
            nodes={(x,y) for x in range(225,4776,50) for y in range(225,5076,50) if free(x,y)}
            start=(1225,2725);seen={start} if start in nodes else set();queue=deque(seen)
            while queue:
                x,y=queue.popleft()
                for q in ((x-50,y),(x+50,y),(x,y-50),(x,y+50)):
                    if q in nodes and q not in seen:seen.add(q);queue.append(q)
            reachable=[]
            for r in g['chairs']:
                edges=[(r[0]-225,(r[1]+r[3])/2),(r[2]+225,(r[1]+r[3])/2),((r[0]+r[2])/2,r[1]-225),((r[0]+r[2])/2,r[3]+225)]
                reachable.append(any(any(abs(x-u)<=50 and abs(y-v)<=50 for x,y in seen) for u,v in edges))
            return reachable
        g['chair_access_450mm']=small_access()
        if not all(g['chair_access_450mm']):issues.append(mode+': не подтверждён боковой доступ к каждому стулу')
    solids=[[s['rect'][0]-60,s['rect'][1],max(0,s['z']-200),s['rect'][2]+60,s['rect'][3],s['z']+1000] for s in stair['steps']]
    sight={}
    for name,xy in STARTS.items():
        start=(*xy,1650)
        sight[name]={'window':segment_clear(start,(4990,2500,1650),solids),
                     'terrace':segment_clear(start,(4990,700,1650),solids)}
    c['sight']=sight
    if not all(all(v.values()) for v in sight.values()):issues.append('Лестница перекрывает вид от одного из входов.')
    c['issues']=issues;c['geometric_ok']=not issues
    return c

def alternative_layout(stair_type, width, dining_x, shape='u', position='west'):
    import copy
    c=make_candidate(stair_type,width,dining_x);c['stair']['shape']=shape
    if shape!='u':
        stair=c['stair'];half=stair['risers']//2;t=stair['tread'];rise=stair['rise'];run=(half-1)*t
        if shape=='l':
            steps=[{'rect':[1100+(half-1-i)*t,0,1100+(half-i)*t,900],'z':i*rise,'role':'lower'} for i in range(1,half)]
            steps += [{'rect':[100,1000+(i-1)*t,1000,1000+i*t],'z':(half+i)*rise,'role':'upper'} for i in range(1,half)]
            steps += [{'rect':[100,0,1100,1000],'z':half*rise,'role':'landing'}]
            end=1000+run;c['holes']=[[0,0,1160+run,1000],[0,1000,1060,end]]
            stair['footprint']=[40,0,1160+run,end]
        else:
            end=(stair['risers']-1)*t
            steps=[{'rect':[100,(i-1)*t,1000,i*t],'z':i*rise,'role':'upper'} for i in range(1,stair['risers'])]
            c['holes']=[[0,0,1060,end]];stair['footprint']=[40,0,1060,end]
        stair['steps']=steps;stair['exit']=[60,end,1060,end+1000]
        c['routes']=[[60,end,width,end+1000],[60,end,1060,4400],[0,3400,2060,4400],[width-1000,2000,width,end+1000]]
        hole_area=sum((r[2]-r[0])*(r[3]-r[1]) for r in c['holes'])
        c['platform_area_m2']=(width*5300-hole_area)/1e6
    if position=='north':
        end=c['stair']['exit'][1];a=c['stair']['exit'][0]
        c['platform']=[0,end,5000,5300];c['holes']=[]
        c['beds']=[furniture([0,4400,2000,5300],'Lounger_1',250),furniture([3000,4400,5000,5300],'Lounger_2',250)]
        c['routes']=[[a,end,4000,end+1000],[a,end,a+1000,4400],[3000,end,4000,4400]]
        c['platform_area_m2']=5000*(5300-end)/1e6;c['position']='north'
    return c


def opened_door_bounds():
    import json
    from pathlib import Path
    from review_geometry import door_model, polygon_at
    spec=json.loads((Path(__file__).resolve().parents[1]/'data/house_stage2_geometry.json').read_text())
    result=[]
    for o in spec['openings']:
        if o['id'] not in ('door_kitchen_north','door_kitchen_west','door_terrace'):continue
        w=next(w for w in spec['walls'] if w['id']==o['wall'])
        ps=[p for width in o['width_range_mm'] for pos in o['position_range_mm'] for p in polygon_at(door_model(o,w,width,pos),90)]
        result.append([min(x for x,y in ps)-6600,min(y for x,y in ps)-400,max(x for x,y in ps)-6600,max(y for x,y in ps)-400])
    return result
