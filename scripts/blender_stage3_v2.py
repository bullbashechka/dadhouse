"""Isolated Blender revision builder. All outputs use --revision; inputs are immutable."""
import argparse,hashlib,json,math,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tests')]
import bpy,bmesh
from mathutils import Vector
import blender_stage2 as base
import blender_stage3 as geom
from geometry_stage3 import corners,inner_profile,rectangle_clearance,roof_inner
from geometry_stage3_v2 import STARTS
from solve_stage3_v2 import world
from blender_stage2_checks import measure,evaluated_vertices,hit
from review_geometry import obstacle_from_mesh,hits_obstacle,door_model
P=argparse.ArgumentParser();P.add_argument('action',choices=['build','verify','preview']);P.add_argument('--revision',default='stage3_v2',choices=['stage3_v2']);P.add_argument('--pilot',action='store_true')
ARGS=P.parse_args(sys.argv[sys.argv.index('--')+1:]);DATA=ROOT/'data'/ARGS.revision;OUT=ROOT/'renders'/ARGS.revision;TARGET=ROOT/'models'/('house_'+ARGS.revision+'.blend');SOURCE=ROOT/'models/house_stage2_review.blend'
C=json.loads((DATA/'concepts.json').read_text());MODES={'Original':'00_Original','mansard':'01_Mansard','gable':'02_Gable','high_kitchen':'03_High_Kitchen'}
def dump(name,v):(DATA/name).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def box(name,r,z0,z1,group,mat='Furniture',role='furniture'):return geom.box(name,r,z0,z1,group,mat,role)
def localbox(name,r,z0,z1,group,mat='Furniture',role='furniture'):return box(name,world(r),z0,z1,group,mat,role)
def localbeam(name,p,q,w,d,group,mat='Frame',role='guard'):return base.beam(name,(p[0]+6600,p[1]+400,p[2]),(q[0]+6600,q[1]+400,q[2]),w,d,group,mat,role)
def roof_at(c,x,y):
    if c['family']!='high_kitchen' or x>=6200 and y<=6600:return c['roof']
    return {'axis':1,'profile':[[-500,4000],[10500,3550]],'domain':[-500,-500,12500,10500]}
geom.roof_for_point=roof_at

def furniture(c,mode,group):
    prefix=c['family']+'_'+mode+'_'
    for f in c['layout']['ground'][mode]['objects']:
        r=f['rect'];name=f['name'];a,b,d,e=r;n=prefix+name
        if name=='Table':
            localbox(n,r,700,750,group)
            for i,(x,y) in enumerate(corners([a+70,b+70,d-110,e-110])):localbox(n+'_Leg'+str(i),[x,y,x+40,y+40],0,700,group,'Frame')
        elif name.startswith('Chair'):
            r=[a+60,b+60,d-60,e-60];a,b,d,e=r
            localbox(n,r,400,450,group,'Upholstery')
            table=c['layout']['ground'][mode]['table']
            back=[a,b,d,b+45] if e<=table[1] else [a,e-45,d,e] if b>=table[3] else [a,b,a+45,e] if d<=table[0] else [d-45,b,d,e]
            localbox(n+'_Back',back,450,850,group,'Upholstery')
            for i,(x,y) in enumerate(corners([a+20,b+20,d-45,e-45])):localbox(n+'_Leg'+str(i),[x,y,x+25,y+25],0,400,group,'Frame')
        elif name=='Sofa':
            localbox(n,r,100,450,group,'Upholstery');localbox(n+'_Back',[a,e-150,d,e],450,850,group,'Upholstery')
        elif name=='TV':localbox(n,r,950,1600,group,'Frame','equipment')
        else:localbox(n,r,0,f['z'],group)
    localbox(prefix+'Sink',[100,3400,500,3800],900,915,group,'Steel','equipment')
    localbox(prefix+'Hob',[100,4050,500,4450],900,915,group,'Frame','equipment')
    if mode=='daily':
        for i in range(2):localbox(prefix+'Stored_Folding_Chair_'+str(i),[1200,950+i*80,1800,1010+i*80],0,850,group,'Frame')

