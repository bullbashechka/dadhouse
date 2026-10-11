"""Create, reopen, inspect and render a preserved stage-2 review revision."""
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
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'tests'))
import blender_stage2 as base
from blender_stage2_checks import measure, evaluated_vertices, hit
from review_geometry import door_model, obstacle_from_mesh, hull, require_scene


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')


def identity():
    return dict(pid=os.getpid(), file=bpy.data.filepath, version=bpy.app.version_string,
                scene=bpy.context.scene.name, engine=bpy.context.scene.render.engine)


def open_exact(args):
    if not bpy.data.filepath:
        bpy.ops.wm.open_mainfile(filepath=str(args.scene))
    require_scene(bpy.data.filepath, args.scene)
    if not bpy.context.scene.get('review_revision'):
        raise RuntimeError('Selected file is not a review revision')
    base.COLS.update({c.name:c for c in bpy.data.collections})
    base.MATS.update({m.name:m for m in bpy.data.materials})


def configure(args):
    base.TARGET = args.scene
    base.DATA_OUTPUT = args.output_dir
    base.RENDER_OUTPUT = args.render_dir
    base.RECEIPT = args.output_dir/'stage2_build.json'


def prepare(args):
    if args.scene.exists():
        raise RuntimeError('Revision exists; choose a new scene and matching output directories')
    if not bpy.app.background:
        raise RuntimeError('Use an isolated background process')
    protected = ['PRD.md', 'TASKS.md', 'models/house_stage1.blend',
                 'models/house_stage2.blend', 'data/house_spec.json', 'data/house_stage2_geometry.json']
    protected += [p.name for p in ROOT.glob('*.pdf')]
    hashes = {p:digest(ROOT/p) for p in protected}
    bpy.ops.wm.open_mainfile(filepath=str(args.source))
    require_scene(bpy.data.filepath, args.source)
    print(json.dumps(identity(), ensure_ascii=False), flush=True)
    before = measure(base.SPEC, ROOT)
    if not before['ok']:
        raise RuntimeError(before['errors'])
    base.COLS.update({c.name:c for c in bpy.data.collections})
    base.MATS.update({m.name:m for m in bpy.data.materials})
    upper = base.collection('Original_Upper_Openings', bpy.data.collections['Roof_Original'])
    access = bpy.data.collections['Exterior_Access']
    for obj in list(bpy.context.scene.objects):
        target = None
        if obj.name.startswith(('Glass_Original_Upper', 'Upper_Frame_', 'Upper_Mullion')):
            target = upper
        elif obj.get('role')=='canopy':
            target = access
        if target:
            for col in list(obj.users_collection):
                col.objects.unlink(obj)
            target.objects.link(obj)
    wallmap = {w['id']:w for w in base.SPEC['walls']}
    for opening in base.SPEC['openings']:
        if opening['kind']!='door':
            continue
        obj = bpy.data.objects['Leaf_'+opening['id']]
        d = door_model(opening, wallmap[opening['wall']])
        old_x = max(v.co.x for v in obj.data.vertices)
        low_y = min(p[1] for p in d['local_polygon'])/1000
        for v in obj.data.vertices:
            v.co.x = (v.co.x/old_x)*d['leaf_length_mm']/1000
            v.co.y = low_y if v.co.y<0 else low_y+.04
        obj.location = (*[v/1000 for v in d['pivot']], 0)
        obj.rotation_euler.z = math.radians(d['closed_angle']+d['sign']*opening['swing_deg'])
        obj['hinge_model']='opening-face corner; 3 mm latch clearance; 40 mm leaf; provisional'
        obj['closed_angle_deg']=d['closed_angle']
        obj['swing_sign']=d['sign']
        obj['frame_clear_width_mm']=d['frame_clear_mm']
    scene = bpy.context.scene
    scene.name = 'House_Stage2_Review'
    scene['review_revision']=True
    scene['naming_status']='C–L deferred by user; geometry included'
    note=bpy.data.texts.get('READ_ME')
    note.clear()
    note.write('Базовый дом по PDF. Геометрическая приёмка отдельно от назначений C–L.\n'
               'Двери: коробки 50 мм, монтажный зазор 5 мм, полотно 40 мм; зазор у притвора 3 мм.\n'
               'Петля условно расположена у открывающейся грани полотна. Эти размеры предварительные.\n'
               'На общих видах двери приоткрыты на 30°. Полный ход 0–90° проверен в отдельном отчёте.\n'
               'Конфликты исходного проекта не устраняются переносом стен или проёмов.\n'
               'Верхнее окно отключается с исходной крышей; навесы остаются у базового дома.\n')
    bpy.context.view_layer.update()
    after=measure(base.SPEC, ROOT)
    if not after['ok']:
        raise RuntimeError(after['errors'])
    scene.camera=bpy.data.objects['Camera_Exterior_Front']
    bpy.ops.wm.save_as_mainfile(filepath=str(args.scene))
    manifest=dict(scene_path=str(args.scene), scene_sha256=digest(args.scene),
                  source_scene=str(args.source), protected_sha256=hashes,
                  geometry_sha256=digest(base.SPEC_PATH), identity=identity(),
                  scope='geometry review; C–L names deferred', authorization='реализуй план')
    dump(args.output_dir/'manifest.json', manifest)
    dump(args.output_dir/'before_validation.json', before)
    dump(args.output_dir/'after_validation.json', after)
    print('SAVED '+str(args.scene), flush=True)


