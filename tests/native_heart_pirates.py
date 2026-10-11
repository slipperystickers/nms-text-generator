"""Isolated Blender native-part regression and render for both reported SVGs."""
import json
import sys
from pathlib import Path
import bpy
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from native_bootstrap import enable_dependencies
enable_dependencies()
import nms_text_generator as addon
from nms_text_generator import icon_ui
addon.register()
assert addon.bl_info['version']==(2,2,15)
scene=bpy.context.scene
for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
out=ROOT/'test_output/heart_pirates';out.mkdir(parents=True,exist_ok=True)
settings=scene.nms_icon_settings
settings.accuracy=50;settings.max_parts=300;settings.height=10
records=[]
for x,name in ((-6,'icon_heart_pirates'),(6,'icon_heart_pirates_outline')):
    source=ROOT/'tests/fixtures'/f'{name}.svg'
    assert bpy.ops.nms_icon.import_svg('EXEC_DEFAULT',filepath=str(source),simplify=True)=={'FINISHED'}
    result=icon_ui.analyze(settings)
    root=icon_ui.create(bpy.context,icon_ui.config(settings),Matrix.Translation((x,0,0)))
    parts=addon.managed_parts(root)
    assert len(parts)==result['part_count']<=300
    for part in parts:
        addon.check_matrix(part.matrix_world)
        assert part.get('ObjectID')=='STORAGEPANEL' and not part.modifiers
        part.color=(.95,.69,.28,1)
    exported=addon.export_data(root)
    assert len(exported['Objects'])==len(parts)
    assert all(obj['ObjectID']=='^STORAGEPANEL' for obj in exported['Objects'])
    records.append({'file':name,'parts':len(parts),'coverage':result['coverage'],'excess':result['excess']})
    curve=bpy.data.curves.new('Review label','FONT')
    curve.body=f'{"FILLED" if x<0 else "THIN OUTLINE"} / {len(parts)} PANELS / {result["coverage"]:.0%} FILLED'
    curve.size=.34
    label=bpy.data.objects.new('GUIDE label',curve);scene.collection.objects.link(label)
    label.location=(x-4.8,-5.8,.2);label.color=(.8,.85,.9,1)
# Mounting surface covers the backs, not the visible panel faces.
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,-10))
back=bpy.context.object;back.name='GUIDE mounting surface';back.dimensions=(30,18,20);back.color=(.025,.038,.052,1)
camera=bpy.data.objects.new('Review Camera',bpy.data.cameras.new('Review Camera'))
scene.collection.objects.link(camera);camera.location=(0,0,100)
camera.data.type='ORTHO';camera.data.ortho_scale=25;scene.camera=camera
scene.render.engine='BLENDER_WORKBENCH';shade=scene.display.shading
shade.light='FLAT';shade.color_type='OBJECT';shade.show_shadows=False;shade.show_specular_highlight=False
scene.view_settings.view_transform='Standard'
scene.render.resolution_x=1800;scene.render.resolution_y=980;scene.render.resolution_percentage=100
scene.render.filepath=str(out/'native-panels.png')
bpy.ops.render.render(write_still=True)
(out/'native-report.json').write_text(json.dumps(records,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(out/'HeartPirates-native-review.blend'))
print('HEART_PIRATES_NATIVE_GENERATION_AND_EXPORT_PASSED',json.dumps(records),flush=True)
