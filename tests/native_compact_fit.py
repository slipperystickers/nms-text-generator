"""Factory-startup Blender smoke and render for the faceted Heart Pirates fit."""
import json
import os
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

ROOT=Path(__file__).resolve().parents[1]
if '--installed' not in sys.argv:sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from native_bootstrap import enable_dependencies

enable_dependencies()
import nms_text_generator as addon
from nms_text_generator import icon_ui
if '--installed' in sys.argv:
    assert Path(addon.__file__).resolve().is_relative_to(Path(os.environ['NMS_TEXT_CLEAN_ROOT']).resolve())

addon.register()
for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
settings=bpy.context.scene.nms_icon_settings
if '--flat' in sys.argv:settings.panel_type='BUILDFLATPANEL'
settings.accuracy=int(sys.argv[sys.argv.index('--accuracy')+1]) if '--accuracy' in sys.argv else 100
settings.max_parts=300
settings.height=10
source=ROOT/'tests/fixtures/icon_heart_pirates.svg'
assert bpy.ops.nms_icon.import_svg('EXEC_DEFAULT',filepath=str(source),simplify=True)=={'FINISHED'}
result=icon_ui.analyze(settings)
assert result['faceted_fit'] and result['part_count']<=240
assert result['seam_check_complete'] and result['face_coverage']>=.995
root=icon_ui.create(bpy.context,icon_ui.config(settings),Matrix.Identity(4))
parts=addon.managed_parts(root)
assert len(parts)==result['part_count']
for part in parts:
    assert part.get('ObjectID')==settings.panel_type
    addon.check_matrix(part.matrix_world)
    part.color=(.95,.69,.28,1)
exported=addon.export_data(root)
assert len(exported['Objects'])==len(parts)
assert all(o['ObjectID']=='^'+settings.panel_type for o in exported['Objects'])

bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,-10))
back=bpy.context.object
back.name='GUIDE mounting surface'
back.dimensions=(14,14,20)
back.color=(.025,.038,.052,1)
camera=bpy.data.objects.new('Review Camera',bpy.data.cameras.new('Review Camera'))
bpy.context.scene.collection.objects.link(camera)
camera.location=(0,0,100)
camera.data.type='ORTHO'
camera.data.ortho_scale=12
bpy.context.scene.camera=camera
bpy.context.scene.render.engine='BLENDER_WORKBENCH'
shade=bpy.context.scene.display.shading
shade.light='FLAT'
shade.color_type='OBJECT'
shade.show_shadows=False
shade.show_specular_highlight=False
bpy.context.scene.view_settings.view_transform='Standard'
bpy.context.scene.render.resolution_x=1200
bpy.context.scene.render.resolution_y=1200
bpy.context.scene.render.resolution_percentage=100
output=ROOT/'test_output/heart_pirates'
output.mkdir(parents=True,exist_ok=True)
name='faceted-native-flat' if '--flat' in sys.argv else 'faceted-native'
if '--accuracy' in sys.argv:name+='-'+str(settings.accuracy)
bpy.context.scene.render.filepath=str(output/(name+'.png'))
bpy.ops.render.render(write_still=True)
(output/(name+'.json')).write_text(json.dumps({
    'parts':len(parts),'accuracy':settings.accuracy,'vertices':sum(map(len,result['_fill_loops'])),'coverage':result['coverage'],
    'face_coverage':result['face_coverage'],'excess':result['excess'],
    'shape_change':result['shape_change'],'remaining_seams':result['remaining_seams'],
    'remaining_edge_pockets':result['remaining_edge_pockets'],
    'remaining_interior_samples':result['remaining_interior_samples']},indent=2))
print('NATIVE_FACETED_FIT_AND_EXPORT_PASSED',len(parts),flush=True)