def guard(name,p,q,z,group):
    if (Vector(p)-Vector(q)).length<1:return
    localbeam(name+'_Rail',(*p,z+1100),(*q,z+1100),40,40,group)
    for i,v in enumerate((p,q)):localbeam(name+'_Post'+str(i),(*v,z-100),(*v,z+1100),40,40,group)
    r=[min(p[0],q[0])-8,min(p[1],q[1])-8,max(p[0],q[0])+8,max(p[1],q[1])+8]
    localbox(name+'_Glass',r,z+50,z+1050,group,'Glass_Stage3','guard')

def interior(c,group):
    name=c['family'];l=c['layout'];p=world(l['platform']);holes=[[world(r)[0],world(r)[1],2600,world(r)[2],world(r)[3],3200] for r in l['holes']]
    base.solid(name+'_Mezzanine',[[p[0],p[1],2700,p[2],p[3],3100]],holes,group,'Timber','mezzanine')
    stairs=l['stair'];end=stairs['footprint'][3];width=l['platform'][2]
    if l['position']!='west' or stairs['shape']!='u':raise RuntimeError('Selected layout needs corresponding geometry implementation')
    for i,s in enumerate(stairs['steps']):localbox(name+'_Step_'+str(i),s['rect'],s['z']-100,s['z'],group,'Timber','stairs')
    for role in ('lower','upper'):
        flight=sorted([s for s in stairs['steps'] if s['role']==role],key=lambda s:s['z'])
        for side in (0,1):
            def point(s):
                r=s['rect'];return (r[0]-30 if side==0 else r[2]+30,(r[1]+r[3])/2,s['z'])
            a=point(flight[0]);b=point(flight[-1]);stem=name+'_'+role+'_'+str(side)
            localbeam(stem+'_Stringer',(a[0],a[1],a[2]-90),(b[0],b[1],b[2]-90),50,180,group,'Frame','stair_support')
            localbeam(stem+'_Rail',(a[0],a[1],a[2]+1000),(b[0],b[1],b[2]+1000),40,40,group)
            for i,s in enumerate(flight):
                a=point(s);localbeam(stem+'_Post'+str(i),(a[0],a[1],a[2]-100),(a[0],a[1],a[2]+1000),30,30,group)
    guard(name+'_Landing',(70,0),(70,900),1550,group);guard(name+'_Landing_Right',(2030,0),(2030,900),1550,group)
    guard(name+'_Edge',(width+20,0),(width+20,5300),3100,group)
    guard(name+'_Stair_Opening',(2080,0),(2080,end-20),3100,group)
    guard(name+'_Stair_Head',(0,end-20),(1040,end-20),3100,group)
    for i,b in enumerate(l['beds']):
        localbox(name+'_Lounger_'+str(i),b['rect'],3100,3350,group,'Upholstery','upper_furniture')
        a,y,d,e=b['rect'];r=[a+70,e-400,d-70,e-70] if e-y>d-a else [d-400,y+70,d-70,e-70]
        localbox(name+'_Pillow_'+str(i),r,3350,3450,group,'Furniture','upper_furniture')
    for mode in ('daily','guests'):
        col=base.collection(name+'_'+mode,base.COLS[group]);furniture(c,mode,col.name)

