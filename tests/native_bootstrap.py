"""Enable dependencies only in a separate factory-startup test process."""
import importlib
import os
import sys
from pathlib import Path
import addon_utils
import bpy


def enable_dependencies():
    assert bpy.app.background
    legacy = os.environ.get('NMS_TEXT_TEST_LEGACY')
    if legacy:
        folder = Path(legacy).resolve()
        sys.path.insert(0, str(folder.parent))
        extra = os.environ.get('NMS_TEXT_TEST_DEPS')
        if extra:
            sys.path.insert(0, extra)
        addon_utils.modules(refresh=True)
        base = folder.name
    else:
        base = 'bl_ext.user_default.no_mans_sky_base_builder'
    if base not in bpy.context.preferences.addons:
        assert addon_utils.enable(base, default_set=True) is not None
    try:
        importlib.import_module(base + '.builder_v2')
    except ModuleNotFoundError as exc:
        if exc.name != base + '.builder_v2':
            raise
        if not os.environ.get('NMS_TEXT_TEST_STANDARD'):
            forge = 'bl_ext.user_default.charon_forge'
            if forge not in bpy.context.preferences.addons:
                assert addon_utils.enable(forge, default_set=True) is not None
    return base
