"""Native panel selector regression tests. Separate background process only."""
import json, math, sys, tempfile
from pathlib import Path
from types import SimpleNamespace
import addon_utils, bpy
from mathutils import Matrix, Vector

assert bpy.app.background
ROOT=Path(__file__).resolve().parents[1]
if '--installed' not in sys.argv:sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from native_bootstrap import enable_dependencies
enable_dependencies()
import nms_text_generator as a
a.register()
ctx=bpy.context;settings=ctx.scene.nms_text_settings
builder=a.get_builder('STORAGEPANEL')

# Check calibration against actual installed game meshes, not guessed dimensions.
probe=builder.add_part('STORAGEPANEL',high_res=True,build_rigs=False).object
back=[p for p in probe.data.polygons if p.normal.y<-.99999 and abs(p.center.y)<1e-6]
verts=[probe.data.vertices[i].co for p in back for i in p.vertices]
dimensions=tuple(max(v[i] for v in verts)-min(v[i] for v in verts) for i in (0,2))
assert max(abs(x-y) for x,y in zip(dimensions,a.panels.STORAGE_FACE_SIZE))<1e-5
native_mesh=probe.data
native_coordinates=tuple(tuple(v.co) for v in native_mesh.vertices)
bpy.data.objects.remove(probe,do_unlink=True)

for key,_,_ in a.layout.FONTS:
    config=dict(a.config_from_settings(settings),font=key,panel_type='STORAGEPANEL',text=a.layout.CHARACTERS)
    root=a.create_text(ctx,config)
    records=a.export_data(root)['Objects']
    assert len(records)==a.make_plan(config)['part_count']
    assert all(r['ObjectID']=='^STORAGEPANEL' for r in records)
    for obj in a.managed_parts(root):
        a.check_matrix(obj.matrix_world)
        assert obj.material_slots and not obj.modifiers
        if getattr(builder,'requires_high_res',True):
            assert obj.data==native_mesh
        else:
            # The standard factory can re-import/copy its FBX rather than share
            # Forge's single mesh. Its native coordinates must remain identical.
            assert tuple(tuple(v.co) for v in obj.data.vertices)==native_coordinates
        normal=(obj.matrix_world.to_3x3()@Vector((0,-1,0))).normalized()
        assert normal.z>.99999
        r=builder.Part.deserialise_from_object(obj,builder.BUILDER).serialise()
        m=builder.Part.create_matrix_from_vectors(r['Position'],r['Up'],r['At'])
        assert max(abs(m[i][j]-obj.matrix_world[i][j]) for i in range(4) for j in range(4))<2e-5
    print('STORAGE_FONT_PASS',key,len(records),flush=True)
    collection=list(root.users_collection)[0]
    for obj in list(collection.objects):bpy.data.objects.remove(obj,do_unlink=True)
    bpy.data.collections.remove(collection)

config=dict(a.config_from_settings(settings),font='VECTOR',text='TYNDUSTRIAL ASTRONAUTICS',panel_type='BUILDFLATPANEL')
root=a.create_text(ctx,config);assert len(a.managed_parts(root))==367
root.matrix_world=Matrix.Translation((8,3,4))@Matrix.Rotation(.7,4,'Y')@Matrix.Scale(1.7,4)
ctx.view_layer.update();pose=root.matrix_world.copy();uid=root[a.OWNER]
config=json.loads(root[a.CONFIG])
flat=[o.matrix_basis.copy() for o in a.managed_parts(root)]
# Stale font and draft text must not get applied when only Panel type changes.
a.load_settings(settings,dict(config,font='INDUSTRIAL',text='UNRELATED DRAFT'))
settings.panel_type='STORAGEPANEL';a.apply_pending_font()
actual=json.loads(root[a.CONFIG])
assert actual['font']=='VECTOR' and actual['text']==config['text'] and actual['panel_type']=='STORAGEPANEL'
assert root.matrix_world==pose and len(a.managed_parts(root))==367
for old,obj in zip(flat,a.managed_parts(root)):
    flat_face=old@Vector((0,a.panels.FLAT_FACE_Y,0))
    storage_face=obj.matrix_basis@Vector(a.panels.STORAGE_FACE_CENTER)
    assert (flat_face-storage_face).length<2e-5
