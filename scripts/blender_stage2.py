"""Stage 2: isolated Blender build, verify, preview, and negative geometry tests.

Run with Blender --background --offline-mode --python-exit-code 1 --python
scripts/blender_stage2.py -- ACTION. Build requires --factory-startup.
"""
import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'tests'))
from geometry_stage2 import boundary_mesh, door_pose
from stage1 import sha256,validate_spec
from blender_stage2_checks import measure

SPEC_PATH=ROOT/'data/house_stage2_geometry.json'
TARGET=ROOT/'models/house_stage2.blend'
RECEIPT=ROOT/'data/stage2_build.json'
DATA_OUTPUT=ROOT/'data'
RENDER_OUTPUT=ROOT/'renders/stage2'
SPEC=json.loads(SPEC_PATH.read_text())
COLS={}
MATS={}


def save_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def collection(name,parent=None):
    c=bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    COLS[name]=c
    return c


def material(name,color,roughness=.7,metal=0):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1)
    mat.use_nodes=True
    bs=mat.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(*color,1)
    bs.inputs['Roughness'].default_value=roughness
    bs.inputs['Metallic'].default_value=metal
    MATS[name]=mat
    return mat


def mesh_object(name,vertices,faces,group,mat='Wall',role='structure',solid=True):
    mesh=bpy.data.meshes.new(name+'_Mesh')
    mesh.from_pydata([[v/1000 for v in p] for p in vertices],[],faces)
    mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free()
    obj=bpy.data.objects.new(name,mesh)
    COLS[group].objects.link(obj)
    obj.data.materials.append(MATS[mat])
    obj['stage']=2;obj['role']=role;obj['check_solid']=solid
    return obj


def solid(name,boxes,voids=(),group='Fixed',mat='Wall',role='structure'):
    v,f=boundary_mesh(boxes,voids)
    return mesh_object(name,v,f,group,mat,role)


def box(name,bounds,group='Fixed',mat='Wall',role='structure'):
    return solid(name,[bounds],group=group,mat=mat,role=role)


