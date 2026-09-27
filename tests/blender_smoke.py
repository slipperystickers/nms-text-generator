"""Run only in a separate background factory-startup Blender process."""
import importlib,json,string,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
import addon_utils,bpy

assert bpy.app.background, 'Run this test in a separate background Blender process.'
ROOT=Path(__file__).resolve().parents[1]
if '--installed' not in sys.argv:sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from native_bootstrap import enable_dependencies
base=enable_dependencies()
import nms_text_generator as a
a.register()
c=bpy.context;s=c.scene.nms_text_settings
assert a.bl_info['version']==(1,6,1)
assert s.auto_font
assert a.NMSTEXT_PT_panel.bl_category=='NMS Text'
s['auto_font']=False;a.initialize_auto_switch();assert s.auto_font
s.auto_font=False;a.initialize_auto_switch();assert not s.auto_font
s.auto_font=True
for key,name,_ in a.layout.FONTS:
    a.load_settings(s,dict(a.config_from_settings(s),font=key,text=string.ascii_uppercase+string.digits))
    root=a.create_text(c,a.config_from_settings(s))
    records=a.export_data(root)['Objects']
    assert len(records)==sum(map(len,a.layout.library(key)['glyphs'].values()))
    assert all(r['ObjectID']=='^BUILDFLATPANEL' for r in records)
    assert root['nms_text_library']==name
    for obj in a.managed_parts(root):
        a.check_matrix(obj.matrix_world)
        assert obj.material_slots and not obj.modifiers
    print('NATIVE_FONT_PASS',key,len(records),flush=True)

uid=root[a.OWNER]
root.location=(12,3,4);c.view_layer.update();matrix=root.matrix_world.copy()
saved_text=json.loads(root[a.CONFIG])['text']
s.text='UNRELATED DRAFT';s.font='ORBITAL';a.apply_pending_font()
assert json.loads(root[a.CONFIG])['font']=='ORBITAL'
assert json.loads(root[a.CONFIG])['text']==saved_text
assert root.matrix_world==matrix
before=root[a.CONFIG]
bpy.ops.object.select_all(action='DESELECT')
part=a.managed_parts(root)[0];part.select_set(True);c.view_layer.objects.active=part
s.font='FOUNDRY';a.apply_pending_font();assert root[a.CONFIG]==before
a.select_parts(c,root);s.font='INDUSTRIAL';part.select_set(False)
a.apply_pending_font();assert root[a.CONFIG]==before
a.select_parts(c,root)
extra=bpy.data.objects.new('Unrelated',None);c.scene.collection.objects.link(extra);extra.select_set(True)
s.font='FOUNDRY';a.apply_pending_font();assert root[a.CONFIG]==before
bpy.ops.object.select_all(action='DESELECT');part.select_set(True);c.view_layer.objects.active=part
dialog=SimpleNamespace(root_name='')
wm=SimpleNamespace(invoke_props_dialog=lambda op,width:{'RUNNING_MODAL'})
ctx=SimpleNamespace(active_object=part,window_manager=wm)
dialog.invoke=lambda context,event:a.NMSTEXT_OT_edit.invoke(dialog,context,event)
assert a.NMSTEXT_OT_edit.execute(dialog,ctx)=={'RUNNING_MODAL'}
assert dialog.font=='ORBITAL'
dialog.text='EDIT 123';dialog.font='FOUNDRY'
assert root[a.CONFIG]==before # Cancel/no application is non-mutating.
class MenuLayout:
    operator_context='EXEC_REGION_WIN'
    def separator(self):pass
    def row(self):return self
    def operator(self,name,**kw):assert self.operator_context=='INVOKE_DEFAULT'
a.text_context_menu(SimpleNamespace(layout=MenuLayout()),c)
args={k:getattr(dialog,k) for k in a.FIELDS}
assert bpy.ops.nms_text.edit('EXEC_DEFAULT',root_name=dialog.root_name,owner=dialog.owner,**args)=={'FINISHED'}
assert root.matrix_world==matrix and 'EDIT 123' in root.name
assert extra.name in bpy.data.objects
legacy=json.loads(root[a.CONFIG]);legacy.pop('font');legacy.pop('panel_type');root[a.CONFIG]=json.dumps(legacy)
assert bpy.ops.nms_text.load_settings()=={'FINISHED'} and s.font=='FUTURE_Z' and s.panel_type=='BUILDFLATPANEL'
# Restore before undo test.
legacy['font']='FOUNDRY';root[a.CONFIG]=json.dumps(legacy);a.load_settings(s,legacy)
c.preferences.edit.use_global_undo=True
bpy.ops.ed.undo_push(message='Before auto font');s.font='INDUSTRIAL';a.apply_pending_font()
bpy.ops.ed.undo_push(message='After auto font')
assert bpy.ops.ed.undo()=={'FINISHED'}
find=lambda:next(o for o in bpy.data.objects if o.get(a.ROOT) and o.get(a.OWNER)==uid)
assert json.loads(find()[a.CONFIG])['font']=='FOUNDRY'
assert bpy.ops.ed.redo()=={'FINISHED'}
assert json.loads(find()[a.CONFIG])['font']=='INDUSTRIAL'
# Switch an existing sign into the new font, then persist and re-edit it.
root=find();a.select_parts(bpy.context,root)
s=bpy.context.scene.nms_text_settings
s.font='VECTOR';a.apply_pending_font()
assert json.loads(root[a.CONFIG])['font']=='VECTOR'
config=json.loads(root[a.CONFIG]);config['text']='AVWD RKYX 47'
assert bpy.ops.nms_text.edit('EXEC_DEFAULT',root_name=root.name,owner=uid,**config)=={'FINISHED'}
assert root['nms_text_library']=='Vector'
with tempfile.TemporaryDirectory(prefix='nms-text-smoke-') as folder:
    file=Path(folder)/'test.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(file));bpy.ops.wm.open_mainfile(filepath=str(file))
    root=find();a.select_parts(bpy.context,root)
    assert a.NMSTEXT_OT_edit.poll(bpy.context)
    assert json.loads(root[a.CONFIG])['font']=='VECTOR'
a.unregister();a.register();a.unregister()
print('ALL_NATIVE_TESTS_PASSED',bpy.app.version_string,flush=True)
