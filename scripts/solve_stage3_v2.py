"""Finite, deterministic revision search. Never modifies accepted v1 assets."""
import argparse, hashlib, itertools, json, math
from pathlib import Path
from geometry_stage3_v2 import *
from geometry_stage3 import rectangle_clearance, roof_inner, inner_profile, lines
from review_geometry import door_model,sweep,intersects
ROOT=Path(__file__).resolve().parents[1]

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def world(r):return [r[0]+6600,r[1]+400,r[2]+6600,r[3]+400]
def parts(spec):
    result=[]
    for w in spec['walls']:
        a,b,c,d=w['rect_mm'];xs=sorted({a,c,*[x for x in (400,6200,6600,11600) if a<x<c]});ys=sorted({b,d,*[y for y in (400,5700,6100,6600,9600) if b<y<d]})
        for x0,x1 in zip(xs,xs[1:]):
            for y0,y1 in zip(ys,ys[1:]):
                x,y=(x0+x1)/2,(y0+y1)/2
                garage=w['id']=='west' and y>=6100 or w['id']=='north' and x<=6200 or w['id']=='cross' and x<=6200 or w['id']=='spine' and y>=6100
                kitchen=w['id']=='south' and x>=6600 or w['id']=='east' and y<=5700 or w['id']=='cross' and x>=6600 or w['id']=='spine' and y<=5700
                result.append({'wall':w['id'],'rect':[x0,y0,x1,y1],'height':2200 if garage else 2800 if kitchen else 2900})
    return result

def door_check(c,spec):
    conflicts=[]
    for o in spec['openings']:
        if o['id'] not in ('door_kitchen_north','door_kitchen_west','door_terrace'):continue
        w=next(w for w in spec['walls'] if w['id']==o['wall'])
        motions=[sweep(door_model(o,w,width,pos)) for width in o['width_range_mm'] for pos in o['position_range_mm']]
        for mode,g in c['ground'].items():
            obs=[(f['name'],world(f['rect'])) for f in g['objects']]+[(s['role'],world(s['rect'])) for s in c['stair']['steps'] if s['z']-200<2100]
            for name,r in obs:
                if any(intersects(piece['polygon'],corners(r)) for motion in motions for piece in motion):conflicts.append([mode,o['id'],name])
    return conflicts

def requirements(c):
    qs=[{'rect':world(r),'z':3100,'role':'upper_route'} for r in c['routes']]
    qs += [{'rect':world(s['rect']),'z':s['z'],'role':'stair'} for s in c['stair']['steps']]
    for b in c['beds']:
        r=b['rect'];qs.append({'rect':world(r),'z':3350+600-2050,'role':'lying_600_above_mattress'})
        seated=[r[0],r[1]+1000,r[2],r[3]] if r[3]-r[1]>r[2]-r[0] else [r[0]+1000,r[1],r[2],r[3]]
        qs.append({'rect':world(seated),'z':3350+1100-2050,'role':'seated_1100_above_mattress'})
    return qs

def fit(family,c,wall_parts):
    domain=[-500,-500,12500,10500] if family!='high_kitchen' else [6200,-500,12500,6600]
    qs=requirements(c)
    supports=[{'rect':p['rect'],'z':p['height']+200-2050} for p in wall_parts if family!='high_kitchen' or p['rect'][0]>=6200 and p['rect'][3]<=6100]
    results=[]
    for axis,eave,ratio in itertools.product((0,1),(3250,3500,3750,4000,4250,4500),(.35,.4,.45,.5,.55,.6,.65,.7,.75)):
        a,b=domain[axis],domain[axis+2];ridge=a+(b-a)*ratio;platform=world(c['platform'])
        if not platform[axis]<=ridge<=platform[axis+2]:continue
        for angle in ((45,55,65) if family=='mansard' else (None,)):
            def profile(h):
                if angle is None:return [(a,eave),(ridge,h),(b,eave)]
                left=a+(ridge-a)*.4;right=b-(b-ridge)*.4;m=math.tan(math.radians(angle))
                return [(a,eave),(left,eave+(left-a)*m),(ridge,h),(right,eave+(b-right)*m),(b,eave)]
            lo=eave+100;hi=16000
            if angle:
                m=math.tan(math.radians(angle));lo=max(eave+(ridge-a)*(.4*m+.6*math.tan(math.radians(15))),eave+(b-ridge)*(.4*m+.6*math.tan(math.radians(15))))
                hi=min(eave+(ridge-a)*m,eave+(b-ridge)*m)
            def valid(h):
                p=profile(h)
                return all(rectangle_clearance(p,axis,q['rect'],q['z'],450)>=2060 for q in qs+supports)
            if hi<=lo or not valid(hi):continue
            for _ in range(24):
                mid=(lo+hi)/2
                if valid(mid):hi=mid
                else:lo=mid
            h=math.ceil(hi/10)*10;p=profile(h)
            if not valid(h) or any(abs(math.degrees(math.atan(m)))>75 for m,_ in lines(p)):continue
            clearance=min(rectangle_clearance(p,axis,q['rect'],q['z'],450) for q in qs if q['role'] in ('upper_route','stair'))
            results.append({'domain':domain,'axis':axis,'profile':p,'ridge_z':h,'eave_z':eave,'symmetric':ratio==.5,
                            'slopes_deg':[math.degrees(math.atan(m)) for m,_ in lines(p)],'minimum_clearance_mm':clearance})
    if not results:return None
    results.sort(key=lambda p:(p['ridge_z'],p['eave_z'],not p['symmetric']))
    main=results[0];sym=next((p for p in results if p['symmetric']),None)
    if sym and sym['ridge_z']-main['ridge_z']<200:main=sym
    return {'roof':main,'symmetric':sym,'lowest':results[0],'profile_candidates':len(results)}