def verify(args):
    open_exact(args)
    base.verify()
    result=json.loads((args.output_dir/'stage2_validation.json').read_text())
    manifest=json.loads((args.output_dir/'manifest.json').read_text())
    extra={}
    ramp=bpy.data.objects.get('Garage_Ramp')
    extra['garage_ramp_present']=ramp is not None
    if ramp:
        rv=evaluated_vertices(ramp)
        for axis,label,lo,hi in [(0,'x',-3,0),(1,'y',6.35,9.35),(2,'z',-.6,0)]:
            extra['garage_ramp_'+label]=abs(min(p[axis] for p in rv)-lo)<=.001 and abs(max(p[axis] for p in rv)-hi)<=.001
    walls=bpy.data.objects['Walls_Original']
    wallmap={w['id']:w for w in base.SPEC['walls']}
    for o in base.SPEC['openings']:
        x0,y0,x1,y1=wallmap[o['wall']]['rect_mm']
        along=sum(o['interval_mm'])/2000
        z=sum(o['z_mm'])/2000
        p=(along,(y0+y1)/2000,z) if o['axis']=='x' else ((x0+x1)/2000,along,z)
        head=hit(walls,p,(0,0,1))
        extra[o['id']+'_head_height']=head is not None and abs(head.z-o['z_mm'][1]/1000)<=.001
        if o['z_mm'][0]>0:
            sill=hit(walls,p,(0,0,-1))
            extra[o['id']+'_sill_height']=sill is not None and abs(sill.z-o['z_mm'][0]/1000)<=.001
    roof=bpy.data.collections['Roof_Original']
    upper_names={o.name for o in bpy.data.collections['Original_Upper_Openings'].all_objects}
    extra['upper_window_owned_by_original_roof']=upper_names<=set(o.name for o in roof.all_objects) and len(upper_names)==5
    extra['canopies_owned_by_base']=all(o.name in bpy.data.collections['Base_House'].all_objects for o in bpy.context.scene.objects if o.get('role')=='canopy')
    visibility_before={o.name:o.visible_get() for o in bpy.context.scene.objects}
    roof.hide_viewport=True
    bpy.context.view_layer.update()
    extra['roof_switch_hides_upper_window']=all(not bpy.data.objects[n].visible_get() for n in upper_names)
    extra['roof_switch_keeps_ground_geometry']=all(o.visible_get() for o in bpy.context.scene.objects
        if o.get('role') in ('walls','floor','door_leaf','canopy'))
    roof.hide_viewport=False
    bpy.context.view_layer.update()
    extra['visibility_restored']=visibility_before=={o.name:o.visible_get() for o in bpy.context.scene.objects}
    extra['protected_files_unchanged']=all(digest(ROOT/p)==h for p,h in manifest['protected_sha256'].items())
    extra['saved_revision_digest']=digest(args.scene)==manifest['scene_sha256']
    result['review_checks']=extra
    result['ok']=result['ok'] and all(extra.values())
    result['geometry_verified']=result['ok']
    result['naming_deferred']=True
    result['stage_complete']=False
    dump(args.output_dir/'stage2_validation.json', result)
    print(json.dumps(dict(review_checks=extra, ok=result['ok']),ensure_ascii=False),flush=True)
    if not result['ok']:
        raise RuntimeError('Review verification failed')
    export(args)