def build():
    if not bpy.app.background:raise RuntimeError('Use isolated background Blender')
    if TARGET.exists() and (not (DATA/'build.json').exists() or digest(TARGET)!=json.loads((DATA/'build.json').read_text())['scene_sha256']):raise RuntimeError('Unrecognised scene edits; refusing overwrite')
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE));geom.register();original=base.collection('V2_Original')
    geom.reparent(bpy.data.collections['Original_Walls'],original);geom.reparent(bpy.data.collections['Roof_Original'],original)
    geom.reparent(bpy.data.collections['Openings'],original)
    for n,rgb in [('Proposed_Infill',(.67,.56,.43)),('Furniture',(.76,.70,.59)),('Upholstery',(.32,.47,.48)),('Glass_Stage3',(.9,.97,1)),('Steel',(.4,.45,.5))]:base.material(n,rgb)
    for mat in (base.MATS['Glass_Stage3'],base.MATS['Glass']):
        bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Transmission Weight'].default_value=1;bs.inputs['Roughness'].default_value=.05;bs.inputs['IOR'].default_value=1.45
    roots={'Original':original}
    for c in C['main']:
        f=c['family'];root=base.collection('V2_'+f);roots[f]=root
        groups={n:base.collection(f+'_V2_'+n,root).name for n in ('Walls','Roof','Upper','Interior')}
        openings=base.collection(f+'_V2_Openings',root)
        for source_obj in bpy.data.collections['Openings'].objects:
            obj=source_obj.copy();obj.data=source_obj.data.copy();obj.name=f+'_Opening_'+source_obj.name;openings.objects.link(obj)
            oid=obj.get('opening_id')
            if obj.get('role')=='door_leaf' and oid in ('door_kitchen_north','door_kitchen_west','door_terrace'):
                o=next(o for o in base.SPEC['openings'] if o['id']==oid);w=next(w for w in base.SPEC['walls'] if w['id']==o['wall']);dm=door_model(o,w)
                obj.rotation_euler.z=math.radians(dm['closed_angle']+dm['sign']*90);obj['opening_angle_degrees']=90
        parts=C['walls'];solids=[[p['rect'][0],p['rect'][1],0,p['rect'][2],p['rect'][3],p['height']] for p in parts]
        base.solid(f+'_Walls',solids,[base.opening_box(o) for o in base.SPEC['openings']],groups['Walls'],'Wall','walls')
        geom.shell(f+'_Roof',c['roof'],groups['Roof'])
        if f=='high_kitchen':
            low=lambda y:4000-(y+500)*450/11000
            for i,domain in enumerate([[-500,-500,6200,10500],[6200,6600,12500,10500]]):
                geom.shell(f+'_Low_Roof_'+str(i),{'axis':1,'profile':[(domain[1],low(domain[1])),(domain[3],low(domain[3]))],'domain':domain},groups['Roof'])
            if c['roof']['axis']!=1:raise RuntimeError('High-roof interface needs y-profile geometry')
            ps=c['roof']['profile'];polygon=ps+[(6600,low(6600)),(-500,low(-500))]
            geom.extrude_profile(f+'_West_Flashing',polygon,1,6190,6210,groups['Roof'],'Frame','roof_flashing')
            box(f+'_North_Flashing',[6200,6590,12500,6610],low(6600),ps[-1][1],groups['Roof'],'Frame','roof_flashing')
            box(f+'_Low_Gutter',[-500,10440,12500,10560],3450,3550,groups['Roof'],'Frame','rainwater')
            box(f+'_Low_Downpipe',[12530,10450,12630,10550],-500,3450,groups['Roof'],'Frame','rainwater')
        for room in base.SPEC['rooms']:
            if room['id'] in ('A','B'):continue
            ps=room['polygon_mm'];n=len(ps);v=[(x,y,z) for z in (2700,2900) for x,y in ps]
            faces=[list(reversed(range(n))),list(range(n,n*2))]+[[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]
            base.mesh_object(f+'_Ceiling_'+room['id'],v,faces,groups['Walls'],'Wall','ceiling')
        for i,p in enumerate(parts):
            if p['wall'] not in ('north','south','east','west','spine','cross'):continue
            a,b,d,e=p['rect'];h=p['height'];r=[a,(b+e)/2-100,d,(b+e)/2+100] if d-a>e-b else [(a+d)/2-100,b,(a+d)/2+100,e]
            box(f+'_Mauerlat_'+str(i),r,h,h+200,groups['Upper'],'Timber','mauerlat')
            base.solid(f+'_Closure_'+str(i),[[a,b,h,d,e,h+200]],[[r[0],r[1],h-1,r[2],r[3],h+201]],groups['Upper'],'Proposed_Infill','upper_wall_proposal')
            exterior=p['wall'] in ('north','south','east','west');joint=p['wall']=='spine' and b<6100 or p['wall']=='cross' and a>=6600
            if exterior or joint:geom.upper_wall(f+'_Upper_'+str(i),p,c,groups['Upper'],p['wall']=='east' and e<=5700)
            elif h==2200 and p['wall'] in ('spine','cross'):box(f+'_Adjacent_Infill_'+str(i),p['rect'],2400,2900,groups['Upper'],'Proposed_Infill','upper_wall_proposal')
        interior(c,groups['Interior'])
        r=c['roof'];axis=r['axis'];d=r['domain']
        for i,(u,z) in enumerate((r['profile'][0],r['profile'][-1])):
            rect=[d[0],u-60,d[2],u+60] if axis==1 else [u-60,d[1],u+60,d[3]]
            box(f+'_Gutter_'+str(i),rect,z-100,z,groups['Roof'],'Frame','rainwater')
            x,y=(d[2]+80,u) if axis==1 else (u,d[3]+80)
            box(f+'_Downpipe_'+str(i),[x-50,y-50,x+50,y+50],-500,z-100,groups['Roof'],'Frame','rainwater')
        root['status']='Conditional wall extensions; structural calculation excluded'
    scene=bpy.context.scene;scene.name='House_Stage3_V2'
    for vl in list(scene.view_layers)[1:]:scene.view_layers.remove(vl)
    first=scene.view_layers[0];first.name=MODES['Original']
    for key,name in MODES.items():
        layer=first if key=='Original' else scene.view_layers.new(name)
        for other,col in roots.items():layer.layer_collection.children[col.name].exclude=key!=other
        for c in C['main']:
            f=c['family'];layer.layer_collection.children['V2_'+f].children[f+'_V2_Interior'].children[f+'_guests'].exclude=True
    for i,c in enumerate(C['main']):
        f=c['family'];layer=scene.view_layers.new(f'0{4+i}_{f}_Six_Seats')
        for other,col in roots.items():layer.layer_collection.children[col.name].exclude=f!=other
        for q in C['main']:
            k=q['family'];layer.layer_collection.children['V2_'+k].children[k+'_V2_Interior'].children[k+'_daily'].exclude=True
    cameras=[('V2_Terrace',(24,-20,14),(6.8,4.6,2.8),24),('V2_Garage',(-17,23,13),(6.8,4.6,2.8),24),
             ('V2_Facade_East',(35,5,3.5),(7,5,3.5),19),('V2_Facade_West',(-25,5,3.5),(7,5,3.5),19),
             ('V2_D06',(6.75,3.15,1.65),(11.6,2.7,2.35),0),('V2_D05',(7.8,5.6,1.65),(11.6,2.7,2.35),0),
             ('V2_D06_After',(9.85,3.15,1.65),(11.6,1.0,2.8),0),('V2_D05_After',(9.85,3.5,1.65),(11.6,1.0,2.8),0),
             ('V2_Upper',(8.0,4.0,4.75),(11.6,2.6,3.8),0),
             ('V2_Interior_Reverse',(11.15,1.9,1.65),(8.4,4.5,1.65),0),
             ('V2_Lounge',(9.45,3.3,4.75),(7.6,4.75,3.5),0)]
    for name,pos,target,scale in cameras:base.camera(name,pos,target,scale,28)
    for name,pos,power,size,target in [('V2_Room_Fill',(10.6,3.8,4.9),650,3,(9,3,0)),('V2_Under_Fill',(8.2,4.8,2.65),110,1.5,(8.2,4.8,0))]:
        data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
        obj=bpy.data.objects.new(name,data);base.COLS['Lighting'].objects.link(obj);obj.location=pos;obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    for obj in base.COLS['Lighting'].objects:
        if obj.type=='LIGHT':
            obj.visible_glossy=False
            if hasattr(obj.data,'specular_factor'):obj.data.specular_factor=0
    scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True;scene.cycles.device='CPU'
    scene.view_settings.view_transform='AgX';scene.render.resolution_x=1280;scene.render.resolution_y=960;scene.render.resolution_percentage=100
    bpy.context.window.view_layer=scene.view_layers[MODES['Original']]
    for vl in scene.view_layers:vl.use=vl.name==MODES['Original']
    scene.camera=bpy.data.objects['V2_Terrace'];scene['revision']='stage3_v2';scene['concepts']='//../data/stage3_v2/concepts.json'
    text=bpy.data.texts.new('V2_README_RU');text.write('Три предварительных концепции. Слои 00–03: исходный дом и крыши; 04–06: шесть мест.\nОба входа под антресолью. Лестница сбоку; высокий объём у восточных окон.\nКоричневые надстройки требуют согласования. Проёмы первого этажа сохранены.\nПанорамные проёмы, низкий гараж и другие парные сравнения — после выбора направления.\nРазмеры и проверки: ../data/stage3_v2/index.html\n')
    text=bpy.data.texts.new('V2_CONCEPTS_JSON');text.write((DATA/'concepts.json').read_text())
    bpy.ops.wm.save_as_mainfile(filepath=str(TARGET))
    dump('build.json',{'scene_sha256':digest(TARGET),'scene_path':str(TARGET.relative_to(ROOT)),'concepts_sha256':digest(DATA/'concepts.json'),'blender_version':bpy.app.version_string,'pid':os.getpid(),'objects':len(scene.objects)})
    print('SAVED',TARGET,flush=True)

def open_scene():bpy.ops.wm.open_mainfile(filepath=str(TARGET))
def active(name):
    scene=bpy.context.scene;bpy.context.window.view_layer=scene.view_layers[name]
    for vl in scene.view_layers:vl.use=vl.name==name
    bpy.context.view_layer.update();return bpy.context.view_layer

def verify():
    open_scene();checks={};details={}
    def check(name,value,**kw):checks[name]={'ok':bool(value),**kw}
    check('protected_files',all(digest(ROOT/p)==h for p,h in json.loads((DATA/'protected.json').read_text()).items()))
    check('scene_digest',digest(TARGET)==json.loads((DATA/'build.json').read_text())['scene_sha256'])
    check('concept_digest',digest(DATA/'concepts.json')==json.loads((DATA/'build.json').read_text())['concepts_sha256'])
    active(MODES['Original']);old=measure(base.SPEC,ROOT);geo={k:v for k,v in old['checks'].items() if not k.startswith('source_')};check('baseline_geometry',all(v['ok'] for v in geo.values()),count=len(geo))
    for i,c in enumerate(C['main']):
        f=c['family'];l=c['layout']
        for mode,name in [('daily',MODES[f]),('guests',f'0{4+i}_{f}_Six_Seats')]:
            layer=active(name);visible={o.name for o in layer.objects if o.visible_get(view_layer=layer)}
            for other in MODES:
                own={o.name for o in bpy.data.collections['V2_'+other].all_objects};check(name+'_isolation_'+other,bool(visible&own) if other==f else not bool(visible&own))
            check(name+'_chair_count',len([n for n in visible if n.startswith(f+'_'+mode+'_Chair_') and '_Back' not in n and '_Leg' not in n])==(4 if mode=='daily' else 6))
            obstacles=[];graph=bpy.context.evaluated_depsgraph_get()
            for o in layer.objects:
                if o.type!='MESH' or not o.visible_get(view_layer=layer) or o.get('role')=='environment':continue
                ev=o.evaluated_get(graph);mesh=ev.to_mesh()
                try:
                    verts=[tuple(float(x)*1000 for x in ev.matrix_world@v.co) for v in mesh.vertices]
                    if not verts or max(v[2] for v in verts)<=10 or min(v[2] for v in verts)>=2050:continue
                    mesh.calc_loop_triangles();ob=obstacle_from_mesh(o.name,verts,[list(t.vertices) for t in mesh.loop_triangles],10,2050)
                    if ob:obstacles.append(ob)
                finally:ev.to_mesh_clear()
            conflicts=[]
            for key,path in l['ground'][mode]['circulation']['paths'].items():
                for x,y in path:
                    square=corners(world([x-449,y-449,x+449,y+449]));found=[ob['name'] for ob in obstacles if hits_obstacle(square,ob)]
                    if found:conflicts.append({'path':key,'xy':[x,y],'objects':found});break
            check(name+'_actual_ground_meshes',not conflicts,conflicts=conflicts)
            check(name+'_all_entries_access',l['ground'][mode]['circulation']['ok'])
            check(name+'_chair_approaches',all(l['ground'][mode]['chair_access_450mm']))
        layer=active(MODES[f]);roof=bpy.data.objects[f+'_Roof'];floor=bpy.data.objects[f+'_Mezzanine']
        vertices=evaluated_vertices(floor);check(f+'_floor',abs(max(p.z for p in vertices)-3.1)<.001 and abs(min(p.z for p in vertices)-2.7)<.001)
        for j,q in enumerate(c['requirements']):
            r=q['rect'];vals=[]
            for x,y in corners(r)+[[(r[0]+r[2])/2,(r[1]+r[3])/2]]:
                p=hit(roof,(x/1000,y/1000,q['z']/1000+.001),(0,0,1));vals.append(p.z*1000-q['z'] if p else -1)
            check(f+'_clearance_'+str(j),min(vals)>=2050,minimum_mm=min(vals),role=q['role'])
        support=[]
        for r in l['routes']:
            a,b,d,e=world(r)
            for x in (a+1,(a+d)/2,d-1):
                for y in (b+1,(b+e)/2,e-1):
                    p=hit(floor,(x/1000,y/1000,3.2),(0,0,-1));support.append(p is not None and abs(p.z-3.1)<.001)
        check(f+'_route_floor_support',all(support));check(f+'_door_sweeps',not l['door_conflicts'])
        for t in (350,450):
            for slab in (300,400):
                for wallplate in (150,200):
                    h=min(rectangle_clearance(c['roof']['profile'],c['roof']['axis'],q['rect'],q['z'],t) for q in c['requirements'])
                    check(f+'_thickness_'+str((t,slab,wallplate)),h>=2050 and 3100-slab>=2700,minimum_mm=h,roof_datum='fixed exterior; closure changes with mauerlat')
        walls=bpy.data.objects[f+'_Walls']
        for o in base.SPEC['openings']:
            w=next(w for w in base.SPEC['walls'] if w['id']==o['wall']);a,b,d,e=w['rect_mm'];u=sum(o['interval_mm'])/2;z=sum(o['z_mm'])/2
            origin=(u/1000,(b-20)/1000,z/1000) if o['axis']=='x' else ((a-20)/1000,u/1000,z/1000)
            direction=(0,1,0) if o['axis']=='x' else (1,0,0);distance=((e-b) if o['axis']=='x' else (d-a))/1000+.04
            check(f+'_opening_'+o['id'],hit(walls,origin,direction,distance) is None)
        fridge=next(o for o in layer.objects if o.name==f+'_daily_Fridge');fv=evaluated_vertices(fridge);fridge_top=max(p.z for p in fv);clearances=[]
        for x,y in corners(world([1200,1200,1900,1900])):
            hits=[hit(o,(x/1000,y/1000,fridge_top+.001),(0,0,1)) for o in layer.objects if o.visible_get(view_layer=layer) and o.get('role') in ('stairs','stair_support')]
            hits=[p for p in hits if p is not None]
            if hits:clearances.append(min(p.z for p in hits)-fridge_top)
        check(f+'_fridge_head_allowance',bool(clearances) and min(clearances)>=.1,minimum_mm=min(clearances)*1000 if clearances else None,assumption_mm=100)
        if f=='high_kitchen':
            panels=[o for o in layer.objects if o.visible_get(view_layer=layer) and o.get('role')=='upper_wall_proposal']
            check('high_roof_east_junction_closed',any(hit(o,(12.2,6.35,3.5),(-1,0,0),.8) is not None for o in panels))
        details[f]={'upper_wall_proposals':[{'name':o.name,'extension_mm':o['maximum_extension_mm']} for o in layer.objects if o.visible_get(view_layer=layer) and 'maximum_extension_mm' in o], 'entry_experience':c['entry_experience']}
        for entry,xy in [('D06',(150,2750)),('D05',(1200,5200))]:
            for label,target in [('window',(4990,2500,1650)),('terrace',(4990,700,1650))]:
                start=Vector(((xy[0]+6600)/1000,(xy[1]+400)/1000,1.65));end=Vector(((target[0]+6600)/1000,(target[1]+400)/1000,target[2]/1000));delta=end-start;blocked=[]
                for o in layer.objects:
                    if o.type=='MESH' and o.visible_get(view_layer=layer) and o.name.startswith(f+'_') and o.get('role') not in ('guard','upper_glazing','route_marker'):
                        if hit(o,start,delta.normalized(),delta.length) is not None:blocked.append(o.name)
                check(f+'_view_'+entry+'_'+label,not blocked,blocking_objects=blocked)
    failures=[]
    for c in C['main']:
        for o in bpy.data.collections['V2_'+c['family']].all_objects:
            if o.type!='MESH':continue
            bm=bmesh.new();bm.from_mesh(o.data)
            if any(not e.is_manifold for e in bm.edges) or bm.calc_volume(signed=True)<=0:failures.append(o.name)
            bm.free()
    check('closed_new_meshes',not failures,failures=failures)
    check('resources',all(i.packed_file or not i.filepath or Path(bpy.path.abspath(i.filepath)).exists() for i in bpy.data.images if i.source=='FILE'))
    # Detect an actual bad edit; never save the perturbed state.
    c=next(c for c in C['main'] if c['family']=='gable');roof=bpy.data.objects['gable_Roof'];active(MODES['gable']);q=min(c['requirements'],key=lambda q:rectangle_clearance(c['roof']['profile'],c['roof']['axis'],q['rect'],q['z'],450));roof.location.z-=.2;bpy.context.view_layer.update()
    bad=[]
    for x,y in corners(q['rect']):
        p=hit(roof,(x/1000,y/1000,q['z']/1000+.001),(0,0,1));bad.append(p is None or p.z*1000-q['z']<2050)
    check('negative_lowered_roof',any(bad));roof.location.z+=.2
    result={'ok':all(v['ok'] for v in checks.values()),'checks':checks,'details':details,'scene_sha256':digest(TARGET),'scope':'Saved mesh and conservative spatial checks; architectural concept, not structural certification'};dump('validation.json',result)
    print(json.dumps({'ok':result['ok'],'checks':len(checks),'failed':[k for k,v in checks.items() if not v['ok']]},ensure_ascii=False),flush=True)
    if not result['ok']:raise RuntimeError('Validation failed')

def preview():
    open_scene();scene=bpy.context.scene;OUT.mkdir(parents=True,exist_ok=True);manifest=[]
    device='CPU'
    try:
        prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='METAL';prefs.get_devices()
        devices=[d for d in prefs.devices if d.type=='METAL']
        if devices:
            for d in prefs.devices:d.use=d.type=='METAL'
            scene.cycles.device='GPU';device='METAL'
    except (TypeError,RuntimeError):pass
    print('Render device:',device,flush=True)
    views=['Terrace','Garage','Facade_East','Facade_West','D06','D05','D06_After','D05_After','Upper','Interior_Reverse','Lounge']
    if ARGS.pilot:views=['D06_After','Interior_Reverse','Lounge']
    for f,name in MODES.items():
        if ARGS.pilot and f!='gable':continue
        active(name)
        for view in views:
            if f=='Original' and view not in ('Terrace','Garage','Facade_East','Facade_West'):continue
            scene.camera=bpy.data.objects['V2_'+view];scene.render.engine='CYCLES';scene.cycles.samples=12 if ARGS.pilot else 24
            scene.render.resolution_x=800 if ARGS.pilot else 1280;scene.render.resolution_y=600 if ARGS.pilot else 960
            file=OUT/(f'{f}_{view}'+('_pilot' if ARGS.pilot else '')+'.png');scene.render.filepath=str(file)
            bpy.ops.render.render(write_still=True,layer=name);manifest.append({'file':file.name,'sha256':digest(file),'view':view,'layer':name})
    dump('pilot_manifest.json' if ARGS.pilot else 'render_manifest.json',{'scene_sha256':digest(TARGET),'engine':'CYCLES','device':device,'images':manifest})

{'build':build,'verify':verify,'preview':preview}[ARGS.action]()