def main(revision):
    out=ROOT/'data'/revision;out.mkdir(parents=True,exist_ok=True)
    def dump(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    protected=[ROOT/'PRD.md',ROOT/'TASKS.md',ROOT/'models/house_stage2_review.blend',ROOT/'models/house_stage3.blend',ROOT/'data/house_stage2_geometry.json',ROOT/'data/house_spec.json',*ROOT.glob('*.pdf'),*ROOT.glob('*.png')]
    protected += list((ROOT/'data/stage3').glob('*'))+list((ROOT/'renders/stage3').glob('*'))
    if not (out/'protected.json').exists():dump('protected.json',{str(p.relative_to(ROOT)):digest(p) for p in protected if p.is_file()})
    spec=json.loads((ROOT/'data/house_stage2_geometry.json').read_text());wall_parts=parts(spec)
    layouts=[]
    for stair,width,tx,shape,pos in itertools.product(('compact','ordinary'),(3100,3200,3300),(2500,2600,2700),('u','l','straight'),('west','north')):
        c=check_candidate(alternative_layout(stair,width,tx,shape,pos));c['id']=f'{pos}_{stair}_{shape}_{width}_{tx}'
        c['door_conflicts']=door_check(c,spec) if c['geometric_ok'] else []
        if c['door_conflicts']:c['issues'].append('Конфликт с открыванием двери.');c['geometric_ok']=False
        layouts.append(c)
    viable=sorted((c for c in layouts if c['geometric_ok']),key=lambda c:(c['platform_area_m2'],c['stair']['slope_deg'],c['id']))
    print('Layouts:',len(layouts),'passing:',len(viable),flush=True)
    selected=[]
    for family in ('mansard','gable','high_kitchen'):
        fits=[]
        for c in viable[:6]:
            p=fit(family,c,wall_parts)
            if p:fits.append((c,p))
        if not fits:raise RuntimeError('No geometric candidate for '+family+'; preserve outputs and inspect constraints')
        c,p=min(fits,key=lambda q:(q[0]['platform_area_m2'],q[1]['roof']['ridge_z'],q[0]['stair']['slope_deg']))
        roof=p['roof'];low=[(u,z-(300 if 0<i<len(roof['profile'])-1 else 0)) for i,(u,z) in enumerate(roof['profile'])]
        lower_min=min(rectangle_clearance(low,roof['axis'],q['rect'],q['z'],450) for q in requirements(c) if q['role'] in ('upper_route','stair'))
        selected.append({'family':family,'layout':c,**p,'requirements':requirements(c),'status':'conditional_wall_extensions',
                         'lower_300mm':{'profile':low,'minimum_mm':lower_min,'passes_height':lower_min>=2050},
                         'approval_required':['Надстройки над стенами гаража и гостиной','Опирание и конструктивные габариты'],
                         'entry_experience':'Оба входа под антресолью; высокий объём раскрывается перед восточным остеклением.'})
        print(family,roof['ridge_z'],c['id'],flush=True)
    # Keep rejected search evidence compact; no duplicated route paths per rejected layout.
    matrix=[{k:c[k] for k in ('id','position','stair_type','platform_area_m2','geometric_ok','issues','door_conflicts')} for c in layouts]
    dump('concepts.json',{'schema_version':2,'revision':revision,'main':selected,'layouts':matrix,'walls':wall_parts,
         'assumptions':{'floor_mm':3100,'roof_thickness_mm':[350,450],'platform_thickness_mm':[300,400],'mauerlat_mm':[150,200],
                        'upper_route_mm':1000,'lower_route_mm':900,'chair_side_access_mm':450,'headroom_mm':2050,
                        'entry_views':['D06','D05'],'scope':'Finite rigid U/L/straight placements. Rejections do not establish general impossibility.',
                        'low_garage':'Основные концепции требуют повышения верхнего объёма. Строго низкий гараж не подтверждён и не подменён подписью 2,20 м.',
                        'later_comparisons':['garage_height','roof_height_symmetry','stairs','mezzanine_size_entry_sequence','panoramic_openings','terrace_cover','seating','guardrail']}})
    dump('search_summary.json',{'layouts':len(layouts),'spatially_passing':len(viable),'main':[{ 'family':s['family'],'ridge_mm':s['roof']['ridge_z'],'platform_m2':s['layout']['platform_area_m2']} for s in selected]})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--revision',default='stage3_v2',choices=['stage3_v2']);main(p.parse_args().revision)