def prism_x(name,x0,x1,yz,group,mat,role='structure'):
    n=len(yz)
    v=[(x,y,z) for x in (x0,x1) for y,z in yz]
    faces=[list(reversed(range(n))),list(range(n,2*n))]
    faces += [[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]
    return mesh_object(name,v,faces,group,mat,role)


def beam(name,a,b,width,depth,group='Original_Structure',mat='Timber',role='illustrative_structure'):
    a,b=Vector(a),Vector(b)
    obj=box(name,[-width/2,-depth/2,0,width/2,depth/2,(b-a).length],group,mat,role)
    obj.location=a/1000
    obj.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
    return obj


def roof_z(y):
    r=SPEC['roof'];dy=y-r['ridge_y_mm']
    angle=r['slope_north_deg'] if dy>=0 else r['slope_south_deg']
    return r['ridge_z_mm']-abs(dy)*math.tan(math.radians(angle))


def wall_boxes():
    return [[w['rect_mm'][0],w['rect_mm'][1],w['z_mm'][0],w['rect_mm'][2],w['rect_mm'][3],w['z_mm'][1]] for w in SPEC['walls']]


def opening_box(o):
    w=next(w for w in SPEC['walls'] if w['id']==o['wall'])
    x1,y1,x2,y2=w['rect_mm'];lo,hi=o['interval_mm'];z0,z1=o['z_mm']
    if o['axis']=='x':x1,x2=lo,hi;y1-=1;y2+=1
    else:y1,y2=lo,hi;x1-=1;x2+=1
    return [x1,y1,z0,x2,y2,z1]


def add_opening(o):
    w=next(w for w in SPEC['walls'] if w['id']==o['wall'])
    x1,y1,x2,y2=w['rect_mm'];lo,hi=o['interval_mm'];z0,z1=o['z_mm']
    # Local u runs along the aperture; v is across the wall.
    def local_box(name,u0,v0,bottom,u1,v1,top,mat,role):
        b=[u0,(y1+y2)/2+v0,bottom,u1,(y1+y2)/2+v1,top] if o['axis']=='x' else [(x1+x2)/2+v0,u0,bottom,(x1+x2)/2+v1,u1,top]
        ob=box(name,b,'Openings',mat,role);ob['opening_id']=o['id'];return ob
    frame=60 if o['kind']=='window' else 50
    gap=5;depth=80 if o['kind']=='window' else 100
    base=o['id']
    local_box('Frame_'+base+'_L',lo+gap,-depth/2,z0+gap,lo+gap+frame,depth/2,z1-gap,'Frame','opening_frame')
    local_box('Frame_'+base+'_R',hi-gap-frame,-depth/2,z0+gap,hi-gap,depth/2,z1-gap,'Frame','opening_frame')
    local_box('Frame_'+base+'_Top',lo+gap+frame,-depth/2,z1-gap-frame,hi-gap-frame,depth/2,z1-gap,'Frame','opening_frame')
    clear_lo,clear_hi=lo+gap+frame,hi-gap-frame
    if o['kind']=='window':
        local_box('Frame_'+base+'_Sill',clear_lo,-depth/2,z0+gap,clear_hi,depth/2,z0+gap+frame,'Frame','opening_frame')
        local_box('Glass_'+base,clear_lo,-3,z0+gap+frame,clear_hi,3,z1-gap-frame,'Glass','glass')
        mid=(lo+hi)/2
        local_box('Mullion_'+base,mid-25,-depth/2,z0+gap+frame,mid+25,depth/2,z1-gap-frame,'Frame','opening_frame')
    elif o['kind']=='gate':
        local_box('Leaf_'+base,clear_lo,-20,z0+10,clear_hi,20,z1-gap-frame,'Gate','gate')
        for i in range(1,7):
            z=z0+(z1-z0)*i/7
            local_box('Gate_Joint_'+str(i),clear_lo,-23,z-4,clear_hi,-20,z+4,'Frame','detail')
    else:
        # Door width is its actual modelled panel width. Default view shows schematic opening.
        ob=box('Leaf_'+base,[0,-20,z0+10,clear_hi-clear_lo,20,z1-gap-frame],'Openings','Door','door_leaf')
        center=(y1+y2)/2 if o['axis']=='x' else (x1+x2)/2
        pos,angle=door_pose(o['axis'],clear_lo,clear_hi,center,o['hinge'],o['swing_sign'],o['swing_deg'])
        ob.location=(pos[0]/1000,pos[1]/1000,0)
        ob.rotation_euler.z=math.radians(angle)
        ob['opening_id']=base;ob['clear_frame_width_mm']=clear_hi-clear_lo
        ob['opening_angle_degrees']=o['swing_deg'];ob['pose_status']=o['swing_status']


def setup():
    scene=bpy.context.scene
    scene.name='House_Stage2_Original'
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1;scene.unit_settings.length_unit='METERS'
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o,do_unlink=True)
    base=collection('Base_House')
    for n in ('Fixed','Original_Walls','Openings','Exterior_Access'):
        collection(n,base)
    roofs=collection('Roofs');orig=collection('Roof_Original',roofs)
    for n in ('Original_Shell','Original_Upper_Walls','Original_Ceiling','Original_Structure'):
        collection(n,orig)
    for n in ('Roof_Mansard','Roof_Gable','Roof_High_Kitchen'):collection(n,roofs)
    for n in ('Mezzanines','Stairs','Furniture','Lighting','Cameras','Diagnostics'):collection(n)
    for n,c in [('Wall',(.76,.75,.70)),('Roof',(.105,.13,.15)),('Frame',(.07,.085,.095)),
                ('Glass',(.24,.43,.51)),('Floor',(.58,.54,.46)),('Plinth',(.34,.36,.36)),
                ('Timber',(.42,.26,.13)),('Door',(.38,.32,.23)),('Gate',(.3,.33,.34)),
                ('Ground',(.76,.77,.76)),('Ink',(.035,.06,.08))]:
        material(n,c)
    scene.world.color=(.7,.7,.7)
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.75,.8,.9,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7
    scene.render.engine='BLENDER_WORKBENCH'
    scene.display.shading.light='STUDIO'
    scene.display.shading.color_type='MATERIAL'
    scene.display.shading.show_shadows=True
    scene.display.shading.show_cavity=True
    scene.display.shading.cavity_type='BOTH'
    scene.display.shading.show_object_outline=True
    scene.display.shading.background_type='WORLD'
    scene.world.color=(.91,.91,.89)
    scene.render.image_settings.file_format='PNG'
    scene.render.resolution_percentage=100
    scene.view_settings.view_transform='Standard'
    scene['house_spec_path']='//../data/house_spec.json'
    scene['stage2_geometry_path']='//../data/house_stage2_geometry.json'
    scene['stage2_geometry_sha256']=sha256(SPEC_PATH)
    scene['stage']=2;scene['active_house_variant']='Original'
    scene['naming_status']='A/B confirmed; C-L await owner mapping'


