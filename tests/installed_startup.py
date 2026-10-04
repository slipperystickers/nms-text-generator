"""Normal GUI launch, no blend file: validate the saved enabled installation."""
import bpy
import nms_text_generator as addon
from pathlib import Path
assert addon.bl_info['version']==(2,2,8)
assert bpy.context.scene.nms_text_settings.bl_rna.properties['panel_type'].default=='STORAGEPANEL'
assert bpy.context.scene.nms_icon_settings.bl_rna.properties['panel_type'].default=='STORAGEPANEL'
assert 'scripts/addons' in Path(addon.__file__).as_posix()
assert hasattr(bpy.types,'NMSTEXT_PT_panel'), 'Startup registration failed'
assert hasattr(bpy.types.Scene,'nms_text_settings')
assert hasattr(bpy.types.Scene,'nms_icon_settings')
assert not bpy.context.scene.nms_icon_settings.bl_rna.properties['match_colors'].default
assert not bpy.context.scene.nms_icon_settings.bl_rna.properties['include_station'].default
assert bpy.ops.nms_icon.import_svg.get_rna_type()
assert bpy.ops.nms_icon.simplify_import.get_rna_type()
# Only the isolated verification process; never save preferences/startup.
bpy.context.preferences.use_preferences_save=False
bpy.context.preferences.view.show_splash=False
def verify():
    assert 'BANNER' in addon._previews
    assert addon.NMSTEXT_PT_panel.bl_category=='NMS Text'
    print('NORMAL_INSTALLED_GUI_STARTUP_PASSED',addon.__file__,flush=True)
    bpy.ops.wm.quit_blender()
bpy.app.timers.register(verify,first_interval=3)
