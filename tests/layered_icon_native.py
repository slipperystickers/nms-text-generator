"""Exercise the reported SVG through Import and Generate, with native panels."""
import json,sys
from pathlib import Path
import bpy
from mathutils import Quaternion,Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from native_bootstrap import enable_dependencies
enable_dependencies()
import nms_text_generator as a
a.register()
assert a.bl_info['version']==(2,2,8)
for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
s=bpy.context.scene.nms_icon_settings
s.accuracy=100;s.max_parts=2000;s.height=5;s.panel_type='STORAGEPANEL'
source=ROOT/'tests/fixtures/icon_layered_emblem.svg'
assert bpy.ops.nms_icon.import_svg(filepath=str(source))=={'FINISHED'}
assert bpy.ops.nms_icon.generate()=={'FINISHED'}
root=a.icon_ui.selected(bpy.context);parts=a.managed_parts(root)
result=a.icon_ui.analyze(s)
assert result['layered'] and result['coverage']>.85 and result['silhouette_coverage']>.95
assert len(parts)==result['part_count']<=2000
assert all(o.get('ObjectID')=='STORAGEPANEL' and not o.modifiers for o in parts)
payload=a.export_data(root)
assert len(payload['Objects'])==len(parts)
out=ROOT.parent/'output/tyndustrial'
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            r=area.spaces.active.region_3d;r.view_rotation=Quaternion((1,0,0,0))
            r.view_location=Vector((0,0,0));r.view_distance=7;r.view_perspective='ORTHO'
            area.spaces.active.overlay.show_relationship_lines=False
            area.spaces.active.shading.type='MATERIAL'
name=root.name;bpy.context.preferences.filepaths.save_version=0
bpy.ops.file.pack_all()
blend=out/'Industrial_T_Generator_2.2.8.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.wm.open_mainfile(filepath=str(blend));root=bpy.data.objects[name]
assert a.export_data(root)==payload
(out/'Industrial_T_Generator_2.2.8.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
report={'version':'2.2.8','blender':bpy.app.version_string,'panels':len(parts),
        'coverage':result['coverage'],'silhouette_coverage':result['silhouette_coverage'],
        'operator_import_generate':True,'save_reopen_export':True,'panel':'STORAGEPANEL'}
(out/'Generator_Native_Validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
scene=bpy.context.scene
# Mounting surface and render helpers are added after saving the clean icon.
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,-2.5))
back=bpy.context.object;back.dimensions=(7,7,5)
mat=bpy.data.materials.new('Review mounting surface');mat.diffuse_color=(.02,.025,.03,1);back.data.materials.append(mat)
camera=bpy.data.objects.new('Review camera',bpy.data.cameras.new('Review camera'));scene.collection.objects.link(camera)
camera.location=(0,0,25);camera.data.type='ORTHO';camera.data.ortho_scale=5.5;scene.camera=camera
light=bpy.data.objects.new('Review light',bpy.data.lights.new('Review light','AREA'));scene.collection.objects.link(light)
light.location=(0,0,10);light.data.energy=1000;light.data.size=10
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.view_settings.view_transform='Standard'
scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.render.filepath=str(out/'Generator_Native_Render.png');bpy.ops.render.render(write_still=True)
print('ACTUAL_SVG_IMPORT_GENERATE_ROUNDTRIP_PASSED',json.dumps(report),flush=True)