def build_roof():
    r=SPEC['roof'];a,b=r['y_mm'];cy=r['ridge_y_mm'];t=r['thickness_mm']
    yz=[(a,roof_z(a)),(cy,roof_z(cy)),(b,roof_z(b)),
        (b,roof_z(b)-t),(cy,roof_z(cy)-t),(a,roof_z(a)-t)]
    prism_x('Roof_Original_Shell',*r['x_mm'],yz,'Original_Shell','Roof','roof')
    def wallprofile(a,b):
        top=[(a,roof_z(a)-t)]
        if a<cy<b:top.append((cy,roof_z(cy)-t))
        top.append((b,roof_z(b)-t))
        return [(a,2900),(b,2900),*reversed(top)]
    prism_x('Gable_West',0,400,wallprofile(0,10000),'Original_Upper_Walls','Wall','upper_wall')
    east=prism_x('Gable_East',11600,12000,wallprofile(0,10000),'Original_Upper_Walls','Wall','upper_wall')
    prism_x('Eave_Wall_South',400,11600,wallprofile(0,400),'Original_Upper_Walls','Wall','upper_wall')
    prism_x('Eave_Wall_North',400,11600,wallprofile(9600,10000),'Original_Upper_Walls','Wall','upper_wall')
    # Existing triangular upper glazing, height marks from façade; horizontal shape reconstructed.
    triangle=[(1100,3130),(5300,3130),(4250,3980)]
    cutter=prism_x('Upper_Window_Cutter',11590,12010,triangle,'Diagnostics','Glass','cutter')
    bpy.context.view_layer.objects.active=east
    mod=east.modifiers.new('Original triangular opening','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    prism_x('Glass_Original_Upper',11897,11903,triangle,'Openings','Glass','glass')
    for i,(p,q) in enumerate(zip(triangle,triangle[1:]+triangle[:1])):
        beam('Upper_Frame_'+str(i),(11900,*p),(11900,*q),60,60,'Openings','Frame','opening_frame')
    beam('Upper_Mullion',(11900,4250,3130),(11900,4250,3980),50,50,'Openings','Frame','opening_frame')
    # Two source-section schemes, not a calculated truss layout/spacing specification.
    for index,x in enumerate((3300,9800)):
        low,high=200,9800;zc=2975
        beam(f'Truss_{index}_Tie',(x,low,zc),(x,high,zc),100,150)
        beam(f'Truss_{index}_Rafter_S',(x,low,roof_z(low)-195),(x,cy,roof_z(cy)-195),100,150)
        beam(f'Truss_{index}_Rafter_N',(x,cy,roof_z(cy)-195),(x,high,roof_z(high)-195),100,150)
        beam(f'Truss_{index}_King',(x,cy,zc),(x,cy,roof_z(cy)-195),100,100)
        beam(f'Truss_{index}_Diagonal_S',(x,2700,zc),(x,cy,4770),100,100)
        beam(f'Truss_{index}_Diagonal_N',(x,cy,4770),(x,8200,zc),100,100)


def build_access():
    # South porch x=3200..5400; north x=6250..8450; terrace aligned to printed chain.
    for n,x0,x1,y0,y1 in [('South',3200,5400,-1900,0),('North',6250,8450,10000,11900)]:
        # Landing shortened where the four-riser stair is located, inside the drawn porch footprint.
        sy=1 if n=='North' else -1
        near=10000 if sy==1 else 0
        lo,hi=sorted((near,near+sy*700))
        box('Porch_'+n,[x0,lo,-600,x1,hi,-20],'Exterior_Access','Plinth','access')
        for i in range(3):
            ystart=near+sy*(700+i*300);yend=ystart+sy*300
            box(f'Porch_{n}_Step_{i}',[x0+400,min(ystart,yend),-600,x1-400,max(ystart,yend),-165-i*145],
                'Exterior_Access','Plinth','access')
        # Side cheeks/plinths and railings shown on elevations.
        for j,x in enumerate((x0+100,x1-100)):
            box(f'Porch_{n}_Cheek_{j}',[x-100,y0,-600,x+100,y1,-20],'Exterior_Access','Plinth','access')
            beam(f'Porch_{n}_Rail_{j}',(x,y0,900),(x,y1,900),65,65,'Exterior_Access','Frame','railing')
            yc=near+sy*1800
            post=box(f'Porch_{n}_Post_{j}',[x-45,yc-45,-20,x+45,yc+45,2300],'Exterior_Access','Frame','post')
            for vertex in post.data.vertices:
                if vertex.co.z>0:
                    vertex.co.z=(2520-abs(vertex.co.y*1000-near)*.16)/1000
        # Canopy pitches away from wall; 80-mm placeholder depth.
        yz=[(near,2600),(near+sy*2000,2280),(near+sy*2000,2200),(near,2520)]
        prism_x('Canopy_'+n,x0-100,x1+100,yz,'Original_Shell','Roof','canopy')
    box('Terrace',[12000,-50,-600,15000,6150,-20],'Exterior_Access','Plinth','access')
    # Recessed stair footprint at the south-east corner: 1400 along Y, 1200 along X.
    terrace=bpy.data.objects.get('Terrace')
    bpy.data.objects.remove(terrace,do_unlink=True)
    solid('Terrace',[[12000,-50,-600,15000,6150,-20]],[[13800,350,-600,15000,1750,-20]],
          'Exterior_Access','Plinth','access')
    for i in range(3):
        box('Terrace_Step_'+str(i),[13800+i*300,350,-600,14100+i*300,1750,-165-i*145],
            'Exterior_Access','Plinth','access')
    for i,y in enumerate((100,3050,6000)):
        post=box('Terrace_Post_'+str(i),[14850,y-50,-20,14950,y+50,2300],'Exterior_Access','Frame','post')
        for vertex in post.data.vertices:
            if vertex.co.z>0:
                vertex.co.z=(2520-(vertex.co.x*1000-11800)*320/3400)/1000
    for i,(y0,y1) in enumerate(((100,350),(1750,6000))):
        beam('Terrace_Rail_'+str(i),(14900,y0,900),(14900,y1,900),65,65,'Exterior_Access','Frame','railing')
    for i,y in enumerate((100,6000)):
        beam('Terrace_End_Rail_'+str(i),(12100,y,900),(14900,y,900),65,65,'Exterior_Access','Frame','railing')
    # Terrace canopy is a ruled panel sloping east; direct vertex construction.
    verts=[(x,y,z) for dz in (0,-80) for x,z0 in ((11800,2600),(15200,2280)) for y in (-200,6300) for z in (z0+dz,)]
    mesh_object('Canopy_Terrace',verts,[[0,2,3,1],[4,5,7,6],[0,1,5,4],[2,6,7,3],[0,4,6,2],[1,3,7,5]],
                'Original_Shell','Roof','canopy')


def camera(name,position,target,scale=18,lens=35):
    data=bpy.data.cameras.new(name);obj=bpy.data.objects.new(name,data)
    COLS['Cameras'].objects.link(obj)
    obj.location=position;obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    data.type='ORTHO' if scale else 'PERSP';data.ortho_scale=scale or 18;data.lens=lens
    data.clip_start=.05;data.clip_end=200
    return obj


def setup_cameras():
    camera('Camera_Exterior_Front',(24,-23,17),(6.8,4.6,1.6),23)
    camera('Camera_Facade_South',(7,-25,2.4),(7,5,2.4),19)
    camera('Camera_Facade_North',(7,35,2.4),(7,5,2.4),19)
    camera('Camera_Facade_East',(35,5,2.4),(7,5,2.4),17)
    camera('Camera_Facade_West',(-25,5,2.4),(7,5,2.4),17)
    camera('Camera_Section_Kitchen',(30,5,2.1),(9.8,5,2.1),14)
    camera('Camera_Section_Garage',(30,5,2.1),(3.3,5,2.1),14)
    camera('Camera_Interior_Kitchen',(10.8,1,1.65),(7.5,5.5,1.45),0,30)
    camera('Camera_Cutaway',(24,-23,22),(6.5,4.6,1),22)
    bpy.context.scene.camera=bpy.data.objects['Camera_Exterior_Front']
    for name,pos,power,size in [('Area_Key',(5,-3,14),2000,8),('Area_Fill',(15,10,10),1400,7)]:
        data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
        ob=bpy.data.objects.new(name,data);COLS['Lighting'].objects.link(ob);ob.location=pos
        ob.rotation_euler=(Vector((6,5,0))-ob.location).to_track_quat('-Z','Y').to_euler()


def build():
    if not bpy.app.background or bpy.data.filepath:
        raise RuntimeError('Build only in a fresh isolated background process')
    errors=validate_spec(json.loads((ROOT/'data/house_spec.json').read_text()))
    if errors:raise RuntimeError(errors)
    target=TARGET
    if target.exists():
        old=json.loads(RECEIPT.read_text()) if RECEIPT.exists() else {}
        if old.get('scene_sha256')!=sha256(target):
            target=TARGET.with_name('house_stage2_revision.blend')
            if target.exists():raise RuntimeError('Preserve manual revisions; new revision path occupied')
    print(json.dumps(dict(pid=os.getpid(),version=bpy.app.version_string,file=bpy.data.filepath,action='build')))
    setup()
    solid('Walls_Original',wall_boxes(),[opening_box(o) for o in SPEC['openings']],'Original_Walls','Wall','walls')
    box('Floor_Slab',[0,0,-200,12000,10000,0],'Fixed','Floor','floor')
    solid('Plinth_Original',[[0,0,-600,12000,10000,-200]],[[400,400,-600,11600,9600,-200]],'Fixed','Plinth','plinth')
    solid('Ceiling_Original',[[0,0,2700,12000,10000,2900]],wall_boxes(),'Original_Ceiling','Wall','ceiling')
    for o in SPEC['openings']:add_opening(o)
    build_roof();build_access()
    ground=box('Ground_Display',[-30000,-30000,-620,40000,40000,-610],'Fixed','Ground','environment')
    ground['check_solid']=False
    setup_cameras()
    bpy.context.view_layer.update()
    result=measure(SPEC,ROOT)
    save_json(DATA_OUTPUT/'stage2_build_validation.json',result)
    if not result['ok']:
        print(json.dumps(result,ensure_ascii=False))
        # Keep a separate diagnostic file, never publish a failed candidate as the accepted deliverable.
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'models/house_stage2_diagnostic.blend'))
        raise RuntimeError(result['errors'])
    text=bpy.data.texts.new('Stage2_Geometry.json');text.write(SPEC_PATH.read_text())
    note=bpy.data.texts.new('READ_ME')
    note.write('Исходный дом по PDF. A — гараж, B — кухня-гостиная. C–L ожидают привязки от владельца.\n'
               'Реестр: //../data/house_stage2_geometry.json. Неподписанные размеры предварительные.\n'
               'Геометрические проверки не подтверждают назначение комнат или несущую способность конструкций.\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    save_json(RECEIPT,dict(scene_sha256=sha256(target),scene_path=str(target),geometry_sha256=sha256(SPEC_PATH),
                           blender_version=bpy.app.version_string,pid=os.getpid(),checks_passed=len(result['checks']),
                           stage_complete=result['stage_complete']))
    print(json.dumps(dict(saved=str(target),checks=len(result['checks']),naming_complete=result['naming_complete'])))


