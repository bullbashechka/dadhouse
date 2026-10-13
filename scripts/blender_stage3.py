"""Build/verify/preview stage 3 in an isolated Blender process; input is never overwritten."""
import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'scripts'), str(ROOT/'tests')]
import blender_stage2 as base
from geometry_stage3 import (inner_profile, roof_inner, corners, footprint_overlap,
                             ground_furniture, rectangle_clearance, passes_height)
from blender_stage2_checks import measure, evaluated_vertices, hit
from review_geometry import door_model, sweep, intersects, obstacle_from_mesh, hits_obstacle

DATA = ROOT/'data/stage3'
RENDERS = ROOT/'renders/stage3'
TARGET = ROOT/'models/house_stage3.blend'
SOURCE = ROOT/'models/house_stage2_review.blend'
CONCEPTS = json.loads((DATA/'concepts.json').read_text())
MODES = {'Original':'00_Original', 'mansard':'01_Mansard', 'gable':'02_Gable', 'high_kitchen':'03_High_Kitchen'}
COMPACT_MODES={'mansard':'04_Mansard_Compact','gable':'05_Gable_Compact','high_kitchen':'06_High_Kitchen_Compact'}


def dump(name, value):
    (DATA/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reparent(col, parent):
    parents=[p for p in bpy.data.collections if col.name in p.children]
    if col.name in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.unlink(col)
    for p in parents:
        p.children.unlink(col)
    parent.children.link(col)


def register():
    base.COLS.update({c.name:c for c in bpy.data.collections})
    base.MATS.update({m.name:m for m in bpy.data.materials})


def box(name, rect, bottom, top, group, mat='Wall', role='stage3_structure'):
    obj=base.box(name,[rect[0],rect[1],bottom,rect[2],rect[3],top],group,mat,role)
    obj['stage']=3
    return obj


def extrude_profile(name, polygon, axis, lo, hi, group, mat, role):
    obj=base.prism_x(name,lo,hi,polygon,group,mat,role)
    if axis==0:
        for v in obj.data.vertices:
            v.co.x,v.co.y=v.co.y,v.co.x
        # Reflection swaps winding; rebuild normals.
        import bmesh
        bm=bmesh.new();bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
    obj['stage']=3
    return obj


def shell(name, roof, group):
    axis=roof['axis'];domain=roof['domain'];p=roof['profile']
    polygon=p+list(reversed(inner_profile(p,450)))
    obj=extrude_profile(name,polygon,axis,domain[1-axis],domain[3-axis],group,'Roof','roof')
    obj['normal_thickness_mm']=450
    return obj


def wall_parts():
    parts=[]
    for w in base.SPEC['walls']:
        a,b,c,d=w['rect_mm']
        xs=sorted({a,c,*[x for x in (400,6200,6600,11600) if a<x<c]})
        ys=sorted({b,d,*[y for y in (400,5700,6100,9600) if b<y<d]})
        for x0,x1 in zip(xs,xs[1:]):
            for y0,y1 in zip(ys,ys[1:]):
                x,y=(x0+x1)/2,(y0+y1)/2
                garage=(w['id']=='west' and y>=6100 or w['id']=='north' and x<=6200 or
                        w['id']=='cross' and x<=6200 or w['id']=='spine' and y>=6100)
                kitchen=(w['id']=='south' and x>=6600 or w['id']=='east' and y<=5700 or
                         w['id']=='cross' and x>=6600 or w['id']=='spine' and y<=5700)
                height=2200 if garage else 2800 if kitchen else 2900
                parts.append(dict(wall=w['id'],rect=[x0,y0,x1,y1],height=height))
    return parts


def roof_for_point(concept, x, y):
    if concept['family']!='high_kitchen' or (x>=6200 and y<=6600):
        return concept['roof']
    return dict(axis=1,profile=[(-500,4000),(10500,3550)],domain=[-500,-500,12500,10500])


def upper_wall(name, part, concept, group, glazing=False):
    a,b,c,d=part['rect'];bottom=part['height']+200
    axis=1 if c-a<=d-b else 0
    lo,hi=(b,d) if axis==1 else (a,c)
    cross0,cross1=(a,c) if axis==1 else (b,d)
    coord=(cross0+cross1)/2
    roof=roof_for_point(concept, (a+c)/2,(b+d)/2)
    def z(u):
        return roof_inner(roof['profile'],u if axis==roof['axis'] else coord,450)
    us={lo,hi}
    if axis==roof['axis']:
        us.update(x for x,_ in inner_profile(roof['profile'],450) if lo<x<hi)
    ps=[(u,z(u)) for u in sorted(us)]
    if min(z for _,z in ps)<bottom:
        raise RuntimeError(f'Roof cuts a wall/mauerlat at {name}: {ps}, bottom {bottom}')
    polygon=[(lo,bottom),(hi,bottom)]+list(reversed(ps))
    if glazing:
        mid=(cross0+cross1)/2
        cross0,cross1=mid-10,mid+10
    obj=extrude_profile(name,polygon,axis,cross0,cross1,group,'Glass_Stage3' if glazing else 'Proposed_Infill',
                        'upper_glazing' if glazing else 'upper_wall_proposal')
    obj['proposal_requires_review']=True
    obj['maximum_extension_mm']=max(z for _,z in ps)-bottom
    if glazing:
        def world(u,z):
            return (coord,u,z) if axis==1 else (u,coord,z)
        outline=[(lo,bottom),(hi,bottom),*reversed(ps),(lo,bottom)]
        for i,(p,q) in enumerate(zip(outline,outline[1:])):
            if (Vector(p)-Vector(q)).length>1:
                base.beam(f'{name}_Frame_{i}',world(*p),world(*q),60,60,group,'Frame','glazing_frame')
        for u in range(int(lo+1000),int(hi),1000):
            base.beam(f'{name}_Mullion_{u}',world(u,bottom),world(u,z(u)),50,50,group,'Frame','glazing_frame')


def make_furniture(prefix, group):
    for f in ground_furniture():
        rect=f['rect'];name=f['name']
        if name=='Dining_Table':
            box(prefix+name,rect,700,750,group,'Furniture','furniture')
            for x,y in corners([rect[0]+60,rect[1]+60,rect[2]-100,rect[3]-100]):
                box(prefix+name+f'_Leg_{x}_{y}',[x,y,x+40,y+40],0,700,group,'Frame','furniture')
        elif name.startswith('Chair'):
            box(prefix+name,rect,400,450,group,'Upholstery','furniture')
            y=rect[1] if rect[1]<5000 else rect[3]-50
            box(prefix+name+'_Back',[rect[0],y,rect[2],y+50],450,850,group,'Upholstery','furniture')
            for x,y in corners([rect[0]+30,rect[1]+30,rect[2]-60,rect[3]-60]):
                box(prefix+name+f'_Leg_{x}_{y}',[x,y,x+30,y+30],0,400,group,'Frame','furniture')
        elif name=='Sofa':
            box(prefix+name,rect,0,450,group,'Upholstery','furniture')
            box(prefix+name+'_Back',[rect[0],rect[1],rect[0]+150,rect[3]],450,850,group,'Upholstery','furniture')
        else:
            box(prefix+name,rect,0,f['z'],group,'Furniture','furniture')
    box(prefix+'Sink',[11100,3220,11500,3720],900,910,group,'Steel','equipment')
    box(prefix+'Hob',[11100,4230,11500,4780],900,910,group,'Frame','equipment')
    # TV attached to the outside of the stair support; does not occupy the passage.
    box(prefix+'TV',[8640,1150,8700,2150],950,1550,group,'Frame','equipment')


def make_mezzanine(concept, group):
    prefix=concept['family']+'_';layout=concept['layout'];p=layout['platform'];opening=layout['opening']
    envelope=base.collection(prefix+'Platform_Rectangular',base.COLS[group]).name
    compact=base.collection(prefix+'Platform_Compact',base.COLS[group]).name
    voids=[] if not opening else [[opening[0],opening[1],2600,opening[2],opening[3],3200]]
    floor=base.solid(prefix+'Mezzanine',[[p[0],p[1],2700,p[2],p[3],3100]],voids,envelope,'Timber','mezzanine')
    floor['structural_status']='400-mm overall envelope, including edge beam; 5-m span requires calculation'
    floor['stage']=3
    stair=layout['stair']
    solids=[[s['rect'][0],s['rect'][1],max(0,s['z']-100),s['rect'][2],s['rect'][3],s['z']] for s in stair['steps']]
    steps=base.solid(prefix+'Stair_Treads',solids,group=group,mat='Timber',role='stairs')
    steps['stage']=3;steps['clear_width_mm']=900
    # Side-mounted rails preserve clear route width; interruption at the exit.
    a,b,c,d=p
    exit_rect=stair['exit']
    if layout['position']=='north':
        edge=b-30
        segments=[((a,edge,4200),(exit_rect[0]-30,edge,4200)),
                  ((exit_rect[2]+30,edge,4200),(c,edge,4200))]
    else:
        edge=c+30
        segments=[((edge,b,4200),(edge,exit_rect[1]-30,4200)),
                  ((edge,exit_rect[3]+30,4200),(edge,d,4200))]
    for i,(start,end) in enumerate(segments):
        base.beam(prefix+f'Guard_Top_{i}',start,end,40,40,envelope,'Frame','guard')
        count=max(1,math.ceil((Vector(end)-Vector(start)).length/1000))
        for j in range(count+1):
            v=Vector(start).lerp(Vector(end),j/count)
            base.beam(prefix+f'Guard_Post_{i}_{j}',(v.x,v.y,2700),v,40,40,envelope,'Frame','guard')
        # Closed infill expresses a complete barrier, not unprotected large gaps.
        r=[min(start[0],end[0])-10,min(start[1],end[1])-10,max(start[0],end[0])+10,max(start[1],end[1])+10]
        box(prefix+f'Guard_Infill_{i}',r,3150,4150,envelope,'Glass_Stage3','guard')
    if layout['position']!='north':raise RuntimeError('Compact corner-cut option requires north layout')
    bed_front=min(bed['rect'][1] for bed in layout['beds'])
    cutouts=[[a,b,2699,a+1000,bed_front,3101],[c-1000,b,2699,c,bed_front,3101]]
    smaller=base.solid(prefix+'Mezzanine_Compact',[[a,b,2700,c,d,3100]],cutouts,compact,'Timber','mezzanine')
    smaller['stage']=3;smaller['corner_cut_area_m2']=2*1000*(bed_front-b)/1e6
    compact_edges=[((a,bed_front-30),(a+970,bed_front-30)),
                   ((a+970,bed_front-30),(a+970,b-30)),
                   ((a+970,b-30),(exit_rect[0]-30,b-30)),
                   ((exit_rect[2]+30,b-30),(c-970,b-30)),
                   ((c-970,b-30),(c-970,bed_front-30)),
                   ((c-970,bed_front-30),(c,bed_front-30))]
    for i,(s,e) in enumerate(compact_edges):
        if (Vector(s)-Vector(e)).length<1:continue
        base.beam(prefix+f'Compact_Rail_{i}',(*s,4200),(*e,4200),40,40,compact,'Frame','guard')
        for j,v in enumerate((s,e)):
            base.beam(prefix+f'Compact_Post_{i}_{j}',(*v,2700),(*v,4200),40,40,compact,'Frame','guard')
        r=[min(s[0],e[0])-10,min(s[1],e[1])-10,max(s[0],e[0])+10,max(s[1],e[1])+10]
        box(prefix+f'Compact_Infill_{i}',r,3150,4150,compact,'Glass_Stage3','guard')
    for i,bed in enumerate(layout['beds']):
        box(prefix+f'Bed_{i}',bed['rect'],3100,3100+bed['z'],group,'Upholstery','upper_furniture')
        r=bed['rect'];box(prefix+f'Pillow_{i}',[r[0]+80,r[3]-450,r[2]-80,r[3]-50],3350,3450,group,'Furniture','upper_furniture')
    turn=next(s for s in stair['steps'] if s['role']=='stair_landing')
    a,b,c,d=turn['rect'];z=turn['z']
    landing_edges=[((a-30,b-30),(c+30,b-30)),((a-30,b),(a-30,d)),((c+30,b),(c+30,d))]
    for i,(p,q) in enumerate(landing_edges):
        base.beam(prefix+f'Landing_Guard_{i}',(*p,z+1000),(*q,z+1000),40,40,group,'Frame','guard')
        for j,v in enumerate((p,q)):
            base.beam(prefix+f'Landing_Post_{i}_{j}',(*v,z-100),(*v,z+1000),40,40,group,'Frame','guard')
        r=[min(p[0],q[0])-10,min(p[1],q[1])-10,max(p[0],q[0])+10,max(p[1],q[1])+10]
        box(prefix+f'Landing_Infill_{i}',r,z+50,z+950,group,'Glass_Stage3','guard')
    # Flight handrails outside tread rectangles; supports are conceptual envelopes.
    for role in ('lower_tread','upper_tread'):
        flight=[s for s in stair['steps'] if s['role']==role]
        flight.sort(key=lambda s:s['z'])
        first,last=flight[0],flight[-1]
        for side in (0,1):
            def pt(s):
                r=s['rect']
                if layout['position']=='north':
                    return (r[0]-30 if side==0 else r[2]+30,(r[1]+r[3])/2,s['z']+1000)
                return ((r[0]+r[2])/2,r[1]-30 if side==0 else r[3]+30,s['z']+1000)
            start,end=pt(first),pt(last)
            # Sloped support is outboard of the clear tread width.
            base.beam(prefix+f'{role}_Stringer_{side}',(start[0],start[1],first['z']-90),
                      (end[0],end[1],last['z']-90),50,180,group,'Frame','stair_support')
            base.beam(prefix+f'{role}_Rail_{side}',start,end,40,40,group,'Frame','guard')
            for idx,s in enumerate(flight):
                q=pt(s)
                base.beam(prefix+f'{role}_Post_{side}_{idx}',(q[0],q[1],s['z']-100),q,30,30,group,'Frame','guard')
    for i,r in enumerate(layout['routes']):
        ob=box(prefix+f'Route_{i}',r,3110,3115,group,'Route','route_marker')
        ob.hide_render=True
        ob.hide_viewport=True
    make_furniture(prefix,group)


def build():
    if not bpy.app.background:
        raise RuntimeError('Use an isolated background process')
    if TARGET.exists():
        receipt=DATA/'build.json'
        if not receipt.exists() or digest(TARGET)!=json.loads(receipt.read_text())['scene_sha256']:
            raise RuntimeError('Target contains unrecognised edits; preserve it')
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    register()
    original=base.collection('Stage3_Original')
    reparent(bpy.data.collections['Original_Walls'],original)
    reparent(bpy.data.collections['Roof_Original'],original)
    base.material('Proposed_Infill',(.67,.56,.43))
    base.material('Furniture',(.76,.70,.59))
    base.material('Upholstery',(.36,.49,.49))
    base.material('Glass_Stage3',(.32,.53,.60))
    bs=base.MATS['Glass_Stage3'].node_tree.nodes.get('Principled BSDF')
    bs.inputs['Transmission Weight'].default_value=1
    bs.inputs['Roughness'].default_value=.1
    bs.inputs['IOR'].default_value=1.45
    base.material('Steel',(.46,.5,.53),.4,.7)
    base.material('Route',(.1,.75,.48))
    roots={'Original':original}
    parts=wall_parts()
    for concept in CONCEPTS['main']:
        family=concept['family'];root=base.collection('Stage3_'+family);roots[family]=root
        groups={suffix:base.collection(family+'_'+suffix,root).name for suffix in ('Walls','Roof','Upper','Interior')}
        solids=[[p['rect'][0],p['rect'][1],0,p['rect'][2],p['rect'][3],p['height']] for p in parts]
        walls=base.solid(family+'_Walls',solids,[base.opening_box(o) for o in base.SPEC['openings']],groups['Walls'],'Wall','walls')
        walls['stage']=3
        shell(family+'_Roof',concept['roof'],groups['Roof'])
        if family=='high_kitchen':
            for i,domain in enumerate([[-500,-500,6200,10500],[6200,6600,12500,10500]]):
                p=[(domain[1],4000-(domain[1]+500)*450/11000),(domain[3],4000-(domain[3]+500)*450/11000)]
                shell(family+f'_Low_Roof_{i}',dict(axis=1,profile=p,domain=domain),groups['Roof'])
            high=concept['roof']
            if high['axis']!=1:raise RuntimeError('Junction detailing currently requires a y-profile')
            ps=high['profile'];low=lambda y:4000-(y+500)*450/11000
            polygon=ps+[(6600,low(6600)),(-500,low(-500))]
            extrude_profile(family+'_West_Flashing',polygon,1,6190,6210,groups['Roof'],'Frame','roof_flashing')
            box(family+'_North_Flashing',[6200,6590,12500,6610],low(6600),ps[-1][1],groups['Roof'],'Frame','roof_flashing')
        # Ceilings are kept over C-L; B is open, A is explicitly left as an unoccupied roof volume.
        for room in base.SPEC['rooms']:
            if room['id'] in ('A','B'):
                continue
            ps=room['polygon_mm']
            v=[(x,y,z) for z in (2700,2900) for x,y in ps];n=len(ps)
            f=[list(reversed(range(n))),list(range(n,2*n))]+[[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]
            base.mesh_object(family+'_Ceiling_'+room['id'],v,f,groups['Walls'],'Wall','ceiling')
        for i,part in enumerate(parts):
            if part['wall'] not in ('north','south','east','west','spine','cross'):
                continue
            a,b,c,d=part['rect'];h=part['height']
            if c-a>d-b:
                r=[a,(b+d)/2-100,c,(b+d)/2+100]
            else:
                r=[(a+c)/2-100,b,(a+c)/2+100,d]
            box(family+f'_Mauerlat_{i}',r,h,h+200,groups['Upper'],'Timber','mauerlat')
            enclosure=base.solid(family+f'_Mauerlat_Enclosure_{i}',[[a,b,h,c,d,h+200]],
                                 [[r[0],r[1],h-1,r[2],r[3],h+201]],groups['Upper'],'Proposed_Infill','upper_wall_proposal')
            enclosure['stage']=3
            exterior=part['wall'] in ('north','south','east','west')
            joint=((part['wall']=='spine' and b<5700) or (part['wall']=='cross' and a>=6600))
            joint=joint or (family=='high_kitchen' and part['wall']=='spine' and b<6100)
            if exterior or joint:
                glass=part['wall']=='east' and d<=5700
                upper_wall(family+f'_Upper_{i}',part,concept,groups['Upper'],glass)
            elif part['height']==2200 and part['wall'] in ('spine','cross'):
                box(family+f'_Adjacent_Ceiling_Infill_{i}',part['rect'],2400,2900,groups['Upper'],'Proposed_Infill','upper_wall_proposal')
        make_mezzanine(concept,groups['Interior'])
        roof=concept['roof'];axis=roof['axis'];domain=roof['domain']
        for i,(u,z) in enumerate((roof['profile'][0],roof['profile'][-1])):
            r=[domain[0],u-60,domain[2],u+60] if axis==1 else [u-60,domain[1],u+60,domain[3]]
            box(family+f'_Gutter_{i}',r,z-100,z,groups['Roof'],'Frame','rainwater')
            x,y=(domain[2]+80,u) if axis==1 else (u,domain[3]+80)
            box(family+f'_Downpipe_{i}',[x-50,y-50,x+50,y+50],-500,z-100,groups['Roof'],'Frame','rainwater')
        root['status']='conditional; review upper-wall/roof supports and six-seat dining circulation'
    scene=bpy.context.scene
    scene.name='House_Stage3_Roof_Concepts'
    for layer in list(scene.view_layers)[1:]:scene.view_layers.remove(layer)
    first=scene.view_layers[0];first.name=MODES['Original']
    for key,name in MODES.items():
        layer=first if key=='Original' else scene.view_layers.new(name)
        for k,col in roots.items():
            layer.layer_collection.children[col.name].exclude=k!=key
        for family in COMPACT_MODES:
            interior=layer.layer_collection.children['Stage3_'+family].children[family+'_Interior']
            interior.children[family+'_Platform_Compact'].exclude=True
    for family,name in COMPACT_MODES.items():
        layer=scene.view_layers.new(name)
        for k,col in roots.items():layer.layer_collection.children[col.name].exclude=k!=family
        interior=layer.layer_collection.children['Stage3_'+family].children[family+'_Interior']
        interior.children[family+'_Platform_Rectangular'].exclude=True
    bpy.context.window.view_layer=scene.view_layers[MODES['Original']]
    scene['stage']=3
    scene['stage3_concepts_path']='//../data/stage3/concepts.json'
    scene['stage3_status']='Geometric concepts with explicit conditional support changes; see report.'
    scene.render.engine='BLENDER_WORKBENCH'
    scene.display.shading.light='STUDIO';scene.display.shading.studiolight_rotate_z=.35
    scene.display.shading.color_type='MATERIAL';scene.display.shading.show_shadows=False
    scene.display.shading.show_cavity=True;scene.display.shading.cavity_type='BOTH'
    scene.display.shading.background_type='WORLD';scene.world.color=(.91,.92,.93)
    scene.view_settings.view_transform='Standard'
    scene.camera=bpy.data.objects['Camera_Exterior_Front']
    scene.camera.data.ortho_scale=24
    # Raise all comparison camera targets without changing relative scale between variants.
    scene.camera.rotation_euler=(Vector((6.8,4.6,2.5))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    base.camera('Camera_Stage3_Interior',(7.85,.65,1.65),(8.6,4.8,2.0),0,24)
    base.camera('Camera_Stage3_Upper',(8.05,3.2,4.75),(9.7,4.8,3.85),0,28)
    base.camera('Camera_Stage3_Cutaway',(16,-8,10),(9.1,3.1,1.8),10)
    base.camera('Camera_Stage3_Plan',(9.1,3.05,16),(9.1,3.05,0),7)
    text=bpy.data.texts.new('STAGE3_README_RU')
    text.write('ЭТАП 3. Переключайте View Layer: 00_Original / 01_Mansard / 02_Gable / 03_High_Kitchen.\n'
               'Слои 04–06 показывают компактную площадку с вырезанными углами: 12,82 вместо 14,70 м².\n'
               'Все альтернативы условные: надстройки стен и опоры требуют согласования и расчёта.\n'
               'Кухня-гостиная: 5 × 5,3 м. Проход наверху: 2,05 м минимум при толщине крыши 450 мм.\n'
               'Площадка +3,10; низ +2,70. Основная компоновка: компактная П-образная лестница и две лежанки.\n'
               'Гараж: верх основной стены +2,20; над ним явно показана предлагаемая надстройка. Это не согласованное изменение.\n'
               'Фасадное остекление и конструктивные габариты предварительные.\n'
               'Полный отчёт: ../data/stage3/report.txt. PRD.md и TASKS.md не изменены.\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(TARGET))
    dump('build.json',dict(scene_sha256=digest(TARGET),scene_path=str(TARGET),source_sha256=digest(SOURCE),
                          blender_version=bpy.app.version_string,pid=os.getpid(),objects=len(scene.objects),
                          concepts_sha256=digest(DATA/'concepts.json')))
    print(json.dumps(dict(saved=str(TARGET),objects=len(scene.objects)),ensure_ascii=False),flush=True)


def open_target():
    bpy.ops.wm.open_mainfile(filepath=str(TARGET))
    register()
    if Path(bpy.data.filepath)!=TARGET:
        raise RuntimeError('Wrong file')


def verify():
    open_target()
    scene=bpy.context.scene;checks={};details={}
    def check(name, good, **kwargs):
        checks[name]=dict(ok=bool(good),**kwargs)
    protected=json.loads((DATA/'protected.json').read_text())
    check('protected_sources',all(digest(ROOT/p)==h for p,h in protected.items()))
    check('saved_file_digest',digest(TARGET)==json.loads((DATA/'build.json').read_text())['scene_sha256'])
    bpy.context.window.view_layer=scene.view_layers[MODES['Original']]
    original=measure(base.SPEC,ROOT)
    geometric={k:v for k,v in original['checks'].items() if not k.startswith('source_')}
    check('original_geometry_regression',all(v['ok'] for v in geometric.values()),checks=len(geometric),
          legacy_source_digest_mismatches=[e for e in original['errors'] if e.startswith('source_')])
    for family,name in MODES.items():
        layer=scene.view_layers[name];bpy.context.window.view_layer=layer;layer.update()
        visible={o.name for o in layer.objects if o.visible_get(view_layer=layer)}
        for other in MODES:
            root=bpy.data.collections['Stage3_'+other]
            owned={o.name for o in root.all_objects if not o.hide_viewport}
            check(f'{family}_isolates_{other}',bool(visible & owned) if other==family else not bool(visible & owned))
        check(f'{family}_ground_floor_kept','Floor_Slab' in visible and 'Leaf_door_terrace' in visible)
        if family=='Original':continue
        concept=next(c for c in CONCEPTS['main'] if c['family']==family);layout=concept['layout']
        roof=bpy.data.objects[family+'_Roof'];wall=bpy.data.objects[family+'_Walls']
        floor=bpy.data.objects[family+'_Mezzanine']
        v=evaluated_vertices(floor)
        check(f'{family}_floor_top',abs(max(p.z for p in v)-3.1)<.001)
        check(f'{family}_floor_bottom',abs(min(p.z for p in v)-2.7)<.001)
        v=evaluated_vertices(roof)
        check(f'{family}_ridge',abs(max(p.z for p in v)*1000-concept['roof']['ridge_z'])<1)
        check(f'{family}_old_ceiling_hidden','Ceiling_Original' not in visible)
        measured=[]
        for i,q in enumerate(layout['requirements']):
            r=q['rect'];points=corners(r)+[((r[0]+r[2])/2,(r[1]+r[3])/2)]
            values=[]
            for x,y in points:
                p=hit(roof,(x/1000,y/1000,q['z']/1000+.001),(0,0,1))
                values.append(p.z*1000-q['z'] if p is not None else -1)
            measured+=values
            check(f'{family}_route_{i}',min(values)>=2050,minimum_mm=min(values),role=q['role'])
        # Actual opening voids: cast across each wall at centre of the aperture.
        for o in base.SPEC['openings']:
            w=next(w for w in base.SPEC['walls'] if w['id']==o['wall']);a,b,c,d=w['rect_mm']
            u=sum(o['interval_mm'])/2;z=sum(o['z_mm'])/2
            origin=(u/1000,(b-20)/1000,z/1000) if o['axis']=='x' else ((a-20)/1000,u/1000,z/1000)
            direction=(0,1,0) if o['axis']=='x' else (1,0,0)
            distance=((d-b) if o['axis']=='x' else (c-a))/1000+.04
            check(f'{family}_opening_{o["id"]}',hit(wall,origin,direction,distance) is None)
        # Source room spans at 1.8 m, below reduced garage wall top.
        for roomid,x,y,width,depth in [('B',9100,3050,5000,5300),('A',3300,7850,5800,3500)]:
            for axis,expected in [(0,width),(1,depth)]:
                direction=[0,0,0];direction[axis]=1
                p=hit(wall,(x/1000,y/1000,2.15),direction)
                direction[axis]=-1;q=hit(wall,(x/1000,y/1000,2.15),direction)
                check(f'{family}_room_{roomid}_{axis}',p is not None and q is not None and abs((p-q).length*1000-expected)<1)
        door_conflicts=[]
        for o in base.SPEC['openings']:
            if o['id'] not in ('door_kitchen_north','door_kitchen_west','door_terrace'):continue
            w=next(w for w in base.SPEC['walls'] if w['id']==o['wall'])
            for width in o['width_range_mm']:
                for pos in o['position_range_mm']:
                    pieces=sweep(door_model(o,w,width,pos))
                    for f in ground_furniture():
                        if any(intersects(piece['polygon'],corners(f['rect'])) for piece in pieces):
                            door_conflicts.append(dict(door=o['id'],furniture=f['name'],width=width,position=pos))
                    for s in layout['stair']['steps']:
                        if s['z']-100<2100 and any(intersects(piece['polygon'],corners(s['rect'])) for piece in pieces):
                            door_conflicts.append(dict(door=o['id'],stair=s['role'],width=width,position=pos))
        check(f'{family}_door_sweeps',not door_conflicts,conflicts=door_conflicts)
        check(f'{family}_ground_routes',layout['ground']['ok'])
        for i,bed in enumerate(layout['beds']):
            r=bed['rect'];minimum=[];seated=[]
            for x,y in corners(r):
                pt=hit(roof,(x/1000,y/1000,(3100+bed['z']+1)/1000),(0,0,1))
                minimum.append(pt.z*1000-3100-bed['z'] if pt else -1)
            seat=[r[0],r[3]-1000,r[2],r[3]-400]
            for x,y in corners(seat):
                pt=hit(roof,(x/1000,y/1000,(3100+bed['z']+1)/1000),(0,0,1))
                seated.append(pt.z*1000-3100-bed['z'] if pt else -1)
            check(f'{family}_bed_{i}_lying_envelope',min(minimum)>=600,minimum_above_mattress_mm=min(minimum),assumption_mm=600)
            check(f'{family}_bed_{i}_seated_envelope',min(seated)>=1100,minimum_above_mattress_mm=min(seated),assumption_mm=1100)
        for thickness in (350,450):
            for platform in (300,400):
                for mauerlat in (150,200):
                    clearance=min(rectangle_clearance(concept['roof']['profile'],concept['roof']['axis'],q['rect'],q['z'],thickness) for q in layout['requirements'])
                    check(f'{family}_thickness_{thickness}_{platform}_{mauerlat}',clearance>=2050 and 3100-platform>=2700,
                          upper_minimum_mm=clearance,lower_clearance_mm=3100-platform,
                          roof_datum='fixed; closure above smaller mauerlat increases by 50 mm')
        # Validate the prescribed corridor against actual evaluated mesh surfaces,
        # including handrail posts/stringers; do not substitute bounding-box success.
        obstacles=[]
        graph=bpy.context.evaluated_depsgraph_get()
        for obj in layer.objects:
            if obj.type!='MESH' or not obj.visible_get(view_layer=layer) or obj.get('role')=='environment':continue
            ev=obj.evaluated_get(graph);mesh=ev.to_mesh()
            try:
                verts=[tuple(float(a)*1000 for a in ev.matrix_world@v.co) for v in mesh.vertices]
                if not verts or max(v[2] for v in verts)<=10 or min(v[2] for v in verts)>=2050:continue
                mesh.calc_loop_triangles()
                ob=obstacle_from_mesh(obj.name,verts,[list(t.vertices) for t in mesh.loop_triangles],10,2050)
                if ob:obstacles.append(ob)
            finally:ev.to_mesh_clear()
        ground_conflicts=[]
        for name,path in layout['ground']['paths'].items():
            for x,y in path:
                square=corners([x-449,y-449,x+449,y+449])
                found=[ob['name'] for ob in obstacles if hits_obstacle(square,ob)]
                if found:
                    ground_conflicts.append(dict(route=name,point=[x,y],objects=found));break
        check(f'{family}_actual_ground_surfaces',not ground_conflicts,conflicts=ground_conflicts)
        details[family]=dict(minimum_measured_clearance_mm=min(measured),door_conflicts=door_conflicts,
                             proposed_upper_walls=[dict(name=o.name,extension_mm=o['maximum_extension_mm']) for o in layer.objects if 'maximum_extension_mm' in o])
    for family,name in COMPACT_MODES.items():
        layer=scene.view_layers[name];bpy.context.window.view_layer=layer;layer.update()
        floor=bpy.data.objects[family+'_Mezzanine_Compact']
        check(f'{family}_compact_switch',floor.visible_get(view_layer=layer) and not bpy.data.objects[family+'_Mezzanine'].visible_get(view_layer=layer))
        layout=next(c for c in CONCEPTS['main'] if c['family']==family)['layout']
        supported=[]
        for r in layout['routes']:
            for x in (r[0]+1,(r[0]+r[2])/2,r[2]-1):
                for y in (r[1]+1,(r[1]+r[3])/2,r[3]-1):
                    p=hit(floor,(x/1000,y/1000,3.2),(0,0,-1))
                    supported.append(p is not None and abs(p.z-3.1)<.001)
        check(f'{family}_compact_route_supported',all(supported))
    # Closed, consistently oriented surfaces of every newly owned mesh.
    import bmesh
    mesh_failures=[]
    for family in COMPACT_MODES:
        for obj in bpy.data.collections['Stage3_'+family].all_objects:
            if obj.type!='MESH':continue
            bm=bmesh.new();bm.from_mesh(obj.data)
            if any(not e.is_manifold for e in bm.edges) or bm.calc_volume(signed=True)<=0:
                mesh_failures.append(obj.name)
            bm.free()
    check('new_meshes_closed_positive_volume',not mesh_failures,failures=mesh_failures)
    check('external_resources_resolve',all(i.packed_file or not i.filepath or Path(bpy.path.abspath(i.filepath)).exists() for i in bpy.data.images if i.source=='FILE'))
    # Negative geometry tests use in-memory mutations only; never save.
    bpy.context.window.view_layer=scene.view_layers[MODES['gable']]
    c=next(c for c in CONCEPTS['main'] if c['family']=='gable');roof=bpy.data.objects['gable_Roof']
    q=min(c['layout']['requirements'],key=lambda q:rectangle_clearance(c['roof']['profile'],c['roof']['axis'],q['rect'],q['z'],450))
    samples=corners(q['rect'])
    roof.location.z=-.1;bpy.context.view_layer.update()
    vals=[]
    for x,y in samples:
        p=hit(roof,(x/1000,y/1000,q['z']/1000+.001),(0,0,1));vals.append(p.z*1000-q['z'] if p else -1)
    check('negative_lowered_roof_detected',min(vals)<2050)
    roof.location.z=0;bpy.context.view_layer.update()
    result=dict(ok=all(c['ok'] for c in checks.values()),checks=checks,details=details,
                scope='Measured saved geometry; structural adequacy and final room naming remain conditional.')
    dump('validation.json',result)
    print(json.dumps(dict(ok=result['ok'],checks=len(checks),failures=[k for k,v in checks.items() if not v['ok']]),ensure_ascii=False),flush=True)
    if not result['ok']:raise RuntimeError('Stage 3 validation failed')


def preview():
    open_target();scene=bpy.context.scene
    RENDERS.mkdir(parents=True,exist_ok=True)
    scene.render.resolution_x=1600;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    manifest=[]
    for family,name in MODES.items():
        layer=scene.view_layers[name];bpy.context.window.view_layer=layer
        for vl in scene.view_layers:vl.use=vl.name==name
        scene.camera=bpy.data.objects['Camera_Exterior_Front']
        scene.render.filepath=str(RENDERS/f'{family}_exterior.png')
        bpy.ops.render.render(write_still=True,layer=name)
        manifest.append(Path(scene.render.filepath).name)
        if family=='Original':continue
        scene.camera=bpy.data.objects['Camera_Stage3_Interior']
        scene.display.shading.light='FLAT'
        scene.render.filepath=str(RENDERS/f'{family}_interior.png')
        bpy.ops.render.render(write_still=True,layer=name);manifest.append(Path(scene.render.filepath).name)
        scene.camera=bpy.data.objects['Camera_Stage3_Upper']
        scene.render.filepath=str(RENDERS/f'{family}_upper.png')
        bpy.ops.render.render(write_still=True,layer=name);manifest.append(Path(scene.render.filepath).name)
        compact_name=COMPACT_MODES[family]
        bpy.context.window.view_layer=scene.view_layers[compact_name]
        for vl in scene.view_layers:vl.use=vl.name==compact_name
        scene.camera=bpy.data.objects['Camera_Stage3_Interior']
        scene.render.filepath=str(RENDERS/f'{family}_compact_interior.png')
        bpy.ops.render.render(write_still=True,layer=compact_name);manifest.append(Path(scene.render.filepath).name)
        bpy.context.window.view_layer=layer
        for vl in scene.view_layers:vl.use=vl.name==name
        # Diagnostic cutaway from south/east, on an ephemeral loaded scene.
        changed=[]
        for group in ('Roof','Upper'):
            for o in bpy.data.collections[family+'_'+group].all_objects:
                changed.append((o,o.hide_render,o.hide_viewport));o.hide_render=True;o.hide_viewport=True
        wall=bpy.data.objects[family+'_Walls'];changed.append((wall,wall.hide_render,wall.hide_viewport));wall.hide_render=True;wall.hide_viewport=True
        layer.update()
        scene.camera=bpy.data.objects['Camera_Stage3_Cutaway']
        scene.render.filepath=str(RENDERS/f'{family}_cutaway.png')
        bpy.ops.render.render(write_still=True,layer=name);manifest.append(Path(scene.render.filepath).name)
        for o,state,vp in changed:o.hide_render=state;o.hide_viewport=vp
        scene.display.shading.light='STUDIO'
    dump('render_manifest.json',dict(scene_sha256=digest(TARGET),images=manifest,engine=scene.render.engine))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['build','verify','preview'])
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    {'build':build,'verify':verify,'preview':preview}[args.action]()
