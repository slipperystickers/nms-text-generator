"""Run in isolated background Blender, using real dependency/native meshes."""
import json,sys
from pathlib import Path
from mathutils import Matrix,Vector
import bpy
ROOT=Path(__file__).resolve().parents[1]
if '--installed' not in sys.argv:sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from native_bootstrap import enable_dependencies
enable_dependencies()
import nms_text_generator as a
from nms_text_generator import icon_ui as icons
a.register();c=bpy.context;s=c.scene.nms_icon_settings
source=(ROOT/'tests/fixtures/icon_rocket.svg').read_text()
assert bpy.ops.nms_icon.import_svg('EXEC_DEFAULT',filepath=str(ROOT/'tests/fixtures/icon_rocket.svg'))=={'FINISHED'}
assert s.source==source and c.scene.nms_text_settings.mode=='ICON'
s.source=source;s.source_name='Rocket';s.accuracy=45;s.max_parts=120
result=icons.analyze(s)
assert result['part_count']<=120
text=a.create_text(c,a.config_from_settings(c.scene.nms_text_settings))
text_objects=set(a.managed_parts(text));text_config=text[a.CONFIG]
for panel in ('BUILDFLATPANEL','STORAGEPANEL'):
    s.panel_type=panel
    root=icons.create(c,icons.config(s));parts=a.managed_parts(root)
    assert a.selected_root(c) is None and icons.selected(c)==root
    assert len(parts)==result['part_count'] and root.get(icons.ROOT)
    for obj in parts:
        a.check_matrix(obj.matrix_world);assert obj.get('ObjectID')==panel and obj.material_slots and not obj.modifiers
    exported=a.export_data(root)
    assert all(o['ObjectID']=='^'+panel for o in exported['Objects'])
    assert len(exported['Objects'])==len(parts)
    # Editing from just one selected panel, while preserving transformed root.
    bpy.ops.object.select_all(action='DESELECT');parts[0].select_set(True);c.view_layer.objects.active=parts[0]
    assert bpy.ops.nms_icon.edit()=={'FINISHED'}
    root.matrix_world=Matrix.Translation((5,9,2))@Matrix.Rotation(.4,4,'Z')@Matrix.Scale(1.5,4)
    c.view_layer.update();original=root.matrix_world.copy();uid=root[a.OWNER]
    extra=bpy.data.objects.new('User attachment',None);c.scene.collection.objects.link(extra);extra.parent=root
    before={o.as_pointer() for o in bpy.data.objects}
    bad=dict(icons.config(s),source='<svg><image/></svg>')
    try:icons.replace(c,root,bad);assert False
    except ValueError:pass
    assert before=={o.as_pointer() for o in bpy.data.objects}
    # Failure after several native parts: old icon and unrelated objects survive.
    backend=a.get_builder(panel);real=backend.add_part;calls=[0]
    def fail(*args,**kwargs):
        calls[0]+=1
        if calls[0]>2:raise RuntimeError('Injected native factory failure')
        return real(*args,**kwargs)
    backend.add_part=fail
    try:
        try:icons.replace(c,root,icons.config(s));assert False
        except RuntimeError:pass
    finally:backend.add_part=real
    assert before=={o.as_pointer() for o in bpy.data.objects}
    s.accuracy=70;s.max_parts=150
    icons.replace(c,root,icons.config(s))
    assert root.matrix_world==original and extra.parent==root and root[a.OWNER]==uid
    assert set(a.managed_parts(text))==text_objects and text[a.CONFIG]==text_config
    assert len(a.managed_parts(root))<=150
    print('ICON_NATIVE_PASS',panel,len(a.managed_parts(root)),flush=True)
    s.accuracy=45;s.max_parts=120
# Stroke-only art generates independently as well.
orbit=(ROOT/'tests/fixtures/icon_orbits.svg').read_text()
stroke_root=icons.create(c,dict(icons.config(s),source=orbit,source_name='Orbits',accuracy=25))
assert a.managed_parts(stroke_root)
# Undo restores old panel collection, not a newly interpreted SVG.
c.preferences.edit.use_global_undo=True
a.select_parts(c,root);bpy.ops.ed.undo_push(message='Before icon update')
s.accuracy=15;assert bpy.ops.nms_icon.replace()=={'FINISHED'}
bpy.ops.ed.undo_push(message='After icon update')
assert bpy.ops.ed.undo()=={'FINISHED'}
root=next(o for o in bpy.data.objects if o.get(icons.ROOT) and o.get(a.OWNER)==uid)
assert json.loads(root[icons.CONFIG])['accuracy']==70
assert bpy.ops.ed.redo()=={'FINISHED'}
root=next(o for o in bpy.data.objects if o.get(icons.ROOT) and o.get(a.OWNER)==uid)
assert json.loads(root[icons.CONFIG])['accuracy']==15
out=ROOT/'test_output/svg_icon_roundtrip.blend'
c.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out))
bpy.ops.wm.open_mainfile(filepath=str(out))
root=next(o for o in bpy.data.objects if o.get(icons.ROOT) and o.get(a.OWNER)==uid)
assert json.loads(root[icons.CONFIG])['source']==source
a.select_parts(bpy.context,root)
assert bpy.ops.nms_icon.edit()=={'FINISHED'}
assert icons.analyze(bpy.context.scene.nms_icon_settings)['part_count']==len(a.managed_parts(root))
assert a.NMSTEXT_Settings.bl_rna.properties['mode'].enum_items['ICON'].name=='Icon / Sticker'
a.unregister()
print('ICON_UNDO_SAVE_REEDIT_AND_ROLLBACK_PASSED',flush=True)