def ensure_open():
    if not bpy.data.filepath:
        bpy.ops.wm.open_mainfile(filepath=str(TARGET))
    if Path(bpy.data.filepath).resolve()!=TARGET:
        raise RuntimeError('Wrong scene; expected exact stage 2 deliverable')
    COLS.update({c.name:c for c in bpy.data.collections})
    MATS.update({m.name:m for m in bpy.data.materials})
    if 'Ink' not in MATS:
        material('Ink',(.035,.06,.08))


def verify():
    ensure_open()
    result=measure(SPEC,ROOT)
    result['reopened_file']=bpy.data.filepath
    result['scene_sha256']=sha256(TARGET)
    result['geometry_hash_matches']=bpy.context.scene.get('stage2_geometry_sha256')==sha256(SPEC_PATH)
    result['resource_errors']=[im.filepath for im in bpy.data.images if im.source=='FILE' and not im.packed_file and not Path(bpy.path.abspath(im.filepath)).is_file()]
    result['ok']=result['ok'] and result['geometry_hash_matches'] and not result['resource_errors']
    result['stage_complete']=result['ok'] and result['naming_complete']
    save_json(DATA_OUTPUT/'stage2_validation.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
    if not result['ok']:raise RuntimeError('Saved scene verification failed')


def negative_tests():
    ensure_open()
    initial=measure(SPEC,ROOT)
    if not initial['ok']:raise RuntimeError('Need a passing baseline before corruption tests')
    cases=[]
    def expect(name,mutate,restore,expected):
        mutate();bpy.context.view_layer.update()
        r=measure(SPEC,ROOT)
        caught=expected in r['errors']
        restore();bpy.context.view_layer.update()
        cases.append(dict(case=name,rejected=caught,errors=r['errors']))
    wall=bpy.data.objects['Walls_Original'];roof=bpy.data.objects['Roof_Original_Shell']
    expect('incorrect scene scale',lambda:setattr(bpy.context.scene.unit_settings,'scale_length',.001),
           lambda:setattr(bpy.context.scene.unit_settings,'scale_length',1),'scale_length')
    expect('wall shifted 100 mm',lambda:setattr(wall.location,'x',.1),lambda:setattr(wall.location,'x',0),'house_x')
    expect('ridge shifted 65 mm',lambda:setattr(roof.location,'z',.065),lambda:setattr(roof.location,'z',0),'ridge')
    oldmesh=wall.data
    # Move one aperture jamb across a 900-mm opening; actual mesh must fail the independent span test.
    damaged=oldmesh.copy()
    for v in damaged.vertices:
        if abs(v.co.x-3.8)<1e-5 and 5.69<v.co.y<6.11 and v.co.z<2.11:v.co.x=4.7
    expect('collapsed garage doorway',lambda:setattr(wall,'data',damaged),lambda:setattr(wall,'data',oldmesh),'door_garage_width')
    bpy.data.meshes.remove(damaged)
    dup=oldmesh.copy();bm=bmesh.new();bm.from_mesh(dup)
    bm.faces.ensure_lookup_table();f=bm.faces[0]
    verts=[bm.verts.new(v.co.copy()) for v in f.verts];bm.faces.new(verts)
    bm.to_mesh(dup);bm.free()
    expect('duplicate surface',lambda:setattr(wall,'data',dup),lambda:setattr(wall,'data',oldmesh),'closed_solids_outward_normals_no_duplicates')
    bpy.data.meshes.remove(dup)
    altered=json.loads(json.dumps(SPEC));altered['sources'][0]['sha256']='0'*64
    caught='source_'+altered['sources'][0]['path'] in measure(altered,ROOT)['errors']
    cases.append(dict(case='changed source digest',rejected=caught))
    result=dict(ok=all(c['rejected'] for c in cases),cases=cases,restored_baseline=measure(SPEC,ROOT)['ok'])
    save_json(DATA_OUTPUT/'stage2_negative_tests.json',result)
    print(json.dumps(result,ensure_ascii=False))
    if not result['ok'] or not result['restored_baseline']:raise RuntimeError('Negative scenario not detected')


def annotation(text,position,size=.17,rotation=(math.pi/2,0,math.pi/2)):
    data=bpy.data.curves.new('Dimension_'+text,'FONT');data.body=text;data.size=size;data.align_x='CENTER'
    ob=bpy.data.objects.new('Dimension_'+text,data);COLS['Diagnostics'].objects.link(ob)
    ob.location=position;ob.rotation_euler=rotation;ob.data.materials.append(MATS['Ink']);ob['role']='annotation'
    return ob


def slice_objects(x):
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('role')!='environment']
    copies=[]
    for obj in originals:
        obj.hide_render=True
        if obj.get('role') in ('glass','door_leaf','detail'):continue
        ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
        bm=bmesh.new();bm.from_mesh(me);ev.to_mesh_clear();bm.transform(obj.matrix_world)
        for xx,normal in ((x-.025,(-1,0,0)),(x+.025,(1,0,0))):
            if not bm.verts:break
            geom=list(bm.verts)+list(bm.edges)+list(bm.faces)
            bmesh.ops.bisect_plane(bm,geom=geom,dist=1e-6,plane_co=(xx,0,0),plane_no=normal,clear_outer=True)
            edges=[e for e in bm.edges if e.is_boundary]
            if edges:bmesh.ops.holes_fill(bm,edges=edges,sides=0)
        if not bm.faces:
            bm.free();continue
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        data=bpy.data.meshes.new('Section_'+obj.name);bm.to_mesh(data);bm.free()
        ob=bpy.data.objects.new('Section_'+obj.name,data);COLS['Diagnostics'].objects.link(ob)
        for mat in obj.data.materials:ob.data.materials.append(mat)
        copies.append(ob)
    return originals,copies


