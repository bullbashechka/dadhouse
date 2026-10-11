"""Audit measured door meshes and continuous parameter envelopes, in mm."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

from geometry_stage2 import boundary_mesh
from review_geometry import (bounds, boxes_overlap, door_model, hits_obstacle,
    hull, intersects, obstacle_from_mesh, pair_collision, scan_motion, sweep)

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wall_obstacle(spec, opening_id, interval):
    wallmap={w['id']:w for w in spec['walls']}
    solids=[[w['rect_mm'][0],w['rect_mm'][1],w['z_mm'][0],
             w['rect_mm'][2],w['rect_mm'][3],w['z_mm'][1]] for w in spec['walls']]
    voids=[]
    for o in spec['openings']:
        x0,y0,x1,y1=wallmap[o['wall']]['rect_mm']
        lo,hi=interval if o['id']==opening_id else o['interval_mm']
        z0,z1=o['z_mm']
        if o['axis']=='x':
            x0,x1=lo,hi
            y0,y1=y0-1,y1+1
        else:
            y0,y1=lo,hi
            x0,x1=x0-1,x1+1
        voids.append([x0,y0,z0,x1,y1,z1])
    v,f=boundary_mesh(solids,voids)
    return obstacle_from_mesh('Walls_Original',v,f)


def frame_obstacles(opening,wall,position,width):
    x0,y0,x1,y1=wall['rect_mm']
    low=position+5
    high=position+width-5
    result=[]
    for suffix,a,b in [('L',low,low+50),('R',high-50,high)]:
        rect=([a,(y0+y1)/2-50,5,b,(y0+y1)/2+50,2095] if opening['axis']=='x' else
              [(x0+x1)/2-50,a,5,(x0+x1)/2+50,b,2095])
        v,f=boundary_mesh([rect])
        result.append(obstacle_from_mesh('Frame_'+opening['id']+'_'+suffix,v,f))
    return result


def audit_motion(model,obstacles):
    all_points=[p for piece in sweep(model) for p in piece['polygon']]
    bbox=bounds(all_points)
    nearby=[o for o in obstacles if boxes_overlap(bbox,o['bounds'])]
    conflicts=[]
    for obstacle in nearby:
        result=scan_motion(model,lambda poly: hits_obstacle(poly,obstacle))
        if result['status']!='clear':
            conflicts.append(dict(obstacle=obstacle['name'],**result))
    return dict(status='collision' if any(c['status']=='collision' for c in conflicts) else
                'conditional' if conflicts else 'clear',conflicts=conflicts,
                clear_until_deg=min([c['clear_until_deg'] for c in conflicts]+[90]))


def envelope(models):
    count=max(len(sweep(model)) for model in models)
    result=[]
    for i in range(count):
        a,b=90*i/count,90*(i+1)/count
        poly=hull([point for m in models for p in sweep(m,a,b) for point in p['polygon']])
        result.append(dict(polygon=poly,bounds=bounds(poly),start=a,stop=b))
    return result


def range_envelope_hits(pieces,obstacles):
    hits=set()
    for p in pieces:
        for o in obstacles:
            if boxes_overlap(p['bounds'],o['bounds']) and hits_obstacle(p['polygon'],o):
                hits.add(o['name'])
    return sorted(hits)


def run(scene,out):
    spec_path=ROOT/'data/house_stage2_geometry.json'
    spec=json.loads(spec_path.read_text())
    snapshot=json.loads((out/'geometry_snapshot.json').read_text())
    if Path(snapshot['scene_path']).resolve()!=scene.resolve() or snapshot['scene_sha256']!=sha(scene):
        raise ValueError('Snapshot belongs to another scene or revision')
    if snapshot['geometry_sha256']!=sha(spec_path):
        raise ValueError('Geometry register changed')
    wallmap={w['id']:w for w in spec['walls']}
    rows=[]
    variants={}
    envelopes={}
    for index,o in enumerate(x for x in spec['openings'] if x['kind']=='door'):
        key=o['id']
        actual=snapshot['doors'][key]
        nominal=audit_motion(actual,snapshot['obstacles'])
        w0=o['interval_mm'][1]-o['interval_mm'][0]
        p0=o['interval_mm'][0]
        ws=sorted(set(o['width_range_mm']+[w0]))
        ps=sorted(set(o['position_range_mm']+[p0]))
        samples=[]
        models=[]
        static=[x for x in snapshot['obstacles'] if x['name']!='Walls_Original' and x.get('opening_id')!=key]
        for width,position in itertools.product(ws,ps):
            model=door_model(o,wallmap[o['wall']],width,position)
            models.append(model)
            if width==w0 and position==p0:
                audit=nominal
            else:
                obstacles=static+[wall_obstacle(spec,key,[position,position+width])]
                obstacles+=frame_obstacles(o,wallmap[o['wall']],position,width)
                audit=audit_motion(model,obstacles)
            samples.append(dict(width_mm=width,position_mm=position,**audit))
        # At every angle the panel's along-wall span stays within its own aperture.
        # sqrt((clear-3)^2+40^2) < clear proves latch clearance for every width.
        # Moving host-jamb material can therefore be removed over the union aperture
        # when testing the continuous uncertainty envelope against other obstacles.
        smallest_clear=min(ws)-110
        jamb_proof=math.hypot(smallest_clear-3,40)<smallest_clear
        envelope_walls=wall_obstacle(spec,key,[min(ps),max(ps)+max(ws)])
        pieces=envelope(models)
        uncertain_hits=range_envelope_hits(pieces,static+[envelope_walls])
        statuses={s['status'] for s in samples}
        range_status=('collision' if 'collision' in statuses else
                      'conditional' if uncertain_hits or 'conditional' in statuses or not jamb_proof else 'clear')
        frame_width=actual['frame_clear_mm']
        from review_geometry import polygon_at
        opened=polygon_at(actual,90)
        axis=0 if o['axis']=='x' else 1
        leaf_projection=max(p[axis] for p in opened)-min(p[axis] for p in opened)
        rows.append(dict(label='Д'+str(index+1).zfill(2),id=key,opening_width_mm=w0,
            width_range_mm=o['width_range_mm'],position_mm=p0,position_range_mm=o['position_range_mm'],
            nominal=nominal,frame_clear_mm=frame_width,clear_width_at_90_mm=frame_width-leaf_projection,
            clear_width_range_at_90_mm=[min(ws)-150,max(ws)-150],
            attained_angle_deg=nominal['clear_until_deg'],
            range_status=range_status,range_envelope_obstacles=uncertain_hits,
            host_jamb_clearance_proved=jamb_proof,scenarios=samples,model=actual))
        variants[key]=models
        envelopes[key]=pieces
        print(key,nominal['status'],'range',range_status,flush=True)
    pairs=[]
    for a,b in itertools.combinations(rows,2):
        nominal=pair_collision(a['model'],b['model'])
        possible=any(boxes_overlap(ap['bounds'],bp['bounds']) and intersects(ap['polygon'],bp['polygon'])
                     for ap in envelopes[a['id']] for bp in envelopes[b['id']])
        range_result=dict(status='clear')
        if possible:
            range_result=dict(status='conditional')
            for am,bm in itertools.product(variants[a['id']],variants[b['id']]):
                result=pair_collision(am,bm)
                if result['status']=='collision':
                    range_result=dict(**result,parameters_a={k:am[k] for k in ('opening_width_mm','opening_position_mm')},
                        parameters_b={k:bm[k] for k in ('opening_width_mm','opening_position_mm')})
                    break
        pairs.append(dict(doors=[a['id'],b['id']],labels=[a['label'],b['label']],nominal=nominal,range=range_result))
    result=dict(scene_path=str(scene),scene_sha256=sha(scene),spec_sha256=sha(spec_path),
        doors_checked=len(rows),pairs_checked=len(pairs),door_review_complete=len(rows)==14 and len(pairs)==91,
        angle_range_deg=[0,90],sweep_error_mm=.25,collision_angle_resolution_at_tip_mm=.5,
        method='Evaluated world-space mesh surfaces clipped to leaf height; projected surfaces and solid containment; circumscribed tangent sweep envelopes. Independent angles for pairs. Continuous affine width/position envelopes, with witness samples.',
        assumptions=['Коробка 50 мм, монтажный зазор 5 мм, полотно 40 мм, зазор у притвора 3 мм.',
            'Положение петли у открывающейся грани полотна предварительное; ручки и фурнитура не заданы.',
            'Ширина при 90° — геометрический просвет проёма. Полный маршрут и мебель относятся к следующим этапам.',
            'Новые минимальные нормативные ширины не назначались. Механизм ворот не проверялся.'],
        doors=rows,pairs=pairs,
        nominal_conflicts=[r['label'] for r in rows if r['nominal']['status']!='clear'],
        uncertain_doors=[r['label'] for r in rows if r['range_status']!='clear'],
        pair_conflicts=[p['labels'] for p in pairs if p['nominal']['status']!='clear' or p['range']['status']!='clear'])
    (out/'door_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('doors','pairs','method','assumptions')},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--scene',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    run(args.scene.resolve(),args.output_dir.resolve())
