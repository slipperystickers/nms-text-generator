"""Factory-startup regression: use Blender's restricted addon enable path."""
import sys
from pathlib import Path
import bpy,addon_utils
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
errors=[]
addon=addon_utils.enable('nms_text_generator',handle_error=lambda:errors.append(sys.exc_info()))
assert addon is not None and not errors,errors
assert hasattr(bpy.types,'NMSTEXT_PT_panel')
assert hasattr(bpy.types.Scene,'nms_text_settings')
assert bpy.app.timers.is_registered(addon.load_banner)
assert 'BANNER' not in addon._previews
addon.load_banner()
assert 'BANNER' in addon._previews
import numpy as np
pixels=np.array(addon._previews['BANNER'].image_pixels_float).reshape(-1,4)
assert np.all(pixels[:,:3]<=pixels[:,3:4]+1/255), 'UI alpha must be premultiplied'
addon_utils.disable('nms_text_generator')
assert not bpy.app.timers.is_registered(addon.load_banner)
assert addon._previews is None
assert not hasattr(bpy.types,'NMSTEXT_PT_panel')
addon=addon_utils.enable('nms_text_generator',handle_error=lambda:errors.append(sys.exc_info()))
assert addon and not errors
original=addon._load_banner_tiles
def fail(_):raise RuntimeError('injected banner failure')
addon._load_banner_tiles=fail
addon.load_banner()
assert hasattr(bpy.types,'NMSTEXT_PT_panel')
addon._load_banner_tiles=original
addon.load_banner()
assert 'BANNER' in addon._previews
addon_utils.disable('nms_text_generator')
print('RESTRICTED_REGISTRATION_AND_RECOVERY_PASSED')