def preview():
    ensure_open()
    scene=bpy.context.scene;out=RENDER_OUTPUT;out.mkdir(parents=True,exist_ok=True)
    def render(name,cam,width=2400,height=1500):
        scene.camera=bpy.data.objects[cam];scene.render.resolution_x=width;scene.render.resolution_y=height
        scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
        print('RENDERED '+name,flush=True)
    render('01_original_exterior','Camera_Exterior_Front',2400,1700)
    for direction in ('South','North','East','West'):
        render('facade_'+direction.lower(),'Camera_Facade_'+direction,2400,1200)
    render('02_original_room_with_ceiling','Camera_Interior_Kitchen',2400,1600)
    for name,x in [('Kitchen',9.8),('Garage',3.3)]:
        originals,copies=slice_objects(x)
        labels=[]
        for text,y,z in [('+5.320',5.9,5.65),('+2.700 ceiling',2.1,2.42),('0.000',1,-.3),
                         ('-0.600 ground',8,-.87),('20 deg',2.5,4.7),('28 deg',8,4.6)]:
            labels.append(annotation(text,(x+.1,y,z)))
        labels.append(annotation('SECTION / '+name.upper()+' / provisional structure',(x+.1,5,6.08),.18))
        render('section_'+name.lower(),'Camera_Section_'+name,2400,1500)
        for o in labels+copies:bpy.data.objects.remove(o,do_unlink=True)
        for o in originals:o.hide_render=False
    hidden=[]
    for o in scene.objects:
        if o.get('role') in ('roof','canopy','upper_wall','ceiling','illustrative_structure') or o.name.startswith(('Glass_Original_Upper','Upper_Frame_','Upper_Mullion')):
            o.hide_render=True;hidden.append(o)
    render('03_diagnostic_cutaway','Camera_Cutaway',2400,1800)
    for o in hidden:o.hide_render=False
    print('Previews only; saved baseline was not changed.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action', choices=['build','verify','preview','test'])
    parser.add_argument('--scene', type=Path, default=TARGET)
    parser.add_argument('--output-dir', type=Path, default=DATA_OUTPUT)
    parser.add_argument('--render-dir', type=Path, default=RENDER_OUTPUT)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    TARGET=args.scene.resolve()
    DATA_OUTPUT=args.output_dir.resolve()
    RENDER_OUTPUT=args.render_dir.resolve()
    DATA_OUTPUT.mkdir(parents=True, exist_ok=True)
    RECEIPT=DATA_OUTPUT/'stage2_build.json'
    {'build':build,'verify':verify,'preview':preview,'test':negative_tests}[args.action]()
