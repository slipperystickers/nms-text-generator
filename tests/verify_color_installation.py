"""Read-only startup verification in a new process using saved preferences."""
import inspect
from pathlib import Path
import bpy
import nms_text_generator as addon
from nms_text_generator import icon_ui

assert bpy.app.background
bpy.context.preferences.use_preferences_save=False
assert addon.bl_info['version']==(2,2,8)
assert 'scripts/addons' in Path(addon.__file__).as_posix()
assert hasattr(bpy.types,'NMSTEXT_PT_panel') and hasattr(bpy.types.Scene,'nms_icon_settings')
assert 'v2.2.8' in inspect.getsource(addon.NMSTEXT_PT_panel.draw)
assert not bpy.context.scene.nms_icon_settings.bl_rna.properties['match_colors'].default
assert len(icon_ui.color_match.catalog()['palettes'])==151
assert bpy.ops.nms_text.follow_curve.get_rna_type() and bpy.ops.nms_text.restore_flat.get_rna_type()
assert not bpy.context.scene.nms_curve_settings.expanded
assert bpy.ops.nms_icon.colors.get_rna_type() and bpy.ops.nms_text.pick_curve.get_rna_type()
assert not bpy.context.scene.nms_icon_settings.bl_rna.properties['use_curve'].default
assert not bpy.context.scene.nms_text_settings.bl_rna.properties['use_curve'].default
provider=addon.get_builder()
print('INSTALLED_COLOR_STARTUP_VERIFIED',bpy.app.version_string,addon.__file__,type(provider).__name__,flush=True)
