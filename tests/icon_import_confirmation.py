"""Isolated Blender checks: no simplified import before approval, no cancel damage."""
import hashlib
import math
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import bpy

ROOT=Path(__file__).resolve().parents[1]
if '--installed' not in sys.argv:sys.path.insert(0,str(ROOT))
import nms_text_generator as addon
from nms_text_generator import icon_ui as icons,icon_fit,svg_outline
addon.register()
context=bpy.context;s=context.scene.nms_icon_settings
simple='<svg><rect width="100" height="50"/></svg>'
points=' '.join(f'{i},{50+20*math.sin(i/20):.3f}' for i in range(140))
dense=f'<svg><polyline points="{points}" fill="none" stroke="white" stroke-width="5" stroke-linejoin="round"/></svg>'
with tempfile.TemporaryDirectory(prefix='nmscribe-import-confirmation-') as folder:
    path=Path(folder)/'detailed.svg';path.write_text(dense,encoding='utf-8')
    simple_path=Path(folder)/'simple.svg';simple_path.write_text(simple,encoding='utf-8')
    assert bpy.ops.nms_icon.import_svg('EXEC_DEFAULT',filepath=str(simple_path))=={'FINISHED'}
    assert s.source==simple
    context.scene.nms_text_settings.mode='TEXT'
    old=icons.config(s);old_preview=s.preview_name;old_status=s.status
    objects={o.as_pointer() for o in bpy.data.objects}
    file_digest=hashlib.sha256(path.read_bytes()).hexdigest()
    # In background mode no dialog can be shown, so an unapproved complex
    # import must cancel. It must not silently simplify just because it can.
    with patch.object(svg_outline,'recover',side_effect=AssertionError('Unapproved trace')):
        assert bpy.ops.nms_icon.import_svg('EXEC_DEFAULT',filepath=str(path))=={'CANCELLED'}
    assert icons.config(s)==old and s.preview_name==old_preview and s.status==old_status
    assert context.scene.nms_text_settings.mode=='TEXT'
    assert objects=={o.as_pointer() for o in bpy.data.objects}
    # The dialog delegates execution to its affirmative button only.
    wm=SimpleNamespace(invoke_props_dialog=Mock(return_value={'RUNNING_MODAL'}))
    sentinel=object()
    assert icons.NMSICON_OT_simplify_import.invoke(sentinel,SimpleNamespace(window_manager=wm),None)=={'RUNNING_MODAL'}
    wm.invoke_props_dialog.assert_called_once_with(sentinel,width=430,title='Simplify SVG?',confirm_text='Simplify & Import',cancel_default=True)
    assert icons.config(s)==old
    assert bpy.ops.nms_icon.simplify_import('EXEC_DEFAULT',source=dense,source_name='detailed')=={'FINISHED'}
    assert s.source==dense and s.source_name=='detailed'
    assert icons.analyze(s)['outline_recovered']
    assert context.scene.nms_text_settings.mode=='ICON'
    assert objects=={o.as_pointer() for o in bpy.data.objects}
    assert hashlib.sha256(path.read_bytes()).hexdigest()==file_digest
    # Even an already cached approved import still needs approval next time.
    with patch.object(svg_outline,'recover',side_effect=AssertionError('Unapproved trace')):
        assert bpy.ops.nms_icon.import_svg('EXEC_DEFAULT',filepath=str(path))=={'CANCELLED'}
    assert bpy.ops.nms_icon.import_svg('EXEC_DEFAULT',filepath=str(path),simplify=True)=={'FINISHED'}
addon.unregister()
print('SVG_IMPORT_CONFIRM_APPROVE_CANCEL_AND_SOURCE_PRESERVATION_PASSED',flush=True)