assert all(o['ObjectID']=='STORAGEPANEL' for o in a.managed_parts(root))
# Partial selection and disabled auto-switch must not mutate the sign.
before=root[a.CONFIG]
# A failed replacement may not remove the original parts or leave partial ones.
before_objects={o.as_pointer() for o in bpy.data.objects}
original_add=builder.add_part
calls=[0]
def fail_second(*args,**kwargs):
    calls[0]+=1
    if calls[0]==2:raise RuntimeError('Injected asset-load failure')
    return original_add(*args,**kwargs)
builder.add_part=fail_second
try:
    settings.panel_type='BUILDFLATPANEL';a.apply_pending_font()
finally:
    builder.add_part=original_add
assert root[a.CONFIG]==before
assert {o.as_pointer() for o in bpy.data.objects}==before_objects
assert settings.panel_type=='STORAGEPANEL'
bpy.ops.object.select_all(action='DESELECT')
part=a.managed_parts(root)[0];part.select_set(True);ctx.view_layer.objects.active=part
settings.panel_type='BUILDFLATPANEL';a.apply_pending_font();assert root[a.CONFIG]==before
a.select_parts(ctx,root);settings.auto_font=False
settings.panel_type='STORAGEPANEL';settings.panel_type='BUILDFLATPANEL';a.apply_pending_font();assert root[a.CONFIG]==before
settings.auto_font=True
a.load_settings(settings,json.loads(before))
# Right-click reads the saved panel type; Cancel/no execute changes nothing.
dialog=SimpleNamespace(root_name='')
window_manager=SimpleNamespace(invoke_props_dialog=lambda op,width:{'RUNNING_MODAL'})
context=SimpleNamespace(active_object=a.managed_parts(root)[0],window_manager=window_manager)
assert a.NMSTEXT_OT_edit.invoke(dialog,context,None)=={'RUNNING_MODAL'}
assert dialog.panel_type=='STORAGEPANEL'
dialog.panel_type='BUILDFLATPANEL';assert root[a.CONFIG]==before
# Undo and redo work for a panel-only auto switch.
ctx.preferences.edit.use_global_undo=True
bpy.ops.ed.undo_push(message='Before panel switch')
settings.panel_type='BUILDFLATPANEL';a.apply_pending_font()
bpy.ops.ed.undo_push(message='After panel switch')
find=lambda:next(o for o in bpy.data.objects if o.get(a.ROOT) and o.get(a.OWNER)==uid)
assert bpy.ops.ed.undo()=={'FINISHED'}
root=find();assert json.loads(root[a.CONFIG])['panel_type']=='STORAGEPANEL'
assert bpy.ops.ed.redo()=={'FINISHED'}
root=find();assert json.loads(root[a.CONFIG])['panel_type']=='BUILDFLATPANEL'
# Reopen and explicit right-click execution preserve the saved choice.
settings=ctx.scene.nms_text_settings;a.select_parts(ctx,root)
settings.panel_type='STORAGEPANEL';a.apply_pending_font()
with tempfile.TemporaryDirectory(prefix='nms-panel-switch-') as directory:
    file=Path(directory)/'sign.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(file));bpy.ops.wm.open_mainfile(filepath=str(file))
    root=find();assert json.loads(root[a.CONFIG])['panel_type']=='STORAGEPANEL'
    a.select_parts(bpy.context,root)
    args=json.loads(root[a.CONFIG]);args['text']='CAR';args['panel_type']='BUILDFLATPANEL'
    assert bpy.ops.nms_text.edit('EXEC_DEFAULT',root_name=root.name,owner=uid,**args)=={'FINISHED'}
    assert all(o['ObjectID']=='BUILDFLATPANEL' for o in a.managed_parts(root))
# Legacy files have no panel_type and must remain editable as Flat Panels.
legacy=json.loads(root[a.CONFIG]);legacy.pop('panel_type');root[a.CONFIG]=json.dumps(legacy)
a.load_settings(bpy.context.scene.nms_text_settings,legacy)
assert bpy.context.scene.nms_text_settings.panel_type=='BUILDFLATPANEL'
settings=bpy.context.scene.nms_text_settings;a.select_parts(bpy.context,root)
settings.font='INDUSTRIAL';settings.panel_type='STORAGEPANEL';a.apply_pending_font()
assert json.loads(root[a.CONFIG])['font']=='INDUSTRIAL'
assert json.loads(root[a.CONFIG])['panel_type']=='STORAGEPANEL'
assert json.loads(root[a.CONFIG])['text']=='CAR'
print('ALL_PANEL_SWITCH_TESTS_PASSED',flush=True)
a.unregister()