def export(args):
    obstacles=[]
    doors={}
    depsgraph=bpy.context.evaluated_depsgraph_get()
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or obj.get('role')=='environment':
            continue
        ev=obj.evaluated_get(depsgraph)
        mesh=ev.to_mesh()
        try:
            vertices=[tuple(float(v)*1000 for v in ev.matrix_world@p.co) for p in mesh.vertices]
            mesh.calc_loop_triangles()
            faces=[list(t.vertices) for t in mesh.loop_triangles]
            if obj.get('role')=='door_leaf':
                local=[tuple(float(v)*1000 for v in p.co) for p in mesh.vertices]
                doors[obj['opening_id']]=dict(pivot=[float(v)*1000 for v in ev.matrix_world.translation[:2]],
                    closed_angle=float(obj['closed_angle_deg']),sign=int(obj['swing_sign']),
                    local_polygon=hull([p[:2] for p in local]),
                    frame_clear_mm=float(obj['frame_clear_width_mm']),
                    z_mm=[min(p[2] for p in vertices),max(p[2] for p in vertices)])
            else:
                obstacle=obstacle_from_mesh(obj.name,vertices,faces)
                if obstacle:
                    obstacle['role']=obj.get('role')
                    obstacle['opening_id']=obj.get('opening_id')
                    obstacles.append(obstacle)
        finally:
            ev.to_mesh_clear()
    dump(args.output_dir/'geometry_snapshot.json',dict(scene_path=str(args.scene),scene_sha256=digest(args.scene),
        geometry_sha256=digest(base.SPEC_PATH), doors=doors, obstacles=obstacles))


def preview(args):
    open_exact(args)
    # Russian annotation glyphs are packed into the ephemeral render scene.
    font=bpy.data.fonts.load('/System/Library/Fonts/Supplemental/Arial.ttf')
    font.pack()
    original_annotation=base.annotation
    translations={'+2.700 ceiling':'+2,700 потолок','0.000':'0,000',
        '-0.600 ground':'−0,600 земля','20 deg':'20°','28 deg':'28°','+5.320':'+5,320',
        'SECTION / KITCHEN / provisional structure':'Разрез кухни-гостиной · конструкции предварительные',
        'SECTION / GARAGE / provisional structure':'Разрез гаража · конструкции предварительные'}
    def annotation(text,position,size=.17,rotation=(math.pi/2,0,math.pi/2)):
        obj=original_annotation(translations.get(text,text),position,size,rotation)
        obj.data.font=font
        return obj
    base.annotation=annotation
    base.RENDER_OUTPUT=args.render_dir/'raw'
    base.preview()
    dump(base.RENDER_OUTPUT/'render_manifest.json',dict(scene_path=str(args.scene),scene_sha256=digest(args.scene),
        images={p.name:digest(p) for p in base.RENDER_OUTPUT.glob('*.png')},engine=bpy.context.scene.render.engine))


def finish_geometry(args):
    open_exact(args)
    manifest=json.loads((args.output_dir/'manifest.json').read_text())
    if digest(args.scene)!=manifest['scene_sha256']:
        raise RuntimeError('Preserve manually changed revision')
    if not bpy.data.objects.get('Garage_Ramp'):
        vertices=[(x,y,z) for y in (6350,9350) for x,z in [(-3000,-600),(0,-600),(0,0)]]
        obj=base.mesh_object('Garage_Ramp',vertices,[[2,1,0],[3,4,5],[0,1,4,3],[1,2,5,4],[2,0,3,5]],
                            'Exterior_Access','Plinth','access')
        obj['source']='PDF page 1, garage access ramp; dimensions reconstructed'
        obj['assumption']='3000 mm run, 3000 mm width; rise 600 mm to floor; provisional'
    bpy.context.view_layer.update()
    result=measure(base.SPEC,ROOT)
    if not result['ok']:
        raise RuntimeError(result['errors'])
    bpy.data.texts['READ_ME'].write('Пандус гаража по фасаду: длина ≈3000 мм, ширина 3000 мм по воротам; подъём 600 мм. Длина и конструкция предварительные.\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(args.scene))
    manifest['scene_sha256']=digest(args.scene)
    manifest['additional_assumptions']=['Garage ramp run 3000 mm reconstructed from facade; width 3000 mm, rise 600 mm.']
    dump(args.output_dir/'manifest.json',manifest)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','finish_geometry','verify','test','preview'])
    parser.add_argument('--scene',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--render-dir',type=Path,required=True)
    parser.add_argument('--source',type=Path,default=ROOT/'models/house_stage2.blend')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    for name in ('scene','output_dir','render_dir','source'):
        setattr(args,name,getattr(args,name).resolve())
    args.output_dir.mkdir(parents=True,exist_ok=True)
    args.render_dir.mkdir(parents=True,exist_ok=True)
    configure(args)
    if args.action=='test':
        open_exact(args)
        base.negative_tests()
    else:
        globals()[args.action](args)


if __name__=='__main__':
    main()
