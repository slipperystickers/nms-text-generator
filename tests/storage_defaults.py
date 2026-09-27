"""Fresh-mode defaults, real native transforms, and saved/legacy preservation."""
import bpy,json,sys
from pathlib import Path
from mathutils import Matrix,Vector
assert bpy.app.background
ROOT=Path(__file__).resolve().parents[1]
if '--installed' not in sys.argv:sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from native_bootstrap import enable_dependencies
enable_dependencies()
import nms_text_generator as a
from nms_text_generator import icon_ui
a.register();ctx=bpy.context
text=ctx.scene.nms_text_settings;icon=ctx.scene.nms_icon_settings
assert text.panel_type==icon.panel_type=='STORAGEPANEL'
assert a.panels.from_flat_matrix(Matrix.Identity(4))==Matrix.Identity(4)
assert a.panels.from_flat_matrix(Matrix.Identity(4),'STORAGEPANEL')!=Matrix.Identity(4)
text.text='CCB';root=a.create_text(ctx,a.config_from_settings(text))
icon.source='<svg><circle cx="50" cy="50" r="50"/></svg>';icon.accuracy=25;icon.max_parts=100
icons=icon_ui.create(ctx,icon_ui.config(icon))
for control in (root,icons):
    parts=a.managed_parts(control)
    assert parts and all(p['ObjectID']=='STORAGEPANEL' for p in parts)
    for p in parts:
        assert (p.matrix_world.to_3x3()@Vector((0,-1,0))).normalized().z>.99999
    assert all(p['ObjectID']=='^STORAGEPANEL' for p in a.export_data(control)['Objects'])
# An explicit Flat choice remains Flat when old settings are restored.
a.load_settings(text,dict(a.config_from_settings(text),panel_type='BUILDFLATPANEL'))
assert text.panel_type=='BUILDFLATPANEL'
icon_ui.load(icon,dict(icon_ui.config(icon),panel_type='BUILDFLATPANEL'))
assert icon.panel_type=='BUILDFLATPANEL'
legacy=a.config_from_settings(text);legacy.pop('panel_type')
a.load_settings(text,legacy);assert text.panel_type=='BUILDFLATPANEL'
for control in (root,icons):
    collection=control.users_collection[0]
    for p in list(collection.objects):bpy.data.objects.remove(p,do_unlink=True)
    bpy.data.collections.remove(collection)
# Restore genuinely unset values for the fresh-state suite that follows us.
text.property_unset('panel_type');icon.property_unset('panel_type')
a.unregister()
print('STORAGE_DEFAULTS_AND_LEGACY_PRESERVATION_PASSED',flush=True)
