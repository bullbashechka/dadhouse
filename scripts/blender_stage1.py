"""Run only in an isolated Blender background process. See stage1_report.md."""
import argparse
import json
import os
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from stage1 import mm_to_m, sha256, validate_spec

TARGET = ROOT / 'models/house_stage1.blend'
SPEC = ROOT / 'data/house_spec.json'
RECEIPT = ROOT / 'data/template_build.json'


def verify():
    scene = bpy.context.scene
    errors = []
    if scene.unit_settings.system != 'METRIC' or abs(scene.unit_settings.scale_length - 1.0) > 1e-9:
        errors.append('Scene must use METRIC with scale_length = 1')
    if scene.unit_settings.length_unit != 'METERS':
        errors.append('Display length must use METERS')
    if bpy.data.objects:
        errors.append('Stage 1 must have no objects')
    expected = {'Base_House', 'Roofs', 'Mezzanines', 'Stairs', 'Furniture', 'Lighting', 'Cameras'}
    if {c.name for c in scene.collection.children} != expected:
        errors.append('Unexpected top-level collections')
    roof = bpy.data.collections.get('Roofs')
    if roof is None or {c.name for c in roof.children} != {'Roof_Original', 'Roof_Mansard', 'Roof_Gable', 'Roof_High_Kitchen'}:
        errors.append('Roof alternatives are missing')
    if scene.get('house_spec_path') != '//../data/house_spec.json':
        errors.append('Expected relative spec link')
    elif Path(bpy.path.abspath(scene['house_spec_path'])).resolve() != SPEC:
        errors.append('Relative spec path does not resolve')
    if scene.get('house_spec_sha256') != sha256(SPEC):
        errors.append('Spec checksum mismatch')
    if not bpy.data.filepath or Path(bpy.data.filepath).resolve() != TARGET:
        errors.append('Expected saved delivery file')
    errors.extend(validate_spec(json.loads(SPEC.read_text())))
    result = {'ok': not errors, 'errors': errors, 'blender_version': bpy.app.version_string,
              'pid': os.getpid(), 'scene_file': str(bpy.data.filepath),
              'scene_sha256': sha256(TARGET) if TARGET.exists() else None,
              'spec_sha256': sha256(SPEC), 'unit_system': scene.unit_settings.system,
              'scale_length': scene.unit_settings.scale_length,
              'length_unit': scene.unit_settings.length_unit, 'objects': len(bpy.data.objects),
              'collections': sorted(c.name for c in bpy.data.collections),
              'conversion_examples_m': [mm_to_m(v) for v in (1000, 5000, 5300)]}
    print(json.dumps(result, ensure_ascii=False))
    if errors:
        raise RuntimeError('; '.join(errors))
    (ROOT / 'data/scene_validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')


def create():
    # Refuse attachment to any loaded user file, and refuse replacing edited deliverables.
    if not bpy.app.background or bpy.data.filepath:
        raise RuntimeError('Use a fresh background process with --factory-startup')
    if TARGET.exists():
        receipt = json.loads(RECEIPT.read_text()) if RECEIPT.exists() else {}
        if receipt.get('scene_sha256') != sha256(TARGET):
            raise RuntimeError('Existing scene was modified or is unowned; preserve it before regeneration')
    errors = validate_spec(json.loads(SPEC.read_text()))
    if errors:
        raise ValueError('; '.join(errors))
    print(json.dumps({'pid': os.getpid(), 'file': bpy.data.filepath, 'scene': bpy.context.scene.name,
                      'version': bpy.app.version_string, 'engine': bpy.context.scene.render.engine}))
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    scene = bpy.context.scene
    scene.name = 'House_Stage1'
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = 'METERS'
    for name in ('Base_House', 'Roofs', 'Mezzanines', 'Stairs', 'Furniture', 'Lighting', 'Cameras'):
        collection = bpy.data.collections.new(name)
        scene.collection.children.link(collection)
    for name in ('Roof_Original', 'Roof_Mansard', 'Roof_Gable', 'Roof_High_Kitchen'):
        bpy.data.collections['Roofs'].children.link(bpy.data.collections.new(name))
    scene['stage'] = 1
    scene['house_spec_path'] = '//../data/house_spec.json'
    scene['house_spec_sha256'] = sha256(SPEC)
    scene['coordinates'] = 'Origin: lower-left exterior corner in plan; X right, Y up plan, Z up; floor Z=0'
    scene['linear_conversion'] = 'source mm / 1000 = Blender metres'
    scene['scope'] = 'Empty preparation template; no house geometry yet'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(TARGET))
    RECEIPT.write_text(json.dumps({'scene_sha256': sha256(TARGET), 'spec_sha256': sha256(SPEC)}, indent=2) + '\n')


parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['create', 'verify'])
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
create() if args.action == 'create' else verify()
