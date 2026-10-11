"""Independent checks on evaluated Blender geometry (metres)."""
import json
import math
from collections import Counter
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector


def evaluated_vertices(obj):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    try:
        return [ev.matrix_world @ v.co for v in mesh.vertices]
    finally:
        ev.to_mesh_clear()


def hit(obj, origin, direction, distance=30):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    inv = ev.matrix_world.inverted()
    start = Vector(origin)
    unit = Vector(direction).normalized()
    local_direction = inv.to_3x3() @ unit
    ok, loc, normal, index = ev.ray_cast(inv @ start, local_direction.normalized(),
                                        distance=distance * local_direction.length)
    return ev.matrix_world @ loc if ok else None


def measure(spec, root):
    bpy.context.view_layer.update()
    checks, errors = {}, []
    def check(name, actual, expected, tolerance=.001):
        good = isinstance(actual, (int,float)) and math.isfinite(actual) and abs(actual-expected) <= tolerance + 1e-7
        checks[name] = dict(actual=actual,expected=expected,tolerance=tolerance,ok=good)
        if not good:
            errors.append(name)
    def condition(name, good):
        checks[name]=dict(ok=bool(good))
        if not good:
            errors.append(name)
    scene=bpy.context.scene
    condition('metric_units',scene.unit_settings.system=='METRIC')
    check('scale_length',scene.unit_settings.scale_length,1,1e-9)
    walls=bpy.data.objects.get('Walls_Original')
    roof=bpy.data.objects.get('Roof_Original_Shell')
    ceiling=bpy.data.objects.get('Ceiling_Original')
    for name,obj in [('walls_exist',walls),('roof_exists',roof),('ceiling_exists',ceiling)]:
        condition(name,obj is not None)
    if not all((walls,roof,ceiling)):
        return dict(ok=False,checks=checks,errors=errors)
    verts=evaluated_vertices(walls)
    for a,name,extent in [(0,'house_x',12),(1,'house_y',10),(2,'wall_top',2.9)]:
        check(name,max(p[a] for p in verts),extent)
        check(name+'_origin',min(p[a] for p in verts),0)
    # Above the opening heads; independent landmarks from the source drawing.
    for prefix,p,width,depth in [('kitchen',(9.1,3.05,2.4),5,5.3),
                                ('garage',(3.3,7.85,2.4),5.8,3.5)]:
        ends=[hit(walls,p,d) for d in [(-1,0,0),(1,0,0),(0,-1,0),(0,1,0)]]
        check(prefix+'_width',(ends[1]-ends[0]).length if all(x is not None for x in ends[:2]) else None,width)
        check(prefix+'_depth',(ends[3]-ends[2]).length if all(x is not None for x in ends[2:]) else None,depth)
    # All rectangular rooms: ray spans compare the final wall surfaces with the transcription.
    for room in spec['rooms']:
        poly=room['polygon_mm']
        if len(poly)!=4:
            continue
        xmin,xmax=min(p[0] for p in poly)/1000,max(p[0] for p in poly)/1000
        ymin,ymax=min(p[1] for p in poly)/1000,max(p[1] for p in poly)/1000
        pt=((xmin+xmax)/2,(ymin+ymax)/2,2.4)
        for axis,d1,d2,w in [('x',(-1,0,0),(1,0,0),xmax-xmin),('y',(0,-1,0),(0,1,0),ymax-ymin)]:
            p,q=hit(walls,pt,d1),hit(walls,pt,d2)
            check('room_'+room['id']+'_'+axis,(p-q).length if p is not None and q is not None else None,w)
    # L-shaped J has two distinct widths/depths; its bounding box is not a room span.
    for name,p,axis,expected in [('lower_width',(4.4,3.2,2.4),0,2.5),
                                ('upper_width',(4.2,4.8,2.4),0,1.1),
                                ('left_depth',(4.2,3.2,2.4),1,3.2),
                                ('right_depth',(5.5,3.2,2.4),1,1.5)]:
        d=Vector((1,0,0) if axis==0 else (0,1,0))
        a,b=hit(walls,p,-d),hit(walls,p,d)
        check('room_J_'+name,(b-a).length if a is not None and b is not None else None,expected)
    for name,p,d,expected in [('outer_wall',(1,-.5,2.4),(0,1,0),.4),
                               ('spine',(6,5,2.4),(1,0,0),.4),
                               ('partition_200',(3.3,1,2.4),(1,0,0),.2),
                               ('partition_100',(4.8,1,2.4),(1,0,0),.1)]:
        first=hit(walls,p,d)
        second=hit(walls,first+Vector(d)*.0001,d) if first is not None else None
        check(name,(second-first).length if second is not None else None,expected)
    wallmap={w['id']:w for w in spec['walls']}
    for o in spec['openings']:
        x1,y1,x2,y2=[v/1000 for v in wallmap[o['wall']]['rect_mm']]
        lo,hi=[v/1000 for v in o['interval_mm']]
        z=sum(o['z_mm'])/2000
        if o['axis']=='x':
            start=((lo+hi)/2,y1-.01,z);direction=(0,1,0);length=y2-y1+.02
            center=((lo+hi)/2,(y1+y2)/2,z);left=(-1,0,0);right=(1,0,0)
        else:
            start=(x1-.01,(lo+hi)/2,z);direction=(1,0,0);length=x2-x1+.02
            center=((x1+x2)/2,(lo+hi)/2,z);left=(0,-1,0);right=(0,1,0)
        condition(o['id']+'_through_wall',hit(walls,start,direction,length) is None)
        p,q=hit(walls,center,left),hit(walls,center,right)
        check(o['id']+'_width',(q-p).length if p is not None and q is not None else None,hi-lo)
    cv=evaluated_vertices(ceiling)
    check('ceiling_bottom',min(v.z for v in cv),2.7)
    check('ceiling_top',max(v.z for v in cv),2.9)
    rv=evaluated_vertices(roof)
    # Canopy columns must meet the underside, not stop below a sloped panel.
    for post in [o for o in scene.objects if o.get('role')=='post']:
        canopy=bpy.data.objects['Canopy_Terrace' if post.name.startswith('Terrace') else
                                'Canopy_North' if '_North_' in post.name else 'Canopy_South']
        vertices=evaluated_vertices(post)
        top=[p for p in vertices if p.z>2]
        for index,p in enumerate(top):
            underside=hit(canopy,(p.x,p.y,1.5),(0,0,1))
            check(post.name+'_joint_'+str(index),p.z-underside.z if underside is not None else None,0)
    check('ridge',max(v.z for v in rv),5.32)
    check('roof_width',max(v.x for v in rv)-min(v.x for v in rv),13)
    check('roof_depth',max(v.y for v in rv)-min(v.y for v in rv),11)
    for name,a,b,expected in [('slope_south',1,2,20),('slope_north',8,9,28)]:
        p,q=hit(roof,(6,a,8),(0,0,-1)),hit(roof,(6,b,8),(0,0,-1))
        angle=math.degrees(math.atan2(abs(q.z-p.z),b-a)) if p is not None and q is not None else None
        check(name,angle,expected,.1)
    topology=[]
    for obj in scene.objects:
        if obj.type!='MESH' or not obj.get('check_solid'):
            continue
        ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh=ev.to_mesh()
        bm=bmesh.new()
        try:
            bm.from_mesh(mesh)
            bad_edges=sum(not e.is_manifold for e in bm.edges)
            duplicate_faces=len(mesh.polygons)-len({tuple(sorted(p.vertices)) for p in mesh.polygons})
            volume=bm.calc_volume(signed=True)
            bad_faces=sum(p.area<1e-12 for p in mesh.polygons)
            if bad_edges or duplicate_faces or bad_faces or volume<=0:
                topology.append(dict(object=obj.name,nonmanifold_edges=bad_edges,duplicate_faces=duplicate_faces,
                                     degenerate_faces=bad_faces,signed_volume=volume))
        finally:
            bm.free();ev.to_mesh_clear()
    condition('closed_solids_outward_normals_no_duplicates',not topology)
    # The geometric source paths and the original stage-1 register must remain intact.
    import hashlib
    for source in spec['sources']:
        p=root/source['path']
        condition('source_'+source['path'],p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==source['sha256'])
    condition('stage1_register_unchanged',hashlib.sha256((root/'data/house_spec.json').read_bytes()).hexdigest()==spec['stage1_spec_sha256'])
    for name in ('Roof_Mansard','Roof_Gable','Roof_High_Kitchen'):
        collection=bpy.data.collections.get(name)
        condition(name+'_empty',collection is not None and not collection.all_objects)
    unresolved=[r['id'] for r in spec['rooms'] if r['naming_status'] not in ('confirmed','user_confirmed')]
    return dict(ok=not errors,checks=checks,errors=errors,topology_defects=topology,
                naming_complete=not unresolved,unresolved_room_names=unresolved,
                stage_complete=not errors and not unresolved)


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    result=measure(json.loads((root/'data/house_stage2_geometry.json').read_text()),root)
    print(json.dumps(result,ensure_ascii=False))
    if not result['ok']:
        raise SystemExit(1)
